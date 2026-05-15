# AI 附件上传与回复链路调研报告

- **日期**: 2026-05-15
- **范围**: 前端文件选择 → 七牛上传 → 后台 Vision 分析 → AI Prompt 组装 → 流式回复
- **目的**: 审视全链路，识别潜在漏洞与风险点

---

## 一、完整链路概览

```
用户选择/粘贴文件
  │
  ├─ ① 前端本地校验（类型、数量≤3、去重）
  ├─ ② 立即显示预览（blob URL）+ 后台启动上传
  │     ├─ POST /ai/prepare-upload → 获取七牛凭证
  │     ├─ POST 七牛直传（文件不经过 Python 服务器）
  │     └─ POST /ai/confirm-upload → 后端创建 DB 记录 + 触发后台 Vision 分析
  │
  ├─ ③ 后台 Vision 分析（asyncio.Task，不阻塞上传）
  │     ├─ 等 3s（CDN 传播）
  │     ├─ 按类型路由：图片→Vision API / PDF→文本提取→Vision / 文档→文本提取
  │     └─ 结果写入 DB: vision_description + processing_status
  │
用户点击发送
  │
  ├─ ④ 前端等待上传完成（≤3s）→ 过滤出真实 attachment_id
  ├─ ⑤ POST /ai/chat-stream { attachment_ids: ["abc123...", ...] }
  │
  ├─ ⑥ 后端 _resolve_attachment_descriptions
  │     ├─ DB 查询附件（含 customer_id 所有权校验）
  │     ├─ 逐附件解析描述（已分析→直取 / 进行中→等锁≤8s / 未开始→调 Vision）
  │     └─ build_user_message_with_attachments → effective_message
  │
  ├─ ⑦ _prepare_ai_turn_cached → _prepare_ai_turn_async
  │     ├─ RAG 检索（用 original_message，不含附件描述）
  │     ├─ Profile 加载 + Prompt 组装
  │     └─ effective_message 嵌入 user message 末尾
  │
  ├─ ⑧ chat_completion_stream → SSE 流式回复
  │     ├─ progress: "收到提问" → "正在查询知识库" → "召回X条" → "模型整合回复中"
  │     ├─ rag: RAG 引用卡片
  │     ├─ delta: AI 回复文本
  │     └─ done: 完成
  │
  └─ ⑨ 前端展示 AI 回复
```

---

## 二、关键节点详细分析

### 节点 ① 前端本地校验

**位置**: `useAiFileUpload.ts:112-162`

| 校验项 | 实现 | 潜在问题 |
|--------|------|----------|
| 文件类型 | `ACCEPTED_TYPES` 白名单 + 扩展名兜底 | 无 |
| 数量限制 | `pendingAttachments.length >= 3` | 无 |
| 重复检测 | SHA-256 哈希对比 | HTTP 环境下 `crypto.subtle` 不可用，哈希返回空串，去重失效 |
| 文件大小 | **无校验** | 大文件上传超时或内存占用过高 |

**数据流转**: `File` → `fixFileMimeType()` 修正 MIME → 图片经 `compressImage()` 压缩（≤1920px, 0.8 quality）→ 调用 `uploadAttachmentDirect()`

### 节点 ② 七牛直传

**位置**: `useAiCoach.ts:584-631` + `routers/ai_attachment.py`

三步上传流程：
1. `prepare-upload` → 获取七牛凭证（含 content_hash 去重）
2. 前端直传七牛（文件不经过 Python 服务器）
3. `confirm-upload` → 后端创建 DB 记录 + 触发后台 Vision 分析

**attachment_id 格式**: `uuid4().hex[:32]` — 32 字符十六进制字符串（非整数）

**去重机制**: `prepare-upload` 接收 `content_hash`，如果已有相同 hash 的附件记录，直接返回 `mode: "existing"`，不重复上传。复用粒度为同一客户维度。

