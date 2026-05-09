# CRM AI 上下文缓存与预加载优化计划

## 1. 背景与目标

当前客户档案页已经能加载客户 360 档案，并在 AI 抽屉中发起“正式回复流 + 思考流”。但从使用体验看，首次发起 AI 对话时仍可能卡在 prepare 阶段，原因不是模型本身慢，而是 AI 对话链路在真正发送问题时才开始组装客户上下文、读取补充备注、写审计会话，并且当前缓存 key 口径存在不一致。

本计划目标：

- 用户进入某个客户档案详情页后，后台异步预热 AI 所需上下文。
- 用户打开 AI 抽屉或发送第一句话时，大概率直接命中缓存，减少 prepare 等待。
- 保持上下文 freshness、权限、安全门禁和审计真值清晰，不把预加载缓存写成长期正式事实。
- 为后续 Redis、多进程部署和缓存指标化留出工程接口。

## 2. 当前架构现状

### 2.1 当前链路

1. 前端进入客户档案详情页：
   - `frontend/src/views/CrmProfile/composables/useCrmProfile.ts`
   - 调用 `GET /api/v1/crm-customers/{customer_id}/profile?window=7|14|30`

2. 后端加载档案：
   - `app/crm_profile/router.py:get_customer_profile`
   - `app/crm_profile/services/profile_loader.py:load_profile`
   - 串行加载 `basic_profile / safety_profile / goals_preferences / health_summary / body_comp / points_engagement / service_scope`

3. 当前客户档案页缓存：
   - `app/crm_profile/services/cache.py`
   - TTL: `PROFILE_TTL = 600s`
   - 当前 profile 接口使用 key：`profile:{customer_id}:hw{window_days}`

4. 用户发起 AI 对话：
   - 前端 `useAiCoach.ts` 同时请求：
     - `POST /ai/chat-stream`
     - `POST /ai/thinking-stream`
   - 后端进入 `app/crm_profile/services/ai_coach.py`

5. AI 对话 prepare：
   - `_prepare_ai_turn_cached`：15 秒 turn-level cache，避免同一轮 `answer/thinking` 重复组装。
   - `_prepare_ai_turn`：加载 profile、校验安全档案、构建 `context_text`、读取 profile note、组装 prompt。

### 2.2 当前已有缓存

| 缓存层 | 位置 | 当前 key | TTL | 用途 | 当前问题 |
|---|---|---|---:|---|---|
| 客户档案缓存 | `cache.py` | `profile:{id}:hw{window}` | 600s | 给客户详情页复用 profile | AI prepare 不读这个 key |
| AI profile 缓存 | `ai_coach.py` | `profile:{id}` | 600s | 给 AI prepare 复用 profile | 和页面 profile key 不一致 |
| stale-while-revalidate | `cache.py` + `ai_coach.py` | 同上 | 额外 300s | 过期后先用 stale，再后台刷新 | 只在 AI 的 `profile:{id}` key 上生效 |
| turn cache | `ai_coach.py` | `(customer_id, message, session_id, scene_key, output_style)` | 15s | 同轮 answer/thinking 共享上下文准备结果 | 只解决同一轮重复，不解决首次进入预热 |
| Prompt 文件缓存 | `prompts/registry.py` | `lru_cache` | 进程级 | 缓存 prompt md 文件 | 正常 |

## 3. 主要问题判断

### 3.1 缓存 key 口径不一致

这是当前最直接的缓存未命中原因：

- 客户档案页已加载并缓存：`profile:{customer_id}:hw7`
- AI 对话 prepare 读取：`profile:{customer_id}`

因此用户已经看到了客户档案，AI 仍可能认为 profile cache miss，并重新查询 CRM 数据库。

### 3.2 首次 AI 对话没有预热

目前只有用户点击发送后，后端才执行 AI 上下文准备。即使 key 修正后，如果用户没有先完整走过 `/profile`，或页面数据刚过期，AI 首问仍会同步等待。

### 3.3 DeepSeek thinking 轻量路径绕过标准 prepare

`stream_ai_coach_thinking` 在 DeepSeek provider 下有一条轻量路径，直接读 `profile:{customer_id}`。如果只改通用 prepare，不同步这条路径，thinking 流仍可能 miss。

### 3.4 多进程部署下 in-memory cache 不是 official truth

当前 `cache.py` 明确是进程内缓存。单进程开发/小规模部署可用；多 worker、容器横向扩展后，不同 worker 的缓存不共享，命中率会波动。它只能是 support cache，不应写成正式上下文存储。

### 3.5 缓存观测不足

现在日志能看到部分 `[SSE-TIMING] profile from cache/miss`，但没有统一指标：

