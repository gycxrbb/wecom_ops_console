# AI 对话 - 图片型 PDF 解析失败 Bug 修复方案

- **日期**：2026-05-14
- **影响范围**：CRM 客户档案 → AI 对话 → 上传扫描型 / 图片型 PDF 附件
- **严重程度**：中高（同一附件无法重试，进入"永久失败"状态）

---

## 一、现象

### 用户侧表现
| 附件类型 | 表现 |
|---------|------|
| 单张图片（jpg/png/webp） | ✅ 正常解析 |
| 文字版 PDF（可选中文字） | ✅ 正常解析 |
| **图片版 / 扫描版 PDF**（页面内容是位图） | ❌ AI 永远无法识别，提示"附件无法识别：xxx" |

### 复现条件
1. 在 AI 对话中通过附件按钮上传一份"扫描版 PDF"（如手机拍的报告、扫描件、整页都是图片的 PDF）
2. 紧接着发起一轮提问
3. 后端日志连续打印：
   ```
   Cannot download attachment 68f3608aadd0462f930b70b933b8ed0c
   httpcore.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol
   Vision analysis failed for 68f3608aadd0462f930b70b933b8ed0c: Cannot read PDF file
   RuntimeError: Cannot read PDF file: 68f3608aadd0462f930b70b933b8ed0c
   ```
4. 之后无论提问多少次，AI 都拿不到该 PDF 的内容

---

## 二、根因分析

### 2.1 直接根因：七牛下载未做重试，单次 SSL 异常即放弃

错误堆栈核心：

```
File "app/services/storage/qiniu.py", line 246, in download_bytes
    resp = httpx.get(url, timeout=60)
httpx.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING]
```

`QiniuStorageProvider.download_bytes()` 直接 `httpx.get(url, timeout=60)`，未做任何重试。
SSL 握手层面的瞬时异常（代理掉线、CDN 节点波动）只要发生一次就直接抛错。

### 2.2 间接根因 1：客户端直传后服务器没有本地副本，必须再次下载

附件上传走的是**客户端直传到七牛**链路：

```
前端 → /ai/prepare-upload → 拿到七牛 token + object_key
前端 → 直传文件到七牛
前端 → /ai/confirm-upload → 服务端只创建一条 DB 记录
```

参见 [app/crm_profile/routers/ai_attachment.py:136](app/crm_profile/routers/ai_attachment.py:136)：

```python
attachment = _create_attachment_record(
    customer_id=customer_id,
    user_id=user.id,
    filename=body.filename,
    mime_type=body.mime_type,
    file_size=body.file_size,
    storage_provider='qiniu',
    storage_key=body.object_key,
    storage_public_url=body.public_url,
    content_hash=normalize_content_hash(body.content_hash),
)
```

**注意：完全没有传 `storage_local_path`**。

而 Vision 分析读取附件的逻辑 [app/crm_profile/services/vision_analyzer.py:181](app/crm_profile/services/vision_analyzer.py:181)：

```python
def _read_attachment_file(attachment):
    if attachment.storage_local_path and Path(attachment.storage_local_path).exists():
        return Path(attachment.storage_local_path).read_bytes()
    # Fallback: 从七牛下载
    return sf.download_bytes(handle)
```

由于 `storage_local_path` 永远为空，**每次分析都必须经过一次七牛 HTTPS 下载**。
同样的，[app/services/storage/facade.py:78](app/services/storage/facade.py:78) 中"下载失败回退到本地副本"的兜底也用不上（`handle.local_path` 是空的）。

### 2.3 间接根因 2：失败结果被永久缓存，没有重试机制

[app/crm_profile/services/vision_analyzer.py:46](app/crm_profile/services/vision_analyzer.py:46)：

```python
if attachment.processing_status == "analyzed" and attachment.vision_description:
    return attachment.vision_description
```

而异常分支 [vision_analyzer.py:58](app/crm_profile/services/vision_analyzer.py:58)：

```python
except Exception as e:
    fallback = f"[附件无法识别：{attachment.original_filename}]"
    _update_attachment(attachment, fallback, "failed")
    return fallback
```

第一次下载失败后 `processing_status` 被置成 `failed`，但 `vision_description` 也写成了 fallback 文案。
下一次进入分析时虽然 status 不是 `analyzed`，但仍会走完 try 分支再失败。**关键问题在于：失败状态没有回收策略，没有重试上限，也没有"前几次失败就强制重新分析"机制**。结果就是用户每次提问都重复跑同一个 SSL 失败链路，永远拿不到内容。

### 2.4 间接根因 3：后台分析启动过早，CDN 还没准备好

[app/crm_profile/services/ai_attachment.py:160](app/crm_profile/services/ai_attachment.py:160)：

```python
async def _analyze():
    await asyncio.sleep(1)
    ...
```

确认上传后只 `sleep(1)` 就开始 Vision 分析。七牛新对象写入到全国 CDN 节点的传播 + 私有 bucket 签名 URL 生效有时延，对于 5–30MB 的扫描 PDF，1 秒内首次 GET 大概率打到尚未就绪的边缘节点。

### 2.5 为什么图片附件 / 文字版 PDF 看起来正常？

这是个很容易误判的现象，但本质上**不是这两种格式天生没问题，只是它们更不容易踩到全部条件**：

| 条件 | 图片附件 | 文字版 PDF | 图片版 PDF |
|------|---------|-----------|-----------|
| 体积 | 通常 < 1MB（前端压缩到 2048px） | < 1MB | 5–30MB（扫描件） |
| Vision 调用次数 | 1 次 | 1–N 次（每页一次） | N 次（每页一次） |
| 单次七牛下载耗时 | 短，握手成功率高 | 短 | 长，更易遇到代理瞬时抖动 |
| 失败缓存影响 | 重新上传新文件易绕过 | 同左 | 同一附件被复用提问，缓存常驻 |

