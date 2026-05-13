# AI 对话附件处理 — Bug 修复与未来优化报告

> 调研日期：2026-05-13  
> 调研范围：AI 教练附件上传、Vision 解析、与对话流程的耦合关系  
> 问题来源：用户反馈的三个痛点（扫描件 PDF 识别失败、不支持 Word、附件阻塞回复）

---

## 1. 问题清单与现状诊断

### 问题 ①：图片版本 PDF（扫描件）Vision 无法提取内容

**现象**：
- 上传纯图片（jpg/png）→ Vision 能正确识别内容
- 上传文字版 PDF → Vision 能识别
- 上传图片版 PDF（扫描件/图片嵌入型 PDF）→ Vision 返回空或无意义内容

**根因定位**（文件：`app/crm_profile/services/vision_analyzer.py:124`）：

当前 `_analyze_pdf` 的实现流程：
```python
pix = page.get_pixmap(dpi=100)           # ← DPI 偏低
png_bytes = pix.tobytes("png")
jpeg_bytes = _downscale_for_vision(png_bytes)  # ← 再压缩：max 1024px + JPEG q70
```

问题出在**两次压缩叠加**：
1. **第一次压缩**：`VISION_PDF_DPI = 100` — 典型扫描件 PDF 原始分辨率是 300 DPI，栅格化到 100 DPI 时文字清晰度已大幅下降
2. **第二次压缩**：`_downscale_for_vision` 再次限制到 max 1024px 并按 JPEG quality=70 编码 — 本来就模糊的图片经过 JPEG 有损压缩，文字基本无法辨识

**为什么单张图片没问题但 PDF 不行**：
- 直接上传的图片：原始 2048px + JPEG q70 → 下采样一次，细节损失一次
- PDF 扫描件：100 DPI 栅格化 + 下采样到 1024px + JPEG q70 → 细节损失两次，叠加效应

**额外隐患**：
- 未区分"文字版 PDF"和"扫描版 PDF"
- 对文字版 PDF，应优先用 `page.get_text()` 提取原生文本（免 Vision 成本）
- 对扫描版 PDF，应提高 DPI 或启用 OCR 兜底

---

### 问题 ②：不支持 Word 格式附件

**现状**（文件：`app/crm_profile/services/ai_attachment.py:22`）：
```python
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "application/pdf",
}
```

**缺失的 MIME 类型**：
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (.docx)
- `application/msword` (.doc)
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (.xlsx)
- `text/plain` (.txt)

**为什么当前架构不支持**：
- 整个附件处理链路假设内容是"图像可识别的"，走 Vision API
- Word/Excel 是富文本+表格结构化数据，直接栅格化给 Vision 浪费 token 且损失结构
- 正确处理方式应该是：**文档类附件走文本提取通道，不走 Vision**

---

### 问题 ③：附件解析阻塞 AI 回复

**用户描述**：
> "我已经做了附件的异步上传，但是和 AI 回复是串行的，必须得等 Vision 解析完图片才能生成最终的回复"

**用户的理解是对的**。根因定位：

**当前流程**（文件：`app/crm_profile/services/ai/__init__.py:188`）：

```python
async def stream_ai_coach_answer(...):
    # Stage 1: Vision analysis for attachments（阻塞点）
    effective_message = message
    if attachment_ids:
        yield AiStreamEvent(event="analyzing", data={"status": "analyzing_attachments"})
        effective_message = await _resolve_attachment_descriptions(
            customer_id, attachment_ids, message
        )  # ← 在这里等 Vision 完成

    # Stage 2: 进入 prepare + LLM 调用
    prepared = await _prepare_ai_turn_cached(
        customer_id,
        effective_message,   # ← 必须带着附件描述进入
        ...
    )
```

**阻塞链条**：
1. 用户发消息 → 后端等 Vision 解析 → 拼接 `effective_message` → 进入 prepare → 调用 LLM
2. Vision 调用 GPT-4o-mini（aihubmix），通常耗时 **3-8 秒**（PDF 多页时更久，单页 ~3s × N 页并行）
3. 在 Vision 返回前，前端只能看到 `event=analyzing`，无任何内容产出

**现有的异步机制为什么没用**：

上传时已经启动了 `_start_background_analysis`（文件：`ai_attachment.py:143`）：
```python
async def _analyze():
    await asyncio.sleep(1)              # ← 延迟 1s 才开始
    await analyze_attachment(attachment)
```

