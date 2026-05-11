# AI 对话功能迁移方案（企微 → CRM 前端）

> 状态：candidate，可作为前端迁移开发蓝图使用。  
> 更新日期：2026-05-11  
> 核心目标：把企微侧已验证的 AI 对话能力接入 CRM 前端，优先打通链路，同时保证本次新增代码高内聚、低耦合，不继续加重 CRM 现有页面的大文件问题。

---

## 1. 当前结论

可以开始开发，但必须按“隔离接入”方式推进：

1. CRM 前端新增独立 AI 通道，不改造现有 `/api` 请求链路。
2. AI 对话代码放在客户详情页局部模块下，不把复杂逻辑继续写进 `src/view/customer/profile/index.vue`。
3. 企微后端新增 CRM token 兼容校验，先以跑通为主；但文档中明确该兼容层不是 CRM 后端 official 鉴权实现。
4. 发送中心、RAG 管理、企微运营台专属能力先隐藏或降级，不作为本轮 official CRM 功能。
5. 本轮完成标准不是“组件能打开”，而是：CRM 登录态下能访问企微 AI 接口、SSE 能返回、页面不影响 CRM 原有客户详情功能。

---

## 2. 真实认证机制

### 2.1 CRM 后端 token 真值

CRM 后端 token 机制如下：

```text
POST /sys/userLogin
→ 签发 access token（3h）和 refreshToken（30d）
→ refreshToken 写入 Cookie
→ access token 写入 Redis
   key = mfg-crm:sys:token:{userId}
→ 响应体返回 { userId, token }
```

每次请求校验流程：

```text
1. 从 Authorization header 取 access token
2. JWT verify，解出 payload：{ id }
3. 从 Redis 读取 mfg-crm:sys:token:{id}
4. 与 header 中的 access token 比对
5. 如果 access token 失效，尝试用 Cookie refreshToken 换新 token
```

JWT 签名密钥来自 CRM 后端环境变量：

```text
APP_PUBLIC_KEY=123456
```

代码口径：

```text
config.app.publicKey = process.env.APP_PUBLIC_KEY || ''
jwt.sign({ id: user.id }, config.app.publicKey, { expiresIn: '3h' })
```

### 2.2 CRM 前端 token 真值

CRM 前端当前通过 Pinia 持有 token：

```text
src/pinia/modules/user.js
token = localStorage.getItem('token') || ''
```

现有请求封装会自动带上：

```text
Authorization: Bearer <userStore.token>
```

因此 AI 模块前端也应使用同一份 CRM token，而不是企微前端原来的 `access_token`。

### 2.3 企微后端兼容策略

企微后端原本只识别自己的 JWT：

```text
payload.sub → wecom users.id
```

迁移后需要新增一条 CRM token fallback：

```text
Authorization: Bearer <CRM access token>
→ 用 CRM APP_PUBLIC_KEY verify
→ 读取 payload.id 作为 crm_admin_id
→ 尝试映射到企微本地 users.crm_admin_id
→ 得到企微后端当前 user
```

为了优先跑通，本轮可以先实现最小兼容：

```text
1. 校验 CRM JWT 签名和 exp
2. 读取 payload.id
3. 按 crm_admin_id 查找或创建企微本地 user
4. 后续接口沿用企微后端现有 get_current_user 返回值
```

如果企微后端能访问 CRM Redis，建议同步做 Redis token 比对；如果当前环境暂时不具备 Redis 访问条件，可先作为 known gap 标记，不得写成 official 安全闭环。

推荐环境变量命名：

```env
CRM_JWT_SECRET_KEY=123456
CRM_TOKEN_REDIS_URL=redis://127.0.0.1:6379/0
CRM_TOKEN_REDIS_KEY_PREFIX=mfg-crm:sys:token:
CRM_TOKEN_STRICT_REDIS_CHECK=false
```

说明：

- `CRM_JWT_SECRET_KEY` 对应 CRM 后端 `APP_PUBLIC_KEY`。
- `CRM_TOKEN_STRICT_REDIS_CHECK=false` 表示开发期先跑通，不阻塞联调。
- 生产环境应改为 `true`，否则 access token 被 CRM 后端登出/刷新后，企微后端仍可能短时间接受旧 token。

