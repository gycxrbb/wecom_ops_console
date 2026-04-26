# 积分运营升级任务计划

## 目标
- 基于 CRM 的 `customers / customer_groups / groups / point_logs`，为群管理-外部群、发送中心、运营编排设计一套可实现的积分展示与积分运营升级方案。
- 当前阶段先完成现状恢复、方案设计和落盘计划，不进入代码实现。

## 阶段
- [x] Phase 1: 读取 CRM 表说明、Schema 知识与积分运营参考 Excel
- [x] Phase 2: 梳理当前外部群积分榜、发送中心、运营编排实现现状
- [x] Phase 3: 输出积分展示、排行推送、积分运营编排升级方案
- [x] Phase 4: 将正式计划写入 `docs/`

## 当前判断
- 当前群管理积分视图只基于 `customers.points/total_points` 做静态聚合，没有周/月积分口径。
- 当前发送中心支持模板/运营编排节点引用，但没有“按 CRM 外部群积分排行生成动态内容”的发送逻辑。
- 当前运营编排是标准 `Plan -> Day -> Node` 固定节奏模型，适合周期内容运营，不适合积分榜驱动的事件型运营。

## 风险与待确认
- `customers.points` 与 `customers.total_points` 的业务含义存在历史口径，需要在升级中明确 UI 保留哪个列。
- 积分运营文案不是纯模板替换，涉及 `point_logs` 趋势分析与人群识别，需要单独的数据分析层。
- 现有导入/导出链路对节点类型和 Excel 列结构有硬编码，改编排模型时要避免直接破坏旧流程。

---

## 2026-04-26 临时任务锚点：CRM 健康摘要 7/14/30 天升级研究

### 目标
- 基于 `customer_health` 与 `customer_glucose` 的真实字段，评估如何把“近7天健康摘要”升级为支持 7/14/30 天的正式健康摘要，并明确 UI 展示口径与 AI 上下文接法。

### 阶段
- [x] Phase 1: 读取 `mfgcrmdb_database_explanation.md`、`mfgcrmdb_schema_knowledge.json`、当前 `health_summary.py`
- [x] Phase 2: 梳理 `customer_health` 与 `customer_glucose` 的字段角色、表关系与当前缺口
- [x] Phase 3: 输出健康摘要升级开发报告到 `docs/`
- [ ] Phase 4: 后续如进入实现，再拆后端模块重构、前端窗口切换、AI 上下文升级

### 当前判断
- 当前 `health_summary.py` 只用了 `customer_health` 的少量标量字段，还没有正式接入三餐 JSON 与 `customer_glucose.points`。
- `customer_health` 应作为每日业务概览真值，`customer_glucose` 应作为血糖曲线与波动分析真值，两者通过 `customer_id + 日期` 在服务层轻量对齐。
- `diet_assessment`、餐食图片 URL、全量血糖 `points` 原始数组不适合作为 AI 默认正式上下文，更适合作为 support 或按需展开。

### 风险与待确认
- 高血糖/低血糖阈值不宜在第一版硬编码到多处，建议统一配置。
- 现有主报告 `CRM_USER_PROFILE_AI_INTEGRATION_REPORT.md` 仍以 `health_summary_7d` 为主，后续需要和本次报告同步口径，避免真值漂移。