它确实让上传完成后 Vision 就开始跑。但在 `stream_ai_coach_answer` 入口的 `_resolve_attachment_descriptions` 仍然**无条件 `await analyze_attachment()`**：
- 如果后台已分析完：`analyze_attachment` 在函数开头判断 `processing_status == "analyzed"` → 直接返回缓存，几乎零耗时 ✅
- 如果后台还在跑：**两个协程会同时调用 Vision API**（没有分布式锁），各自跑各自的，返回后覆盖对方的结果 ⚠️
- 如果用户上传完立刻发送（<1s）：后台分析还没开始（`await asyncio.sleep(1)`），前台就已经在等了，完全没异步到 ❌

**最关键的架构问题**：
- 当前把"附件内容"当作"用户消息的一部分"拼到 prompt 里：`effective_message = "【附件】...\n【提问】..."`
- 这导致 LLM 调用必须等附件就绪
- 但从对话语义上说，附件是**独立的上下文**，完全可以：
  - LLM 先回答基于用户文字问题的部分
  - 附件解析好后作为增量信息追加展示
  - 或用 Function Calling 让 LLM 主动"查阅附件"

---

## 2. Bug 修复方案

### Bug #1：图片版本 PDF 识别失败

**修复策略**：三层兜底 + 质量自适应

#### 2.1 文本版 PDF 优先走原生文本提取

在 `_analyze_pdf` 里加入分类判断：

```python
async def _analyze_pdf(attachment):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    
    # 1. 先尝试提取原生文本
    native_text = _try_extract_native_text(doc)
    if native_text and _text_is_meaningful(native_text):
        # 文本版 PDF — 直接用原生文本，免 Vision 成本
        return _format_pdf_text(native_text, total_pages)
    
    # 2. 降级到栅格化 + Vision
    return await _analyze_pdf_as_images(doc, attachment)


def _try_extract_native_text(doc) -> str:
    """Try pymupdf native text extraction. Returns "" if mostly empty."""
    texts = []
    for page in doc:
        t = page.get_text("text").strip()
        if t:
            texts.append(t)
    return "\n\n".join(texts)


def _text_is_meaningful(text: str) -> bool:
    """Heuristic: enough alphanumeric content?"""
    clean = text.strip()
    if len(clean) < 50:
        return False
    # 判断是否主要是乱码或空白
    alnum_ratio = sum(c.isalnum() or '\u4e00' <= c <= '\u9fff' for c in clean) / len(clean)
    return alnum_ratio > 0.3
```

#### 2.2 扫描版 PDF 提高 DPI 并跳过第二次压缩

```python
# _health_summary_const 同级的 const：
VISION_PDF_DPI = 150        # 从 100 提高到 150
VISION_PDF_MAX_DIM = 1800   # PDF 页面单独放宽尺寸限制

async def _analyze_page(page_idx):
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=VISION_PDF_DPI)
    png_bytes = pix.tobytes("png")
    
    # PDF 页面用更高分辨率参数做压缩，保留文字清晰度
    jpeg_bytes = await asyncio.to_thread(
        _downscale_for_vision_hq, png_bytes,
        max_dim=VISION_PDF_MAX_DIM, quality=85,
    )
    ...
```

新增 `_downscale_for_vision_hq(raw, max_dim, quality)` 函数，与 `_downscale_for_vision` 区分开，专供 PDF 使用。

#### 2.3 兜底：直接提取嵌入图片

某些 PDF 每页是**一张大图片嵌入**（比如微信导出的聊天记录截图）。此时 `get_pixmap` 栅格化再次压缩效果差，应直接提取嵌入的原图：

```python
def _try_extract_embedded_image(page) -> bytes | None:
    """If page has exactly one large embedded image, extract it directly."""
    images = page.get_images(full=True)
    if len(images) != 1:
        return None
    xref = images[0][0]
    img_dict = doc.extract_image(xref)
    if img_dict["width"] >= 800 and img_dict["height"] >= 800:
        return img_dict["image"]
    return None
```

决策流程：
```
优先级 1: native_text（文本版 PDF）
优先级 2: 嵌入图片原图（单图嵌入页）
优先级 3: 栅格化 150 DPI + 大尺寸 JPEG（扫描版）
```

---

