# CRM AI Profile 缓存机制当前实现报告

> 日期: 2026-04-27  
> 范围: CRM 客户档案页、AI 对话 prepare、Profile 预热、缓存状态门禁、本地数据库 L2 快照  
> 当前阶段: 不引入 Redis，使用应用本地数据库作为 L2 support cache，保障用户进入 AI 对话时不等待 CRM 业务表聚合查询。

---

## 1. 总体结论

当前 CRM AI Profile 缓存机制已经从“只靠进程内缓存”升级为：

```text
CRM official 业务表
  -> 用户档案页构建 CustomerProfileContextV1
  -> L1 进程内短缓存
  -> L2 本地应用数据库快照 crm_ai_profile_cache
  -> AI 对话 prepare 只读 L1/L2
```

当前 official 口径：

1. CRM 业务表仍是用户档案的 official truth。
2. `crm_ai_profile_cache` 是 AI 对话加速用的 support snapshot，不替代 CRM 业务表。
3. Redis 不是当前依赖，只是未来多机、分布式锁和更强缓存治理的候选方向。
4. 用户进入档案页后，后端允许同步构建 profile context，并写入 L1/L2。
5. AI 对话阶段只读 L1/L2；如果完全 miss，只触发后台 preload，并快速提示缓存准备中，不在 AI 对话线程同步查 CRM DB。
6. 前端已经接入缓存状态门禁：缓存构建中时，AI 输入区会短暂禁用发送，避免用户点击后等待慢查询。

业务含义：

- 用户在“看见客户档案”阶段承担 profile 聚合查询。
- 用户在“AI 对话”阶段尽量只读已经准备好的快照。
- 首问体验不再依赖 AI 线程实时查 CRM 多张业务表。

---

## 2. 设计目标与非目标

### 2.1 设计目标

1. **不引 Redis 也要有跨请求缓存**  
   用应用数据库表 `crm_ai_profile_cache` 临时承担 L2 快照能力。

2. **AI 对话不能把 DB 聚合查询放到用户等待链路里**  
   AI prepare 只读缓存；miss 时后台构建并提示稍后再问。

3. **健康窗口口径一致**  
   7/14/30 天窗口统一进入 cache key，避免页面看的是 30 天，AI 用的是 7 天。

4. **缓存状态可观测**  
   后端提供只读 `cache-status`，前端可以知道 ready/building/missing/stale。

5. **过期快照有治理**  
   后台定期清理超出 stale TTL 的 L2 support snapshot。

### 2.2 当前非目标

1. 不把 L2 快照写成用户档案 official truth。
2. 不在当前阶段引 Redis。
3. 不做独立缓存管理后台。
4. 不承诺跨多机的分布式 singleflight。
5. 不保证直接从 AI 入口进入时首问一定有缓存；这种场景会先触发后台 preload。

---

## 3. 核心数据模型

### 3.1 L2 快照表

表名：

```text
crm_ai_profile_cache
```

模型文件：

```text
app/crm_profile/models.py
```

关键字段：

| 字段 | 含义 |
| --- | --- |
| `cache_key` | 唯一缓存 key，格式为 `profile:{customer_id}:hw{window_days}` |
| `crm_customer_id` | CRM 客户 ID |
| `health_window_days` | 健康窗口，当前支持 7/14/30 |
| `context_json` | 序列化后的 `CustomerProfileContextV1` |
| `generated_at` | 快照生成时间 |
| `expires_at` | fresh TTL 过期时间 |
| `stale_expires_at` | stale TTL 过期时间 |
| `last_hit_at` | 最近命中时间 |
| `updated_at / created_at` | 快照维护时间 |

索引/迁移：

```text
app/schema_migrations.py
```

当前会保证：

- `ix_crm_ai_profile_cache_key`
- `ix_crm_ai_profile_cache_customer_window`
- `ix_crm_ai_profile_cache_expires`

### 3.2 缓存 Key

统一 key helper：

```text
app/crm_profile/services/cache.py
```

格式：

```text
profile:{customer_id}:hw{window_days}
```

示例：

```text
profile:892:hw7
profile:892:hw14
profile:892:hw30
```

为什么必须带 `health_window_days`：

