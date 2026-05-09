# CRM AI 对话优化实施计划

> 创建时间：2026-05-09
> 依据文档：`docs/CRM_AI_CHAT_CURRENT_OPTIMIZATION_RESEARCH.md`
> 实施策略：按风险从低到高分三轮推进，每轮独立可交付、可验证

---

## 实施总览

| 轮次 | 主题 | 任务数 | 风险 | 预估改动量 |
|------|------|--------|------|-----------|
| 第一轮 | 数据一致性与审计对齐 | 4 | 低 | 后端 ~150 行，前端 ~30 行 |
| 第二轮 | 体验稳定性与 RAG 增强 | 4 | 中 | 后端 ~300 行，前端 ~100 行 |
| 第三轮 | 架构治理（文件拆分） | 3 | 中（纯重构） | 文件迁移，行为不变 |

---

## 第一轮：数据一致性与审计对齐

> 目标：让 AI 对话的"谁用了什么模型、检索了什么知识"可追溯。不改行为，只补数据。

### Task 1.1：模型选择与审计记录统一

**问题**：
- `stream_ai_coach_answer()` 审计写入 `model=settings.ai_model`（全局配置），而非用户实际选择的模型
- `ask_ai_coach()` 完全不接受 `model` 参数
- `regenerate_ai_coach_answer()` 不继承原消息的模型
- 前端 `AiChatRequest` 有 `model` 字段，但 `/ai/chat` 非流式端点忽略了它

**改动**：

后端 `ai_coach.py`：
1. `ask_ai_coach()` 增加 `model: str | None = None` 参数
2. `ask_ai_coach()` 把 `model` 传给 `chat_completion()`
3. `ask_ai_coach()` 审计写入 `model=model or settings.ai_model`
4. `stream_ai_coach_answer()` 审计写入 `model=model or settings.ai_model`（非固定 `settings.ai_model`）

后端 `router.py`：
5. `ai_chat` 端点把 `body.model` 传给 `ask_ai_coach(model=body.model)`

后端 `ai_coach.py` regenerate：
6. `regenerate_ai_coach_answer()` 读取原 assistant message 的 `model` 字段，传给 `stream_ai_coach_answer(model=original_model)`
7. 如果原消息 model 为空，fallback 到 `settings.ai_model`

前端（无改动，已经正确传递 model）

**验证**：
- 选 `gpt-4o-mini` 发消息 → `crm_ai_messages` 记录 `model='gpt-4o-mini'`
- 选 DeepSeek 发消息 → 记录 DeepSeek 模型名
- 重新生成 → 继承原模型
- 非流式 `/ai/chat` → 同样记录实际模型

### Task 1.2：RAG 检索日志绑定 session/message

**问题**：
- `_prepare_ai_turn_async()` 调用 `retrieve_rag_context()` 时不传 `session_id` / `message_id`
- RAG 日志与 AI 回复无法关联

**改动**：

后端 `ai_coach.py`：

当前 `stream_ai_coach_answer()` 的时序：
```
prepare (含 RAG) → 创建 user_message → 创建 assistant_message → 流式回复 → 审计
```

需要改为：
```
预生成 user_message_id + assistant_message_id → prepare (传入 ids) → 创建消息 → 流式回复 → 审计
```

具体步骤：
1. `stream_ai_coach_answer()` 开头先生成 `user_message_id` 和 `assistant_message_id`
2. 把 `session_id`、`user_message_id` 传给 `_prepare_ai_turn_async()`
3. `_prepare_ai_turn_async()` 把这些 id 传给 `retrieve_rag_context(session_id=..., message_id=...)`
4. 后续消息创建和审计使用预生成的 id

同样改动 `ask_ai_coach()` 的非流式路径。

**验证**：
- 发一条 AI 消息后，`rag_retrieval_logs` 中能找到对应的 `session_id` 和 `message_id`
- `GET /api/v1/rag/retrieval-logs?message_id=xxx` 能查出该条 AI 回复的检索记录

### Task 1.3：重试保留原始请求参数

**问题**：
- 前端 `retryLast()` 只用最后一条用户消息文本重新发送，丢失 `attachmentIds`、`healthWindowDays`、`quotedMessage`、`selectedExpansions`
- 后端 `regenerate_ai_coach_answer()` 固定 `health_window_days=7`，不继承原消息窗口

**改动**：

后端 `models.py`：
1. `CrmAiMessage` 增加 `request_params_json` Text 字段（nullable），存储 user message 的请求参数快照

