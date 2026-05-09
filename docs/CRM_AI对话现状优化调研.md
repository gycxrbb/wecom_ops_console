# CRM AI 对话当前优化点调研报告

> 调研日期：2026-05-09  
> 调研范围：CRM 客户档案 AI 对话、SSE 流式回复、客户上下文缓存、RAG 检索、附件识别、教练反馈闭环、前端 AI 抽屉  
> 结论口径：CRM/业务数据库与用户手工确认记录是 `official truth`；AI profile cache、RAG 召回、可见思考、教练反馈样本都是 `support/candidate`，不能直接升格为 `formal/live truth`。

---

## 1. 当前阶段判断

AI 对话模块已经从“功能接入态”进入 **可运营 MVP + 部分生产治理能力已落地** 阶段。

已经 official 落地的能力：

1. 客户档案页可打开 AI 教练助手，支持场景、输出模式、客户专属备注、历史会话。
2. 后端有正式 AI 对话接口：非流式、正式回复流、可见思考流、重新生成、引用追问、附件上传、反馈。
3. Prompt 已拆成 base / scene / style / context / RAG 多层结构，由 `prompt_builder.py` 拼装。
4. 客户上下文已有 L1 进程缓存 + L2 DB 快照缓存，并在客户详情加载后预热。
5. AI 输出写入 session/message/context snapshot/guardrail/feedback 表，具备审计基础。
6. RAG 已接入对话 prepare 阶段，并能把来源和推荐素材通过 SSE 返回前端。
7. 前端 AI 抽屉已支持双 SSE、模型选择、附件、上下文预览、RAG 参考、发送中心衔接、点赞/点踩/反馈审核。

仍不是完成态的地方：

1. 模型选择、审计模型名、重新生成参数之间还没有完全统一。
2. RAG 检索日志没有稳定绑定本次 AI session/message，难以做完整复盘。
3. Profile cache 已有，但 prompt-ready 级别的 AI context cache 仍未落地。
4. 前端 AI 抽屉和 composable 文件超过项目文件大小红线，后续维护成本高。
5. 反馈闭环已能收集，但还缺“反馈样本如何进入 prompt 版本迭代”的治理工作台。

---

## 2. 当前 AI 对话链路

### 2.1 看见：用户入口与前端状态

主要文件：

```text
frontend/src/views/CrmProfile/index.vue
frontend/src/views/CrmProfile/components/AiCoachPanel.vue
frontend/src/views/CrmProfile/components/AiCoachMessageList.vue
frontend/src/views/CrmProfile/components/AiCoachAssistantMessage.vue
frontend/src/views/CrmProfile/composables/useAiCoach.ts
frontend/src/views/CrmProfile/composables/useCrmProfile.ts
```

当前前端能力：

1. 客户详情加载后调用 `/ai/preload` 预热 AI profile cache。
2. 发送消息时同时发起：
   - `/ai/chat-stream`：正式回复。
   - `/ai/thinking-stream`：界面可见的思考摘要。
3. 前端可选择模型，并把 `model` 放入 `chat-stream` 请求体。
4. 支持附件上传、附件预览、RAG 参考消息、素材发送到发送中心。
5. 支持历史会话、重新生成、追问、点赞/点踩反馈。

### 2.2 理解：上下文加载与缓存

主要文件：

```text
app/crm_profile/services/profile_loader.py
app/crm_profile/services/profile_context_cache.py
app/crm_profile/services/context_builder.py
app/crm_profile/services/ai_context_preload.py
```

当前链路：

1. `profile_loader.load_profile()` 串行加载 13 个客户模块。
2. `profile_context_cache` 提供：
   - L1 in-memory cache。
   - L2 `crm_ai_profile_cache` DB 快照。
   - fresh / stale TTL。
   - single-flight 预加载锁。
3. AI prepare 使用 `get_ai_ready_profile_context()`，只读 L1/L2；真正 miss 时调度后台 preload，并快速返回“缓存准备中”。
4. 前端在 cache 未就绪时禁用发送，避免首问同步卡死。

### 2.3 决策：Prompt、RAG、模型调用

主要文件：

```text
app/crm_profile/services/ai_coach.py
app/crm_profile/services/prompt_builder.py
app/crm_profile/prompts/
app/clients/ai_chat_client.py
app/rag/retriever.py
app/rag/query_compiler.py
```

