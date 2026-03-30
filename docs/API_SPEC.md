# 企微群消息运营后台统一接口文档

- 项目名称：企微群消息运营后台（WeCom Ops Console）
- 文档版本：v1.0
- 文档状态：可评审
- 基础路径：`/api/v1`
- 编写日期：2026-03-27

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

## 2.3 获取当前用户

- 方法：`GET /auth/me`
- 是否鉴权：是

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
- 方法：`GET /materials`

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 素材名 |
| material_type | string | 否 | image/file |
| enabled | int | 否 | 是否启用 |

## 6.2 上传素材
- 方法：`POST /materials/upload`
- Content-Type：`multipart/form-data`

### 表单字段
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | binary | 是 | 上传文件 |
| material_type | string | 是 | image/file |
| tags | string | 否 | 逗号分隔 |

## 6.3 获取素材详情
- 方法：`GET /materials/{id}`

## 6.4 更新素材
- 方法：`PUT /materials/{id}`

## 6.5 删除素材
- 方法：`DELETE /materials/{id}`

---

## 7. 发送接口

## 7.1 立即发送
- 方法：`POST /messages/send`
- 权限：登录用户

### 请求体

```json
{
  "group_id": 1,
  "template_id": 12,
  "msg_type": "markdown",
  "content": "### 早安\n今日主题：**{topic}**",
  "variables": {
    "topic": "CGM+记录餐食"
  },
  "require_approval": false,
  "send_mode": "formal"
}
```

### 字段说明
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| group_id | int | 是 | 正式群 ID |
| template_id | int | 否 | 模板 ID |
| msg_type | string | 是 | 消息类型 |
| content | string/object | 是 | 原始内容 |
| variables | object | 否 | 模板变量 |
| require_approval | bool | 否 | 是否发起审批 |
| send_mode | string | 否 | formal/test |
| test_group_id | int | 否 | 当 send_mode=test 时可指定测试群 |

### 响应体

```json
{
  "code": 0,
  "message": "accepted",
  "data": {
    "message_id": 1001,
    "status": "pending"
  }
}
```

## 7.2 渲染预览
- 方法：`POST /messages/preview`

### 请求体

```json
{
  "msg_type": "news",
  "content": {
    "articles": [
      {
        "title": "今日打卡说明",
        "description": "点击查看详细规则",
        "url": "https://example.com/rule",
        "picurl": "https://example.com/pic.jpg"
      }
    ]
  },
  "variables": {}
}
```

### 响应体

```json
{
  "code": 0,
  "message": "ok",
  "data": {
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
}
```

## 7.3 发送到测试群
- 方法：`POST /messages/test-send`

### 请求体

```json
{
  "target_group_id": 1,
  "test_group_id": 2,
  "template_id": 12,
  "msg_type": "markdown",
  "content": "### 测试消息\n主题：{topic}",
  "variables": {
    "topic": "餐前醋+饮食顺序"
  }
}
```

## 7.4 重试发送
- 方法：`POST /messages/{id}/retry`
- 权限：admin 或拥有者（可配置）

### 请求体

```json
{
  "force": false
}
```

## 7.5 消息详情
- 方法：`GET /messages/{id}`

## 7.6 消息列表
- 方法：`GET /messages`

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| status | string | 否 | 状态 |
| group_id | int | 否 | 群 |
| msg_type | string | 否 | 类型 |
| source_type | string | 否 | 来源 |
| created_by | int | 否 | 创建人 |
| start_time | string | 否 | 开始时间 |
| end_time | string | 否 | 结束时间 |

---

## 8. 定时任务接口

## 8.1 任务列表
- 方法：`GET /schedules`

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 名称关键字 |
| enabled | int | 否 | 是否启用 |
| approval_status | string | 否 | 审批状态 |
| group_id | int | 否 | 目标群 |

## 8.2 创建任务
- 方法：`POST /schedules`

### 请求体（Cron）