---

## 3. 总体架构

```text
CRM 前端 mfg-crm-admin
├─ 原有 CRM 功能
│  └─ /api → CRM 后端 :3007
└─ 新增 AI 对话模块
   └─ /wecom-ai → 企微后端 :8000/api

企微后端
├─ 原有 AI 对话接口
├─ 原有 crm_admin_id 权限与客户可见范围逻辑
└─ 新增 CRM token fallback
```

关键边界：

- CRM 原有业务仍走 `/api`。
- AI 对话所有普通请求和 SSE 请求都走 `/wecom-ai`。
- AI 模块不复用 CRM 全局 `src/utils/request.js`，避免 loading、错误弹窗、响应结构相互污染。
- AI 模块不修改 CRM 原有客户详情功能的数据流。

---

## 4. 前端目录设计

CRM 当前客户详情页 `src/view/customer/profile/index.vue` 已经很大，本轮不能继续把 AI 逻辑写进去。

新增目录建议：

```text
src/view/customer/profile/aiCoach/
├── index.vue                         # AI 对话入口容器，可 re-export AiCoachPanel
├── components/
│   ├── AiCoachPanel.vue
│   ├── AiCoachMessageList.vue
│   ├── AiCoachAssistantMessage.vue
│   ├── AiCoachUserMessage.vue
│   ├── AiCoachThinkingPanel.vue
│   ├── AiCoachFeedbackDialog.vue
│   ├── AiCoachReferenceMessage.vue
│   └── AiSessionHistoryList.vue
├── composables/
│   ├── aiCoachTypes.ts
│   ├── useAiCoach.ts
│   ├── useAiFileUpload.ts
│   └── sseStream.ts
└── styles/
    └── aiCoachPanel.css
```

Markdown 渲染建议本轮先放局部，避免污染全局组件：

```text
src/view/customer/profile/aiCoach/markdown/
├── MarkdownRenderer.vue
├── CodeBlock.vue
├── useMarkdownIt.ts
├── chunkBuffer.ts
└── markdown.css
```

如果后续有第二个模块复用 Markdown 渲染，再提升到全局 `src/components/common/` 或 `src/composables/`。

---

## 5. 前端代理与请求封装

### 5.1 Vite 代理

在 `vite.config.js` 中新增独立代理：

```js
'/wecom-ai': {
  target: process.env.VITE_WECOM_AI_BASE || 'http://127.0.0.1:8000',
  changeOrigin: true,
  rewrite: path => path.replace(/^\/wecom-ai/, '/api'),
  configure: (proxy) => {
    proxy.on('proxyRes', (proxyRes) => {
      if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
        proxyRes.headers['x-accel-buffering'] = 'no'
        proxyRes.headers['cache-control'] = 'no-cache, no-transform'
        delete proxyRes.headers['content-encoding']
        delete proxyRes.headers['content-length']
      }
    })
  },
}
```

`.env.development` / `.env.localdev` 增加：

```env
VITE_WECOM_AI_BASE=http://127.0.0.1:8000
```

### 5.2 独立 AI request

新增：

```text
src/utils/wecomAiRequest.js
```

职责：

- baseURL 固定为 `/wecom-ai`
- 从 CRM Pinia `userStore.token` 读取 token
- 发 `Authorization: Bearer <CRM token>`
- 兼容企微后端 `{ code, message, data }` 与统一包裹响应
- 不触发 CRM 全局 loading
- 不处理 CRM 原有 token refresh，只在 401 时给出 AI 服务登录态异常提示

示例：