当前链路：

1. `ai_coach.py` 负责 prepare、快捷直答、RAG 检索、AI 调用、输出安全检查、审计。
2. `prompt_builder.py` 组装 base prompt、客户上下文、RAG 上下文、客户专属备注、输出风格。
3. `ai_chat_client.py` 支持 OpenAI-compatible provider、DeepSeek fallback、HTTP/2 fallback、流式 usage。
4. `retriever.py` 已有结构化 query intent、标签 boost、分数门槛、素材二阶段检索、RAG 检索日志。

### 2.4 闭环：审计与反馈

主要文件：

```text
app/crm_profile/models.py
app/crm_profile/services/audit.py
app/crm_profile/services/feedback.py
frontend/src/views/FeedbackReview/index.vue
```

当前 official 审计对象：

1. `crm_ai_sessions`：一次 AI 对话会话。
2. `crm_ai_messages`：用户/AI 消息。
3. `crm_ai_context_snapshots`：本次对话使用的上下文快照。
4. `crm_ai_guardrail_events`：安全门禁事件。
5. `crm_ai_message_feedback`：教练对 AI 回复的反馈。

注意：反馈中的 `expected_answer` 只能是 `candidate answer`，不能自动成为正式 prompt 或正式话术。

---

## 3. 优化点总览

| 优先级 | 优化点 | 当前判断 | 业务影响 |
|---|---|---|---|
| P0 | 统一模型选择与审计口径 | 已有模型选择 UI，但审计/重生成/非流式不完全一致 | 影响问题复盘和模型效果评估 |
| P0 | RAG 检索日志绑定 AI session/message | RAG 写日志时缺少本次正式 message id | 难以解释“这次回答用了哪些知识” |
| P0 | AI 对话文件拆分 | 多个文件超过项目红线 | 后续迭代容易互相踩线 |
| P1 | prompt-ready AI context cache | 只有 profile cache，没有完整 prompt 准备缓存 | prepare 阶段仍有重复组装成本 |
| P1 | 重生成/重试保留原参数 | 重生成固定 7 天窗口，重试可能丢场景/附件/引用参数 | 同一问题前后答案口径可能漂移 |
| P1 | RAG 结合客户上下文检索 | 当前检索主要看 message/scene，没有用客户目标/风险 | 个性化推荐还不够稳 |
| P1 | 反馈闭环进入 prompt 版本治理 | 已收集反馈，缺少从反馈到 prompt 发布的工作流 | 难以持续提升质量 |
| P2 | Profile loader 并行化或分级加载 | 13 个模块串行加载 | 缓存 miss 时仍慢 |
| P2 | SSE 可观测指标面板 | 有日志，没有结构化指标 | 排查线上慢请求成本高 |
| P2 | 附件分析状态与消息绑定 | 附件记录有 session/message 字段但上传时未绑定 | 后续审计附件来源不完整 |

---

## 4. P0 优化建议

### 4.1 统一模型选择、实际调用与审计记录

当前现象：

1. 前端 `useAiCoach.ts` 中 `selectedModel` 会进入 `chat-stream` 请求体。
2. `router.py` 的 `chat-stream` 会把 `body.model` 传给 `stream_ai_coach_answer()`。
3. `stream_ai_coach_answer()` 调用模型时使用了 `model=model`。
4. 但写入 `crm_ai_messages.model` 时仍使用 `settings.ai_model`，不是本次实际选择的模型。
5. 非流式 `/ai/chat` 调用 `ask_ai_coach()` 时没有透传 `body.model`。
6. `regenerate_ai_coach_answer()` 重新生成时也没有保留原模型。

建议：

1. `ask_ai_coach()` 增加 `model` 参数，非流式和流式统一。
2. `stream_ai_coach_answer()` 审计写入时记录 `model or settings.ai_model`。
3. `CrmAiSession` 或 `CrmAiMessage` 中保留每次 message 的 actual provider/model。
4. 重新生成时默认继承原 assistant message 的 model，也允许前端显式切换。
5. 前端模型选择的“推荐”标签不要固定展示在当前选中模型上，应该来自后端推荐策略。

验收标准：