**回退路径**: 七牛不可用时返回 `mode: "server"`，前端走服务器中继上传（`upload-attachment` 端点），文件经 Python 服务器转发到存储。

### 节点 ③ 后台 Vision 分析

**位置**: `ai_attachment.py:188-211` + `vision_analyzer.py`

```
_create_attachment_record()
  └─ _start_background_analysis(attachment)     # fire-and-forget asyncio.Task
       └─ asyncio.sleep(3)                       # 等 CDN 传播
            └─ analyze_attachment(attachment)     # 按类型路由
                 ├─ 图片 → GPT-4o-mini Vision API（3 次重试 + 模型降级）
                 ├─ PDF  → pymupdf 文本提取 → 失败则逐页光栅化+Vision
                 └─ 文档 → document_extractor 文本提取
            └─ DB 更新: vision_description, processing_status, vision_tokens
```

**重试策略**: 最多 3 次（跨多次调用累计 `analysis_retry_count`），每次失败返回占位文本 `[附件解析中，请稍后再试（第N次失败）]`。3 次全部失败后标记 `processing_status="failed"`，返回 `[附件无法识别：filename]`。

**关键时序**: 上传完成（confirm-upload）到 Vision 分析完成之间有 3s 等待 + Vision API 调用时间（通常 2-8s）。即用户上传后约 5-11s 才能拿到附件描述。

### 节点 ④ 发送时附件等待

**位置**: `AiCoachPanel.vue:885-916`

```typescript
// 1. 如果有附件正在上传，等待完成（最多 3s）
if (uploadingAttachment.value) {
  const ok = await waitForUploads(3000)
  if (!ok) {
    // 超时：移除未完成的附件，只发已完成的
    pendingAttachments.value = pendingAttachments.value.filter(a => !a.uploading)
  }
}

// 2. 过滤出真实 ID（排除 temp_ 前缀）
const attachmentIds = readyAttachments
  .map(a => a.attachment_id)
  .filter((id): id is string => typeof id === 'string' && !id.startsWith('temp_'))
```

**注意**: 这里只等待「附件上传到七牛」完成，不等待「Vision 分析」完成。Vision 分析在发送后的 SSE 流中处理。

### 节点 ⑤⑥ 后端附件描述解析

**位置**: `_prepare.py:272-310` → `vision_analyzer.py`

当 `stream_ai_coach_answer` 收到 `attachment_ids` 后：

1. **先发 SSE 事件**: `analyzing` + `progress: "正在分析附件"`（前端显示进度）
2. **调用 `_resolve_attachment_descriptions`**:
   - `load_attachments(db, ids, customer_id)` — **含 customer_id 所有权校验**
   - 对每个附件并行解析描述：
     - **已分析** → 直接返回 DB 中的 `vision_description`
     - **后台分析中** → 尝试获取同一把 asyncio Lock，等待最多 **8 秒**
       - 获取成功 → 重新读 DB，取后台分析的结果
       - 获取失败（超时）→ 调用 `analyze_attachment` 同步分析
     - **未开始分析** → 调用 `analyze_attachment` 同步分析
3. **组装 effective_message**:
   ```
   【附件分析结果】
   [附件: report.pdf]
   <vision_description 文本>

   [附件: photo.jpg]
   <vision_description 文本>

   【用户提问】
   <用户原始问题>
   ```

**潜在问题**: 如果 Vision 分析耗时较长（如多页 PDF），这一步可能阻塞 SSE 流长达 8+ 秒，用户看到"正在分析附件"后长时间无进展。虽然有 progress 事件机制，但 Vision 分析内部没有细粒度的进度回调。

### 节点 ⑦ AI Prompt 组装

**位置**: `prompt_builder.py:75-151`

最终发送给 LLM 的 messages 结构：

| # | role | 内容 |
|---|------|------|
| 1 | system | 基础系统指令 + 场景指令 |
| 2 | system | 客户上下文（档案数据） |
| 3 | system | RAG 检索结果 + 客户备注 + 场景提示 |
| 4 | user | **effective_message**（含附件描述）+ 输出风格提示 |

