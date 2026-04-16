# Progress

## 2026-04-16
- 已读取 `docs/CRM/mfgcrmdb_database_explanation.md` 和 `docs/CRM/mfgcrmdb_schema_knowledge.json`。
- 已确认本次主要依赖表：`customers / customer_groups / groups / point_logs`。
- 已梳理当前代码入口：
  - `app/services/crm_group_directory.py`
  - `app/routers/api_crm_groups.py`
  - `frontend/src/views/Groups/CrmLeaderboard.vue`
  - `app/routers/api_operation_plans.py`
  - `app/services/operation_plan_import.py`
  - `app/services/operation_plan_export.py`
  - `frontend/src/views/SendCenter/*`
- 已读取积分运营参考 Excel，确认存在“话术库”和“投送阶段节点”两层结构。
- 已完成正式方案文档：`docs/POINTS_OPERATIONS_UPGRADE_PLAN.md`。
- 下一步：按计划进入实现阶段，优先做积分指标层、发送映射层和 `points_campaign` 最小可用版。
