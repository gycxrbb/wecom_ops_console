# 侧边栏接口预热与缓存刷新机制建设计划

- **日期**: 2026-05-01
- **状态**: candidate plan
- **面向阶段**: 体验优化 / 性能治理 / 数据一致性收口
- **适用范围**: 前端侧边栏入口首次访问加速、DB 查询接口预热、缓存命中与失效刷新

## 1. 背景与目标

当前系统已经有登录后静默预取机制：`fetchUser()` 成功后调用 `prefetchSidebarData()`，并发请求一批侧边栏常用接口，再写入前端内存缓存。用户首次进入部分页面时，如果页面请求 URL 与预热 key 完全一致，就可以直接消费缓存，减少等待。

但这套机制目前还不是完整的“真且有效”的体验优化：

1. 它是一次性接口缓存，不是页面组件 `KeepAlive`。
2. 缓存 key 只按 URL 字符串，不完整覆盖 method、params、用户身份、权限上下文。
3. 变更请求后的缓存刷新机制不系统，容易出现旧列表、假命中或重复 DB 查询。
4. 预热清单不是从侧边栏路由能力统一声明出来的，覆盖面和页面真实请求之间存在漂移。
5. 缺少命中率、预热耗时、DB 压力等可观测指标。

本计划目标是把当前 support 级预热优化升级为一套可验证、可维护、不会污染业务真值的正式能力。

## 2. 当前真值

### 2.1 已存在能力

- 鉴权入口：`frontend/src/router/index.ts` 中路由守卫触发 `userStore.fetchUser()`。
- 预热入口：`frontend/src/stores/user.ts` 中 `fetchUser()` 调用 `prefetchSidebarData()`。
- 缓存容器：`frontend/src/utils/preloadCache.ts` 使用内存 `Map` 保存预热响应。
- 消费入口：`frontend/src/utils/request.ts` 在请求拦截器中消费预加载缓存。
- 已修复门禁：预加载缓存只允许 `GET` 消费，变更请求必须真实访问后端。

### 2.2 当前预热清单

```text
/v1/dashboard/summary
/v1/groups
/v1/templates
/v1/schedules
/v1/assets/folders/all
/v1/speech-templates/scenes
/v1/speech-templates
/v1/crm-customers/list?page=1&page_size=20&include_filters=1
/v1/crm-customers/filters
/v1/external-docs/home/summary
/v1/external-docs/bindings/flat
/v1/external-docs/terms?dimension=stage
/v1/system-docs/entries?mode=published
/v1/rag/tags
```

### 2.3 已知缺口

- `crm-customers/list` 页面实际请求使用 axios `params`，预热清单使用 query string，可能命不中。
- 飞书文档的 `terms` 页面请求是 `/v1/external-docs/terms` + params，但预热清单是 query string，可能命不中。
- 素材库页面实际使用 `/v1/asset-folders` 和 `/v1/assets`，当前预热了 `/v1/assets/folders/all`，不一定命中页面首屏。
- 系统教学页面首屏请求 `/v1/system-docs/tree`，当前预热 `/v1/system-docs/entries?mode=published`，不等价。
- 发送记录、审批中心、用户管理、权限管理、提示词管理、反馈审核等侧边栏入口尚未纳入统一预热清单。
- `<router-view>` 未使用 Vue `<KeepAlive>`，路由切换后页面组件会重新挂载。

## 3. 设计原则

1. **缓存只能加速读取，不能替代 truth**  
   DB 和后端接口返回仍是 official truth；前端预热缓存只是 support layer。

2. **method + URL + params + user scope 共同组成缓存 key**  
   不允许只按裸 URL 判断命中。

3. **变更请求必须触发资源级失效**  
   创建、更新、删除、审批、切换启用状态后，要清理相关列表缓存。

4. **预热必须有预算和优先级**  
   不能登录后无节制压 DB。预热要分 P0/P1/P2，并支持并发上限。

5. **命中与刷新必须可观测**  
   没有命中率和耗时统计，就不能确认体验是否真的变好。

6. **页面保活和接口缓存分层处理**  
   `KeepAlive` 解决“切回来不重建页面”，预热缓存解决“第一次打开不等 DB”。两者不能混为一谈。

## 4. 目标架构

