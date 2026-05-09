# AI 教练助手 — 图片/文档上传提问功能调研报告

> 日期：2025-04-27  
> 状态：调研完成，方案已确定（两阶段管线）

---

## 一、需求概述

用户（教练）在 AI 教练助手对话界面中，除了文本提问之外，还希望能上传**图片**或**文档**作为提问的附件，让 AI 结合附件内容进行回答。

典型场景：
- 上传客户的**血糖曲线图**（CGM 截图），让 AI 分析波动规律并给出调整建议
- 上传客户的体检报告图片，让 AI 分析关键指标
- 上传客户的饮食照片，让 AI 进行营养评估
- 上传 PDF 格式的客户文档，让 AI 提取关键信息

**关键挑战**：血糖曲线图等图表包含的是**视觉信息**（曲线走势、波动幅度、时间段分布），纯 OCR 无法提取这些图表语义，需要具备 Vision 能力的模型才能理解。

---

## 二、现有架构分析

### 2.1 当前数据流

```
前端输入框 (纯文本)
  → useAiCoach.sendChat()
    → streamSse() POST JSON { message: string, ... }
      → 后端 /api/v1/crm-customers/{id}/ai/chat-stream
        → AiChatRequest (Pydantic, message: str)
          → ai_coach.stream_ai_coach_answer()
            → prompt_builder.assemble_prompt() → messages: [{role, content: str}]
              → ai_chat_client.chat_completion_stream() → OpenAI-compatible API (DeepSeek)
```

### 2.2 关键文件清单

| 层级 | 文件 | 职责 |
|------|------|------|
| **前端 UI** | `frontend/src/views/CrmProfile/components/AiCoachPanel.vue` | 抽屉面板、输入框、发送按钮 |
| **前端 composable** | `frontend/src/views/CrmProfile/composables/useAiCoach.ts` | 聊天状态管理、SSE 流式请求、消息类型定义 |
| **前端消息组件** | `AiCoachUserMessage.vue` | 用户消息气泡（目前只渲染文本） |
| **前端消息列表** | `AiCoachMessageList.vue` | 消息列表渲染 |
| **后端路由** | `app/crm_profile/router.py` (L556-653) | `/ai/chat`, `/ai/chat-stream`, `/ai/thinking-stream` |
| **后端 Schema** | `app/crm_profile/schemas/api.py` (`AiChatRequest`) | 请求体定义，当前只有 `message: str` |
| **后端核心服务** | `app/crm_profile/services/ai_coach.py` | 准备对话上下文、调 AI、安全门控、审计 |
| **Prompt 组装** | `app/crm_profile/services/prompt_builder.py` | 5 层 prompt 组装，user message 目前是纯 `str` |
| **AI Client** | `app/clients/ai_chat_client.py` | OpenAI-compatible HTTP 调用，messages 是 `list[dict]` |
| **审计模型** | `app/crm_profile/models.py` (`CrmAiMessage`) | content 字段为 `Text`（纯文本） |
| **存储基础设施** | `app/services/storage/` (facade + local + qiniu) | 已有完整文件上传基础设施 |
| **配置** | `app/config.py` | `UPLOAD_DIR`, 七牛云存储配置, AI provider 配置 |

### 2.3 现有可复用基础设施

1. **文件存储系统**（`app/services/storage/`）— 已有 local + 七牛云双引擎，支持上传、下载、公共 URL 生成
2. **文件上传路由**（`app/routers/api.py` 等多处）— 已有 `UploadFile` 参数处理经验
3. **`python-multipart`** — 已在 `requirements.txt`，FastAPI 文件上传依赖已满足
4. **`Pillow`** — 已在 `requirements.txt`，图片处理库已可用
5. **`UPLOAD_DIR`** — `data/uploads/` 已配置并自动创建
6. **多 AI Provider 配置** — aihubmix + deepseek 双通道已配置，`ai_chat_client.py` 支持按 provider 切换

---

## 三、AI 模型能力评估

### 3.1 当前配置的模型