- 客户健康摘要、模块数据和 AI 上下文会受 7/14/30 天窗口影响。
- 如果 key 不带窗口，前端切换窗口后，AI 可能读到另一份上下文。

### 3.3 TTL

配置文件：

```text
app/config.py
```

当前配置：

```text
crm_profile_cache_fresh_ttl_seconds = 1800
crm_profile_cache_stale_ttl_seconds = 86400
crm_profile_cache_preload_wait_ms = 15000
```

解释：

- fresh TTL: 30 分钟。
- stale TTL: 24 小时。
- AI 对话允许使用 stale 快照，以保证对话体验优先不中断。
- 超出 stale TTL 后，快照不可用，并会被清理任务删除。

---

## 4. 后端服务分层

### 4.1 L1 进程内缓存

文件：

```text
app/crm_profile/services/cache.py
```

作用：

- 同一 uvicorn worker 内快速复用 profile context。
- 降低反复读 L2 数据库快照的成本。
- 不承担跨进程、跨机器的一致性职责。

### 4.2 L2 本地数据库快照

文件：

```text
app/crm_profile/services/profile_context_cache.py
```

主要方法：

| 方法 | 作用 |
| --- | --- |
| `get_cached_profile_context()` | 只读 L1/L2，返回 hit/miss |
| `ensure_profile_context()` | 可同步构建 profile context，并写入 L1/L2 |
| `get_ai_ready_profile_context()` | AI 专用，只读 L1/L2，miss 时后台 preload 并抛 `ProfileCacheNotReady` |
| `schedule_profile_preload()` | 后台线程预热，带同进程 singleflight |
| `get_profile_cache_status()` | 只读缓存状态，不触发构建 |
| `cleanup_expired_profile_cache()` | 删除 stale 已过期的 L2 快照 |

关键边界：

- `ensure_profile_context()` 可以同步查 CRM DB，适合档案页。
- `get_ai_ready_profile_context()` 不同步查 CRM DB，适合 AI 对话。

### 4.3 同进程 Singleflight

当前机制：

```text
_singleflight_locks: dict[str, threading.Lock]
```

效果：

- 同一个进程内，同一个 cache key 同时只会有一个构建线程。
- 后续请求会得到 `already_running` 或 `building` 状态。

边界：

- 这是进程内 singleflight。
- 多 uvicorn worker 或多机器场景下，不能完全避免并发构建。
- 因为 L2 已落在应用数据库，即使多进程重复构建，最终会收敛到同一个 `cache_key` 快照。
- 如果后续进入多机高并发，再考虑 Redis 分布式锁。

---

## 5. 请求链路

### 5.1 用户进入档案页

接口：

```text
GET /api/v1/crm-customers/{customer_id}/profile?window=7|14|30
```

代码入口：

```text
app/crm_profile/router.py
```

调用：

```text
ensure_profile_context(customer_id, window_days=w, allow_stale=True)
```

流程：

```text
读取 L1
  -> L1 miss 读取 L2
  -> L2 hit 返回 CustomerProfileContextV1
  -> L2 miss 同步 load_profile()
  -> 写入 L1
  -> 写入 crm_ai_profile_cache
  -> 返回档案页数据
```

业务解释：

- 用户正在打开档案页，此时可以接受 profile 数据构建。
- 这一步完成后，AI 对话需要的上下文已经提前准备好。

### 5.2 档案页静默预热

接口：

```text
POST /api/v1/crm-customers/{customer_id}/ai/preload
```

请求体：

```json
{
  "health_window_days": 7,
  "wait_ms": 0
}
```

前端触发点：

```text
frontend/src/views/CrmProfile/composables/useCrmProfile.ts
```

触发时机：

1. `loadProfile()` 成功后。
2. `switchHealthWindow()` 成功后。

后端行为：

```text
已有 L1/L2 -> 直接返回 ready
无缓存且未构建 -> schedule_profile_preload() 后返回 scheduled
已有同 key 构建中 -> 返回 already_running
```

这个接口是 fire-and-forget，不阻塞用户看档案。

### 5.3 缓存状态检查

接口：

```text
GET /api/v1/crm-customers/{customer_id}/ai/cache-status?health_window_days=7|14|30
```

响应字段：

