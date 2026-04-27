# CRM AI 用户 Profile 缓存机制调研与优化报告

> 日期: 2026-04-27  
> 范围: CRM 用户档案页、AI 对话 prepare、profile 预热、SSE 双流、本地应用数据库 L2 快照  
> 当前诉求: 先不引入 Redis，使用本地数据库临时承接 L2 profile cache，确保 AI 对话不让用户等待 CRM 业务表聚合查询。

---

## 1. 当前结论

本轮代码已经从“只靠进程内 dict”推进到 **L1 进程内缓存 + L2 本地应用数据库快照**。

当前 official 口径如下：

1. **CRM 业务表仍是 official truth**，例如 `customers / customer_health / customer_glucose / customer_info`。
2. **`crm_ai_profile_cache` 是 support cache snapshot**，用于加速 AI prepare，不替代 CRM 业务表真值。
3. **Redis 暂不作为当前依赖**，只保留为未来多机部署或更强分布式锁的候选方向。
4. **AI 对话 prepare 阶段不再同步构建 CRM profile**。如果 L1/L2 都 miss，只触发后台 preload，并快速返回“客户档案缓存正在准备，请稍后再试”。
5. **用户进入档案页后会静默检查/预热当前窗口 profile cache**。健康窗口切换后也会静默预热对应 7/14/30 天快照。

这已经解决了最关键问题：正常从用户档案页进入 AI 对话时，AI 首问应命中已经构建好的 L2 快照，不再把用户卡在 CRM DB 聚合查询上。

---

## 2. 已落地的缓存架构

### 2.1 L1: 进程内短缓存

文件: `app/crm_profile/services/cache.py`

作用：

1. 降低同一 worker 内频繁读取本地 DB L2 的开销。
2. key 统一为 `profile:{customer_id}:hw{window_days}`。
3. 仍然只是进程内缓存，不作为跨 worker truth。

### 2.2 L2: 本地应用数据库快照

文件:

1. `app/crm_profile/models.py`
2. `app/crm_profile/services/profile_context_cache.py`
3. `app/schema_migrations.py`

新增/使用表:

```text
crm_ai_profile_cache
```

核心字段:

1. `cache_key`: `profile:{customer_id}:hw{window_days}`，唯一。
2. `crm_customer_id`: CRM 客户 ID。
3. `health_window_days`: 7/14/30。
4. `context_json`: 序列化后的 `CustomerProfileContextV1`。
5. `generated_at`: profile context 生成时间。
6. `expires_at`: fresh 过期时间。
7. `stale_expires_at`: stale 可接受过期时间。
8. `last_hit_at`: 最近命中时间。

TTL 当前配置:

```python
crm_profile_cache_fresh_ttl_seconds = 1800
crm_profile_cache_stale_ttl_seconds = 86400
```

含义：

1. fresh 30 分钟。
2. stale 24 小时。
3. AI 对话可使用 fresh 或 stale 快照。
4. 完全 miss 时不在 AI 线程查 CRM DB，只后台构建。

---

## 3. 当前代码链路

### 3.1 用户档案页

入口:

```text
GET /api/v1/crm-customers/{customer_id}/profile?window=7|14|30
```

文件: `app/crm_profile/router.py`

当前行为:

1. 调用 `ensure_profile_context(customer_id, window_days=w, allow_stale=True)`。
2. 如果 L1/L2 命中，直接返回缓存快照。
3. 如果 miss，用户档案页允许同步构建 profile，因为用户正在打开档案页。
4. 构建完成后写入 L1 和本地 DB L2。

这是合理的：查询成本前移到用户已经在看档案页的阶段，而不是拖到 AI 对话首问。

### 3.2 用户档案页静默预热

文件: `frontend/src/views/CrmProfile/composables/useCrmProfile.ts`

当前行为:

1. `loadProfile()` 成功后静默调用 `/ai/preload`。
2. `switchHealthWindow()` 成功后也静默调用 `/ai/preload`。
3. 这个动作不阻塞页面，不把缓存状态暴露成用户必须理解的 UI。

请求:

```ts
POST /api/v1/crm-customers/{customer_id}/ai/preload
{
  "health_window_days": 7 | 14 | 30
}
```

### 3.3 AI 对话

入口:

```text
POST /api/v1/crm-customers/{customer_id}/ai/chat-stream
POST /api/v1/crm-customers/{customer_id}/ai/thinking-stream
```

文件:

1. `app/crm_profile/router.py`
2. `app/crm_profile/services/ai_coach.py`

当前行为:

1. 前端会把 `health_window_days` 随 chat/thinking 请求传入。
2. answer-stream 和 thinking-stream 都进入统一 cached prepare 路径。
3. prepare 阶段调用 `get_ai_ready_profile_context()`。
4. `get_ai_ready_profile_context()` 只读 L1/L2。
5. 如果 L1/L2 都 miss，调用 `schedule_profile_preload()` 后快速返回错误事件，不同步执行 `load_profile()`。

这意味着 AI 对话线程不再直接承担 CRM profile 聚合查询。

### 3.4 AI 视角预览

入口:

```text
GET /api/v1/crm-customers/{customer_id}/ai/context-preview
```

当前行为:

1. 后端通过统一缓存服务读取 profile context。
2. 前端会携带当前 `health_window_days`。
3. 预览内容和当前页面窗口保持一致。

### 3.5 Cache Status 状态检查

入口:

```text
GET /api/v1/crm-customers/{customer_id}/ai/cache-status?health_window_days=7|14|30
```

当前行为:

1. 只读取 L1/L2 状态，不触发 CRM profile 构建。
2. 返回 `ready / status / source / cache_key / generated_at / expires_at / stale_expires_at`。
3. 如果同进程 preload 正在执行，返回 `building`。
4. 前端用它更新 AI 输入区门禁状态，而不是让用户点击发送后才发现缓存未就绪。

### 3.6 L2 过期快照清理

文件:

1. `app/crm_profile/services/profile_context_cache.py`
2. `app/main.py`

当前行为:

1. `cleanup_expired_profile_cache()` 删除 `stale_expires_at` 已过期的 L2 快照。
2. 应用启动后会开启后台循环，每 6 小时清理一次。
3. 清理对象仍然只是 support cache，不影响 CRM official 用户档案 truth。

---

## 4. 本轮修复了哪些半成品问题

### 问题 1: 后端路由传了 health_window_days，但 service 没接住

修复前：

1. `AiChatRequest` 已有 `health_window_days`。
2. `router.py` 已向 `ask_ai_coach / stream_ai_coach_answer / stream_ai_coach_thinking` 传参。
3. 但 `ai_coach.py` 三个函数签名没有这个参数，运行时会出现 unexpected keyword argument。

修复后：

1. 三个入口都接收 `health_window_days`。
2. prepare cache key 也纳入 `health_window_days`。
3. 7/14/30 天窗口不会再混用同一个 AI prepare。

### 问题 2: DeepSeek thinking-stream 绕过新缓存服务

修复前：

DeepSeek thinking 轻量路径还在引用旧的：

```text
profile_cache_key
cache_get
cache_get_stale
load_profile
get_connection
return_connection
```

这些符号在当前文件中已经没有导入，且这条路径会绕过本地 DB L2。

修复后：

1. thinking-stream 收回统一 cached prepare。
2. answer/thinking 共用 L1/L2 profile 快照。
3. 去掉重复 DB fallback。

### 问题 3: AI 对话还可能 true miss 后同步查 CRM DB

修复前：

AI prepare miss 时会执行 `load_profile()`，用户需要等待 CRM DB 聚合。

修复后：

AI prepare 只读缓存：

```text
L1 hit -> 直接回答
L2 fresh hit -> 直接回答
L2 stale hit -> 直接回答
L1/L2 miss -> 后台 preload + 快速提示缓存准备中
```

### 问题 4: 前端 AI 请求没有携带当前窗口

修复前：

用户切到 14/30 天健康窗口后，页面和 AI 可能不是同一份上下文。

修复后：

1. `AiCoachPanel` 接收 `healthWindowDays`。
2. `sendChat()` 请求体写入 `health_window_days`。
3. `context-preview` 也携带 `health_window_days`。

### 问题 5: 缓存状态不可见，用户可能点进未就绪 AI

修复前：

1. preload 是静默动作，前端不保存结果。
2. 缓存是否 ready 只能看日志。
3. 用户可能在后台构建尚未完成时直接发送问题。

修复后：

1. 新增 `GET /ai/cache-status`。
2. `useCrmProfile()` 保存 `profileCacheStatus`。
3. AI 输入区在 `checking / scheduled / already_running / building / missing` 状态下短暂禁用发送。
4. ready 或 stale ready 时允许发送。

### 问题 6: L2 快照缺少过期治理

修复前：

`crm_ai_profile_cache` 有 stale TTL 字段，但没有清理逻辑，长时间运行后会积累过期 support snapshot。

修复后：

1. 新增 `cleanup_expired_profile_cache()`。
2. 应用生命周期中启动后台定时清理循环。
3. 只删除 stale 已过期的缓存行。