```json
{
  "name": "周一早安提醒",
  "group_id": 1,
  "template_id": 3,
  "msg_type": "markdown",
  "content_snapshot": "### 早安\n今日主题：**{topic}**",
  "variables": {
    "topic": "CGM+记录餐食"
  },
  "schedule_type": "cron",
  "cron_expr": "0 8 * * 1",
  "timezone": "Asia/Shanghai",
  "skip_weekends": false,
  "skip_dates": ["2026-04-05"],
  "require_approval": true,
  "enabled": true
}
```

### 请求体（一次性）

```json
{
  "name": "训练营开营通知",
  "group_id": 1,
  "msg_type": "text",
  "content_snapshot": "今晚8点开营，请准时参加。",
  "variables": {},
  "schedule_type": "once",
  "run_at": "2026-04-01T20:00:00+08:00",
  "timezone": "Asia/Shanghai",
  "skip_weekends": false,
  "skip_dates": [],
  "require_approval": false,
  "enabled": true
}
```

## 8.3 获取任务详情
- 方法：`GET /schedules/{id}`

## 8.4 更新任务
- 方法：`PUT /schedules/{id}`

## 8.5 启停任务
- 方法：`PATCH /schedules/{id}/status`

### 请求体

```json
{
  "enabled": false
}
```

## 8.6 复制任务
- 方法：`POST /schedules/{id}/clone`

### 请求体

```json
{
  "name": "周一早安提醒-复制"
}
```

## 8.7 手动执行任务
- 方法：`POST /schedules/{id}/run-now`

### 请求体

```json
{
  "send_mode": "test",
  "test_group_id": 2
}
```

## 8.8 删除任务
- 方法：`DELETE /schedules/{id}`

---

## 9. 审批接口

## 9.1 审批列表
- 方法：`GET /approvals`

### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| status | string | 否 | pending/approved/rejected |
| target_type | string | 否 | message/schedule |
| applicant_id | int | 否 | 申请人 |

## 9.2 提交审批
- 方法：`POST /approvals`

### 请求体

```json
{
  "target_type": "schedule",
  "target_id": 8,
  "reason": "一期训练营正式启用"
}
```

## 9.3 审批通过
- 方法：`POST /approvals/{id}/approve`
- 权限：admin

### 请求体

```json
{
  "comment": "内容已审核通过"
}
```

## 9.4 审批拒绝
- 方法：`POST /approvals/{id}/reject`
- 权限：admin

### 请求体

```json
{
  "comment": "请补充测试群验证截图"
}
```

---

## 10. 仪表盘接口

## 10.1 看板汇总
- 方法：`GET /dashboard/summary`

### 响应体

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "group_total": 12,
    "enabled_group_total": 10,
    "template_total": 42,
    "schedule_total": 31,
    "pending_approval_total": 5,
    "today_message_total": 66,
    "today_success_rate": 0.97
  }
}
```

## 10.2 近期发送趋势
- 方法：`GET /dashboard/message-trend?days=7`

## 10.3 失败原因分布
- 方法：`GET /dashboard/failure-distribution?days=7`

---

## 11. 枚举定义

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

## 12. 前后端协作约定

1. 前端统一通过 Axios 拦截器注入 access token。
2. 401 自动尝试刷新令牌，刷新失败跳转登录页。
3. 前端表单字段命名与 API 保持一致，避免二次映射。
4. 时间字段统一使用 ISO 8601，默认以 `Asia/Shanghai` 处理并展示。
5. JSON 类型消息前端采用代码编辑器，提交前做基础 JSON 解析校验；后端做最终权威校验。
6. 对于模板预览、消息预览，以后端渲染结果为准。
7. Webhook 明文不得出现在任何前端接口响应中。

---

## 13. TypeScript 类型建议

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

---

## 14. Next.js 补充接口边界（可选）

> Next.js 不作为核心业务主 API，而作为预览/公开页能力层。

### 示例用途
- `/preview/template/:id`
- `/campaign/:slug`
- `/materials/:id/view`

### 调用方式
- Next.js 从 FastAPI 拉取已发布内容数据
- 对外页面不直接暴露管理后台接口