也就是说，**这是一个"高概率失败 + 永久缓存失败结果"叠加放大的体验问题**，并不是 PDF 内容是否为图片本身导致解析逻辑分叉。Vision API 自身完全有能力识别扫描页（`_analyze_pdf` 走的就是把页面渲染成 JPEG 再喂给 Vision），关键卡点在"文件取不下来"。

---

## 三、修复方案

### 3.1 短期修复（必做，工作量 ~1 小时）

**修复点 A：七牛下载加重试 + 区分异常类型**

文件：[app/services/storage/qiniu.py:244](app/services/storage/qiniu.py:244)

- 对 `httpx.ConnectError` / `httpx.ReadTimeout` / `httpx.RemoteProtocolError` 等网络层异常做指数退避重试（建议 3 次，间隔 0.5s / 1.5s / 3s）
- 对 `httpx.HTTPStatusError`（4xx）不重试，直接抛
- 适当增大首次超时（60s → 90s），适配大 PDF

**修复点 B：失败结果不进缓存，并加重试上限**

文件：[app/crm_profile/services/vision_analyzer.py:58](app/crm_profile/services/vision_analyzer.py:58) + [models.py](app/crm_profile/models.py)

- 给 `CrmAiAttachment` 增加字段 `analysis_retry_count`（默认 0）
- 失败分支：retry_count < 3 时**不写 fallback 描述**、不改 status 为 `failed`，仅 +1 retry_count
- 下次请求进入 `analyze_attachment` 时，发现 `processing_status != 'analyzed'` 就重新跑
- 超过 3 次再写 fallback 与 `failed`，避免无限循环

**修复点 C：背景分析延迟拉长**

文件：[app/crm_profile/services/ai_attachment.py:160](app/crm_profile/services/ai_attachment.py:160)

- `asyncio.sleep(1)` → `asyncio.sleep(3)`，给七牛 CDN 留出传播时间
- 或更稳妥：背景分析前先 `httpx.head(url)` 探测一次，404/403 时再延迟 2 秒重试

### 3.2 中期优化（建议做，工作量 ~半天）

**优化点 D：PDF 文字版优先走原生抽取**

文件：[app/crm_profile/services/vision_analyzer.py:123](app/crm_profile/services/vision_analyzer.py:123)

```
_analyze_pdf 流程改为：
1. 先用 pymupdf 的 page.get_text() 抽全文
2. 如果总文字长度 / 页数 > 阈值（比如 100 字/页），判定为文字 PDF，直接返回文字
3. 否则才走 Vision 渲染路径
```

收益：
- 文字版 PDF 不再调 Vision，**响应速度提升 5–10 倍**，**Token 成本降到 0**
- 准确度反而更高（OCR 总有误差）
- 也顺手降低了文字版 PDF 因为下载失败而踩到 SSL 问题的概率

**优化点 E：客户端直传后服务端做异步落本地副本**

可选方案：`confirm-upload` 之后，背景任务把文件从七牛拉到 `data/cache/attachments/` 并回写 `storage_local_path`，后续 Vision 分析、再次提问都直接读本地，无需重新走七牛。

风险：本地磁盘占用增长，需要配套清理策略（比如 LRU 7 天清理）。

### 3.3 长期改进（可选）

- 把 `WeComService` 那种内存频控替换为带集中式重试的 HTTP 客户端中间件（统一加重试、加 trace 日志）
- 在前端附件列表上展示 `processing_status`，失败时给用户"重试分析"按钮，避免用户感觉"上传成功但 AI 装作没看见"

---

## 四、关联文件

| 文件 | 角色 |
|------|------|
| [app/services/storage/qiniu.py](app/services/storage/qiniu.py) | 七牛下载缺重试 |
| [app/services/storage/facade.py](app/services/storage/facade.py) | 本地回退依赖 `local_path`，但客户端直传链路不写 |
| [app/crm_profile/routers/ai_attachment.py](app/crm_profile/routers/ai_attachment.py) | `confirm-upload` 不存 `storage_local_path` |
| [app/crm_profile/services/ai_attachment.py](app/crm_profile/services/ai_attachment.py) | 背景分析 `sleep(1)` 太短 |
| [app/crm_profile/services/vision_analyzer.py](app/crm_profile/services/vision_analyzer.py) | 失败结果被永久缓存；PDF 缺文字直抽快路径 |
| [app/crm_profile/models.py](app/crm_profile/models.py) | 缺 `analysis_retry_count` 字段 |

---

## 五、验证清单

修复后必须覆盖以下用例：

- [ ] 上传扫描版 PDF（10MB / 5 页位图），AI 能拿到识别结果
- [ ] 模拟一次七牛 SSL 异常（mock httpx），重试后能成功
- [ ] 模拟连续 3 次 SSL 异常，最终 status 变为 `failed`，前端能看到失败提示
- [ ] 文字版 PDF 走原生抽取分支（如已实施 D 优化），不调 Vision，响应 < 2s
- [ ] 同一 content_hash 上传两次：第二次走去重命中
- [ ] 上传后 1s 内立刻提问：分析任务在 sleep 期内并发触发也能正确收口

---

## 六、与既有文档的关系

- 与 [AI对话附件处理-Bug修复与优化报告.md](docs/AI对话附件处理-Bug修复与优化报告.md) 互补：彼文档侧重附件加载流程，本文档专门记录"七牛下载失败 → 缓存固化"这条死循环
- 与 [AI附件七牛直传方案.md](docs/AI附件七牛直传方案.md) 配对修订：直传方案应增补"服务端不持有本地副本时的取回容错"约束
