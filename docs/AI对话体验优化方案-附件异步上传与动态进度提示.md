# AI 对话体验优化方案 — 附件异步上传 + 动态进度提示

- **日期**: 2026-05-15
- **涉及模块**: 前端 AI 对话组件、后端附件上传、后端 SSE 流
- **目标**: 消除附件上传阻塞 + AI 回复前展示真实处理进度

---

## 一、现状问题

### 问题 1：附件上传仍然阻塞用户发送

用户预期：选文件 → 立刻看到预览 → 后台上传七牛 → 打完字发送时上传已完毕

实际行为：选文件 → **await 上传** → 上传完成后才能发送

**阻塞点**：

| # | 位置 | 阻塞方式 |
|---|------|---------|
| 1 | `useAiFileUpload.ts:159` | `await uploadAttachmentDirect(...)` 在 `addAndUploadFile` 中同步等待上传完成 |
| 2 | `AiCoachPanel.vue:885` | `send()` 检查 `uploadingAttachment`，为 true 时直接 return 并弹 warning，**完全阻止发送** |

用户体感：选完附件后要等 2-5 秒（上传到七牛），发送按钮点了也没反应。

### 问题 2：AI 思考阶段无进度反馈

当前时间线（用户体感）：

```
T+0s    用户点击发送
T+0s    聊天区出现用户消息 + 空白 assistant 卡片（骨架屏动画）
T+0~3s  骨架屏闪烁，无任何文字说明在做什么
         实际后端在: 附件分析 → RAG检索 → Profile加载 → Prompt组装
T+3s    骨架屏消失，RAG引用卡片出现
T+3s    AI回复开始流式输出
```

用户在 T+0 到 T+3s 之间只能看到一个旋转图标 + 骨架屏动画，**完全不知道系统在做什么**，体感"卡住了"。

---

## 二、优化方案一：附件异步上传

### 目标行为

```
用户选文件 → 立即显示预览（blob URL）→ 后台静默上传七牛
用户继续打字 → 打完点击发送 → 如果上传已完成则正常发送
                                    如果上传未完成则等待（最多 3s）后发送
```

### 改动文件

#### 1. `frontend/src/views/CrmProfile/composables/useAiFileUpload.ts`

**改动点**: `addAndUploadFile` 不再 await 上传，上传在后台自动完成。

```typescript
// 现状（阻塞）：
const addAndUploadFile = async (file: File) => {
  // ... 校验、本地预览、压缩
  uploadingCount.value++
  try {
    const att = await uploadAttachmentDirect(customerId, uploadFile, ...)  // 阻塞在这里
    // ... 更新 pendingAttachments
  } finally {
    uploadingCount.value--
  }
}

// 改为（非阻塞）：
const addAndUploadFile = async (file: File) => {
  // ... 校验、本地预览、压缩（这些很快，保持同步）
  uploadingCount.value++
  // 不 await，后台执行
  _doUpload(tempAtt, uploadFile, contentHash).finally(() => uploadingCount.value--)
}

const _doUpload = async (tempAtt: AiAttachment, file: File, hash: string) => {
  try {
    const att = await uploadAttachmentDirect(customerId, file, (pct) => {
      const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempAtt.attachment_id)
      if (idx >= 0) pendingAttachments.value[idx].progress = pct
    }, hash)
    // 上传完成，用真实 attachment_id 替换临时条目
    const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempAtt.attachment_id)
    if (idx >= 0) {
      att.url = tempAtt.url || att.url  // 保留本地 blob URL 用于预览
      att.uploading = false
      att.progress = 100
      pendingAttachments.value[idx] = att
    }
  } catch (err: any) {
    // 上传失败，移除该条目并提示
    const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempAtt.attachment_id)
    if (idx >= 0) pendingAttachments.value.splice(idx, 1)
    if (tempAtt.url) URL.revokeObjectURL(tempAtt.url)
    ElMessage.error(err?.message || '附件上传失败')
  }
}
```

