# AI 对话审计与故障诊断优化调研报告

> 调研日期：2026-05-13  
> 调研范围：CRM 客户档案 AI 对话、RAG 召回、AI 消息审计、前端错误体验、管理员审核入口

## 1. 背景与目标

当前 AI 对话已经进入真实业务使用阶段，后续必须补齐两类能力：

1. **管理员可审计**：管理员可以追溯每一次 AI 调用，知道是谁、在哪个客户、问了什么、AI 使用了什么上下文、RAG 是否召回、模型回复了什么、是否报错以及为什么报错。
2. **用户可理解错误**：当 AI 对话失败时，用户不应该只看到“请求失败”或“未知错误”，系统需要尽量判断是权限、登录态、网络、上游模型、RAG、并发还是配置问题，并给出可执行提示。

这两个目标本质上是同一条闭环：**调用过程必须可记录，故障原因必须可归因，管理员和用户看到的信息必须来自同一套真实审计数据。**

## 2. 当前实现现状

### 2.1 已有 AI 审计底座

后端已经有一批可复用的审计模型，主要位于：

- `app/crm_profile/models.py`
- `app/crm_profile/services/audit.py`
- `app/crm_profile/services/ai/__init__.py`

现有模型包括：

| 模型 | 当前用途 | 对新需求的价值 |
| --- | --- | --- |
| `CrmAiSession` | 记录 AI 会话、客户、调用人、场景、Prompt 版本等 | 可以作为审计主线的会话层 |
| `CrmAiMessage` | 记录 user / assistant 消息、模型、token、耗时、请求参数等 | 可以作为问题和回复层 |
| `CrmAiContextSnapshot` | 记录上下文快照、使用模块、健康摘要窗口、缓存 key 等 | 可以满足“AI 预加载上下文是什么”的核心要求 |
| `CrmAiGuardrailEvent` | 记录安全规则事件 | 可用于未来医疗敏感、风险话术审计 |
| `CrmAiMessageFeedback` | 记录教练对 AI 回复的反馈 | 已有管理员反馈审核入口 |

结论：**系统不是完全没有审计能力，而是已有数据分散在会话、消息、上下文、反馈、RAG 日志中，还没有形成一次调用级别的完整审计视图。**

### 2.2 已有管理员入口

当前前端已有两个相关入口：

- `frontend/src/views/FeedbackReview/index.vue`：AI 反馈审核，只覆盖用户主动点赞/点踩后的反馈记录。
- `frontend/src/views/RagManage/components/RetrievalLogTable.vue`：RAG 检索日志，只覆盖 RAG 检索记录。

这两个入口都不能完整回答“某一次 AI 调用到底发生了什么”：

- 反馈审核只看到被反馈的 AI 消息，不覆盖所有调用。
- RAG 日志只看到检索过程，不覆盖用户问题、预加载上下文、模型回复、错误状态。
- 两者目前没有被统一串联到同一个调用详情页。

### 2.3 当前 AI 调用链路

当前 AI 调用大致流程如下：

1. 前端在客户档案中发起 AI 对话。
2. 后端进入 `stream_ai_coach_answer` 或 `ask_ai_coach`。
3. 后端准备客户上下文、健康摘要、扩展模块、RAG 召回结果。
4. 写入 session、user message、context snapshot。
5. 调用上游模型并流式返回。
6. 成功时写入 assistant message。

已有优点：

- 会话、用户问题、上下文快照已经能写入数据库。
- 上下文快照已经包含 `health_window_days` 和 `cache_key`，有利于排查“到底看的是几天窗口”。
- RAG 检索日志中包含 `session_id`、`message_id`、`customer_id`、query、filter、hit、latency、intent 等字段。
- AI 客户端已有基础错误分类：`timeout`、`connection`、`upstream`、`not_configured`、`unknown`。

主要缺口：

- 调用失败时，很多错误只通过 SSE 返回给前端或写普通日志，没有稳定落到数据库。
- 如果模型流式输出中途失败，assistant message 可能不会持久化，审计侧看不到这次失败调用的完整结尾。
- `ProfileCacheNotReady` 等准备阶段失败也可能没有形成一条完整审计记录。
- RAG disabled / unavailable / no_hit / ok 的状态没有统一进入 AI 调用审计详情。
- 管理员没有“按调用查看”的统一页面。