### Bug #2：不支持 Word 格式附件

**修复策略**：分通道处理 —— 文档类走文本提取，图像类走 Vision

#### 2.4 扩展 MIME 白名单

```python
# ai_attachment.py
ALLOWED_MIME_TYPES = {
    # 图像类 → Vision
    "image/jpeg", "image/png", "image/webp",
    # 文档类 → 文本提取
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",                                                         # .doc
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",         # .xlsx
    "application/vnd.ms-excel",                                                   # .xls
    "text/plain",                                                                 # .txt
    "text/markdown",                                                              # .md
}

DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/plain",
    "text/markdown",
}
```

#### 2.5 新增 `document_extractor.py`

按 AGENTS.md 的工程规范，新建文件：

```
app/crm_profile/services/
├── document_extractor.py   ← 新增，纯文本提取
├── vision_analyzer.py      ← 保持，只处理图像
```

接口设计：

```python
async def extract_document_text(attachment: CrmAiAttachment) -> str:
    """Extract plain text from document attachments (Word/Excel/txt)."""
    mime = attachment.mime_type
    if mime.startswith("application/vnd.openxmlformats-officedocument.wordprocessingml") \
       or mime == "application/msword":
        return await _extract_docx(attachment)
    if mime.startswith("application/vnd.openxmlformats-officedocument.spreadsheetml") \
       or mime == "application/vnd.ms-excel":
        return await _extract_xlsx(attachment)
    if mime in ("text/plain", "text/markdown"):
        return _extract_plain(attachment)
    raise ValueError(f"Unsupported document mime: {mime}")
```

依赖：
- `python-docx` — .docx 提取
- `openpyxl` — .xlsx 提取
- 旧版 .doc 需要 LibreOffice 或 `antiword`（Linux 系统）— 可先不支持，提示用户转 .docx

#### 2.6 `analyze_attachment` 入口按 MIME 分流

```python
async def analyze_attachment(attachment):
    if attachment.processing_status == "analyzed" and attachment.vision_description:
        return attachment.vision_description

    try:
        if attachment.mime_type in DOCUMENT_MIME_TYPES and attachment.mime_type != "application/pdf":
            description = await extract_document_text(attachment)  # ← 新通道
        elif attachment.mime_type == "application/pdf":
            description = await _analyze_pdf(attachment)
        else:
            description = await _analyze_image(attachment)
        _update_attachment(attachment, description, "analyzed")
        return description
    except Exception as e:
        ...
```

---

### Bug #3：附件解析阻塞回复（短期修复）

在不改动核心架构的前提下，能做的短期优化：

#### 2.7 上传完成立即启动分析（去掉 sleep）

```python
# ai_attachment.py
async def _analyze():
    # 去掉 await asyncio.sleep(1)
    from .vision_analyzer import analyze_attachment
    try:
        await analyze_attachment(attachment)
    except Exception:
        _log.warning(...)
```

`asyncio.sleep(1)` 是早期调试时加的延迟，当前没有必要保留。

#### 2.8 加分布式锁/内存锁避免重复分析

在 `analyze_attachment` 中加入 per-attachment-id 锁：

```python
_ANALYSIS_LOCKS: dict[str, asyncio.Lock] = {}

async def analyze_attachment(attachment):
    lock = _ANALYSIS_LOCKS.setdefault(attachment.attachment_id, asyncio.Lock())
    async with lock:
        # 进锁后再次检查 status（可能另一个协程已经跑完）
        fresh = _reload_attachment(attachment.attachment_id)
        if fresh.processing_status == "analyzed" and fresh.vision_description:
            return fresh.vision_description
        # ...do the actual analysis
```

避免用户"上传后立即发送"时前后台同时调用 Vision API 浪费一倍 token。

#### 2.9 `_resolve_attachment_descriptions` 加 wait-with-timeout

如果后台分析正在进行，等待最多 N 秒：

```python
async def _wait_for_analysis(attachment, timeout=15.0) -> str:
    start = time.time()
    while time.time() - start < timeout:
        fresh = _reload_attachment(attachment.attachment_id)
        if fresh.processing_status in ("analyzed", "failed"):
            return fresh.vision_description or ""
        await asyncio.sleep(0.3)
    # 超时则触发一次同步分析
    return await analyze_attachment(attachment)
```

---

## 3. 未来优化方向（根本性改造）