后端 `audit.py`：
2. `write_message()` 增加 `request_params: dict | None = None` 参数，user message 写入时序列化存储

后端 `router.py`：
3. `ai_chat_stream` 和 `ai_chat` 端点在写入 user message 时，把请求参数（`health_window_days`、`attachment_ids`、`quoted_message_id`、`selected_expansions`、`model`）序列化存入

后端 `ai_coach.py`：
4. `regenerate_ai_coach_answer()` 从原 user message 的 `request_params_json` 读取参数，继承 `health_window_days` 和 `model`

前端 `useAiCoach.ts`：
5. `retryLast()` 读取最后一条 user message 上保存的 `requestParams`（从后端历史消息加载时带回），透传给 `sendChat()`

短期方案（不做 DB 字段）：
- 前端在 `chatHistory` 的 user message 上附加 `requestOptions` 对象
- `retryLast()` 从内存中读取这些 options
- 历史会话重试暂不支持（需后端快照）

**验证**：
- 带附件发消息 → 重试 → 附件仍在
- 切换到 14 天窗口 → 发消息 → 重新生成 → 新回复也用 14 天窗口

### Task 1.4：附件审计绑定 message

**问题**：
- `CrmAiAttachment` 有 `session_id/message_id` 字段，但上传时未绑定到具体 message
- 历史会话看不到"本轮使用了哪些附件"

**改动**：

后端 `router.py`：
1. `ai_chat_stream` 和 `ai_chat` 端点，在创建 user message 后，把 `body.attachment_ids` 对应的附件记录回填 `message_id`

后端 `ai_attachment.py` 或 `audit.py`：
2. 新增 `bind_attachments_to_message(attachment_ids, session_id, message_id)` 函数

**验证**：
- 上传附件 → 发消息 → 查 `crm_ai_attachments` 表 → `message_id` 非空
- 历史会话打开 → 能看到该轮附件列表

---

## 第二轮：体验稳定性与 RAG 增强

### Task 2.1：RAG 检索引入客户画像信号

**问题**：
- 当前 RAG 检索只用 message + scene，不用客户目标、安全风险、服务阶段
- 导致推荐不够个性化

**改动**：

后端 `ai_coach.py`：
1. `_prepare_ai_turn_async()` 把 `profile_context` 传给 `retrieve_rag_context(profile_context=ctx)`（当前传的是 None）

后端 `retriever.py`：
2. 从 `profile_context` 提取 boost 信号：
   - `goals_preferences` → `customer_goal` tag boost
   - `safety_profile` → 过滤 `medical_sensitive` 资源或降权
   - `service_issues` → `intervention_scene` tag boost
3. 对 `customer_reply` 输出模式，优先返回 `customer_visible` 素材
4. `doctor_review/contraindicated` 资源默认只作为风险提醒，不进入客户话术

后端 `query_compiler.py`：
5. 增加 `compile_from_profile(profile_context)` 方法，从客户画像生成补充查询标签

**验证**：
- 减脂客户问"怎么吃" → RAG 命中减脂相关话术
- 有禁忌的客户 → RAG 不返回医疗敏感素材给客户话术模式
- 在检索日志中能看到客户画像相关的 filter/boost

### Task 2.2：重试/重新生成 SSE done 事件补充模型信息

**问题**：
- 前端 SSE `done` 事件不包含实际使用的模型名
- 前端无法在 UI 上显示"本次回复使用了 xxx 模型"

**改动**：

后端 `ai_coach.py`：
1. `stream_ai_coach_answer()` 的 done SSE 事件增加 `model` 字段（实际使用的模型）
2. 增加 `prompt_tokens` / `completion_tokens` 字段（如果流式 usage 可用）

前端 `useAiCoach.ts`：
3. SSE 事件处理中，从 done 事件读取 model，更新到 assistant message 对象

前端 `AiCoachAssistantMessage.vue`：
4. 可选：显示模型标签（小字灰色）

**验证**：
- 选不同模型发消息 → 回复完成后能看到"使用了 xxx 模型"

### Task 2.3：SSE 结构化计时指标

**问题**：
- 只有 `[SSE-TIMING]` 日志，没有结构化指标
- 排查慢请求成本高

**改动**：

后端 `ai_coach.py`：
1. `stream_ai_coach_answer()` 在 done 事件中增加 `timing` 对象：
   ```json
   {
     "prepare_ms": 320,
     "rag_ms": 150,
     "first_chunk_ms": 800,
     "total_ms": 3500
   }
   ```
2. 同时写入 `crm_ai_messages.latency_ms`（已有字段）