```text
登录/恢复会话
  |
  v
bootstrap + profile
  |
  v
Preload Manifest 生成当前用户可访问入口
  |
  v
Preload Scheduler
  - P0 立即预热
  - P1 空闲预热
  - P2 进入页面前/hover 预热
  - 并发上限
  - 超时与失败静默降级
  |
  v
Preload Cache Store
  - normalized key
  - ttl
  - stale flag
  - resource tags
  - user scope
  |
  v
request.get 消费缓存
  |
  v
mutation 请求后 invalidate tags
```

## 5. 核心实现方案

### 5.1 统一缓存 key

新增 `buildRequestCacheKey(config)`：

```ts
type CacheKeyParts = {
  method: 'get'
  path: string
  params: Record<string, unknown>
  userId: number | string
  permissionHash: string
}
```

规则：

- method 固定小写。
- path 去除 host/baseURL，只保留 API path。
- query string 与 axios `params` 合并后排序。
- 空值、undefined、默认分页参数按统一规则规范化。
- 当前用户 ID 与权限摘要进入 key，避免 A 用户缓存被 B 用户消费。

### 5.2 缓存记录结构

```ts
type PreloadCacheEntry = {
  key: string
  method: 'get'
  path: string
  params: Record<string, unknown>
  resourceTags: string[]
  data: unknown
  createdAt: number
  expiresAt: number
  stale: boolean
  source: 'login_preload' | 'route_prefetch' | 'manual_refresh'
}
```

默认 TTL 建议：

- 看板摘要：30 秒
- 列表类资源：60 秒
- 字典/分类/权限类资源：5 分钟
- RAG tags、话术场景等低频变更字典：10 分钟

注意：TTL 到期不代表数据错误，只代表不能再作为首屏 official 展示依据；页面可先展示 stale 数据，但必须后台刷新并给出轻量 loading 状态。

### 5.3 资源标签与失效规则

每个缓存条目绑定资源标签：

```ts
{
  '/v1/schedules': ['schedules'],
  '/v1/groups': ['groups'],
  '/v1/templates': ['templates'],
  '/v1/assets': ['assets'],
  '/v1/asset-folders': ['assets', 'asset-folders'],
  '/v1/external-docs/bindings/flat': ['external-docs', 'external-doc-bindings'],
}
```

变更请求后按 method + path 触发失效：

```text
POST /v1/schedules                  -> invalidate schedules, dashboard
POST /v1/schedules/{id}/toggle      -> invalidate schedules, dashboard
DELETE /v1/schedules/{id}           -> invalidate schedules, dashboard

POST /v1/groups                     -> invalidate groups, send-center
PUT /v1/groups/{id}                 -> invalidate groups, send-center

POST /v1/templates                  -> invalidate templates, send-center
PUT /v1/templates/{id}              -> invalidate templates, send-center

POST /v1/asset-folders              -> invalidate assets, asset-folders
POST /v1/assets                     -> invalidate assets, asset-folders

POST /v1/external-docs/*            -> invalidate external-docs
PUT /v1/external-docs/*             -> invalidate external-docs
DELETE /v1/external-docs/*          -> invalidate external-docs
```

第一期可以前端维护失效表；第二期若需要更稳，可以后端响应头返回：

```text
X-Invalidate-Tags: schedules,dashboard
```

### 5.4 预热清单 Manifest

新增 `frontend/src/utils/preloadManifest.ts`，不再在 `user.ts` 里硬编码 URL。

每个条目包含：

```ts
type PreloadTask = {
  id: string
  route: string
  permission?: PermissionKey
  priority: 'P0' | 'P1' | 'P2'
  request: {
    method: 'get'
    url: string
    params?: Record<string, unknown>
  }
  resourceTags: string[]
  ttlMs: number
}
```

建议首期 P0：

- `/dashboard`: `/v1/dashboard/summary`
- `/send`: `/v1/groups`, `/v1/templates`
- `/groups`: `/v1/groups`
- `/templates`: `/v1/templates`
- `/schedules`: `/v1/schedules`

建议首期 P1：