### 2.4 当前前端错误体验

前端 AI 错误展示主要位于：

- `frontend/src/views/CrmProfile/components/AiCoachAssistantMessage.vue`
- `frontend/src/views/CrmProfile/composables/useAiCoach.ts`
- `frontend/src/views/CrmProfile/composables/sseStream.ts`

已有能力：

- 可以根据后端 SSE error code 展示不同提示。
- 已支持 `connection`、`timeout`、`upstream`、`not_configured`、`unknown`。
- 错误卡片支持重试。

主要缺口：

- SSE 使用 `fetch`，没有复用 `frontend/src/utils/request.ts` 的 token refresh 逻辑。
- 401 / 403 / 权限不足 / token 过期在 SSE 链路里容易退化成普通请求失败。
- 前端看到的错误 code 粒度偏粗，无法区分用户无权限、登录过期、模型限流、并发过高、RAG 不可用、客户上下文未准备好。
- 目前没有一个“故障诊断结果”对象返回给前端，用户无法知道下一步应该刷新页面、联系管理员、稍后重试还是检查网络。

## 3. 和目标需求的差距判断

### 3.1 管理员 AI 调用审计差距

用户提出的字段要求如下：

| 需求字段 | 当前是否已有数据 | 差距 |
| --- | --- | --- |
| 谁在调用 | `CrmAiSession.local_user_id`、`crm_admin_id` | 需要在列表页联表显示用户名/管理员名 |
| 哪个客户里调用 | `CrmAiSession.crm_customer_id` | 需要联表显示客户姓名/手机号等脱敏信息 |
| 问题是什么 | `CrmAiMessage(role=user).content` | 成功准备后已有，准备前失败可能缺失 |
| 预加载上下文是什么 | `CrmAiContextSnapshot.compact_json` | 需要详情页可读化展示，并区分窗口、模块、缓存 key |
| RAG 是否召回 | `RagRetrievalLog` | 需要通过 session/message 关联到调用详情 |
| RAG 召回内容 | `RagRetrievalLog.hit_json` | 需要统一展示命中数、素材、参考话术 |
| AI 回复是什么 | `CrmAiMessage(role=assistant).content` | 成功时已有，失败或中断时可能缺失 |
| 是否报错 | 目前主要在 SSE / 日志中 | 需要数据库级状态字段 |
| 报错原因 | `_classify_ai_error` 粗分类 | 需要错误阶段、错误码、原始异常摘要、诊断结果 |

结论：**70% 的原始信息已有，但缺少“调用级审计记录”和“失败持久化”。这是落地的关键。**

### 3.2 故障诊断差距

用户提出的诊断方向可以分为两类：

| 类型 | 是否适合后端判断 | 说明 |
| --- | --- | --- |
| AI 配置是否存在 | 适合 | 后端可检查 API KEY、base_url、模型配置 |
| 当前用户是否有权限 | 适合 | 后端可检查登录态、权限、客户可见性 |
| token 是否过期 | 适合 | 后端能返回 401，前端需要正确识别并刷新或提示登录 |
| 后端到模型服务的网络连通性 | 适合 | 后端可做 DNS、TCP、TLS、HTTP 探测 |
| 上游模型是否超时/限流/拥塞 | 适合 | 后端可做轻量模型调用、统计近期 429/5xx/timeout |
| 当前系统并发是否过高 | 适合 | 后端可统计 in-flight、队列等待、连接池、近段错误率 |
| 用户是否使用 VPN 导致卡顿 | 不能只靠后端准确判断 | 后端只能判断服务器出口网络，不能直接判断用户浏览器网络；需要前端浏览器侧测速配合 |
| 访问 ChatGPT / YouTube 判断网络 | 后端只能判断服务器出口，前端才能更接近用户网络 | 建议做成可配置探针，避免硬编码和误判 |