```js
import axios from 'axios'
import { useUserStore } from '@/pinia/modules/user'

const service = axios.create({
  baseURL: '/wecom-ai',
  timeout: 120000,
  withCredentials: true,
})

service.interceptors.request.use(config => {
  const userStore = useUserStore()
  const token = userStore.token || localStorage.getItem('token')
  config.headers = {
    'Content-Type': 'application/json',
    ...config.headers,
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

service.interceptors.response.use(
  response => {
    const res = response.data
    if (res && typeof res === 'object' && 'code' in res) {
      if (res.code !== 0 && res.code !== 200) {
        return Promise.reject(new Error(res.message || 'AI 服务异常'))
      }
      return res.data
    }
    if (res && typeof res === 'object' && 'data' in res && !('errcode' in res)) {
      return res.data
    }
    return res
  },
  error => Promise.reject(error),
)

export default service
```

### 5.3 SSE 请求

`sseStream.ts` 需要从 CRM token 取值，并走 `/wecom-ai`：

```ts
export function buildAuthHeaders() {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

response = await fetch(`/wecom-ai${url}`, {
  method: 'POST',
  headers: buildAuthHeaders(),
  credentials: 'include',
  body: JSON.stringify(body),
  signal,
})
```

---

## 6. 迁移文件清单

### 6.1 必迁移

| 来源 | 目标 | 说明 |
|---|---|---|
| `wecom_ops_console/frontend/src/views/CrmProfile/composables/aiCoachTypes.ts` | `src/view/customer/profile/aiCoach/composables/aiCoachTypes.ts` | 类型定义 |
| `.../sseStream.ts` | `src/view/customer/profile/aiCoach/composables/sseStream.ts` | SSE |
| `.../useAiCoach.ts` | `src/view/customer/profile/aiCoach/composables/useAiCoach.ts` | 核心对话逻辑 |
| `.../useAiFileUpload.ts` | `src/view/customer/profile/aiCoach/composables/useAiFileUpload.ts` | 附件上传 |
| `.../components/AiCoach*.vue` | `src/view/customer/profile/aiCoach/components/` | AI UI |
| `.../components/AiSessionHistoryList.vue` | `src/view/customer/profile/aiCoach/components/` | 历史会话 |
| `.../components/styles/aiCoachPanel.css` | `src/view/customer/profile/aiCoach/styles/aiCoachPanel.css` | 样式 |

### 6.2 Markdown 迁移策略

本轮建议局部迁移 Markdown 能力：

| 来源 | 目标 | 说明 |
|---|---|---|
| `components/markdown/MarkdownRenderer.vue` | `src/view/customer/profile/aiCoach/markdown/MarkdownRenderer.vue` | 局部渲染 |
| `components/markdown/CodeBlock.vue` | `src/view/customer/profile/aiCoach/markdown/CodeBlock.vue` | 代码块 |
| `composables/useMarkdownIt.ts` | `src/view/customer/profile/aiCoach/markdown/useMarkdownIt.ts` | Markdown 解析 |
| `lib/streaming/chunkBuffer.ts` | `src/view/customer/profile/aiCoach/markdown/chunkBuffer.ts` | 流式 Markdown 闭合 |
| `styles/markdown.css` | `src/view/customer/profile/aiCoach/markdown/markdown.css` | 局部样式 |

暂不迁移 `MermaidBlock.vue`、`MathBlock.vue`，除非 AI 回答确实需要流程图或公式渲染。这样可以减少依赖和首轮风险。

---

## 7. 依赖策略

CRM 当前已有：

```text
marked
lucide-vue-next
@element-plus/icons-vue ^0.2.7
```

企微 AI Markdown 方案需要：

```text
markdown-it
markdown-it-task-lists
dompurify
```

本轮推荐新增：

```bash
npm install markdown-it markdown-it-task-lists dompurify
```

暂不建议直接升级 `@element-plus/icons-vue` 到 2.x。原因：

- 这是全局依赖，可能影响 CRM 现有页面。
- 本项目已经有不少页面引用旧版图标。
- AI 模块可以优先用当前可用的 Element Plus 图标或 `lucide-vue-next` 替代缺失图标。

---

## 8. 组件适配规则

### 8.1 import 路径

企微源码中的：

```ts
import request from '#/utils/request'
```

改为：

```ts
import request from '@/utils/wecomAiRequest'
```

企微源码中的：

```ts
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'
```

改为局部路径：

```ts
import MarkdownRenderer from '../markdown/MarkdownRenderer.vue'
```