```text
customer_id
status
cache_key
health_window_days
ready
source
generated_at
expires_at
stale_expires_at
message
```

状态含义：

| status | ready | 含义 |
| --- | --- | --- |
| `l1_fresh` | true | 命中进程内缓存 |
| `l2_fresh` | true | 命中本地 DB fresh 快照 |
| `l2_stale` | true | 命中本地 DB stale 快照，可用于 AI |
| `rebuilt` | true | 本次同步构建完成，主要来自档案页 |
| `scheduled` | false | 已安排后台预热 |
| `already_running` | false | 同进程已有相同 key 构建中 |
| `building` | false | 状态检查发现同进程构建中 |
| `missing` | false | L1/L2 都没有可用快照 |
| `checking` | false | 前端本地临时状态，表示正在请求 preload/status |

重要约束：

- `cache-status` 只读缓存状态。
- 它不会触发 CRM profile 构建。
- 这样可以避免状态接口变成新的慢查询入口。

### 5.4 AI 对话

接口：

```text
POST /api/v1/crm-customers/{customer_id}/ai/chat-stream
POST /api/v1/crm-customers/{customer_id}/ai/thinking-stream
```

请求体关键字段：

```json
{
  "message": "用户问题",
  "scene_key": "qa_support",
  "output_style": "coach_brief",
  "health_window_days": 7
}
```

后端 prepare 行为：

```text
normalize health_window_days
  -> get_ai_ready_profile_context()
  -> 只读 L1/L2
  -> ready: 组装 prompt 并进入模型/RAG
  -> miss: schedule_profile_preload()
  -> 抛 ProfileCacheNotReady
  -> SSE 返回缓存准备中事件
```

关键收益：

- AI 对话线程不会因为 profile cache miss 去同步执行 `load_profile()`。
- answer-stream 和 thinking-stream 现在走同一套 cached prepare。
- DeepSeek thinking 旧分支不再绕过 L2。

### 5.5 AI Context Preview

接口：

```text
GET /api/v1/crm-customers/{customer_id}/ai/context-preview
```

当前口径：

- 前端携带当前 `health_window_days`。
- 后端读取同一套 profile context。
- 预览内容和当前健康窗口保持一致。

### 5.6 L2 过期清理

文件：

```text
app/main.py
app/crm_profile/services/profile_context_cache.py
```

启动行为：

```text
if settings.crm_profile_enabled:
    asyncio.create_task(_crm_profile_cache_cleanup_loop())
```

清理周期：

```text
每 6 小时
```

清理规则：

```text
DELETE FROM crm_ai_profile_cache
WHERE stale_expires_at IS NOT NULL
  AND stale_expires_at < now
```

说明：

- 只清理 support cache。
- 不影响 CRM 业务表。
- 不影响正式用户档案 truth。

---

## 6. 前端交互机制

### 6.1 状态保存

文件：

```text
frontend/src/views/CrmProfile/composables/useCrmProfile.ts
```

核心状态：

```text
profileCacheStatus
```

加载档案时：

1. 清空旧 `profileCacheStatus`。
2. 请求 `/profile`。
3. 成功后调用 `preloadProfileCache(customerId, windowDays)`。
4. 保存 `/ai/preload` 返回状态。
5. 如果未 ready，分别在 1.5 秒和 5 秒后静默刷新 `/ai/cache-status`。

切换健康窗口时：

1. 请求对应窗口的 `/profile`。
2. 更新 `currentWindowDays`。
3. 静默 preload 对应窗口的 cache key。

### 6.2 AI 输入门禁

文件：

```text
frontend/src/views/CrmProfile/components/AiCoachPanel.vue
```

当前阻断状态：

```text
checking
scheduled
already_running
building
missing
```

当前不阻断状态：

```text
l1_fresh
l2_fresh
l2_stale
rebuilt
无状态
```

文案：

- 构建中：`客户档案正在准备，稍后即可提问`
- missing：`客户档案缓存未就绪，系统正在准备`
- stale 可用：`客户档案缓存可用，后台会继续刷新`

业务效果：

- 用户如果刚进入页面、缓存还没准备好，发送按钮会短暂不可用。
- 用户不会点完发送才在 AI 对话里等待 DB 聚合。
- stale 快照可用时仍允许提问，保证体验连续。