### 3.1 附件上下文与用户消息解耦（P0，影响最大）

**当前耦合方式**：
```
LLM messages = [
    system: role/scene/guardrail,
    system: customer_context,
    user: "【附件】图片描述...\n【提问】用户问题"  ← 附件和提问捏在一起
]
```

**建议改造为独立 context block**：
```
LLM messages = [
    system: role/scene/guardrail,
    system: customer_context,
    system: "[图像附件分析结果]\n<desc>",      ← 独立 system message
    user: "用户问题"                            ← 纯净的用户消息
]
```

**收益**：
- 利于 Prompt Cache（customer_context 位置稳定不变）
- 附件 block 可以并行生成，然后**注入到 stream 过程中**
- 可以支持"先回答，再补充基于附件的分析"

---

### 3.2 真·异步：附件分析并行 + 流式注入（P0，解决阻塞）

**目标架构**：

```
时间轴:
t=0s    用户提交 message + attachment_ids
        ├─ 协程 A: analyze_attachments()   （Vision 跑）
        └─ 协程 B: prepare_ai_turn()       （Profile + RAG + Prompt 组装）
                                           （不包含附件描述）
t=2s    协程 B 就绪 → LLM 开始 stream
        前端已经看到 AI 回答的文字（基于客户档案+提问）
t=5s    协程 A 就绪 → 附件描述生成完
        如果 LLM 还在输出 → 发 analysis_supplement 事件
        如果 LLM 已结束 → 触发第二轮 LLM 调用，基于附件做补充分析
```

**实现方式（两种选型）**：

**选型 A：双阶段对话（简单，推荐先做）**

1. 第一阶段：纯文字对话，立即 stream 回答
2. 附件分析完成后，如果内容与问题相关，发 SSE `event="attachment_insight"`
   ```json
   {"attachment": "xxx.pdf", "insight": "根据您上传的体检报告，我看到..."}
   ```
3. 前端在消息下方展示"基于附件的补充分析"

**选型 B：Function Calling（终极方案，工作量大）**

1. 把"读取附件"做成 Tool：`read_attachment(attachment_id) -> description`
2. LLM 根据问题自主决定是否需要读附件
3. 需要时中断 stream、调 tool、继续 stream

---

### 3.3 附件内容分层存储（P1）

当前 `vision_description` 是单字段 TEXT，所有内容平铺存储。

**建议重构**：

```python
class CrmAiAttachment(Base):
    # 原有字段保留...
    vision_description: str          # 主摘要（简短）
    extracted_metadata: JSON         # 结构化数据（指标/数值/表格）
    extracted_full_text: TEXT        # 全文（可选，用于 RAG 索引）
    content_category: str            # 类别：medical_report / food_photo / curve / document
```

**配套改动**：
- Vision prompt 要求返回 JSON 结构（category + metadata + summary）
- RAG 可以索引 `extracted_full_text`，下次问相关问题时能命中
- LLM 上下文只注入 summary + metadata，不注入 full_text（节省 token）

---

### 3.4 OCR 兜底（P1，处理扫描件）

`pymupdf` 对纯扫描件提取不出文本时，接入轻量 OCR：
- PaddleOCR（本地部署，中文效果好，但依赖较重）
- 调用 Vision API 明确要求"逐字 OCR，不要解读"再作为文本源

---

### 3.5 附件预检（P2）

上传时快速扫描第一页，生成 thumbnail + 类型标签：
- "这是一份 3 页的医疗报告，包含血糖曲线图"
- 前端在消息框里预览，用户可提前确认

---

## 4. 实施优先级与工期估算

| 优先级 | 任务 | 文件影响 | 工期 | 风险 |
|--------|------|---------|------|------|
| P0 | Bug#1：PDF 原生文本优先 + 高 DPI 兜底 | `vision_analyzer.py` | 1 天 | 低 |
| P0 | Bug#3：去 sleep(1) + 加锁 | `ai_attachment.py`, `vision_analyzer.py` | 0.5 天 | 低 |
| P0 | 根本改造：附件 context 解耦（选型 A） | `_prepare.py`, `ai/__init__.py`, 前端 | 3 天 | 中 |
| P1 | Bug#2：Word/Excel 文档通道 | 新增 `document_extractor.py` | 2 天 | 低 |
| P1 | PDF 嵌入图片提取兜底 | `vision_analyzer.py` | 1 天 | 低 |
| P1 | 附件内容分层存储 | `models.py` + 迁移 | 2 天 | 中（需要数据迁移） |
| P2 | OCR 兜底 | 新增依赖 | 3-5 天 | 中（依赖部署） |
| P2 | Function Calling（选型 B） | 全链路改造 | 2 周 | 高 |
| P2 | 附件预检 + 前端预览 | 前后端 | 3 天 | 低 |