- `/assets`: `/v1/asset-folders`, `/v1/assets?page=1&page_size=...`
- `/crm-profile`: `/v1/crm-customers/list` + params, `/v1/crm-customers/filters`
- `/speech-templates`: `/v1/speech-templates/scenes`, `/v1/speech-templates`
- `/sop-docs`: `/v1/external-docs/home/summary`, `/v1/external-docs/bindings/flat`, `/v1/external-docs/terms`
- `/system-teaching`: `/v1/system-docs/tree`

建议首期 P2：

- `/logs`
- `/approvals`
- `/users`
- `/permissions`
- `/prompt-manage`
- `/feedback-review`

P2 不建议登录后立即全量压 DB，可以在以下时机触发：

- 用户 hover / focus 侧边栏菜单项超过 150ms。
- 主线程空闲 `requestIdleCallback`。
- 用户进入相邻模块后预取相关模块。

### 5.5 预热调度器

新增 `preloadScheduler.ts`：

- 并发上限：2-3。
- 单请求超时：3-5 秒，超时静默失败。
- P0 登录后立即执行。
- P1 延迟 300-800ms 或浏览器空闲后执行。
- P2 只做按需/hover/idle。
- 同 key 正在请求时复用 promise，避免重复请求。
- 页面真实请求到来时：
  - 若预热已完成：直接返回缓存。
  - 若预热正在进行：等待同一个 promise，避免双打 DB。
  - 若未预热或已过期：正常请求。

### 5.6 页面级 KeepAlive

接口预热解决首次点击等待；页面 keep-alive 解决二次切换体验。

建议第一期只对低风险页面启用：

```vue
<router-view v-slot="{ Component, route }">
  <KeepAlive :include="keepAliveIncludes" :max="8">
    <component :is="Component" :key="route.name" />
  </KeepAlive>
</router-view>
```

首批建议：

- Dashboard
- Groups
- Templates
- Schedules
- Assets
- SpeechTemplates
- SopDocsHome

不建议第一期 keep-alive：

- SendCenter：有草稿、队列、编辑器状态，需先定义恢复语义。
- CrmProfile：客户详情和 AI 面板状态复杂，需要单独做缓存/恢复边界。
- PromptManage：后台编辑态复杂，需避免脏状态常驻。

### 5.7 页面刷新语义

每个页面需要明确三种入口：

1. **首次进入**：允许读 fresh preload cache。
2. **切回页面**：若组件 keep-alive，优先保留本地状态；后台按 TTL 判断是否刷新。
3. **用户点击刷新按钮**：强制绕过前端缓存，真实请求后更新缓存。

强制刷新参数不能进入默认导航恢复路径，避免反复绕过缓存。

## 6. 分阶段实施计划

### Phase 0：现状审计与真值对齐

- 枚举侧边栏所有 route。
- 为每个 route 记录首屏真实请求。
- 标出 DB 重查询接口、轻量字典接口、外部依赖接口。
- 输出 `docs/SIDEBAR_PRELOAD_ENDPOINT_AUDIT.md`。

验收：

- 每个侧边栏入口都有“是否预热 / 预热哪些接口 / 为什么不预热”的结论。

### Phase 1：缓存 key 与失效机制

- 实现统一 key builder。
- 缓存 entry 增加 TTL、tags、source、user scope。
- mutation 后按 tag 失效。
- 修复 axios params 与 query string 不一致导致的命中漂移。

验收：

- `GET /v1/crm-customers/list` 用 query string 和 axios params 都能归一到同一 key。
- `POST /v1/schedules` 后，`schedules` tag 缓存被清理。
- 变更请求不会读取预加载缓存。

### Phase 2：Preload Manifest 与调度器

- 从 `user.ts` 中移出硬编码 endpoints。
- 建立 manifest，按权限过滤。
- 实现 P0/P1/P2 调度。
- 实现 in-flight promise 复用。

验收：

- 登录后 P0 接口并发预热。
- 首次进入看板、发送中心、定时任务时命中缓存。
- 预热失败不影响登录和页面访问。

### Phase 3：资源级刷新与页面刷新按钮联动

- 页面刷新按钮走 force refresh。
- 变更操作后清理相关缓存并可选后台 revalidate。
- 列表页保存/删除/审批/切换状态后统一触发 invalidate。

验收：

- 创建定时任务后进入定时任务列表一定能看到新任务。
- 修改模板后发送中心模板列表不会读旧缓存。
- 上传素材后素材库文件夹计数和素材列表能刷新。