---

## 7. 健壮性设计

### 7.1 Cache-only AI Prepare

最关键的健壮性变化：

```text
AI 对话阶段不再同步查 CRM DB。
```

这避免了：

- 首问被 CRM 多表聚合拖慢。
- answer-stream 和 thinking-stream 同时触发重复查询。
- DeepSeek thinking 旧分支绕过缓存。

### 7.2 Stale 可用策略

AI 对话允许使用 stale 快照：

- fresh 过期不代表立即不可用。
- stale 过期才视为不可用。
- 这样可以在短时间数据波动和缓存刷新之间保持用户体验。

注意：

- stale 是 support snapshot。
- UI 和后续文档都不能把 stale 写成最新 official 用户档案。

### 7.3 同进程 Singleflight

同一进程同一 cache key：

- 只允许一个构建线程。
- 其他请求返回 `already_running` 或 `building`。

这能降低重复构建，但不等同于分布式锁。

### 7.4 只读状态接口

`/ai/cache-status` 不触发构建。

好处：

- 前端可以频繁轻量检查。
- 不会因为 UI 轮询制造新的 CRM DB 压力。
- 调试时能明确看到 `source/cache_key/expires_at`。

### 7.5 过期清理

后台定时清理 stale 过期快照。

好处：

- 避免 L2 表无限增长。
- 清理不影响 official 业务数据。

### 7.6 权限边界

相关接口仍走：

```text
get_current_user()
assert_can_view(user, customer_id)
```

即：

- 不能因为缓存存在而绕过客户可见性检查。
- cache-status / preload / profile 都必须按客户权限校验。

---

## 8. 当前已验证结果

最近一轮已完成的验证：

```text
python -m py_compile app\crm_profile\services\profile_context_cache.py app\crm_profile\services\ai_context_preload.py app\crm_profile\services\ai_coach.py app\crm_profile\router.py app\crm_profile\schemas\api.py app\main.py

cd frontend
.\node_modules\.bin\vue-tsc.cmd --noEmit
npm.cmd run build
```

项目启动验证：

- 后端备用端口启动已确认 `Application startup complete`。
- 前端沙箱内会复现既有 `esbuild spawn EPERM`，提权后 Vite dev server 已确认 ready。

用户现场测试也确认：

- 后端可启动。
- `/profile` 返回 200。
- `/ai/preload` 返回 200。
- `/ai/config`、`/ai/sessions` 返回 200。
- `chat-stream / thinking-stream` 已进入 AI 对话链路。

现场新暴露的 RAG 审计表缺列问题已经另行修复：

- `rag_retrieval_logs.intent_json` 已加入 `ensure_rag_schema()` 幂等补列。
- 当前库已执行迁移并确认字段存在。

---

## 9. 当前仍需注意的风险

### 9.1 多 worker / 多机重复构建

当前 singleflight 是进程内锁。

风险：

- 多 uvicorn worker 可能同时对同一个 `cache_key` 构建。
- 多机器部署时也无法互斥。

当前影响：

- 不是数据正确性问题，更多是性能浪费。
- L2 通过唯一 `cache_key` 最终会收敛。

后续建议：

- 真正多机高并发后，再引入 Redis 分布式锁或数据库级锁。

### 9.2 直接从 AI 入口进入

如果用户没有先打开客户档案页，直接进入 AI 对话：

- L1/L2 可能 miss。
- AI 会触发后台 preload。
- 本次提问会提示缓存准备中。

这是当前设计的预期行为。

后续可优化：

- 在任何能进入 AI 抽屉的入口前，都先调用 preload/status。
- 或在 AI 抽屉打开时立即执行一次状态检查。

### 9.3 L2 管理与可观测性还比较轻

当前可观测能力：

- SSE debug log 中有 `[PROFILE-CACHE]` 日志。
- 前端可看到简单 ready/building/missing 状态。
- 后端有 cache-status 接口。

仍缺：

- 缓存命中率统计。
- L2 表大小监控。
- cache key 维度的管理页。
- 单客户手动刷新/清理入口。

### 9.4 stale 使用要被正确解释

`l2_stale` 是“可用于 AI 对话”的 support snapshot，不是最新档案。