| Provider | 默认模型 | 图片(Vision) | 上下文窗口 | 定位 |
|----------|----------|:---:|:---:|------|
| deepseek | `deepseek-v4-pro` | **❌ 纯文本** | **1M** | 主力推理模型，长上下文深度分析 |
| aihubmix | `gpt-4o-mini` | **✅ 原生支持** | 128K | 可用于 Vision 图像理解 |

> **核心约束**：当前主力模型 DeepSeek V4 Pro 是**纯文本模型**，不支持多模态输入。
> 但 aihubmix 的 GPT-4o-mini **原生支持 Vision**，可以理解图表、曲线、文字等视觉内容。

### 3.2 核心矛盾与解决思路

| 问题 | 说明 |
|------|------|
| **血糖曲线图等图表** | 包含视觉语义（走势、波动、时间分布），纯 OCR/文本提取无法理解 |
| **DeepSeek 不支持图片** | 不能直接把图片传给主力推理模型 |
| **GPT-4o-mini 支持 Vision** | 能理解图表但缺少 DeepSeek 的 1M 长上下文和深度推理优势 |

**解决方案：两阶段管线（Vision 预分析 + DeepSeek 深度推理）**

- **Stage 1**：图片 → GPT-4o-mini (Vision) → 结构化图表描述文本
- **Stage 2**：图表描述 + 用户问题 + 客户档案 → DeepSeek V4 Pro → 教练建议

各取所长：Vision 理解由 GPT-4o-mini 负责，深度推理由 DeepSeek 负责。

### 3.3 两阶段管线详解

```
用户上传图片/文档 + 提问
    │
    ├─── [Stage 1: Vision 预分析]
    │    模型: GPT-4o-mini (aihubmix)
    │    输入: 图片 base64 + 专用 Vision 分析 prompt
    │    输出: 结构化的图表/文档描述文本
    │    耗时: ~2-5 秒（非流式，一次性返回）
    │
    └─── [Stage 2: 深度推理]
         模型: DeepSeek V4 Pro (deepseek)
         输入: Vision 描述文本 + 用户问题 + 5 层 prompt（客户档案等）
         输出: 流式教练建议（走现有 SSE 通道）
         现有流程完全复用，仅在 user message 前注入附件描述
```

#### Stage 1 Vision 分析 Prompt 示例

```
你是一个专业的医学图表分析助手。请仔细观察这张图片，提取以下信息：

1. 图表类型（血糖曲线、体检报告、饮食照片、其他）
2. 关键数据点和数值
3. 如果是曲线图：波动趋势、峰值/谷值时间、异常区间
4. 如果是报告：所有指标及其正常/异常状态
5. 如果是照片：可见的食物/物品及其特征

请用结构化文本输出，确保信息完整准确。不要做医学诊断，只做客观描述。
```

#### 各类附件处理方式

| 附件类型 | Stage 1 处理 | Stage 2 输入 |
|----------|-------------|-------------|
| **血糖曲线图** | GPT-4o-mini Vision 解读图表：时间轴、血糖值、波动趋势、高低糖区间 | 结构化描述注入 user message |
| **体检报告图片** | GPT-4o-mini Vision 识别文字 + 表格 + 指标异常标注 | 识别结果注入 user message |
| **饮食照片** | GPT-4o-mini Vision 识别食物种类、分量、烹饪方式 | 识别结果注入 user message |
| **PDF 文档** | `pymupdf` 渲染为图片 → GPT-4o-mini Vision 逐页解读 | 识别结果注入 user message |
| **纯文字截图** | GPT-4o-mini Vision OCR 识别文字 | 文字内容注入 user message |

### 3.4 方案优势

1. **各取所长** — Vision 由 GPT-4o-mini 负责（擅长图表解读），深度推理由 DeepSeek 负责（1M 上下文 + 强推理）
2. **对现有流程侵入最小** — DeepSeek 的整个对话流程不变，只是 user message 前多了一段"附件描述"文本
3. **prompt_builder 无需改动** — user_message 仍然是纯 `str`，只是内容更丰富了
4. **审计兼容** — content 字段仍是文本，包含附件描述和原始提问，审计链路完全不变
5. **成本可控** — GPT-4o-mini 调用成本低（~$0.15/1M input tokens），图片分析一次 ~$0.01