关键变化：
- `addAndUploadFile` 立即返回（只做校验+本地预览+启动后台上传）
- `_doUpload` 是独立的 async 函数，在后台执行
- `pendingAttachments` 中的条目从 `uploading: true` 自动过渡到 `uploading: false`

#### 2. `frontend/src/views/CrmProfile/components/AiCoachPanel.vue`

**改动点**: `send()` 不再阻止发送，改为等待上传完成（带超时）。

```typescript
// 现状（阻止发送）：
const send = async () => {
  if (uploadingAttachment.value) {
    ElMessage.warning('附件上传中，请稍候...')  // 直接 return
    return
  }
  // ... 发送
}

// 改为（等待上传完成，最多 3s）：
const send = async () => {
  // 如果有附件正在上传，等待完成（最多 3 秒）
  if (uploadingAttachment.value) {
    const waited = await waitForUploads(3000)
    if (!waited) {
      // 超时：移除未完成的附件，只发送已完成的
      pendingAttachments.value = pendingAttachments.value.filter(a => !a.uploading)
      if (pendingAttachments.value.length === 0 && !message.value.trim()) return
      ElMessage.info('部分附件尚未上传完成，已跳过')
    }
  }
  // ... 正常发送（只用 uploading=false 的附件）
  const attachmentIds = pendingAttachments.value
    .filter(a => !a.uploading && a.attachment_id && !a.attachment_id.startsWith('temp_'))
    .map(a => a.attachment_id)
  // ...
}
```

等待函数：

```typescript
// 在 useAiFileUpload.ts 中添加
const waitForUploads = (timeoutMs: number): Promise<boolean> => {
  return new Promise((resolve) => {
    if (!uploadingAttachment.value) { resolve(true); return }
    const start = Date.now()
    const check = () => {
      if (!uploadingAttachment.value) { resolve(true); return }
      if (Date.now() - start > timeoutMs) { resolve(false); return }
      setTimeout(check, 100)
    }
    check()
  })
}
```

#### 3. UI 反馈优化

在输入框附件预览区域，上传中的附件显示进度条（已有 `progress` 字段），让用户知道正在上传。

---

## 三、优化方案二：AI 思考动态进度提示

### 目标行为

```
T+0s    用户点击发送 → 聊天区出现用户消息
T+0.1s  assistant 卡片出现，显示：  "收到提问：用户要出差，推荐一下餐食"
T+0.5s  进度更新：                   "正在查询知识库..."
T+1.5s  进度更新：                   "召回 3 条相关知识"
T+1.8s  进度更新：                   "模型整合回复中"
T+2.5s  RAG 引用卡片出现 + AI 流式回复开始
```

### 设计原则

1. 进度文本是**硬编码**的，不依赖 LLM 生成（避免增加延迟和 token 消耗）
2. 进度事件由后端**在真实处理节点**发出，不是模拟的
3. 前端直接展示进度文本，不需要解析或转换
4. 进度文本在 AI 流式回复开始后自动消失

### 后端改动

#### 1. 新增 SSE 事件类型 `progress`

在 `stream_ai_coach_answer()` 中，在现有事件之间插入 `progress` 事件。

**文件**: `app/crm_profile/services/ai/__init__.py`

当前事件序列：
```
loading {stage: "prepare"}    ← 骨架屏开始
  (RAG检索、Profile加载、Prompt组装 — 2~3s 黑箱)
loading {stage: "model_call"} ← 骨架屏继续
rag {sources, ...}            ← RAG结果
delta {delta: "..."}          ← AI回复开始
```

改为：
```
progress {text: "收到提问：用户要出差，推荐一下餐食", step: "received"}
progress {text: "正在分析附件", step: "analyzing"}          ← 仅附件场景
progress {text: "正在查询知识库...", step: "rag_search"}
progress {text: "召回 3 条相关知识", step: "rag_done"}       ← 显示召回数
progress {text: "模型整合回复中", step: "model_call"}
rag {sources, ...}
delta {delta: "..."}
```

