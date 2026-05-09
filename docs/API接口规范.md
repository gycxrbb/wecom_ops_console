# 企微群消息运营后台统一接口文档

- 项目名称：企微群消息运营后台（WeCom Ops Console）
- 文档版本：v1.0
- 文档状态：可评审
- 基础路径：`/api/v1`
- 编写日期：2026-03-27

---

## 0. 当前实现说明

本文档同时包含两类接口信息：

1. 当前仓库已经存在并可对照代码联调的接口
2. 面向后续收口或演进的规划接口

截至 2026-03-31，联调和排障时请优先以 `app/routers/api.py` 为准。

当前需要特别注意：

- 并非所有接口都严格返回统一的 `{ code, message, data, request_id }`
- 一些文档中定义的 REST 风格接口当前在代码里仍采用“列表 + upsert + 动作接口”的简化形式
- `/auth/refresh` 目前仅在文档中存在，当前代码未看到独立实现

---

## 1. 接口规范

## 1.1 请求头

```http
Authorization: Bearer <access_token>
Content-Type: application/json
X-Request-Id: <optional_request_id>
```

## 1.2 统一响应结构

```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "request_id": "req_xxx"
}
```

### 当前实现补充

当前真实情况是：

- 登录接口采用统一包装
- 部分列表接口直接返回数组
- 部分业务接口直接返回对象
- `request_id` 当前未稳定返回

因此前端联调要对“统一响应”和“直接返回对象/数组”两种情况都保持兼容，直到后端收口完成。

## 1.3 分页结构

```json
{
  "list": [],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

## 1.4 错误码约定

| code | 含义 |
|---|---|
| 0 | 成功 |
| 40000 | 参数错误 |
| 40001 | 模板渲染失败 |
| 40002 | 消息体校验失败 |
| 40003 | 不支持的消息类型 |
| 40004 | 频控限制 |
| 40100 | 未登录或 token 失效 |
| 40300 | 无权限 |
| 40400 | 资源不存在 |
| 40900 | 状态冲突 |
| 50000 | 服务内部错误 |
| 50001 | 调用企微接口失败 |

---

## 2. 鉴权接口

## 2.1 登录

- 方法：`POST /auth/login`
- 说明：账号密码登录
- 是否鉴权：否

### 请求体

```json
{
  "username": "admin",
  "password": "Admin123456"
}
```

### 响应体

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access_token": "xxx",
    "refresh_token": "xxx",
    "token_type": "bearer",
    "expires_in": 7200,
    "user": {
      "id": 1,
      "username": "admin",
      "display_name": "管理员",
      "role": "admin"
    }
  },
  "request_id": "req_xxx"
}
```

## 2.2 刷新令牌

- 方法：`POST /auth/refresh`
- 是否鉴权：否

### 请求体

```json
{
  "refresh_token": "xxx"
}
```

### 当前实现状态

- 文档已定义
- 当前代码未看到对应路由落地
- 现阶段应视为规划接口，而不是已实现接口

## 2.3 获取当前用户

- 方法：`GET /auth/me`
- 是否鉴权：是

### 当前实现状态

- 已实现
- 另外，前端当前更多通过 `GET /bootstrap` 获取当前用户和看板数据

---

## 2.4 启动信息 / 当前用户 + 看板

- 方法：`GET /bootstrap`
- 是否鉴权：是
- 说明：当前前端实际依赖的初始化接口

### 响应示意

```json
{
  "current_user": {
    "id": 1,
    "username": "admin",
    "display_name": "系统管理员",
    "role": "admin"
  },
  "dashboard": {
    "group_count": 2,
    "template_count": 8,
    "schedule_count": 0,
    "log_count": 0,
    "success_rate": 0
  }
}
```

---

## 3. 用户接口

## 3.1 用户列表
- 方法：`GET /users`
- 权限：admin

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 关键字 |
| role | string | 否 | admin/coach |
| status | int | 否 | 1/0 |

## 3.2 创建用户
- 方法：`POST /users`
- 权限：admin

### 请求体

```json
{
  "username": "coach01",
  "password": "Coach123456",
  "display_name": "教练01",
  "role": "coach",
  "status": 1
}
```

## 3.3 更新用户
- 方法：`PUT /users/{id}`
- 权限：admin

### 当前实现状态

- 当前代码使用 `POST /users` 同时处理创建和更新
- 当前更接近 upsert 风格，而不是严格区分 `POST` 和 `PUT`

## 3.4 重置密码
- 方法：`POST /users/{id}/reset-password`
- 权限：admin

---

## 4. 群管理接口