1. 用户选 `gpt-4o-mini`，审计记录就是 `gpt-4o-mini`。
2. 用户选 DeepSeek，审计记录就是 DeepSeek 实际模型。
3. 重新生成、非流式、流式三条路径模型口径一致。

### 4.2 RAG 检索日志绑定本次 AI 会话和消息

当前现象：

1. `retrieve_rag_context()` 支持 `session_id/message_id` 参数。
2. 但 `ai_coach._prepare_ai_turn_async()` 调用 RAG 时没有传入 session/message。
3. `stream_ai_coach_answer()` 在 RAG 之后才创建 `assistant_message_id`。
4. 结果是 `rag_retrieval_logs` 很难与本次 AI 回复形成稳定关联。

建议：

1. 在进入 answer stream 时先生成 `user_message_id` 和 `assistant_message_id`。
2. 把 `session_id/user_message_id/assistant_message_id` 传入 prepare/RAG。
3. RAG 日志至少绑定：
   - `session_id`
   - `customer_id`
   - `user_message_id`
   - `assistant_message_id`
   - `query_intent_json`
   - `hit_json`
   - `visible_hit_count / material_hit_count`
4. 前端 RAG 参考消息也带上对应 assistant message id，便于 UI 展示“本回答引用来源”。

验收标准：

1. 打开 AI 历史会话时，可以查看某条 AI 回复使用的 RAG 来源。
2. 管理员可以按 message 追溯：用户问题 → 检索意图 → 命中资源 → 注入 prompt 的片段 → AI 回复。

### 4.3 拆分超大文件，降低后续协作风险

当前文件行数：

```text
app/crm_profile/services/ai_coach.py                         997 行
app/crm_profile/router.py                                   1068 行
frontend/src/views/CrmProfile/components/AiCoachPanel.vue   1158 行
frontend/src/views/CrmProfile/composables/useAiCoach.ts      810 行
```

这些已经超过项目约束：

1. Python 文件不超过 800 行。
2. TS/Vue 文件不超过 600 行。

建议拆分：

```text
app/crm_profile/services/ai/
├── prepare.py          # profile cache、prompt prepare、turn cache
├── streaming.py        # answer/thinking SSE 编排
├── shortcuts.py        # 姓名/年龄/状态等本地直答
├── safety.py           # 输出安全后检
├── attachments.py      # 附件增强问题
└── regenerate.py       # 重新生成
```

```text
app/crm_profile/routers/
├── profile.py
├── ai_chat.py
├── ai_attachment.py
├── ai_feedback.py
└── ai_cache.py
```

```text
frontend/src/views/CrmProfile/components/AiCoachPanel/
├── index.vue
├── AiCoachSidebar.vue
├── AiCoachInputBox.vue
├── AiCoachContextPanel.vue
├── AiCoachNotePanel.vue
├── AiCoachAttachmentStrip.vue
└── composables/
    ├── useAiStreaming.ts
    ├── useAiAttachments.ts
    ├── useAiFeedback.ts
    └── useAiSessionHistory.ts
```

验收标准：

1. 拆分后单文件符合红线。
2. 路由层只做鉴权、参数校验、调用 service、返回响应。
3. 不改变 API 行为，先做结构治理再做功能改动。

---

## 5. P1 优化建议

### 5.1 增加 prompt-ready AI context cache

当前 `ai_context_preload.py` 只预热 profile cache，不缓存 prompt-ready 结果。也就是说，正式发送时仍要重新：

1. `build_context_text()`
2. 读取 profile note
3. 组装 prompt
4. 计算 used_modules/missing_notes
5. 执行 RAG 检索

建议新增 `ai_context_cache`：

```text
ai_context:{customer_id}:hw{window}:scene:{scene_key}:style:{output_style}:exp:{hash}:note:{updated_at}:rag:{query_hash}
```

缓存内容：

1. `context_text`
2. `used_modules`
3. `missing_notes`
4. `safety_payload`
5. `profile_note_version`
6. `prompt_version/prompt_hash`
7. `estimated_tokens`

注意：

1. 这个缓存是 `support cache`，不是 official truth。
2. 只有用户真正发问后写入的 `crm_ai_context_snapshots` 才是该次对话的 formal audit truth。

### 5.2 重试和重新生成保留原问题参数

当前风险：