### 8.2 用户信息映射

企微字段：

```text
userStore.user.avatar_url
userStore.user.display_name
userStore.user.username
userStore.user.role
```

CRM 字段：

```text
userStore.userInfo.avatar
userStore.userInfo.nickName
userStore.userInfo.authority
userStore.userInfo.powers
```

适配建议：

```ts
const userAvatar = computed(() => userStore.userInfo?.avatar || '')
const userDisplayName = computed(() => userStore.userInfo?.nickName || '当前用户')
const isAdmin = computed(() => {
  const authority = userStore.userInfo?.authority || {}
  return authority.authorityId === 'admin' || authority.authorityName === 'admin'
})
```

实际字段以运行时 CRM 用户信息为准，开发时需要打印一次 `userStore.userInfo` 做 focused validation。

### 8.3 企微专属功能降级

本轮先隐藏：

- 发送到发送中心
- 发送中心批量选择
- RAG 索引管理按钮
- `/v1/rag/status`
- `/v1/rag/reindex`

保留：

- RAG 引用消息展示
- AI 对话
- AI 思考过程
- 历史会话
- 反馈
- 附件上传
- 客户专属补充信息

---

## 9. 客户详情页集成方式

`src/view/customer/profile/index.vue` 只允许做薄集成：

```vue
<AiCoachPanel
  v-model="showAiCoach"
  :customer-id="Number(customerId)"
  :customer-name="customer?.name || customer?.nickName || ''"
/>
```

允许在该文件中新增：

```ts
import AiCoachPanel from './aiCoach/components/AiCoachPanel.vue'

const showAiCoach = ref(false)
```

不允许在 `profile/index.vue` 中新增：

- SSE 解析逻辑
- AI 请求方法
- 附件上传逻辑
- 历史会话处理
- Markdown 渲染逻辑
- 大段 AI 样式

入口样式可以是一个轻量悬浮按钮，或挂到现有客户详情操作区。推荐悬浮按钮，避免改动现有 tab 体系。

---

## 10. 企微后端改动边界

### 10.1 建议改动文件

```text
wecom_ops_console/app/config.py
wecom_ops_console/app/security.py
wecom_ops_console/app/services/crm_admin_auth.py
```

### 10.2 新增配置

```python
crm_jwt_secret_key: str = ''
crm_token_redis_url: str = ''
crm_token_redis_key_prefix: str = 'mfg-crm:sys:token:'
crm_token_strict_redis_check: bool = False
```

### 10.3 fallback 伪代码

```python
def get_current_user(request: Request, db: Session):
    token = read_bearer_token(request)

    # 1. 先按企微原 JWT 解析，保持原系统可用
    user = try_decode_wecom_token(token, db)
    if user:
        return user

    # 2. fallback 到 CRM token
    crm_payload = jwt.decode(
        token,
        settings.crm_jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    crm_admin_id = crm_payload.get("id")

    # 3. 开发期可先不强制 Redis，生产建议开启
    if settings.crm_token_strict_redis_check:
        assert_redis_token_matches(crm_admin_id, token)

    # 4. 映射到企微本地用户
    return sync_or_get_user_by_crm_admin_id(db, crm_admin_id)
```

注意：

- CRM token payload 字段是 `id`，不是 `sub`。
- 不能把 CRM token 解出的 `id` 当成企微 `users.id`。
- 映射后企微 AI 权限逻辑仍应使用 `user.crm_admin_id`。

---

## 11. 执行任务拆分

### 阶段 1：文档与蓝图收口

1. 修正 token 机制描述。
2. 明确前端目录边界。
3. 明确企微专属功能降级范围。
4. 明确首轮验收标准。

### 阶段 2：前端基础设施

1. 新增 `/wecom-ai` Vite proxy。
2. 新增 `src/utils/wecomAiRequest.js`。
3. 新增 AI 模块目录。
4. 新增必要依赖。

### 阶段 3：AI 模块迁移

1. 迁移 composables。
2. 迁移 AI 组件。
3. 迁移局部 Markdown 渲染。
4. 替换 import、token、用户信息字段。
5. 隐藏发送中心和 RAG 管理入口。