---

## 5. 验证清单（AGENTS.md 硬要求）

按规范，所有修改必须通过**后端启动 + 前端编译 + focused validation**三项验证。

### 5.1 后端启动验证

```powershell
cd wecom_ops_console
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8099
```

关注点：
- `document_extractor` 新增依赖 `python-docx`、`openpyxl` 是否已装
- lifespan 正常启动，无 import 错误

### 5.2 Focused Validation

| 场景 | 预期 |
|------|------|
| 上传文字版 PDF（选中文字能复制的） | `processing_status=analyzed`，描述包含原始文本 |
| 上传扫描版 PDF（纯图片，截图拼接） | `processing_status=analyzed`，描述包含从图片识别的文字 |
| 上传 .docx | 描述包含文档所有段落文字 |
| 上传 .xlsx | 描述包含各表 sheet 的表头+数据 |
| 上传图片立即发送问题 | 不重复调 Vision（日志验证 token 不翻倍） |
| 附件分析 > 10s 时 | 前端能看到 AI 已经开始回答，附件内容作为补充增量到达 |

### 5.3 回归检查

- 现有的纯图片附件识别不受影响
- 现有的文字版 PDF 仍能识别
- 前端附件上传 UI 不受影响

---

## 6. 工程经验沉淀（memory.md 候选）

本次调研产出的可复用经验：

1. **Vision 场景的两次压缩陷阱**：栅格化 DPI + JPEG 二次压缩会叠加模糊。PDF 等容器类数据走 Vision 时要单独设参数
2. **"异步上传"≠"异步解析"**：后台任务启动不等于前台流程不等待。真正解耦需要把附件描述从 prompt 里剥离
3. **附件类型分通道**：图像走 Vision，文档走文本提取，不要用同一个 `analyze_attachment` 黑盒处理所有格式
4. **重复分析锁**：异步后台任务 + 同步前台调用 = 容易双跑，需要 per-key 锁

---

## 7. 代码文件索引

| 文件 | 当前职责 | 需改动点 |
|------|---------|---------|
| `app/crm_profile/services/ai_attachment.py` | 上传、DB 记录、后台分析触发 | 扩 MIME、去 sleep、加锁 |
| `app/crm_profile/services/vision_analyzer.py` | Vision 调用、PDF 栅格化 | 原生文本优先、高 DPI、嵌入图提取 |
| `app/crm_profile/services/ai/_prepare.py` | `_resolve_attachment_descriptions` | 改为可等待+超时+解耦 |
| `app/crm_profile/services/ai/__init__.py` | stream 主流程 | 附件 context 独立注入 |
| `app/crm_profile/routers/ai_attachment.py` | 上传/prepare-upload/confirm 端点 | 扩 MIME 校验 |
| `app/crm_profile/services/document_extractor.py` | **新增** | Word/Excel/txt 文本提取 |
| `app/crm_profile/models.py` | `CrmAiAttachment` | 可选扩字段：metadata/category |

---

## 8. 面向项目负责人的状态翻译

### 看见
三个问题都已在代码中定位到确切行号，不是玄学问题。

### 理解
- 扫描件 PDF 识别不了，是因为图片被压缩了两次，文字糊了
- Word 不支持，是因为白名单没加 + 处理逻辑没写
- 阻塞回复，是因为"附件描述"被当成"用户消息的一部分"拼在了一起，必须等

### 决策
- **立刻能做**（1-2 天）：PDF DPI 提升、去掉 sleep、加锁 — 低风险高收益
- **本周能做**（3-4 天）：Word/Excel 支持 — 中等工作量
- **需要规划**（1 周+）：附件 context 与用户消息解耦 — 核心架构改动，但一次改动彻底解决阻塞问题

### 闭环
每条改动都要按 AGENTS.md 规范：改完跑启动测试、前端编译、关键场景手测，通过后沉淀到 bug.md 和 memory.md。