---

## 四、改动方案设计

### 4.1 整体架构（两阶段管线）

```
前端：选择文件 → 上传到后端 → 获得 attachment_id
前端：发送消息时携带 attachment_ids
后端收到消息：
  ├─ 有附件？
  │   ├─ YES → [Stage 1] 调 GPT-4o-mini Vision 分析图片 → 获得描述文本
  │   │         将描述文本拼接到 user_message 前面
  │   └─ NO  → 直接用原始 user_message
  └─ [Stage 2] 走现有 DeepSeek 流程 → stream_ai_coach_answer()
```

### 4.2 分层改动清单

#### 层级 1：新增附件上传接口

**新增文件**：`app/crm_profile/services/ai_attachment.py`

职责：
- 接收上传文件，校验类型和大小
- 存储到 `StorageFacade`
- 记录附件元数据到新表 `crm_ai_attachments`
- 支持的类型：`image/jpeg`, `image/png`, `image/webp`, `application/pdf`
- 大小限制：图片 10MB，PDF 20MB（最多渲染前 10 页）

**新增路由**：`POST /api/v1/crm-customers/{customer_id}/ai/upload-attachment`

```python
@router.post("/{customer_id}/ai/upload-attachment")
async def upload_ai_attachment(
    customer_id: int,
    file: UploadFile,
    request: Request,
    db: Session = Depends(get_db),
):
    ...
    return {"attachment_id": "...", "filename": "...", "mime_type": "...", "file_size": ...}
```

#### 层级 2：新增 Vision 预分析服务

**新增文件**：`app/crm_profile/services/vision_analyzer.py`

这是**两阶段管线的核心新增模块**，职责：
- 读取附件文件 → base64 编码
- 构造 Vision prompt（针对不同附件类型使用不同的分析指令）
- 调用 GPT-4o-mini (aihubmix) Vision API → 获取结构化描述文本
- PDF 附件：先用 `pymupdf` 渲染为图片，再逐页分析
- 缓存分析结果（同一附件不重复分析）
- 超时和错误处理（Vision 分析失败时降级为"[图片无法识别]"提示）

```python
async def analyze_attachment(
    attachment: CrmAiAttachment,
    user_hint: str = "",
) -> str:
    """
    Stage 1: 调用 GPT-4o-mini Vision 分析附件图片。
    返回结构化描述文本，供注入 DeepSeek 的 user_message。
    """
    ...
```

#### 层级 3：数据库模型

**新增表** `crm_ai_attachments`：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| attachment_id | VARCHAR(64) UNIQUE | UUID，前端引用 |
| session_id | VARCHAR(64) | 关联会话（可 nullable，上传时可能还没开始对话） |
| message_id | VARCHAR(64) | 关联消息 |
| crm_customer_id | INTEGER | 客户 ID |
| uploaded_by | INTEGER | 上传用户 |
| original_filename | VARCHAR(255) | 原始文件名 |
| mime_type | VARCHAR(64) | MIME 类型 |
| file_size | INTEGER | 文件大小（字节） |
| storage_provider | VARCHAR(16) | local / qiniu |
| storage_key | VARCHAR(255) | 存储路径 |
| storage_local_path | TEXT | 本地路径 |
| page_count | INTEGER | PDF 页数（图片为 1） |
| rendered_image_keys | TEXT | PDF 渲染后的图片存储 key 列表（JSON） |
| vision_description | TEXT | **Vision 预分析结果文本**（Stage 1 输出） |
| vision_model | VARCHAR(64) | 用于分析的模型名称 |
| vision_tokens | INTEGER | Vision 分析消耗的 token 数 |
| processing_status | VARCHAR(16) | pending / analyzed / failed |
| created_at | DATETIME | 创建时间 |

**改动文件**：`app/crm_profile/models.py` — 新增 `CrmAiAttachment` 模型

#### 层级 4：后端 Schema

**改动文件**：`app/crm_profile/schemas/api.py`

- `AiChatRequest` 新增字段：`attachment_ids: list[str] | None = None`
- 新增 `AiAttachmentResponse` schema

#### 层级 5：核心服务层 — AI Coach 集成