### 阶段 4：客户详情页薄集成

1. 在客户详情页引入 `AiCoachPanel`。
2. 添加打开入口。
3. 只传 `customerId`、`customerName`。
4. 不把 AI 逻辑写入客户详情页。

### 阶段 5：企微后端兼容

1. 新增 CRM JWT 配置。
2. 在 `get_current_user` 中新增 CRM token fallback。
3. 映射 `payload.id` 到 `users.crm_admin_id`。
4. 开发期先允许不强制 Redis，比对逻辑作为生产收口项。

### 阶段 6：验证与收口

1. `npm run build`
2. `npm run dev` 启动 CRM 前端
3. 打开客户详情页，确认原页面功能不受影响
4. 打开 AI 面板，确认 config/history 请求不 401
5. 发送消息，确认 `chat-stream` SSE 正常返回
6. 验证附件上传和反馈接口
7. 记录剩余 gap：Redis 严格校验、生产 nginx、RAG 管理、发送中心

---

## 12. 验收标准

### 12.1 前端验收

- CRM 前端能正常启动。
- CRM 现有客户详情页能正常打开。
- AI 入口只出现在客户详情页，不影响其他页面。
- AI 普通接口走 `/wecom-ai`。
- AI SSE 接口走 `/wecom-ai`，浏览器 Network 能看到 `text/event-stream`。
- token 使用 CRM `localStorage('token')` / Pinia `userStore.token`。
- 不出现 `access_token` 依赖。

### 12.2 后端验收

- CRM 登录后拿到的 token 能访问企微 AI 接口。
- 企微原有登录 token 仍然可用。
- CRM token payload `{ id }` 能映射到企微本地 user。
- 非法 token 返回 401。
- Redis 严格校验如果暂未开启，必须在部署说明中标成 known gap。

### 12.3 工程质量验收

- `profile/index.vue` 只做薄集成。
- AI 模块自包含在 `profile/aiCoach/`。
- 不修改 CRM 原有 request 拦截器。
- 不升级高风险全局依赖，除非有明确验证。
- 不把 support/candidate 能力写成 official 功能。

---

## 13. 生产部署注意事项

生产 nginx 需要新增：

```nginx
location /wecom-ai/ {
    proxy_pass http://wecom-backend:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Authorization $http_authorization;
    proxy_buffering off;
    proxy_cache off;
    chunked_transfer_encoding off;
}
```

SSE 必须关闭 buffering，否则前端会等很久才看到流式内容。

---

## 14. 当前 blocker 与 known gaps

### Blocker

企微后端尚未支持 CRM token fallback。前端可以先迁移 UI 和请求封装，但联调前必须补上该兼容层。

### Known gaps

1. Redis 严格 token 比对开发期可暂缓，但生产前建议开启。
2. RAG 管理入口先不纳入 CRM official 功能。
3. 发送中心能力先不迁移。
4. Markdown 的 Mermaid/Math 能力先不迁移，除非真实回答需要。
5. CRM 客户详情页已有大文件问题，本轮不做大重构，只保证新增 AI 模块不继续扩大问题。

---

## 15. 面向项目负责人的状态口径

### 已经能做什么

企微侧已有 AI 对话、SSE、历史、反馈、附件上传等能力，具备迁移基础。CRM 前端已有稳定登录态和客户详情入口。

### 半能做什么

AI 模块可以作为独立侧边面板接入 CRM，但需要适配 CRM token、用户字段和客户详情页入口。

### 还不能做什么

还不能直接宣布 CRM AI 对话正式可用，因为企微后端尚未识别 CRM token，生产 Redis 严格校验也未收口。

### 当前 blocker

企微后端需要新增 CRM token fallback，把 CRM 的 `{ id }` token 映射成企微本地用户。

### 下一步最值得做什么

先做前端隔离基础设施和企微后端 token fallback，然后以一个真实 CRM 登录用户完成端到端联调：打开客户详情页 → 打开 AI 面板 → 发送问题 → 收到 SSE 回复。
