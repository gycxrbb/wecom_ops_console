## Bug #1: 定时任务与日志模型真值漂移导致调度链路不稳定

- **日期**: 2026-03-31
- **现象**: `Schedule`、`MessageLog`、`scheduler_service` 与 `api.py` 之间字段口径不一致，出现旧模型名 `MessageJob`、旧字段 `content_snapshot` 与新字段 `content_json` / `group_ids_json` 并存，导致定时任务、日志列表、日志重试和素材下载链路不稳定。
- **根因**: 后端代码从旧单群任务模型向当前前端消费口径迁移过程中，路由层先演进，ORM、调度服务、种子数据和日志链路没有同步收口。
- **复现条件**: 创建或查询定时任务、触发调度服务、查看日志列表、重试日志、下载素材时，命中旧字段引用或旧模型名引用。
- **解决方案**: 第一批最小收口不做 refresh、REST 重构或额外功能扩展，保留当前数据库真值，改为在 `api.py`、`scheduler_service.py`、`tasks.py`、`seed.py` 和 `models.py` 中补兼容桥接与旧字段适配，统一围绕当前前端口径稳定工作。
- **关联文件**: app/models.py, app/routers/api.py, app/services/scheduler_service.py, app/services/seed.py, app/tasks.py