**关键设计**: 附件描述嵌入在 `user` message 中，而非 `system` message。这意味着附件内容参与了用户意图的表达，但不影响 system 层的指令和上下文。

**RAG 检索独立**: `_prepare_ai_turn_async` 中 `rag_query = original_message or message`，RAG 检索使用**用户原始问题**而非 effective_message。这是正确设计——避免附件描述污染 RAG 查询语义。

**缓存键**: 包含 `attachment_ids` 元组，不同附件组合产生不同缓存条目，避免缓存污染。

---

## 三、潜在漏洞与风险评估

### 风险 1：Vision 分析阻塞 SSE 流（严重度：中）

**场景**: 用户上传多页 PDF 或多张图片后立即发送。

**现状**: `_resolve_attachment_descriptions` 在 `stream_ai_coach_answer` 中被 `await` 调用，会阻塞 SSE 事件流。如果 Vision 分析耗时 >8s（lock 超时）+ analyze_attachment 耗时，总阻塞时间可达 15-30s。

**用户体感**: 看到"正在分析附件"进度后，长时间无新进度事件，然后突然开始 AI 回复。

**建议**: 在 `_resolve_attachment_descriptions` 内部添加细粒度进度回调（如"正在解析第 2/3 个附件"），利用已有的 `on_progress` Queue 机制传递给前端。

### 风险 2：前端无文件大小校验（严重度：中）

**场景**: 用户上传超大文件（如 50MB PDF）。

**现状**: 前端 `addAndUploadFile` 只校验了文件类型和数量，没有校验文件大小。

**影响**:
- 七牛直传可能超时（前端设了 120s timeout，但大文件在慢网络下仍可能超时）
- 图片压缩在大图上耗时较长（虽然不阻塞用户操作）
- Vision API 处理大文件耗时更长

**建议**: 添加文件大小限制（如单文件 ≤20MB），在前端校验阶段直接拒绝。

### 风险 3：HTTP 环境下去重失效（严重度：低）

**场景**: 系统在 HTTP（非 HTTPS）环境下运行。

**现状**: `hashFile()` 依赖 `window.crypto.subtle`，该 API 仅在安全上下文（HTTPS 或 localhost）可用。不可用时返回空串，`contentHash` 为空，去重检查跳过。

**影响**: 同一文件可能被重复上传到七牛，占用存储空间。`prepare-upload` 后端也有 hash 去重，所以影响仅限于多余的七牛上传操作。

**建议**: 可接受，因为后端也有去重。如需修复，可在前端降级为文件名+大小作为简易指纹。

### 风险 4：Lock 竞争导致 Vision API 重复调用（严重度：低）

**场景**: 后台 Vision 分析正在进行，用户发送消息触发 `_resolve_attachment_descriptions`。

**现状**:
1. `_resolve_one` 尝试获取同一把 Lock，等待 8s
2. 如果 8s 内获取成功 → 重新读 DB，取后台结果 → 正常
3. 如果 8s 超时 → 调用 `analyze_attachment`
4. 但 `analyze_attachment` 内部也会获取同一把 Lock → **此时后台任务仍持有 Lock**
5. 导致 `analyze_attachment` 内部也等待 Lock 释放

**实际效果**: 超时路径不会真正调用 Vision API（因为 Lock 被后台任务持有），而是等待后台任务完成。这不是 bug，但 8s 超时 + Lock 等待可能造成总等待时间过长。

**建议**: 可接受。Lock 机制确保了 Vision API 不会重复调用。

### 风险 5：附件描述长度不可控（严重度：低）

**场景**: 多页 PDF 光栅化后，Vision API 返回非常详细的描述文本。

**现状**: `build_user_message_with_attachments` 直接拼接所有附件描述，没有截断或摘要。