关键判断：**“后端访问 ChatGPT 或 YouTube”不能证明用户是否在使用 VPN，只能证明服务器能不能访问这些站点。要判断用户侧网络，需要浏览器侧发起探测，并把结果作为辅助诊断，而不是正式事实。**

## 4. 推荐方案一：新增 AI 调用审计中心

### 4.1 产品入口

建议新增管理员页面：

- 菜单名称：`AI 调用审计`
- 推荐位置：系统设置或 AI 管理相关菜单，与 `AI 反馈审核`、`RAG 知识库管理`并列
- 前端页面建议：`frontend/src/views/AiAudit/index.vue`
- 后端路由建议：`/api/v1/admin/ai/audit`

页面核心视图：

1. **调用列表**
   - 时间
   - 调用人
   - 客户
   - 场景
   - 用户问题摘要
   - 模型
   - RAG 状态
   - 调用状态：成功 / 失败 / 中断 / 被拦截
   - 错误码
   - 总耗时

2. **调用详情**
   - 基础信息：调用人、客户、session、message、scene、prompt_version、model、provider
   - 用户问题：完整 question
   - 预加载上下文：context snapshot、used_modules、health_window_days、cache_key
   - RAG 召回：状态、query、filter、命中数量、命中内容、耗时
   - 模型请求：模型、温度、上下文长度、token 估算、request params
   - AI 回复：完整 answer，支持复制
   - 错误信息：error_code、error_stage、error_message、error_detail、diagnostics
   - 关联反馈：如果该回复被点赞/点踩，展示反馈内容

### 4.2 数据模型建议

有两种实现方式：

#### 方案 A：基于现有表做联表视图

优点：

- 改动较小。
- 可以快速上线列表和详情。
- 复用 `CrmAiSession`、`CrmAiMessage`、`CrmAiContextSnapshot`、`RagRetrievalLog`。

缺点：

- 失败调用可能没有完整 assistant message。
- 错误原因仍然没有稳定落库。
- 查询逻辑会比较复杂。

适合：快速 P0 上线。

#### 方案 B：新增调用级审计表

建议新增 `crm_ai_invocation_logs`，把一次用户提问到模型响应的全过程作为一个审计对象。

推荐字段：

| 字段 | 含义 |
| --- | --- |
| `call_id` | 调用唯一 ID |
| `session_id` | AI 会话 ID |
| `user_message_id` | 用户消息 ID |
| `assistant_message_id` | AI 回复消息 ID，可为空 |
| `local_user_id` | 平台用户 ID |
| `crm_admin_id` | CRM 管理员 ID |
| `crm_customer_id` | 客户 ID |
| `entry_scene` / `scene_key` | 调用入口和场景 |
| `prompt_version` / `prompt_hash` | Prompt 版本 |
| `model` / `provider` | 模型和供应商 |
| `question` | 用户问题快照 |
| `context_snapshot_id` | 上下文快照 ID |
| `context_hash` | 上下文 hash |
| `health_window_days` | 健康摘要窗口天数 |
| `cache_key` | 上下文缓存 key |
| `rag_status` | `disabled` / `ok` / `no_hit` / `unavailable` / `error` |
| `rag_log_id` | RAG 检索日志 ID |
| `rag_hit_count` | RAG 命中数量 |
| `answer` | AI 回复快照，可截断或单独存 message |
| `status` | `success` / `error` / `partial` / `blocked` |
| `error_code` | 标准化错误码 |
| `error_stage` | `prepare` / `rag` / `model_connect` / `model_stream` / `persist` |
| `error_message` | 用户可读错误 |
| `error_detail` | 管理员可见错误摘要，禁止保存密钥 |
| `diagnostics_json` | 诊断结果 |
| `prompt_tokens` / `completion_tokens` | token 用量 |
| `latency_ms` | 总耗时 |
| `first_token_ms` | 首 token 耗时 |
| `created_at` / `finished_at` | 时间 |

推荐结论：**P0 可以先做联表视图，但必须同步补齐失败持久化；P1 再新增调用级审计表，降低长期查询和排障成本。**

### 4.3 必须补齐的写入点