## 4.1 群列表
- 方法：`GET /groups`
- 权限：登录用户

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 名称/别名 |
| enabled | int | 否 | 是否启用 |
| group_type | string | 否 | formal/test |
| tags | string | 否 | 逗号分隔标签 |

### 响应 data.list 项

```json
{
  "id": 1,
  "name": "训练营1群",
  "alias": "一期正式群",
  "group_type": "formal",
  "tags": ["训练营", "一期"],
  "enabled": 1,
  "has_webhook": true,
  "webhook_mask": "https://qyapi.weixin.qq.com/***",
  "created_at": "2026-03-27T10:00:00"
}
```

## 4.2 新增群
- 方法：`POST /groups`
- 权限：admin

### 请求体

```json
{
  "name": "训练营1群",
  "alias": "一期正式群",
  "group_type": "formal",
  "tags": ["训练营", "一期"],
  "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
  "enabled": 1
}
```

## 4.3 获取群详情
- 方法：`GET /groups/{id}`
- 权限：登录用户

## 4.4 更新群
- 方法：`PUT /groups/{id}`
- 权限：admin

### 当前实现状态

- 当前代码使用 `POST /groups` 同时处理新增和更新
- 当前返回字段更接近：

```json
{
  "id": 1,
  "name": "训练营1群",
  "alias": "一期正式群",
  "description": "",
  "tags": ["训练营", "一期"],
  "is_enabled": true,
  "is_test_group": false,
  "webhook_configured": true,
  "created_at": "2026-03-31T12:00:00"
}
```

## 4.5 启停群
- 方法：`PATCH /groups/{id}/status`
- 权限：admin

### 请求体

```json
{
  "enabled": 0
}
```

## 4.6 删除群
- 方法：`DELETE /groups/{id}`
- 权限：admin

---

## 5. 模板接口

## 5.1 模板列表
- 方法：`GET /templates`
- 权限：登录用户

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 名称关键字 |
| category | string | 否 | 分类 |
| msg_type | string | 否 | 消息类型 |
| enabled | int | 否 | 是否启用 |
| mine_only | int | 否 | 仅我的模板 |

## 5.2 创建模板
- 方法：`POST /templates`
- 权限：登录用户

### 请求体

```json
{
  "name": "晚安总结模板",
  "category": "训练营",
  "msg_type": "markdown",
  "content": "### 晚安总结\n今日主题：**{topic}**\n请完成复盘。",
  "variable_schema": {
    "topic": {
      "type": "string",
      "required": true,
      "label": "今日主题"
    }
  },
  "default_variables": {
    "topic": "211+餐后走"
  },
  "enabled": 1
}
```

## 5.3 获取模板详情
- 方法：`GET /templates/{id}`

## 5.4 更新模板
- 方法：`PUT /templates/{id}`

### 当前实现状态

- 当前代码使用 `POST /templates` 同时处理创建和更新
- 当前模板返回字段为 `content_json`、`variables_json`，而不是文档里更抽象的 `content`、`variable_schema`

## 5.5 复制模板
- 方法：`POST /templates/{id}/clone`

### 请求体

```json
{
  "name": "晚安总结模板-教练版"
}
```

## 5.6 模板预览
- 方法：`POST /templates/{id}/render`
- 说明：按变量渲染模板并返回结构化预览

### 请求体

```json
{
  "variables": {
    "topic": "足量膳食纤维"
  }
}
```