后续任何报告或 UI 都应避免把 stale 表述为：

- 最新档案。
- 已同步业务表。
- official 用户画像。

---

## 10. 当前文件地图

后端核心：

| 文件 | 作用 |
| --- | --- |
| `app/crm_profile/models.py` | 定义 `CrmAiProfileCache` L2 快照表 |
| `app/schema_migrations.py` | 启动期确保 L2 表索引和相关 schema |
| `app/crm_profile/services/cache.py` | L1 进程内缓存和统一 key helper |
| `app/crm_profile/services/profile_context_cache.py` | L1/L2 读写、AI cache-only、preload、status、cleanup |
| `app/crm_profile/services/ai_context_preload.py` | `/ai/preload` service 包装 |
| `app/crm_profile/services/ai_coach.py` | AI prepare 只读 L1/L2，miss 触发 `ProfileCacheNotReady` |
| `app/crm_profile/router.py` | `/profile`、`/ai/preload`、`/ai/cache-status`、AI stream 路由 |
| `app/crm_profile/schemas/api.py` | AI preload/cache-status/chat request schema |
| `app/main.py` | 应用启动后开启 L2 过期清理循环 |

前端核心：

| 文件 | 作用 |
| --- | --- |
| `frontend/src/views/CrmProfile/composables/useCrmProfile.ts` | 档案加载、窗口切换、preload、cache-status 状态保存 |
| `frontend/src/views/CrmProfile/composables/useAiCoach.ts` | AI 请求携带 `health_window_days` |
| `frontend/src/views/CrmProfile/components/AiCoachPanel.vue` | AI 输入区缓存状态提示和发送门禁 |
| `frontend/src/views/CrmProfile/components/styles/aiCoachPanel.css` | 缓存状态提示样式 |
| `frontend/src/views/CrmProfile/index.vue` | 将 `profileCacheStatus/currentWindowDays` 传给 AI 面板 |

文档与沉淀：

| 文件 | 作用 |
| --- | --- |
| `docs/CRM_AI用户Profile缓存机制调研与优化报告.md` | 调研与优化过程报告 |
| `docs/CRM_AI_Profile缓存机制当前实现报告.md` | 当前实现交接报告 |
| `bug.md` | Bug #58 / #59 |
| `memory.md` | 经验 #116 / #117 / #118 |
| `progress.md` | 迭代进度 |
| `task_plan.md` | 当前任务锚点 |

---

## 11. 接下来最值得做的事

优先级建议：

1. **P0: 继续实测真实用户路径**
   - 打开客户档案。
   - 等 preload 返回。
   - 发起 AI 对话。
   - 确认日志中不再出现 profile cache miss 后同步查 CRM DB。

2. **P0: 补充缓存命中日志结构化字段**
   - customer_id
   - health_window_days
   - cache_key
   - source
   - status
   - build_duration_ms

3. **P1: AI 抽屉打开时主动 status check**
   - 当前已在 profile 加载和窗口切换后 preload。
   - 可以再在 AI 抽屉打开时补一次 `cache-status`，增强直接入口场景。

4. **P1: 增加 L2 管理或调试接口**
   - 单客户刷新缓存。
   - 单客户清理缓存。
   - 查看 L2 快照数量和过期分布。

5. **P2: 多 worker / 多机压测后再评估 Redis**
   - 当前不需要先引 Redis。
   - 只有当重复构建或锁竞争成为真实问题时，再升级。

---

## 12. 结论

当前机制已经满足本阶段核心诉求：

```text
不引 Redis。
使用本地数据库做 L2 profile cache snapshot。
用户进入档案页后自动准备 AI 所需上下文。
AI 对话阶段只读缓存，不把 DB 聚合查询放到首问等待链路。
前端能感知缓存状态，并在未就绪时短暂门禁。
```

这套实现的关键不是“缓存表存在”，而是链路边界已经调整：

- 档案页可以构建。
- 预热可以后台跑。
- 状态接口只能读。
- AI 对话只能读缓存。
- L2 快照只是 support cache，不是 official 用户档案 truth。

因此，在当前单机或少量 worker 阶段，这套方案已经可以作为 CRM AI Profile 缓存的 official 当前实现继续推进。
