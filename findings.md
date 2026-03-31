# Findings

## 2026-03-31

- 当前项目已具备前后端分离骨架，但后端模型、API 路由和调度服务仍有明显真值漂移。
- `app/models.py` 中 `Schedule` 字段与 `app/routers/api.py` 中任务相关字段不一致。
- `app/services/scheduler_service.py` 仍引用不存在的 `models.MessageJob`。
- 前端已全面按 `/api/v1` 口径开发，但部分接口返回仍不是统一响应结构。
- 文档已补充当前状态说明，当前下一步最值得做的是统一后端任务、消息、日志模型真值。
- `app/route_helper.py` 已实现 `UnifiedResponseRoute`，说明统一响应协议并非完全缺失，而是落地不彻底。
- `app/tasks.py` 当前通过 Celery task 处理发送，但消息写入内容与 `WeComService.send` 的参数语义之间仍需核对，且日志字段与路由序列化口径不一致。
- 后端模型子线确认：`Schedule`、`MessageLog`、素材下载字段、模板默认变量写入、调度服务模型引用都存在成体系漂移，应以当前路由和前端消费口径反向统一 ORM。
- API 契约子线确认：最小收口优先级是统一响应格式、确定唯一当前用户入口、修正发送中心 `group_ids` 类型，并处理看板字段缺口。

## 后端模型真值盘点

- `serialize_schedule()` 使用 `job.id`、`job.title`、`job.group_ids_json`、`job.content`、`job.approval_required`、`job.approved_at`、`job.status`、`job.skip_dates_json`、`job.last_error`、`job.last_sent_at`，但函数签名参数是 `schedule`，且 `models.Schedule` 不存在其中多数字段。
- `create_or_update_schedule()` 直接写入 `Schedule.title`、`Schedule.group_ids_json`、`Schedule.content`、`Schedule.approval_required`、`Schedule.skip_dates_json`、`Schedule.status`、`Schedule.approved_at`、`Schedule.approved_by_id`，这些字段当前 ORM 未定义。
- `perform_job_send()` 读取 `schedule.group_ids_json` 和 `schedule.content`，而 ORM 当前字段是 `group_id` 和 `content_snapshot`。
- `serialize_log()` 和 `/logs/{id}/retry` 读取 `MessageLog.job_id`、`group_id`、`group`、`msg_type`、`run_mode`、`request_json`、`response_json`、`initiated_by_id`，这些字段当前 `MessageLog` 模型均不存在。
- `/assets/{id}/download` 读取 `asset.file_name`，但 `Material` 模型无该字段。
- `seed_all()` 把模板默认变量写入 `Template.variable_schema`，而接口实际读取和写入的是 `Template.default_variables`。