**改动文件**：

1. **`app/crm_profile/services/ai_coach.py`**
   - `stream_ai_coach_answer()` 和 `stream_ai_coach_thinking()` 新增 `attachment_ids` 参数
   - 在调 DeepSeek 之前，加一步：
     - 加载附件记录
     - 调用 `vision_analyzer.analyze_attachment()` 获取描述（或读缓存）
     - 将描述文本拼接到 `user_message` 前面
   - 拼接格式示例：
     ```
     【附件分析结果】
     [附件1: 血糖曲线图.jpg]
     该图表为连续血糖监测(CGM)24小时曲线图。时间轴为0:00-24:00...
     血糖峰值出现在12:30（约11.2mmol/L），餐后2小时内波动较大...

     [附件2: 体检报告.pdf - 第1页]
     检测项目：空腹血糖 6.8 mmol/L (偏高)，糖化血红蛋白 7.2% (偏高)...

     【用户提问】
     根据这个血糖曲线，这个客户的血糖控制情况怎么样？需要注意什么？
     ```

2. **`app/crm_profile/services/prompt_builder.py`**
   - **无需改动**！user_message 仍然是 `str`，只是内容更丰富了（包含附件描述）

3. **`app/clients/ai_chat_client.py`**
   - **无需改动**！仍然发送纯文本 messages 给 DeepSeek

#### 层级 6：前端 UI

**改动文件**：

1. **`AiCoachPanel.vue`** — 输入区域
   - 输入框旁新增附件按钮（📎 图标）
   - 点击后打开文件选择器，支持图片 + PDF
   - 文件选择后调用上传接口，获得 `attachment_id`
   - 在输入框上方显示已选附件的缩略图/文件名预览
   - 发送时将 `attachment_ids` 随消息一起提交

2. **`useAiCoach.ts`** — Composable
   - `AiChatMessage` 类型扩展：user 消息新增 `attachments?: AiAttachment[]`
   - `sendChat()` 方法新增 `attachment_ids` 参数
   - 新增 `uploadAttachment()` 方法
   - `streamSse()` 请求体携带 `attachment_ids`

3. **`AiCoachUserMessage.vue`** — 用户消息气泡
   - 渲染附件预览（图片缩略图、PDF 图标 + 文件名）

4. **`AiCoachMessageList.vue`** — 消息列表
   - 无需大改，消息组件内部处理附件渲染

---

## 五、影响范围分析

### 5.1 需要新增的文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/crm_profile/services/ai_attachment.py` | 后端服务 | 附件上传、存储、元数据管理 |
| `app/crm_profile/services/vision_analyzer.py` | 后端服务 | **两阶段管线核心**：调 GPT-4o-mini Vision 分析图片 |

### 5.2 需要修改的文件

| 文件 | 改动量 | 改动内容 |
|------|--------|----------|
| `app/crm_profile/models.py` | 小 | 新增 `CrmAiAttachment` 模型（~25 行） |
| `app/crm_profile/schemas/api.py` | 小 | `AiChatRequest` 加字段 + 新增 response schema（~15 行） |
| `app/crm_profile/router.py` | 中 | 新增上传接口 + chat/stream 端点传递 attachment_ids（~40 行） |
| `app/crm_profile/services/ai_coach.py` | 中 | 附件加载 + Vision 描述注入 user_message（~50 行） |
| `app/config.py` | 小 | 新增 Vision 分析相关配置项（~5 行） |
| `app/schema_migrations.py` | 小 | 新增 `crm_ai_attachments` 表迁移（~15 行） |
| `frontend/.../AiCoachPanel.vue` | 中 | 附件按钮、文件选择、缩略图预览（~60 行） |
| `frontend/.../useAiCoach.ts` | 中 | 上传方法、类型扩展、发送携带附件（~50 行） |
| `frontend/.../AiCoachUserMessage.vue` | 小 | 附件缩略图渲染（~30 行） |

### 5.3 不需要修改的文件