- profile cache hit/miss/stale
- preload scheduled/running/success/failure
- prepare 阶段耗时
- 用户进入详情到首次发问的间隔
- 预热命中率

没有这些指标，后续很难判断优化是否真的改善体验。

## 4. 推荐方案

### 总体原则

- `official`：CRM 数据库与实际接口实时加载结果。
- `support`：profile/context/prompt 预热缓存，只用于加速，不作为长期正式事实。
- `candidate`：AI 预加载结果在用户真正发问前只是候选上下文，不能写审计快照。
- `formal`：只有用户发起对话后，写入 `crm_ai_context_snapshots` 的上下文快照才成为该次 AI 会话的正式审计事实。

### 4.1 P0：统一 profile cache key，先让现有缓存命中

新增统一 key helper，避免各处手写：

```python
def profile_cache_key(customer_id: int, window_days: int = 7) -> str:
    return f"profile:{customer_id}:hw{window_days}"
```

调整点：

- `get_customer_profile` 继续使用 `profile:{id}:hw{window}`。
- `_prepare_ai_turn` 改为使用 `profile_cache_key(customer_id, 7)` 或请求传入的 window。
- DeepSeek thinking 轻量路径同步使用同一 key。
- profile note 保存后继续 `invalidate_prefix(f"profile:{customer_id}")`，可覆盖所有窗口。

建议第一阶段 AI 默认只使用 `hw7`，因为当前 AI 上下文 `MODULE_LABELS` 仍以 `health_summary_7d` 为主。后续如果 AI 要支持 14/30 天窗口，需要把 `AiChatRequest` 增加 `health_window_days` 并写入 prompt/audit。

### 4.2 P0：在客户详情加载成功后异步预热 AI 上下文

新增轻量预热接口：

```http
POST /api/v1/crm-customers/{customer_id}/ai/preload
```

请求参数建议：

```json
{
  "health_window_days": 7,
  "scene_key": "qa_support",
  "output_style": "coach_brief",
  "selected_expansions": []
}
```

响应建议：

```json
{
  "customer_id": 123,
  "status": "scheduled",
  "cache_key": "ai_context:123:hw7:scene:qa_support:style:coach_brief:exp:none",
  "profile_cache_status": "hit|miss|stale",
  "ttl_seconds": 600
}
```

前端触发时机：

- `restoreFromUrl/selectCustomer` 完成 profile 加载后触发。
- 不阻塞页面渲染，不阻塞 AI 抽屉打开。
- 每个客户详情页进入后最多触发一次；同一客户短时间重复进入时由后端 single-flight 去重。

后端执行方式：

- FastAPI `BackgroundTasks` 或一个小型 in-process executor。
- 预热任务只做：
  - 权限校验后接受请求。
  - 读取/刷新 profile cache。
  - 构建默认 `context_text`。
  - 读取 `CustomerAiProfileNote`。
  - 组装默认 prompt layers，计算 `context_hash/prompt_hash`。
  - 写入 AI context cache。
- 不写 `crm_ai_sessions`。
- 不写 `crm_ai_messages`。
- 不写 `crm_ai_context_snapshots`。

### 4.3 P0：新增 AI context cache，区别于 profile cache

profile cache 存结构化卡片；AI context cache 存 prompt-ready 的上下文准备结果。

建议新增模块：

```text
app/crm_profile/services/ai_context_cache.py
```

缓存对象建议：

```python
class PreparedCustomerContext:
    customer_id: int
    health_window_days: int
    scene_key: str
    output_style: str
    selected_expansions: list[str]
    context_text: str
    context_hash: str
    prompt_version: str
    prompt_hash: str
    used_modules: list[str]
    missing_notes: list[str]
    safety_payload: dict
    profile_generated_at: str | None
    created_at: float
```

缓存 key 建议：

```text
ai_context:{customer_id}:hw{window}:scene:{scene_key}:style:{output_style}:exp:{expansion_hash}:note:{note_version}
```

其中：

- `expansion_hash`：对排序后的 `selected_expansions` 做稳定 hash，避免数组顺序导致重复缓存。
- `note_version`：第一版可用 `CustomerAiProfileNote.updated_at`；没有 note 时使用 `none`。

AI 发送时优先级：

1. 命中 `ai_context`：直接组装 user message + history。
2. 命中 `profile`：快速 build context text。
3. 命中 stale profile：先用 stale，后台刷新。
4. 全 miss：同步 load_profile，但记录 miss 指标。

### 4.4 P0：single-flight 防止重复预热和重复 DB 查询

同一 customer/window/scene/style/expansion/note_version 同时被多个请求触发时，只允许一个真实任务运行。

建议接口：