1. `retryLast()` 只用最后一条用户消息重新发起 `sendChat(customerId, userMsg.content)`，容易丢失原本的 `healthWindowDays / attachmentIds / quoted_message_id / selected_expansions`。
2. `regenerate_ai_coach_answer()` 固定 `health_window_days=7`，不会继承原消息的 14/30 天窗口。
3. 重新生成只继承 session 的 `scene_key/output_style`，未显式恢复 selected expansions、模型和附件。

建议：

1. 在 `crm_ai_messages` 或 companion metadata 表中保存每条 user message 的请求参数快照。
2. 重试/重新生成默认读取原请求参数。
3. 前端 `AiChatMessage` 的 user message 保存 `requestOptions`，短期先解决当前会话内重试。
4. 历史会话重新生成必须以后端快照为准，不依赖前端内存。

### 5.3 RAG 检索引入客户画像信号

当前 RAG 主要使用：

1. 用户 message。
2. scene_key。
3. query compiler 的关键词规则。
4. RAG 标签与分数门槛。

还没有充分使用：

1. 客户目标：减脂、控糖、运动、长期维护。
2. 安全风险：过敏、禁忌、医生复核等级。
3. 当前服务阶段：新手期、平台期、异常干预期。
4. 教练专属备注：沟通风格、执行障碍。

建议：

1. `retrieve_rag_context(profile_context=ctx)` 真正使用 `ctx`。
2. 从 `goals_preferences / safety_profile / ai_decision_labels / service_issues` 提取检索 boost/filter。
3. 对 `customer_reply` 输出模式优先返回 `customer_visible` 素材。
4. 把 `doctor_review/contraindicated` 资源默认只作为风险提醒，不进入客户可发送话术。

### 5.4 反馈样本进入 prompt 治理流程

当前已经有：

1. 点赞/点踩。
2. 不满意原因。
3. 教练期望回答。
4. admin 反馈审核页面。

缺口：

1. 没有把多条反馈聚类成“prompt 问题类型”。
2. `used_for_prompt` 只是状态，不代表已进入哪个 prompt 版本。
3. 没有 prompt 发布前后的 A/B 或回归样例集。

建议：

1. 新增反馈治理字段：
   - `linked_prompt_file`
   - `linked_prompt_version`
   - `resolution_summary`
   - `regression_case_id`
2. 从点踩样本生成 `candidate eval cases`。
3. 每次修改 prompt 前，至少跑：
   - 基础资料直答
   - 餐食建议
   - 血糖异常
   - 医疗边界
   - 素材推荐
   - 输出格式
4. 只有通过回归样例后，才能把 prompt 版本标记为 formal。

---

## 6. P2 优化建议

### 6.1 Profile loader 分级与并行

`profile_loader.load_profile()` 当前按 `_LOADERS` 串行加载 13 个模块。缓存命中时问题不大，但缓存 miss 或窗口切换时仍可能慢。

建议分两步：

1. P0 必要模块先加载：
   - `basic_profile`
   - `safety_profile`
   - `service_scope`
   - `health_summary`
2. P1/P2 支持模块后台补齐：
   - `learning_engagement`
   - `reminder_adherence`
   - `body_comp`
   - `points_engagement`
   - `service_issues`

也可以在 DB 连接允许的情况下按模块并行，但需要注意 CRM 连接池容量。

### 6.2 SSE 与缓存可观测面板

当前已有较多 `[SSE-TIMING]` 日志，但更适合作为排障日志，不适合作为运营指标。

建议沉淀结构化指标：

1. `prepare_ms`
2. `rag_ms`
3. `first_answer_chunk_ms`
4. `answer_total_ms`
5. `thinking_first_chunk_ms`
6. `profile_cache_source`
7. `prompt_tokens / cached_tokens / completion_tokens`
8. `provider / model`
9. `error_code`

前端或 admin 后台可以展示最近 100 次 AI 调用的性能分布。

### 6.3 附件审计绑定 message

`CrmAiAttachment` 已有 `session_id/message_id` 字段，但当前上传阶段先创建附件记录，真正发送消息时未看到稳定绑定逻辑。

建议：

1. 用户发送消息后，把附件记录回填到本次 `session_id/user_message_id`。
2. AI 回复审计里记录附件分析摘要 hash，而不是只把附件描述塞进 user message。
3. 历史会话打开时可看到“本轮使用了哪些附件”。

---

