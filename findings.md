# Findings

## CRM 真值
- `customers` 是客户主实体，`customer_groups` 是客户-群桥表，`groups` 是 CRM 社群维表。
- `point_logs` 是积分流水真值，`created_at` 可用于周/月积分统计；`num` 为积分变动值，`type` 区分获得/消费。

## 当前群管理实现
- `app/services/crm_group_directory.py` 当前只读查询 `groups/customer_groups/customers`，个人榜、群榜、成员页均展示 `points` 和 `total_points`。
- 现有实现没有接入 `point_logs`，也没有时间窗口统计、趋势分析或榜单快照能力。

## 当前运营编排实现
- 当前模型为 `Plan -> PlanDay -> PlanNode`，节点核心字段只有 `node_type / msg_type / content_json / variables_json`。
- `score_publish` 只是一个普通节点类型，没有专用 payload、规则引擎或动态数据绑定。
- 导入/导出服务对节点类型、列结构、标题映射都有硬编码，说明当前体系偏“固定日程型 SOP”。

## 积分运营参考资料
- Excel 第 1 个 sheet 是“话术库”，按场景类型提供三套风格文案，如头部激励、连续活跃、异常增长、回归用户等。
- Excel 第 2 个 sheet 是“投送阶段节点”，按每日发榜、每周复盘、结营冲刺、结营当天拆了阶段动作与配套 1v1 动作。
- 这说明积分运营不是单一模板，而是“榜单数据 + 人群识别 + 固定风格话术”的组合生成。