**影响**: effective_message 可能非常长（几千字），消耗大量 prompt tokens。但当前 `max_tokens=15000` 和模型的上下文窗口足以容纳。

**建议**: 可考虑对单个附件描述设定长度上限（如 2000 字），超出时截断并提示。

### 风险 6：asyncio.Queue + create_task 的 progress 事件丢失（严重度：低）

**场景**: `_prepare_ai_turn_cached` 命中缓存（瞬间完成），或 RAG 检索极快（<150ms）。

**现状**: `stream_ai_coach_answer` 中的 progress 消费循环每 150ms 轮询 Queue。如果 prepare_task 在第一次轮询前就完成了，循环退出后 `drain remaining` 会取出所有事件。不会丢失。

**潜在问题**: 如果 `_prepare_ai_turn_cached` 抛异常（如 ProfileCacheNotReady），progress 事件可能在异常抛出前未被消费。但由于 `prepare_task.result()` 会 re-raise 异常，此时已 drain 的事件已经 yield 出去了。

**结论**: 正常情况下不会丢失。

### 风险 7：前端 attachment_id 类型过滤 Bug（已修复）

**原问题**: `send()` 中 `typeof id === 'number'` 过滤导致所有附件 ID（字符串类型）被丢弃，后端收不到附件。

**修复**: 改为 `typeof id === 'string' && !id.startsWith('temp_')`。

**根因**: Phase 1 异步上传改造时，将 attachment_id 误判为数字类型。

---

## 四、数据流转全景

### 附件上传路径

```
File (浏览器)
  → 校验/压缩 (前端 JS)
  → FormData (七牛直传) 或 Blob (服务器中继)
  → 七牛云存储 / 本地文件系统
  → DB: crm_ai_attachments 表
      attachment_id: varchar(64)  -- 32位hex字符串
      storage_public_url: varchar -- 七牛/本地 URL
      processing_status: varchar  -- pending/analyzing/analyzed/failed
      vision_description: text    -- Vision分析结果
      content_hash: varchar       -- SHA-256 去重指纹
```

### AI 回复路径

```
attachment_ids: string[]         -- 前端发送
  → _resolve_attachment_descriptions
    → effective_message: string  -- 含【附件分析结果】+【用户提问】
  → _prepare_ai_turn_cached
    → rag_context_text: string   -- RAG 检索结果（基于 original_message）
    → assemble_prompt
      → messages: list[dict]     -- system + user 消息列表
    → ai_messages: list[dict]    -- 含 session 历史消息
  → chat_completion_stream       -- 调用 LLM API
    → SSE: progress/rag/delta/done 事件流
```

### AI 基于什么回复

AI 最终看到的输入：

1. **System 指令**: 基础角色设定 + 场景专用指令（如"qa_support"场景）
2. **客户档案上下文**: 基本信息、健康档案、饮食记录等（经过白名单过滤）
3. **RAG 检索结果**: 从知识库召回的相关话术和素材
4. **附件分析结果**: Vision API 或文本提取的附件内容描述
5. **用户原始问题**: 用户输入的文本
6. **对话历史**: 同一 session 中的历史消息

其中 **附件分析结果** 和 **用户原始问题** 合并在 user message 中，以 `【附件分析结果】...【用户提问】...` 格式呈现。AI 据此理解附件内容并回答用户问题。

---

## 五、结论

当前附件→AI 回复链路整体设计合理，核心流程（上传→分析→Prompt 组装→流式回复）运转正常。主要风险点集中在：

1. **Vision 分析阻塞**: 多附件场景下 `_resolve_attachment_descriptions` 可能长时间阻塞 SSE 流，用户体感为"卡住"。已有 progress 事件机制可扩展此处的细粒度进度反馈。
2. **文件大小无限制**: 前端缺少单文件大小校验，大文件可能导致上传超时或 Vision 分析耗时过长。

这两个问题当前可接受，建议后续迭代优化。