需要修改 AI 调用链路，让所有结果都能落库：

1. 进入调用时生成 `call_id`，贯穿 prepare、RAG、model、SSE、audit。
2. user message、context snapshot 写入成功后，立即创建 pending 调用记录。
3. RAG 返回后写入 `rag_status` 和 `rag_log_id`。
4. 模型成功结束后写入 `status=success`、answer、token、耗时。
5. 模型中途断开时写入 `status=partial`，保留已生成内容和错误原因。
6. prepare 阶段失败时写入 `status=error`、`error_stage=prepare`。
7. 权限、token、配置类错误也要形成轻量审计记录，至少能看到“谁尝试调用、在哪个客户、为什么被拒绝”。

## 5. 推荐方案二：故障诊断与用户提示闭环

### 5.1 标准错误码体系

建议把当前粗粒度错误码升级为统一错误码：

| 错误码 | 场景 | 用户提示 |
| --- | --- | --- |
| `auth_expired` | token 过期或无效 | 登录状态已过期，请刷新页面或重新登录 |
| `permission_denied` | 当前用户没有 AI 对话或客户访问权限 | 当前账号未开通 AI 对话权限，请联系管理员 |
| `ai_disabled` | AI 功能开关关闭 | AI 对话功能未启用，请联系管理员 |
| `profile_cache_not_ready` | 客户上下文还在构建 | 客户资料正在准备，请稍后重试 |
| `provider_config_missing` | API KEY / base_url / model 未配置 | AI 服务未配置，请联系管理员 |
| `provider_auth_failed` | 上游 key 错误或余额异常 | AI 服务认证失败，请联系管理员检查配置 |
| `provider_timeout` | 上游响应超时 | AI 服务响应较慢，请稍后重试 |
| `provider_rate_limited` | 429 或供应商限流 | 当前模型调用繁忙，请稍后重试 |
| `provider_overloaded` | 5xx、上游拥塞 | 上游模型服务繁忙，请稍后再试 |
| `network_unreachable` | 后端无法连接供应商 | AI 服务网络连接异常，请联系管理员排查 |
| `stream_interrupted` | 流式响应中途断开 | AI 回复中断，可点击重试 |
| `rag_unavailable` | RAG 向量库或 embedding 不可用 | 知识库检索暂不可用，AI 将降级回答或提示稍后重试 |
| `concurrency_limited` | 本系统并发队列过高 | 当前使用人数较多，请稍后重试 |
| `unknown` | 未分类错误 | AI 服务暂时异常，请稍后重试或联系管理员 |

### 5.2 后端诊断服务

建议新增服务模块：

- `app/crm_profile/services/ai_diagnostics.py`

建议新增接口：

| 接口 | 权限 | 用途 |
| --- | --- | --- |
| `GET /api/v1/crm-customers/{customer_id}/ai/diagnostics/self` | 当前用户 | 检查自己是否可以使用当前客户的 AI 对话 |
| `POST /api/v1/admin/ai/diagnostics/run` | 管理员 | 主动运行一次后端诊断 |
| `GET /api/v1/admin/ai/diagnostics/recent` | 管理员 | 查看近期错误率、超时率、限流率、并发指标 |
| `GET /api/v1/admin/ai/audit/{call_id}/diagnostics` | 管理员 | 查看某次调用关联诊断 |

后端诊断项：

| 诊断项 | 检查内容 | 注意事项 |
| --- | --- | --- |
| 配置检查 | API KEY 是否存在、base_url 是否有效、模型是否配置 | 不返回密钥明文 |
| 权限检查 | 登录态、角色、客户可见性、AI 功能权限 | 用户端只返回可理解提示 |
| 客户上下文检查 | profile cache 是否 ready、cache_key、health_window_days | 直接关联上下文预加载问题 |
| RAG 检查 | RAG 开关、Qdrant 连通性、collection、embedding 服务 | 区分 disabled、unavailable、no_hit |
| DNS/TCP/TLS 检查 | 后端到模型 base_url 的基础连通性 | 设置短超时，避免拖慢请求 |
| 模型轻量调用 | 使用最小 prompt 检查供应商是否可用 | 需要限流，避免诊断本身消耗过多 |
| 上游错误率 | 最近 5/15/60 分钟 timeout、429、5xx 比例 | 来自调用审计表 |
| 并发检查 | 当前 in-flight、队列长度、连接池等待、p95 latency | 用于判断本系统是否拥塞 |