### 响应体

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "msg_type": "markdown",
    "rendered_content": "### 晚安总结\n今日主题：**足量膳食纤维**\n请完成复盘。",
    "payload_preview": {
      "msgtype": "markdown",
      "markdown": {
        "content": "### 晚安总结\n今日主题：**足量膳食纤维**\n请完成复盘。"
      }
    }
  }
}
```

## 5.7 启停模板
- 方法：`PATCH /templates/{id}/status`

## 5.8 删除模板
- 方法：`DELETE /templates/{id}`

---

## 6. 素材接口

## 6.1 素材列表
- 方法：`GET /assets`

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 素材名 |
| material_type | string | 否 | image/file |
| enabled | int | 否 | 是否启用 |

## 6.2 上传素材
- 方法：`POST /assets`
- Content-Type：`multipart/form-data`

### 表单字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | binary | 是 | 上传文件 |
| material_type | string | 是 | image/file |
| tags | string | 否 | 逗号分隔 |

## 6.3 下载素材
- 方法：`GET /assets/{id}/download`

## 6.4 删除素材
- 方法：`DELETE /assets/{id}`

### 当前实现状态

- 当前素材资源在代码中统一命名为 `assets`
- 文档中的 `materials` 更接近设计层概念，不是当前接口真值

---

## 7. 发送接口

## 7.1 立即发送
- 方法：`POST /send`
- 权限：登录用户

### 请求体

```json
{
  "group_ids": [1],
  "template_id": 12,
  "msg_type": "markdown",
  "content_json": {
    "content": "### 早安\n今日主题：**{{topic}}**"
  },
  "variables_json": {
    "topic": "CGM+记录餐食"
  },
  "test_group_only": false
}
```

### 字段说明
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| group_ids | int[] | 是 | 目标群列表 |
| template_id | int | 否 | 模板 ID |
| msg_type | string | 是 | 消息类型 |
| content_json | object | 是 | 结构化消息内容 |
| variables_json | object | 否 | 模板变量 |
| test_group_only | bool | 否 | 是否改发测试群 |

### 响应体

```json
{
  "results": [
    {
      "group_id": 1,
      "group_name": "测试群",
      "success": true,
      "response": "Queued"
    }
  ]
}
```

## 7.2 渲染预览
- 方法：`POST /preview`

### 请求体

```json
{
  "msg_type": "news",
  "content_json": {
    "articles": [
      {
        "title": "今日打卡说明",
        "description": "点击查看详细规则",
        "url": "https://example.com/rule",
        "picurl": "https://example.com/pic.jpg"
      }
    ]
  },
  "variables_json": {}
}
```

### 响应体

```json
{
  "rendered_content": {},
  "payload_preview": {
    "msgtype": "news",
    "news": {
      "articles": [
        {
          "title": "今日打卡说明",
          "description": "点击查看详细规则",
          "url": "https://example.com/rule",
          "picurl": "https://example.com/pic.jpg"
        }
      ]
    }
  }
}
```

## 7.3 重试发送
- 方法：`POST /logs/{id}/retry`
- 权限：admin 或本人

### 当前实现状态

- 当前重试入口挂在日志资源上，而不是消息资源上
- 当前日志和消息模型字段仍在收口中

---

## 8. 定时任务接口

## 8.1 任务列表
- 方法：`GET /schedules`

## 8.2 创建或更新任务
- 方法：`POST /schedules`

### 当前请求体实际口径

```json
{
  "id": null,
  "title": "周一早安提醒",
  "group_ids": [1],
  "template_id": 3,
  "msg_type": "markdown",
  "content_json": {
    "content": "### 早安\n今日主题：**{{topic}}**"
  },
  "variables_json": {
    "topic": "CGM+记录餐食"
  },
  "schedule_type": "cron",
  "run_at": null,
  "cron_expr": "0 8 * * 1",
  "timezone": "Asia/Shanghai",
  "enabled": true,
  "approval_required": true,
  "skip_dates": ["2026-04-05"],
  "skip_weekends": false
}
```

### 当前实现风险说明

- 当前代码使用的任务字段与 `models.py` 中定义并未完全一致
- 该接口文档代表的是当前前端与路由层的口径，不代表调度链路已完全可用

## 8.3 复制任务
- 方法：`POST /schedules/{id}/clone`

## 8.4 启停任务
- 方法：`POST /schedules/{id}/toggle`

## 8.5 审批任务
- 方法：`POST /schedules/{id}/approve`

## 8.6 手动执行任务
- 方法：`POST /schedules/{id}/run-now`

## 8.7 删除任务
- 方法：`DELETE /schedules/{id}`

---

## 9. 审批接口

## 9.1 审批列表
- 方法：`GET /approvals`

### 当前实现状态

- 当前支持分页参数 `page`、`page_size` 和可选 `status`
- 非管理员默认仅能看到自己的审批单

## 9.2 提交审批
- 方法：`POST /approvals`

## 9.3 审批通过
- 方法：`POST /approvals/{id}/approve`

## 9.4 审批拒绝
- 方法：`POST /approvals/{id}/reject`

---

## 10. 仪表盘接口

## 10.1 当前前端初始化看板
- 方法：`GET /bootstrap`

## 10.2 汇总指标
- 方法：`GET /dashboard/summary`

## 10.3 近期发送趋势
- 方法：`GET /dashboard/message-trend?days=7`

## 10.4 失败原因分布
- 方法：`GET /dashboard/failure-distribution?days=7`

---

## 11. 当前已实现接口一览

以下接口可以直接在 `app/routers/api.py` 中对照：

- `POST /auth/login`
- `GET /auth/me`
- `GET /bootstrap`
- `GET/POST/DELETE /groups`
- `GET/POST/POST clone/DELETE /templates`
- `GET/POST/GET download/DELETE /assets`
- `POST /preview`
- `POST /send`
- `GET/POST/POST clone/POST toggle/POST approve/DELETE /schedules`
- `POST /schedules/{id}/run-now`
- `GET /logs`
- `POST /logs/{id}/retry`
- `GET/POST /approvals`
- `POST /approvals/{id}/approve`
- `POST /approvals/{id}/reject`
- `GET/POST /users`
- `GET /dashboard/summary`
- `GET /dashboard/message-trend`
- `GET /dashboard/failure-distribution`

---

## 12. 规划接口与当前差异说明

以下内容在文档中存在，但当前代码未完全按此实现：

- `POST /auth/refresh`
- 严格 REST 化的 `PUT /groups/{id}`、`PUT /templates/{id}`、`PUT /users/{id}`
- `materials` 命名空间接口
- 严格统一的响应包装
- 完整的 message 资源体系

---

## 13. 前后端协作约定

1. 前端统一通过 Axios 拦截器注入 access token。
2. 当前 401 会直接跳转登录页，尚未接入完整 refresh 自动续期。
3. 前端表单字段目前以当前 Vue 页面和 `api.py` 的真实请求字段为准。
4. 时间字段统一使用 ISO 8601，默认按 `Asia/Shanghai` 处理。
5. 模板预览和消息预览以后端渲染结果为准。
6. Webhook 明文不得出现在任何前端接口响应中。

---

## 14. TypeScript 类型建议

```ts
export type MsgType =
  | 'text'
  | 'markdown'
  | 'news'
  | 'image'
  | 'file'
  | 'template_card'
  | 'raw_json'