后端 `ai_coach.py` thinking 路径：
3. `stream_ai_coach_thinking()` done 事件同样增加 `timing`

后端 `audit.py`：
4. `write_message()` 如果有 timing 数据，存入 `safety_result` JSON 或新增 `timing_json` 字段

前端 `useAiCoach.ts`：
5. 从 done 事件读取 timing，存储到 message 对象（暂不展示 UI，仅用于调试）

**验证**：
- 发消息 → SSE done 事件包含 timing 对象
- `crm_ai_messages.latency_ms` 有合理数值

### Task 2.4：Profile loader 分级加载

**问题**：
- 13 个模块串行加载，缓存 miss 时慢

**改动**：

后端 `profile_loader.py`：
1. 定义两级加载：
   - P0（同步）：`basic_profile`、`safety_profile`、`service_scope`、`health_summary`
   - P1（后台补齐）：其余 9 个模块
2. `load_profile()` 先返回 P0 结果，后台异步加载 P1
3. `profile_context_cache` 支持部分就绪状态

后端 `ai_context_preload.py`：
4. preload 触发时只等 P0 完成，P1 后台补充

前端 `useCrmProfile.ts`：
5. 预热检查区分"P0 就绪可发消息"和"P1 完整上下文可用"

**验证**：
- 冷启动（无缓存）→ profile 加载时间从 >2s 降到 <1s
- AI 对话可用（P0 就绪），上下文信息逐步补齐

---

## 第三轮：架构治理（文件拆分）

> 原则：纯重构，不改变任何 API 行为。拆分后每个文件符合项目红线。

### 当前超线文件

| 文件 | 当前行数 | 红线 |
|------|---------|------|
| `app/crm_profile/services/ai_coach.py` | 997 | 800 (Python) |
| `app/crm_profile/router.py` | 948 | 800 (Python) |
| `frontend/.../AiCoachPanel.vue` | 1069 | 600 (Vue) |
| `frontend/.../useAiCoach.ts` | 743 | 600 (TS) |
| `frontend/.../CrmProfile.css` | 1052 | 600 (CSS) |
| `frontend/.../aiCoachPanel.css` | 972 | 600 (CSS) |
| `frontend/.../index.vue` | 962 | 600 (Vue) |

### Task 3.1：后端 ai_coach.py 拆分

**目标结构**：

```
app/crm_profile/services/ai/
├── __init__.py          # 重导出公共函数
├── coach.py             # 主入口 + prepare 编排 (~200 行)
├── streaming.py         # answer SSE 编排 (~200 行)
├── thinking.py          # thinking SSE 编排 (~100 行)
├── shortcuts.py         # 本地直答 (~100 行)
├── safety.py            # 输出安全后检 (~80 行)
├── attachments.py       # 附件增强问题 (~80 行)
├── regenerate.py        # 重新生成 (~80 行)
└── prepare_cache.py     # turn cache 管理 (~80 行)
```

**步骤**：
1. 创建 `services/ai/` 目录
2. 按职责拆分函数到对应模块
3. `__init__.py` 重导出 `stream_ai_coach_answer`、`ask_ai_coach` 等公共接口
4. 全局搜索 `from ..services.ai_coach import` → 改为 `from ..services.ai import`
5. 逐个验证：每次迁移后运行后端启动测试

**验证**：
- 所有文件 ≤ 800 行
- `uvicorn app.main:app` 启动无报错
- AI 对话功能不变（手动验证发送、流式、重新生成）

### Task 3.2：后端 router.py 拆分

**目标结构**：

```
app/crm_profile/routers/
├── __init__.py          # 汇总注册子路由
├── profile.py           # 客户档案 CRUD (~200 行)
├── ai_chat.py           # AI 对话端点 (~250 行)
├── ai_attachment.py     # 附件上传/下载 (~150 行)
├── ai_feedback.py       # 反馈端点 (~100 行)
└── ai_cache.py          # 缓存状态/预热端点 (~100 行)
```

**步骤**：
1. 创建 `routers/` 目录
2. 按资源拆分端点到对应模块
3. `__init__.py` 用 `APIRouter` 前缀注册
4. `app/main.py` 中把 `crm_profile.router` 改为 `crm_profile.routers`
5. 验证所有路由可访问

**验证**：
- 所有文件 ≤ 800 行
- 前端所有 AI 对话功能正常

### Task 3.3：前端 AI 教练组件拆分

**目标结构**：