### 5.3 用户网络与 VPN 判断

这里需要特别注意技术边界：

后端可以检查：

- 服务器是否能访问模型供应商。
- 服务器是否能访问指定外部站点。
- 服务器出口是否存在 DNS、TCP、TLS、HTTP 问题。

后端不能准确判断：

- 用户浏览器是否正在使用 VPN。
- 用户本地网络是否丢包。
- 用户访问前端和访问模型供应商之间的差异。

如果要辅助判断用户侧 VPN / 网络问题，应增加浏览器侧诊断：

1. 前端先请求本系统 `/api/v1/health`，判断用户到本系统是否通畅。
2. 前端请求一个可配置的静态资源或 CDN 探针，判断用户公网访问延迟。
3. 如确有必要，可配置 `chatgpt.com`、`youtube.com` 等外部探针，但必须：
   - 由配置控制，不硬编码。
   - 明确这是“辅助判断”，不能作为正式结论。
   - 注意 CORS、地区可达性和隐私提示。

建议文案不要写成“检测到你使用了 VPN”，而是：

> 当前浏览器网络访问部分外部服务较慢，可能与本地网络、代理或 VPN 有关。建议切换网络后重试。

### 5.4 前端体验优化

建议改造点：

1. `sseStream.ts` 对 HTTP 非 200 响应做结构化解析。
2. SSE 链路补齐 token 过期处理：
   - 401：尝试刷新 token；失败后提示重新登录。
   - 403：提示无权限联系管理员。
3. AI 错误卡片展示分层信息：
   - 用户可读原因。
   - 推荐动作：刷新、重试、联系管理员、稍后重试、切换网络。
   - 管理员排查 ID：`call_id`。
4. 当错误关联诊断结果时，错误卡片可以显示简短诊断：
   - “登录状态已过期”
   - “当前账号没有 AI 权限”
   - “上游模型返回限流”
   - “客户上下文仍在构建”
5. 所有错误都应该带 `call_id`，用户反馈问题时可以直接提供给管理员。

## 6. 开发落地计划

### P0：先让审计闭环可用

目标：管理员能查到每次调用，失败也能查到。

后端：

1. 在 AI 调用入口生成 `call_id`。
2. 扩展审计写入逻辑，失败、超时、中断、prepare 失败都落库。
3. 将 RAG 状态统一写入调用审计结果。
4. 新增管理员审计列表和详情接口。
5. 补齐 SSE 错误返回结构：`code`、`message`、`call_id`、`stage`。

前端：

1. 新增 `AI 调用审计`页面。
2. 列表支持按时间、调用人、客户、状态、错误码、模型筛选。
3. 详情页展示问题、上下文、RAG、回复、错误。
4. AI 错误卡片展示 `call_id` 和更明确的用户提示。

验收标准：

- 成功调用能在审计页面看到完整问题、上下文、RAG、回复。
- 模型超时也能在审计页面看到问题、上下文、错误码。
- RAG no_hit / unavailable / ok 可以被区分。
- 用户反馈的问题可以通过 `call_id` 反查。

### P1：补齐诊断服务

目标：错误原因从“猜测”变成“可诊断”。

后端：

1. 新增 `ai_diagnostics` 服务。
2. 增加配置、权限、上下文、RAG、网络、模型轻量调用、近期错误率诊断。
3. 诊断结果写入 `diagnostics_json`。
4. 对 429、5xx、timeout、连接失败、认证失败做更细分类。

前端：

1. SSE 401 / 403 / token 过期结构化处理。
2. 错误卡片根据错误码展示不同下一步动作。
3. 用户端提供“重新检测”或“复制排查信息”能力。

验收标准：