export interface BootstrapData {
  current_user: {
    id: number
    username: string
    display_name: string
    role: 'admin' | 'coach'
  }
  dashboard: {
    group_count: number
    template_count: number
    schedule_count: number
    log_count: number
    success_rate: number
  }
}
```

---

## 15. Next.js 补充接口边界（可选）

> Next.js 不作为当前核心业务主 API，而是后续预览/公开页能力层。

### 示例用途
- `/preview/template/:id`
- `/campaign/:slug`
- `/materials/:id/view`

### 调用方式
- Next.js 从 FastAPI 拉取已发布内容数据
- 对外页面不直接暴露管理后台接口
## 16. 枚举定义

## 11.1 msg_type
| 值 | 说明 |
|---|---|
| text | 文本 |
| markdown | Markdown |
| news | 图文 |
| image | 图片 |
| file | 文件 |
| template_card | 模板卡片 |
| raw_json | 原始 JSON |

## 11.2 message_status
| 值 | 说明 |
|---|---|
| pending | 待发送 |
| awaiting_approval | 待审批 |
| sent | 已发送 |
| failed | 发送失败 |
| cancelled | 已取消 |

## 11.3 approval_status
| 值 | 说明 |
|---|---|
| not_required | 无需审批 |
| pending | 待审批 |
| approved | 已通过 |
| rejected | 已拒绝 |

## 11.4 schedule_type
| 值 | 说明 |
|---|---|
| once | 一次性 |
| cron | 周期任务 |

---

## 17. 历史规划说明

文档早期版本使用了更强 REST 风格的资源设计，例如：

- `/messages/send`
- `/materials/*`
- `PUT /groups/{id}`
- `PUT /templates/{id}`

这些设计仍有参考价值，但当前仓库真实接口已演进为更偏向“运营后台快速联调”的简化风格。后续如果要重新规范接口，建议先统一后端模型和返回结构，再进行 REST 化整理。

---

## 18. 前后端协作约定

1. 前端统一通过 Axios 拦截器注入 access token。
2. 当前 401 以跳转登录页为主，尚未自动刷新。
3. 前端表单字段命名与当前已实现 API 保持一致，避免重复映射。
4. 时间字段统一使用 ISO 8601，默认以 `Asia/Shanghai` 处理并展示。
5. JSON 类型消息前端采用代码编辑器，提交前做基础 JSON 解析校验；后端做最终权威校验。
6. 对于模板预览、消息预览，以后端渲染结果为准。
7. Webhook 明文不得出现在任何前端接口响应中。

---

## 19. TypeScript 类型建议

```ts
export type MsgType =
  | 'text'
  | 'markdown'
  | 'news'
  | 'image'
  | 'file'
  | 'template_card'
  | 'raw_json'

export type MessageStatus =
  | 'pending'
  | 'awaiting_approval'
  | 'sent'
  | 'failed'
  | 'cancelled'

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  request_id: string
}

export interface Pagination {
  page: number
  page_size: number
  total: number
}
```
