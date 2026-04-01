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
- 第二轮确认当前运行环境实际连接的是 MySQL；`Schedule` 正式迁移不能按 SQLite 假设写。
- 第二轮结果：`schedules` 表已新增正式列 `title/group_ids_json/content/approval_required/approved_at/approved_by_id/status/skip_dates_json/last_error/last_sent_at`，后端启动通过。

## 后端模型真值盘点

- `serialize_schedule()` 使用 `job.id`、`job.title`、`job.group_ids_json`、`job.content`、`job.approval_required`、`job.approved_at`、`job.status`、`job.skip_dates_json`、`job.last_error`、`job.last_sent_at`，但函数签名参数是 `schedule`，且 `models.Schedule` 不存在其中多数字段。
- `create_or_update_schedule()` 直接写入 `Schedule.title`、`Schedule.group_ids_json`、`Schedule.content`、`Schedule.approval_required`、`Schedule.skip_dates_json`、`Schedule.status`、`Schedule.approved_at`、`Schedule.approved_by_id`，这些字段当前 ORM 未定义。
- `perform_job_send()` 读取 `schedule.group_ids_json` 和 `schedule.content`，而 ORM 当前字段是 `group_id` 和 `content_snapshot`。
- `serialize_log()` 和 `/logs/{id}/retry` 读取 `MessageLog.job_id`、`group_id`、`group`、`msg_type`、`run_mode`、`request_json`、`response_json`、`initiated_by_id`，这些字段当前 `MessageLog` 模型均不存在。
- `/assets/{id}/download` 读取 `asset.file_name`，但 `Material` 模型无该字段。
- `seed_all()` 把模板默认变量写入 `Template.variable_schema`，而接口实际读取和写入的是 `Template.default_variables`。

## 2026-04-01 发送链路全流程盘点

- 后端发送主链路当前已经支持 `text`、`markdown`、`news`、`image`、`file`、`template_card` 六类消息，但前端并非所有类型都提供了可操作的正式配置入口。
- `image` / `file` 类型的后端真实能力是围绕 `asset_id -> attach_asset_paths() -> WeComService.send()` 展开的；此前前端编辑器却要求用户手填 `image_path` 或 `media_id`，产品层实际上不可用。
- 群管理页仍在向 `/v1/groups` 发送旧字段 `group_type` / `enabled`，会导致测试群标记和启用状态存在保存漂移。
- 发送记录页仍按旧字段 `is_success` / `request_payload` / `response_payload` 渲染，而当前后端正式返回的是 `success` / `request_json` / `response_json`。
- `template_card` 编辑器当前能构造基础结构，但仍缺少对链接字段的显式校验；这条线暂时属于“半能做”，不是当前最高优先级 blocker。
- Celery 异步发送仍然可作为正式发送路径，但当前项目已经通过“测试发送直发 + 队列不可用回退直发”保证本地联调不被 Redis/Celery 阻断。
- 2026-04-01 逐类 focused validation 结果：`text / markdown / news / image / file / template_card` 六类消息都能在“渲染内容 -> 资产补全 -> outbound 校验 -> payload 构造”这条本地链路上跑通。
- 当前仍待继续深挖的高风险点，主要不是“六类消息不会构造 payload”，而是“template_card` 缺乏更强结构校验”以及“异步发送/重试/定时任务是否与主入口完全同构”。其中前两条旁路校验已补齐，`template_card` 仍是下一批优先项。
- 2026-04-01 真实接口 smoke 结果：
  - `/api/v1/auth/login` 正常
  - 六类消息 `/api/v1/preview` 全部返回 200
  - `text / markdown / image / file` 已经完成真实 `/api/v1/send + test_group_only` smoke
  - `text / markdown / image / file` 最终都可以成功发到当前测试群
- 真实 smoke 暴露的关键运行级 bug 是：图片消息此前会因为日志写入完整 base64 payload 而在本地 MySQL 层先失败，现已修复为压缩存储。