## 7. 建议推进顺序

第一轮，先做“真值一致性”和低风险治理：

1. 统一模型选择、实际调用、审计记录。
2. RAG 检索日志绑定 session/message。
3. 重新生成/重试参数快照。
4. 拆分超大文件，但不改变行为。

第二轮，再做“体验和性能”：

1. prompt-ready AI context cache。
2. Profile loader 分级加载。
3. RAG 使用客户画像信号。
4. SSE 结构化指标。

第三轮，做“运营闭环”：

1. 反馈样本聚类。
2. prompt eval case 管理。
3. prompt 版本发布记录。
4. AI 质量趋势看板。

---

## 8. 当前 blocker

1. **模型审计漂移**：用户看到可选模型，但后端审计不一定记录真实模型。
2. **RAG 复盘断点**：检索日志与具体 AI 回复缺少稳定关联。
3. **文件体积超线**：核心 AI 文件过大，后续任何多人并行都容易冲突。
4. **反馈还停在收集层**：已有反馈数据，但还没成为 prompt 迭代门禁。

---

## 9. 给项目负责人的状态翻译

按“看见 / 理解 / 决策 / 闭环”表达：

### 已经能做什么

1. **看见**：教练能在客户档案页打开 AI 助手，看历史、看上下文、传附件、选场景和模型。
2. **理解**：系统能把客户基础档案、安全档案、健康摘要、服务关系、阻碍等信息整理给 AI。
3. **决策**：AI 能结合客户信息、prompt 策略和 RAG 知识库生成教练建议与客户话术。
4. **闭环**：系统能记录对话、上下文快照、安全事件和教练反馈，管理员能审核反馈。

### 半能做什么

1. AI 模型可选择，但模型选择和审计记录还没完全统一。
2. RAG 能推荐知识和素材，但还不能完整解释“某条回答到底用了哪条知识”。
3. 教练反馈能收集，但还没形成 prompt 版本迭代流水线。
4. 缓存能减少首问等待，但还没有缓存命中率和慢请求面板。

### 还不能做什么

1. 不能把某条教练标准回答自动升级为正式话术或正式 prompt。
2. 不能把 RAG 召回结果当作客户档案 official truth。
3. 不能稳定按单条 AI 回复复盘完整检索链路。
4. 不能在大文件继续堆功能而不拆分，否则协作风险会快速升高。

### 下一步最值得做什么

最值得优先推进：**模型/审计/RAG 日志/重生成参数一致性 + 文件拆分**。这批改动不追求新 UI，而是把 AI 对话从“功能多”收口到“可解释、可复盘、可继续迭代”。

---

## 10. 本次调研依据

本次主要查看：

```text
app/crm_profile/services/ai_coach.py
app/crm_profile/services/prompt_builder.py
app/crm_profile/services/profile_context_cache.py
app/crm_profile/services/profile_loader.py
app/crm_profile/services/context_builder.py
app/crm_profile/services/audit.py
app/crm_profile/services/feedback.py
app/crm_profile/services/ai_attachment.py
app/crm_profile/services/vision_analyzer.py
app/crm_profile/router.py
app/clients/ai_chat_client.py
app/rag/retriever.py
app/rag/query_compiler.py
frontend/src/views/CrmProfile/components/AiCoachPanel.vue
frontend/src/views/CrmProfile/composables/useAiCoach.ts
frontend/src/views/CrmProfile/composables/useCrmProfile.ts
frontend/src/views/FeedbackReview/index.vue
```

也参考了已有文档：

```text
docs/CRM_AI_SSE_PERFORMANCE_RESEARCH_REPORT.md
docs/CRM_AI_CHAT_RESPONSE_FEEDBACK_PLAN.md
docs/CRM_AI_CONTEXT_CACHE_PRELOAD_OPTIMIZATION_PLAN.md
docs/AI对话RAG检索逻辑调研与改进报告.md
```

---

## 11. 验证说明

本轮是文档调研，没有修改业务代码、依赖或数据库结构。

已完成：

1. 代码链路扫描。
2. 已有文档对照。
3. 文件体积检查。
4. 调研报告落盘。

未执行：

1. 后端启动验证。
2. 前端启动验证。
3. AI 真实接口调用。

原因：本轮交付物是 docs 下的调研文档，不是功能开发或代码修复。