| 文件 | 原因 |
|------|------|
| `app/clients/ai_chat_client.py` | Vision 调用复用同一个 client（切 provider=aihubmix）；DeepSeek 调用不变 |
| `app/crm_profile/services/prompt_builder.py` | **无需改动** — user_message 仍是 `str`，描述文本在上层拼好 |
| `app/services/storage/` | 完全可复用现有存储基础设施 |
| `app/crm_profile/services/safety_gate.py` | 安全门控只检查 answer text，无需改动 |
| `app/crm_profile/services/audit.py` | content 记录纯文本（含附件描述），审计链路不变 |
| `app/crm_profile/services/context_builder.py` | 客户档案上下文构建无需感知附件 |
| `app/crm_profile/services/profile_context_cache.py` | 缓存机制不涉及附件 |

### 5.4 风险评估

| 风险项 | 级别 | 说明 | 缓解措施 |
|--------|------|------|----------|
| **Vision 分析延迟** | 中 | Stage 1 增加 2-5 秒等待 | 前端显示"正在分析附件..."状态；后续可预分析 |
| **Vision 分析质量** | 中 | GPT-4o-mini 对复杂图表的解读可能不完美 | 精调 Vision prompt；支持升级到 GPT-4o 大模型 |
| **Token 消耗增加** | 中 | Vision 调用额外消耗 + 描述文本增加 DeepSeek token | GPT-4o-mini 成本极低；描述文本通常 500-2000 字 |
| **上传超时** | 低 | 大文件上传可能慢 | 前端进度条 + 后端超时配置 |
| **PDF 页数过多** | 低 | 长 PDF 每页都要 Vision 分析 | 限制最多 10 页 + 提示用户 |
| **安全** | 低 | 用户上传恶意文件 | MIME 类型白名单 + 文件大小限制 |

---

## 六、依赖评估

### 6.1 已有依赖（无需安装）

- `python-multipart` — FastAPI 文件上传
- `Pillow` — 图片处理 / 压缩
- `httpx` — AI API 调用（Vision 调用复用）

### 6.2 需要新增的依赖

| 库 | 用途 | 说明 |
|----|------|------|
| `pymupdf` | PDF 页面渲染为图片 | 将 PDF 每页转为 PNG，供 Vision API 分析 |

仅需一个额外依赖。Vision API 调用复用现有的 `ai_chat_client.py`（切换到 aihubmix provider）。

---

## 七、实现优先级建议

### Phase 1：图片上传 + Vision 分析（MVP）
- 后端附件上传接口 + 存储
- `vision_analyzer.py` — 调 GPT-4o-mini Vision 分析图片
- `ai_coach.py` 集成 — Vision 描述注入 user_message
- 前端附件按钮 + 图片预览 + "正在分析附件..."状态
- 限制单次 1-3 张图片
- **重点验证**：血糖曲线图的 Vision 分析质量
- **预估工作量**：3-4 天

### Phase 2：PDF 上传
- `pymupdf` 集成，PDF 页面渲染为图片
- 渲染后的图片逐页走 Vision 分析
- 前端 PDF 文件名 + 页数预览
- **预估工作量**：1-2 天

### Phase 3：增强体验
- Vision prompt 按附件类型细化（血糖图专用 prompt、体检报告专用 prompt）
- 预分析：上传完成后立即触发 Vision 分析，不等用户发送消息
- 图片压缩优化（降低 Vision 调用 token）
- 历史会话中附件回显
- Vision 分析结果缓存
- **预估工作量**：2-3 天

---

## 八、总结

| 维度 | 评估 |
|------|------|
| **技术可行性** | ✅ 高 — 双模型管线各取所长，存储基础设施可复用 |
| **核心架构** | GPT-4o-mini Vision 负责图像理解 → DeepSeek V4 Pro 负责深度推理 |
| **改动范围** | 中等 — 新增 2 个服务文件，修改约 8 个文件 |
| **新增依赖** | 仅 `pymupdf`（PDF→图片），Vision 调用复用现有 AI Client |
| **关键优势** | DeepSeek 对话流程零侵入；prompt_builder 无需改动；审计链路不变 |
| **风险** | 可控 — 主要关注 Vision 分析质量和额外延迟 |
| **建议** | 先做图片上传 MVP，重点验证血糖曲线图的 Vision 分析效果 |