具体实现位置（`__init__.py` 的 `stream_ai_coach_answer` 函数内）：

```python
# 现有代码在 yield loading {stage: "prepare"} 后直接做 _prepare_ai_turn_cached
# 改为分步 yield progress 事件

# 1. 显示用户提问（截断到 30 字）
user_preview = message[:30] + ('...' if len(message) > 30 else '')
yield AiStreamEvent(event="progress", data={
    "text": f"收到提问：{user_preview}",
    "step": "received",
})

# 2. 附件分析（如有附件）
if attachment_ids:
    yield AiStreamEvent(event="progress", data={
        "text": "正在分析附件",
        "step": "analyzing",
    })
    effective_message = await _resolve_attachment_descriptions(...)

# 3. RAG 检索开始
if settings.rag_enabled:
    yield AiStreamEvent(event="progress", data={
        "text": "正在查询知识库...",
        "step": "rag_search",
    })

# _prepare_ai_turn_cached 完成后，检查 RAG 结果
rag_bundle = ...
if rag_bundle and rag_bundle.sources:
    yield AiStreamEvent(event="progress", data={
        "text": f"召回 {len(rag_bundle.sources)} 条相关知识",
        "step": "rag_done",
    })
elif rag_bundle:
    yield AiStreamEvent(event="progress", data={
        "text": "知识库未找到相关内容，直接回复",
        "step": "rag_done",
    })

# 4. 模型调用
yield AiStreamEvent(event="progress", data={
    "text": "模型整合回复中",
    "step": "model_call",
})
```

**问题**: `_prepare_ai_turn_cached()` 是一个整体调用，RAG 检索在内部完成，无法在外部 yield 事件。

**解决**: 在 `_prepare_ai_turn_async()` 内部传入一个 callback，在关键节点回调 yield：

```python
# _prepare.py 中
async def _prepare_ai_turn_async(
    ...,
    on_progress: Callable[[str, str], Awaitable] | None = None,  # 新增
):
    # RAG 检索前
    if on_progress and settings.rag_enabled:
        await on_progress("正在查询知识库...", "rag_search")

    rag_bundle = await retrieve_rag_context(...)

    # RAG 检索后
    if on_progress and rag_bundle:
        count = len(rag_bundle.sources) if rag_bundle.sources else 0
        if count > 0:
            await on_progress(f"召回 {count} 条相关知识", "rag_done")
        else:
            await on_progress("知识库未找到相关内容，直接回复", "rag_done")

    # ... 后续处理
```

然后在 `stream_ai_coach_answer` 中传入 callback：

```python
async def _progress_cb(text: str, step: str):
    yield AiStreamEvent(event="progress", data={"text": text, "step": step})

# 注意：由于是 async generator，callback 需要通过 queue 或事件机制传递
```

由于 Python async generator 无法直接接收内部 yield，推荐使用 `asyncio.Queue`：

```python
# 在 stream_ai_coach_answer 中
progress_queue: asyncio.Queue[dict | None] = asyncio.Queue()

async def _on_progress(text: str, step: str):
    await progress_queue.put({"text": text, "step": step})

# 启动准备任务
prepare_task = asyncio.create_task(
    _prepare_ai_turn_cached(..., on_progress=_on_progress)
)

# 同时消费 progress 事件和等待准备完成
while not prepare_task.done():
    try:
        evt = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
        if evt:
            yield AiStreamEvent(event="progress", data=evt)
    except asyncio.TimeoutError:
        continue

# 获取最终结果
result = prepare_task.result()
```

#### 2. 现有 `loading` 事件保留但不再显示骨架屏

`loading {stage: "prepare"}` 和 `loading {stage: "model_call"}` 保留（向后兼容），但前端不再用它们来显示骨架屏，改为显示 `progress` 事件中的文字。

### 前端改动

#### 1. `useAiCoach.ts` — 处理 `progress` 事件

在 `sendChat()` 的 answer stream 事件处理中新增：