```python
def schedule_preload(key: str, loader: Callable[[], PreparedCustomerContext]) -> PreloadStatus:
    ...
```

状态：

- `scheduled`
- `running`
- `hit`
- `stale_hit_refreshing`
- `failed`

实现方式：

- 单进程第一版：`dict[str, Future] + threading.Lock`。
- 多进程第二版：Redis `SETNX preload_lock:{key}` + 短 TTL。

### 4.5 P0：AI 对话 prepare 改成复用预热结果

把 `_prepare_ai_turn` 拆成两段：

1. `prepare_customer_context(...)`
   - 负责 profile/context/note/prompt metadata。
   - 可被 preload 和真实 chat 共同调用。

2. `prepare_ai_turn(...)`
   - 在 `PreparedCustomerContext` 基础上补：
     - session id
     - history
     - current user message
     - shortcut answer/thinking
     - audit 需要的 metadata

这样预热和真实对话共享同一套上下文构建逻辑，避免“预热一套、发送一套”产生 drift。

## 5. 建议落地顺序

### Phase 1：修正缓存真值口径

改动范围：

- `app/crm_profile/services/cache.py`
- `app/crm_profile/router.py`
- `app/crm_profile/services/ai_coach.py`

任务：

- 新增统一 key helper。
- AI prepare 与 DeepSeek thinking 轻量路径改用 `profile:{id}:hw7`。
- 日志增加 `cache_key` 和 `window_days`。
- 修正 `_prepare_ai_turn_cached` miss 路径未传 `selected_expansions` 的问题。

验收：

- 用户打开客户详情后，首问 AI 不应再出现同客户 `profile cache miss`。
- `logs/sse_debug.log` 可看到 `profile cache hit key=profile:{id}:hw7`。

### Phase 2：增加后台预热接口

改动范围：

- `app/crm_profile/schemas/api.py`
- `app/crm_profile/router.py`
- `app/crm_profile/services/ai_context_preload.py` 或 `ai_context_cache.py`
- `frontend/src/views/CrmProfile/composables/useCrmProfile.ts`

任务：

- 新增 `AiContextPreloadRequest/Response` schema。
- 新增 `POST /{customer_id}/ai/preload`。
- 前端详情加载成功后 fire-and-forget 调用。
- 后端 single-flight 去重。

验收：

- 进入客户详情页后不影响主页面加载。
- 1-2 秒内能生成默认 AI context cache。
- 重复进入同一客户不会重复打 CRM DB。

### Phase 3：AI prepare 接入 context cache

改动范围：

- `app/crm_profile/services/ai_coach.py`
- `app/crm_profile/services/ai_context_cache.py`

任务：

- `_prepare_ai_turn` 优先读取 `ai_context`。
- 未命中才 fallback 到 profile cache/load_profile。
- answer/thinking 两条流共享同一 context cache。
- 写审计快照时仍在真实发问后写，不在 preload 阶段写。

验收：

- 首问 prepare 阶段耗时稳定下降。
- 命中预热时，prepare 只做 session/history/user message 组装。

### Phase 4：观测与治理

改动范围：

- `app/sse_debug_log.py`
- 新增轻量 metrics helper 或日志规范。

任务：

- 统一记录：
  - `profile_cache_hit/miss/stale`
  - `ai_context_cache_hit/miss/stale`
  - `preload_scheduled/running/success/failure`
  - `prepare_ms`
  - `context_chars/context_tokens`
- 给前端可选返回 preload 状态，不在 UI 主流程展示，先用于调试。

验收：

- 通过日志能回答：一次 AI 慢是模型慢、上下文 miss、DB 慢、还是审计写入慢。

### Phase 5：Redis 化与多进程支持

触发条件：

- 生产使用多 worker。
- 单进程内存 cache 命中率不稳定。
- 需要跨部署实例共享预热结果。

任务：

- 基于现有 `settings.redis_url` 实现 cache backend 抽象。
- profile/context cache 支持 in-memory 与 Redis 两种 backend。
- single-flight lock 从进程内迁移到 Redis `SETNX`。

验收：

- 多 worker 下同一客户预热只执行一次。
- 任意 worker 收到 AI 请求都能命中预热结果。

## 6. 性能策略

### 6.1 预热只做“默认轻量上下文”

默认只预热：

- `health_window_days=7`
- `scene_key=qa_support`
- `output_style=coach_brief`
- `selected_expansions=[]`

原因：

- 这是最常见首问路径。
- 不预热所有 scene/style/expansion 组合，避免缓存爆炸。
- 用户切换详细报告、客户话术、展开模块时，允许当次局部 miss。

### 6.2 预热节流

建议限制：

