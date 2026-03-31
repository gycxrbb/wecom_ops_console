# Progress

## 2026-03-31

- 已对照代码和文档完成一轮项目现状梳理。
- 已补充 `README.md` 与 `docs/` 下多份文档，区分当前实现态与规划态。
- 已进入多线程总控模式，准备并行推进：
  - 后端模型真值盘点
  - API / 前端契约盘点
  - 调度链路盘点
- 主线程已补读 `app/tasks.py` 与 `app/route_helper.py`，用于后续收口统一响应和发送执行链路。
- 子线程盘点已收口，主控判断第一批执行改动写集如下：
  - 后端线程：`app/models.py`、`app/routers/api.py`、`app/services/scheduler_service.py`、`app/services/seed.py`、`app/tasks.py`
  - 前端线程：`frontend/src/views/SendCenter/composables/useSendLogic.ts`、`frontend/src/stores/user.ts`、`frontend/src/views/Dashboard.vue`、必要时 `frontend/src/utils/request.ts`
- 已启动两条执行线程：
  - 后端收口线程：统一模型、路由、调度、种子、任务执行真值
  - 前端收口线程：最小契约修正，不触碰后端
- 已发出后端收口执行线程，正在统一模型、调度和日志真值。
- 主线程已确认前端发送中心和用户 store 当前已基本对齐预期，并额外将看板数据源切到 `/v1/dashboard/summary`，进一步拆分当前用户入口与看板入口职责。
- 后端第一批最小收口已完成：统一 `Schedule` / `MessageLog` 的路由消费口径，修复 `scheduler_service.py` 旧模型引用，修复 seed 默认变量字段与素材下载字段，并让 `api.py` 围绕当前前端口径稳定工作。
- 后端启动验证已通过：使用 `uvicorn app.main:app --host 127.0.0.1 --port 8001` 的受控启动探针，日志显示 `Application startup complete` 且 `Uvicorn running on http://127.0.0.1:8001`。
- 已完成后端模型盘点首轮读取，确认任务模型与日志模型存在高严重度字段漂移，足以影响定时任务、日志重试和序列化。
- 主控补充验收完成：
  - 前端 `npm run build` 通过，`vue-tsc -b && vite build` 成功
  - 前端 `npm run dev` 进程探针在 10 秒窗口内保持存活，未出现秒退型失败