```typescript
// 在 streamSse 的 onEvent 回调中
case 'progress':
  if (assistantMessage) {
    assistantMessage.progressText = payload.text
    assistantMessage.progressStep = payload.step
  }
  break
```

#### 2. `aiCoachTypes.ts` — 扩展类型

在 `AiChatMessage` 类型中新增字段：

```typescript
progressText?: string   // 当前进度文字
progressStep?: string   // 当前步骤标识
```

#### 3. `AiCoachAssistantMessage.vue` — 展示进度文字

替换当前的骨架屏动画为动态进度文字：

```vue
<!-- 现状：骨架屏 -->
<div v-if="msg.loadingStage && !msg.content" class="skeleton-bars">
  <div class="skeleton-bar w-3/4"></div>
  <div class="skeleton-bar w-1/2"></div>
  <div class="skeleton-bar w-1/4"></div>
</div>

<!-- 改为：动态进度文字 -->
<div v-if="msg.streaming && !msg.content" class="ai-progress">
  <div class="progress-line">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span class="progress-text">{{ msg.progressText || '正在思考...' }}</span>
  </div>
</div>
```

样式：

```css
.ai-progress {
  padding: 12px 16px;
  color: var(--text-secondary);
  font-size: 13px;
}
.progress-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-text {
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

---

## 四、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/.../useAiFileUpload.ts` | 修改 | 拆分 `addAndUploadFile` 为非阻塞版本 + `waitForUploads` |
| `frontend/.../AiCoachPanel.vue` | 修改 | `send()` 不再阻止发送，改为等待上传完成 |
| `app/crm_profile/services/ai/__init__.py` | 修改 | `stream_ai_coach_answer` 新增 `progress` 事件 + `asyncio.Queue` 机制 |
| `app/crm_profile/services/ai/_prepare.py` | 修改 | `_prepare_ai_turn_async` 接受 `on_progress` callback |
| `frontend/.../useAiCoach.ts` | 修改 | 处理 `progress` SSE 事件 |
| `frontend/.../aiCoachTypes.ts` | 修改 | `AiChatMessage` 新增 `progressText`、`progressStep` |
| `frontend/.../AiCoachAssistantMessage.vue` | 修改 | 骨架屏替换为动态进度文字 |

---

## 五、实施顺序

### Phase 1：附件异步上传（独立，可先上线）

1. 改 `useAiFileUpload.ts`：拆分上传为非阻塞
2. 改 `AiCoachPanel.vue`：`send()` 改为等待而非阻止
3. 测试：选文件 → 立即显示预览 → 打字 → 发送时上传已完成

### Phase 2：AI 进度提示（需要前后端配合）

1. 后端 `_prepare.py`：添加 `on_progress` callback 参数
2. 后端 `__init__.py`：重构 `stream_ai_coach_answer`，用 `asyncio.Queue` 传递进度
3. 前端 `aiCoachTypes.ts`：扩展消息类型
4. 前端 `useAiCoach.ts`：处理 `progress` 事件
5. 前端 `AiCoachAssistantMessage.vue`：替换骨架屏
6. 联调测试

---

## 六、风险与注意事项

1. **附件上传超时**：如果网络慢，3s 等待可能不够。建议等待时间可配置，默认 3s，超时后只发送已完成的附件。

2. **Vision 分析阻塞**：即使附件上传完成，Vision 分析可能还在后台运行。当前 `_resolve_attachment_descriptions` 已有 8s 超时 + 降级机制，保持不变。可在进度提示中加上"正在分析附件"让用户知道在等什么。

3. **progress 事件时序**：`asyncio.Queue` 方案确保 progress 事件不丢失，但如果准备阶段非常快（<100ms），用户可能只看到最后一个进度文本。这是可接受的——快就说明不需要长时间等待。

4. **向后兼容**：`loading` 事件保留，前端同时支持 `loading` 和 `progress`。不支持 `progress` 的旧版前端仍然能正常工作（显示骨架屏）。

5. **thinking stream 不受影响**：`progress` 事件只走 answer stream，thinking stream 保持现有逻辑不变。