- token 过期提示刷新或重新登录。
- 无 AI 权限提示联系管理员。
- 上游 429 提示稍后重试。
- 配置缺失提示联系管理员检查 AI 服务配置。
- 后端网络不可达能在管理员诊断页看到失败点。

### P2：运营化与可扩展

目标：从单次排查升级为运营监控。

建议能力：

1. AI 调用日报：调用量、成功率、错误率、平均耗时、token 消耗。
2. 按模型 / 供应商统计稳定性。
3. 按客户 / 教练统计高频问题和失败原因。
4. RAG 命中率和 no_hit 问题池。
5. 反馈审核、调用审计、RAG 检索日志互相跳转。
6. 支持导出 CSV，方便运营复盘。

## 7. 需要修改的主要文件建议

后端建议涉及：

- `app/crm_profile/models.py`：新增或扩展调用级审计模型。
- `app/crm_profile/services/audit.py`：增加调用级写入、失败写入、RAG 关联写入。
- `app/crm_profile/services/ai/__init__.py`：在 stream / non-stream / regenerate 链路中贯穿 `call_id`。
- `app/crm_profile/services/ai/_helpers.py`：扩展错误分类。
- `app/crm_profile/services/ai_diagnostics.py`：新增诊断服务。
- `app/crm_profile/routers/ai_audit_admin.py`：新增管理员审计接口。
- `app/crm_profile/routers/ai_diagnostics.py`：新增诊断接口。
- `app/rag/retriever.py`：确保 disabled / unavailable / no_hit / ok 都能被调用审计识别。
- `app/schema_migrations.py`：补充新表和索引迁移。
- `app/crm_profile/schemas/api.py`：新增审计和诊断响应 schema。

前端建议涉及：

- `frontend/src/router/index.ts`：新增管理员审计路由。
- `frontend/src/views/AiAudit/index.vue`：新增审计页面。
- `frontend/src/views/CrmProfile/composables/sseStream.ts`：补齐 401/403/结构化错误处理。
- `frontend/src/views/CrmProfile/composables/useAiCoach.ts`：保存 `call_id`、诊断摘要、错误阶段。
- `frontend/src/views/CrmProfile/components/AiCoachAssistantMessage.vue`：升级错误卡片。
- `frontend/src/utils/request.ts`：复用或抽取 token refresh 能力给 SSE 使用。

## 8. 风险与注意事项

1. **上下文审计涉及敏感数据**  
   上下文快照可能包含健康摘要、客户画像、聊天历史等敏感信息。管理员页面必须受权限控制，必要时对手机号、身份证、联系方式等字段脱敏。

2. **错误详情不能泄露密钥**  
   `error_detail` 只能保存异常摘要，不能保存 API KEY、Authorization header、完整请求头。

3. **诊断探针不能每次请求都跑全量**  
   网络探测和轻量模型调用应走短超时、限流、缓存，避免诊断服务本身拖垮 AI 对话。

4. **RAG disabled 和 no_hit 不能混为一谈**  
   disabled 是功能关闭，no_hit 是检索正常但没有命中，unavailable 是检索链路异常。审计页面必须区分。

5. **浏览器网络诊断不能被写成确定结论**  
   用户是否使用 VPN 只能做辅助判断，不能作为正式审计事实。

6. **失败调用也必须有审计 ID**  
   如果只有成功调用有记录，管理员排查时会刚好查不到最需要查的问题。

## 9. 推荐最终闭环

推荐将 AI 对话链路收敛成如下闭环：

1. 用户发起问题，系统生成 `call_id`。
2. 后端准备客户上下文和 RAG，所有关键节点记录到调用审计。
3. 模型成功、失败、中断都落库。
4. 前端错误卡片展示用户可执行提示和 `call_id`。
5. 管理员通过 `AI 调用审计`输入 `call_id`，看到完整问题、上下文、RAG、模型回复、错误和诊断。
6. 运营人员通过审计统计发现高频失败原因，再反向优化权限配置、模型供应商、RAG 召回、Prompt 和上下文预加载。

最终目标不是只增加一张日志表，而是建立一套可追溯、可解释、可运营的 AI 对话质量闭环。