### Phase 4：页面 KeepAlive 小步启用

- 在 layout 层引入可配置 `KeepAlive`。
- 只对低风险页面启用。
- 页面增加 `onActivated` 轻量刷新判断。
- 明确哪些页面不保活及原因。

验收：

- Dashboard/Groups/Templates/Schedules 在侧边栏切换回来时不重新白屏。
- 页面保活不导致旧数据长期不刷新。
- 编辑类页面没有脏状态误保留。

### Phase 5：观测与门禁

- 记录 preload start/end/error。
- 记录 cache hit/miss/stale/revalidate。
- 开发环境输出调试面板或 console group。
- 后端可选增加慢查询日志关联 request id。

验收：

- 可以回答：登录后预热了哪些接口、耗时多少、命中了多少、失败了哪些。
- 可以证明某个页面首次打开是否真的少等 DB。

## 7. Focused Validation

### 前端单元/轻量验证

- key builder：
  - query string 与 params 顺序不同，key 一致。
  - userId 不同，key 不一致。
  - permissionHash 不同，key 不一致。
- cache store：
  - fresh 命中后是否消费或保留，按设计验证。
  - TTL 到期进入 stale。
  - invalidate tag 能清理多条缓存。
- request 拦截器：
  - GET 可命中。
  - POST 永不命中。
  - mutation 后会 invalidate。

### 页面验证

- 登录后直接点“定时任务”：首屏列表来自预热缓存，随后可后台刷新。
- 登录后直接点“发送中心”：群组和模板不等待 DB。
- 登录后直接点“客户档案”：列表和筛选项命中同一规范 key。
- 创建/删除/编辑后回到列表，不能出现旧数据。

### 启动验证

- 后端：`uvicorn app.main:app --host 0.0.0.0 --port 8000` 短启动通过。
- 前端：`npm run build` 通过。
- 前端 dev：`npm run dev` 可访问。

## 8. 风险与对策

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| 登录后预热过多接口压 DB | 初次进入反而变慢 | P0/P1/P2 分级，并发上限，idle/hover 触发 |
| 缓存 key 漂移 | 预热无效 | 统一 key builder，禁止手写 query key |
| 变更后读旧缓存 | 数据不一致 | mutation tag invalidate，关键页面强制 revalidate |
| KeepAlive 保存脏编辑态 | 用户误操作 | 编辑型页面暂不保活，先定义 dirty guard |
| 权限切换后缓存串用 | 数据泄露/错显 | user scope + permission hash 入 key，权限变更清空缓存 |
| 预热失败被误认为页面失败 | 体验误导 | 预热错误静默记录，页面真实请求兜底 |

## 9. 面向项目负责人的状态表达

### 已经能做什么

- 系统已有登录后静默预热的基础能力。
- 部分高频入口可以通过预热缓存减少首次点击等待。
- 变更请求不会再被 GET 预热缓存假成功污染。

### 半能做什么

- 能预热一批接口，但覆盖面和页面真实请求还没有完全对齐。
- 能缓存接口响应，但刷新失效还不是统一资源级机制。
- 能减少首次等待，但还不是页面组件 keep-alive。

### 还不能做什么

- 不能保证所有侧边栏入口首次点击都秒开。
- 不能保证所有变更后列表缓存自动刷新。
- 不能量化证明命中率和 DB 减压效果。

### 当前 blocker

- 缺少侧边栏 route 到首屏接口的 official manifest。
- 缺少统一 key builder 和 tag invalidate。
- 缺少预热观测指标。

### 下一步最值得做什么

先做 Phase 0 + Phase 1：把“哪些接口该预热、怎么命中、什么时候失效”变成正式真值。没有这层，直接扩大预热范围会增加 DB 压力，也容易制造旧数据问题。

## 10. 推荐执行边界

第一轮开发建议只开 3 条线程：

1. **缓存基础线程**：key builder、cache entry、tag invalidate。
2. **预热清单线程**：侧边栏 manifest、权限过滤、P0/P1/P2 分类。
3. **页面验证线程**：定时任务、发送中心、客户档案三个高价值路径的 focused validation。

收口时由主总控统一检查：

- 预热命中是否真实发生。
- 变更后缓存是否被清理。
- 页面是否仍能正常启动。
- 文档真值是否与代码一致。