- 同一用户同一客户 60 秒内只触发一次 preload。
- 同一客户全局同时最多一个 preload running。
- 后台 preload 队列最大并发 2-4。
- 队列满时丢弃低优先级预热，不影响真实 AI 对话。

### 6.3 stale 优先级

建议策略：

- `fresh hit`：直接用。
- `stale hit`：真实 AI 可以用 stale，但 response metadata/log 标记 `context_freshness=stale`，后台刷新。
- `preload`：如果已有 stale，不必同步刷新，可后台刷新。
- `safety_profile` 缺失或过期风险高时，不能只靠 stale 放行高风险建议，需要重新校验安全卡片。

## 7. 安全与权限

- preload 接口必须和 profile/chat 一样执行 `get_current_user + assert_can_view`。
- preload 不能绕过 AI 开关、客户安全档案检查和字段白名单。
- preload 不能写入正式会话审计表，避免产生“用户没问但系统已有对话”的假事实。
- profile note 更新后必须 invalidate：
  - `profile:{customer_id}:*`
  - `ai_context:{customer_id}:*`
- 客户基础资料、健康摘要、安全档案发生写入或同步时，也应按 customer_id invalidation。

## 8. 文件拆分建议

当前 `app/crm_profile/services/ai_coach.py` 已超过项目 800 行红线。预加载实现不建议继续往该文件堆代码。

建议拆分：

```text
app/crm_profile/services/
├── ai_coach.py                # 对话主编排，逐步瘦身
├── ai_turn_prepare.py          # session/history/user turn 组装
├── ai_context_cache.py         # context cache key、get/put/stale/single-flight
├── ai_context_preload.py       # preload 调度与后台任务
├── prompt_builder.py           # 保持 prompt assembly
└── profile_loader.py           # 保持结构化 profile 加载
```

## 9. 推荐接口草案

### 9.1 Preload

```http
POST /api/v1/crm-customers/{customer_id}/ai/preload
```

```json
{
  "health_window_days": 7,
  "scene_key": "qa_support",
  "output_style": "coach_brief",
  "selected_expansions": []
}
```

### 9.2 Preload 状态可选查询

第一版可不做。如果后续需要调试：

```http
GET /api/v1/crm-customers/{customer_id}/ai/preload-status
```

返回：

```json
{
  "customer_id": 123,
  "default_context": {
    "status": "ready",
    "created_at": "2026-04-26T18:30:00",
    "ttl_seconds": 600,
    "context_tokens": 1800
  }
}
```

## 10. 验收口径

### 10.1 技术验收

- `vue-tsc --noEmit` 通过。
- `npm run build` 通过。
- 后端启动通过。
- `python -m py_compile` 覆盖新增/修改后端文件。

### 10.2 行为验收

场景 A：用户进入客户详情后 1-3 秒再提问

- 预期：AI prepare 命中 `ai_context` 或统一后的 `profile` cache。
- 日志：无同步 `load_profile` miss。

场景 B：用户进入客户详情后立刻提问

- 预期：如果 preload 尚未完成，真实对话可等待同一个 single-flight 任务或复用 running future，不重复查库。

场景 C：更新客户专属补充信息后提问

- 预期：旧 `ai_context` invalidated；新问题使用新 note_version。

场景 D：多次在客户之间切换

- 预期：只预热当前客户，历史客户缓存按 TTL 保留，不无限增长。

## 11. 当前 blocker 与下一步

当前 blocker：

- AI 与客户详情页的 profile cache key 不一致，需要先修。
- `ai_coach.py` 已过大，继续追加预热逻辑会加重维护风险。
- 当前缓存缺少统一指标，无法量化优化收益。

下一步最值得做：

1. 先实现 Phase 1，统一 key 并补日志。
2. 再实现 Phase 2，新增 preload endpoint 和前端 fire-and-forget。
3. 最后把 `_prepare_ai_turn` 拆出 `ai_turn_prepare.py / ai_context_cache.py`，让真实对话和预热共用同一上下文构建函数。

## 12. 面向项目负责人的状态翻译

- 已经能做什么：客户档案和 AI 对话已经打通，AI 能基于客户档案、安全档案、健康摘要和服务关系回答问题。
- 半能做什么：现在有缓存，但缓存只在部分路径生效；用户已看过档案不代表 AI 首问一定命中缓存。
- 还不能做什么：还没有“进入客户详情后自动预热 AI 上下文”的正式后台链路，也没有跨进程共享缓存。
- 当前 blocker：缓存 key 口径不统一，以及 AI 对话准备逻辑集中在超大文件里。
- 下一步最值得做什么：先统一缓存 key，再加无感预热，最后补指标和 Redis 化。