---

## 5. 当前还能做什么、半能做什么、还不能做什么

### 已经能做什么

1. 用户打开档案页时，系统会构建或读取 profile context，并写入本地 DB L2。
2. 用户在档案页内打开 AI 对话时，AI prepare 优先读取 L1/L2 快照。
3. 7/14/30 天健康窗口可以贯穿 profile、preload、AI 对话和 context-preview。
4. answer-stream 和 thinking-stream 不再各自用不同 profile 读取逻辑。
5. AI true miss 不再同步查 CRM DB，而是触发后台构建并快速提示。

### 半能做什么

1. 本地 DB L2 能解决同机多 worker 共享快照问题，但 single-flight 仍主要是进程内锁。
2. 如果两个 worker 同时发现完全 miss，可能各自调度一次 preload；但用户不会被同步 DB 查询卡住。
3. `stale` 快照可保障 AI 快速回答，但过期期间可能不是最新 CRM 数据，需要靠后台刷新逐步补强。

### 还不能做什么

1. 还没有跨 worker 的严格分布式构建锁。
2. 还没有针对 `crm_ai_profile_cache` 的管理页。
4. 还没有用真实生产多 worker 流量压测命中率。

---

## 6. 面向项目负责人的状态说明

按业务链路看：

### 看见

用户档案页已经能加载客户基础信息、安全档案、健康摘要、积分活跃、服务关系等模块。

### 理解

系统会把这些模块组装成 `CustomerProfileContextV1`，并把它保存成可复用的本地 DB 快照。

### 决策

AI 对话现在不再把“读取并聚合 CRM 用户档案”放到首问线程里做，而是优先读取已准备好的快照。这样用户发问时等待的主要应是 AI 模型响应，而不是 CRM DB 查询。

### 闭环

用户进入档案页和切换健康窗口后，系统都会静默检查/预热当前窗口的 profile cache。缓存缺失时，AI 会提示正在准备，而不是让用户挂在 DB 查询上。

---

## 7. 当前 blocker 与风险

### 当前 blocker

1. 如果用户绕过档案页直接打 AI 接口，第一次可能收到“客户档案缓存正在准备”。
2. 本地 DB L2 已经解决共享快照，但没有解决严格跨 worker single-flight。

### 风险

1. L2 是 support cache，不能当成 official 用户档案真值。
2. stale 24 小时是体验兜底，不代表用户数据 24 小时都不需要刷新。
3. `AiCoachPanel.vue` 仍然超过 Vue 文件 600 行红线，后续应拆分；本轮只做缓存收口，没有继续扩大重构范围。

---

## 8. 验证记录

本轮 focused validation:

```text
python -m py_compile app\crm_profile\services\profile_context_cache.py app\crm_profile\services\ai_context_preload.py app\crm_profile\services\ai_coach.py app\crm_profile\router.py app\crm_profile\schemas\api.py
cd frontend; .\node_modules\.bin\vue-tsc.cmd --noEmit
cd frontend; npm.cmd run build
```

结果：

1. 后端 Python 编译通过。
2. 前端 TypeScript 校验通过。
3. 前端生产构建通过。

项目启动验证:

1. 后端 `python -m uvicorn app.main:app --host 0.0.0.0 --port 8008 --log-level info` 已启动到 `Application startup complete`，随后已回收测试进程。
2. 前端沙箱内启动仍触发既有 `esbuild spawn EPERM`；提权后 `npm.cmd run dev -- --host 0.0.0.0 --port 5178` 已启动到 Vite ready，并显示 `http://localhost:5178/`，随后已回收监听进程。

---

## 9. 下一步建议

### P0

1. 给 profile cache 日志补 `worker_pid / cache_key / source / health_window_days`，便于确认多 worker 下命中情况。
2. 用一次真实多 worker 流量验证连续 profile -> AI 首问的 L2 命中率。
3. 针对 AI 直达入口，继续优化“缓存准备中”的前端重试体验。

### P1

1. 用本地 DB 行级状态或短 TTL lock 补跨 worker 构建锁。
2. 前端 AI 按钮可以在 building 状态下显示“客户档案准备中”，避免用户误以为 AI 坏了。
3. 拆分 `AiCoachPanel.vue`，把 context tab、notes tab、history tab、send actions 分离出去。

### P2

1. 如果未来部署升级到多机或需要更高吞吐，再引入 Redis 作为 L2 或分布式锁。
2. 做多 worker 压测：连续打开 profile + AI 首问，统计 L1/L2/miss/source 分布。