```
frontend/src/views/CrmProfile/
├── index.vue                              # 主页面 (~300 行)
├── composables/
│   ├── useAiCoach.ts                      # AI 对话主逻辑 (~400 行)
│   ├── useAiStreaming.ts                  # SSE 连接管理 (~150 行)
│   ├── useAiAttachments.ts                # 附件上传/预览 (~100 行)
│   ├── useAiFeedback.ts                   # 反馈提交 (~80 行)
│   ├── useAiSessionHistory.ts             # 历史会话管理 (~100 行)
│   └── useCrmProfile.ts                   # 客户档案加载 (不变)
├── components/
│   ├── AiCoachPanel/
│   │   ├── index.vue                      # 抽屉主框架 (~200 行)
│   │   ├── AiCoachSidebar.vue             # 场景/风格/备注侧栏 (~150 行)
│   │   ├── AiCoachInputBox.vue            # 输入框+工具栏 (~200 行)
│   │   ├── AiCoachContextPanel.vue         # 上下文预览 (~100 行)
│   │   ├── AiCoachNotePanel.vue           # 客户备注 (~80 行)
│   │   └── AiCoachAttachmentStrip.vue     # 附件条 (~80 行)
│   ├── AiCoachAssistantMessage.vue        # (不变)
│   ├── AiCoachMessageList.vue             # (不变)
│   ├── AiCoachReferenceMessage.vue        # (不变)
│   └── ... (其余不变)
└── styles/
    ├── crmProfile.css                     # 主页面样式 (~400 行)
    ├── aiCoachPanel.css                   # AI 教练样式 (~400 行)
    └── aiCoachPanelModelSelector.css      # 模型选择器样式 (~200 行)
```

**步骤**：
1. 从 `useAiCoach.ts` 拆出 `useAiStreaming`（SSE 连接、事件处理、done/error）
2. 从 `useAiCoach.ts` 拆出 `useAiAttachments`（上传、预览、删除）
3. 从 `useAiCoach.ts` 拆出 `useAiFeedback`（点赞/点踩/反馈对话框）
4. 从 `useAiCoach.ts` 拆出 `useAiSessionHistory`（会话列表、切换、加载历史消息）
5. `AiCoachPanel.vue` 拆出子组件
6. CSS 文件按功能拆分
7. `index.vue` 精简（模块详情、标签页等拆出子组件）

**验证**：
- 所有文件 ≤ 600 行
- `npm run build` 编译通过
- AI 对话 UI 功能不变（手动验证）

---

## 实施依赖关系

```
Task 1.1 (模型审计) ──┐
Task 1.2 (RAG 日志)   ├── 第一轮，可并行
Task 1.3 (重试参数)   │
Task 1.4 (附件绑定) ──┘
        │
        ▼
Task 2.1 (RAG 客户画像) ── 依赖 1.2（RAG 日志需要先绑定 session）
Task 2.2 (SSE done 模型) ── 依赖 1.1（模型审计先统一）
Task 2.3 (SSE 计时指标)
Task 2.4 (Profile 分级)
        │
        ▼
Task 3.1 (后端 ai_coach 拆分) ── 建议在第一轮、第二轮功能完成后再拆
Task 3.2 (后端 router 拆分)
Task 3.3 (前端组件拆分) ── 建议最后做，避免拆分中改行为
```

**为什么第三轮放最后**：文件拆分是纯重构，如果在功能改动前拆，后续功能 diff 会分散到多个新文件；如果功能改动前不拆，大文件继续膨胀。但考虑到第一轮改动量小（~150 行），大文件还能承受。第三轮在功能稳定后做，避免"边拆边改"的混乱。

---

## 不在本轮范围的事项

调研报告中的以下优化不在本轮实施计划中，记录备查：

| 事项 | 原因 |
|------|------|
| prompt-ready AI context cache | 收益有限（prepare 已有 15s turn cache），复杂度高 |
| 反馈聚类与 prompt eval case | 属于运营闭环，需要业务方定义评估标准 |
| prompt 版本发布记录 | 需要先有 eval case 管理才能闭环 |
| AI 质量趋势看板 | 数据基础（模型审计、RAG 日志）先补齐再做看板 |

---

## 验证检查清单

每轮完成后必须验证：

- [ ] 后端 `uvicorn app.main:app` 启动无报错
- [ ] 前端 `npm run build` 编译通过
- [ ] AI 对话发送、流式回复、重新生成正常
- [ ] `crm_ai_messages` 表中 `model` 字段记录正确
- [ ] `rag_retrieval_logs` 表中有 session_id/message_id
- [ ] 所有改动文件不超过项目红线
