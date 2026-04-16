# 积分展示与积分运营升级计划

## 1. 文档目标

本文档用于收口这次“群管理 - 外部群”积分相关功能的升级方向，覆盖三条主线：

1. 外部群积分展示升级
2. 发送中心新增“积分排行推送”能力
3. 运营编排支持“围绕积分的动态运营”而不只是固定 Day 流程

本轮结论只代表**方案真值**，不代表代码已经完成。
相关参考文档：
1. docs\feishu\jifen\首钢减重健康群「积分激励专属话术」 (1).xlsx
2. docs\CRM\mfgcrmdb_database_explanation.md
3. docs\CRM\mfgcrmdb_schema_knowledge.json
---

## 2. 当前阶段判断

### 当前阶段

当前处于：

`方案设计 / 架构收口阶段`

不是实现阶段，也不是验收阶段。

### 当前已能做什么

- 已能从 CRM 的 `groups / customer_groups / customers` 读取外部群、成员、积分榜只读视图。
- 已能在群管理页展示个人榜、群榜、群成员列表。
- 已能在发送中心引用模板和运营编排节点，走预览、批量发送、定时发送。
- 已有运营编排中心，支持 `Plan -> Day -> Node` 的固定流程型运营。

### 当前半能做什么

- “积分相关发布”节点已经在运营编排中有位置，但本质仍是普通消息节点。
- 发送中心已经有批量队列能力，具备承接“每个群单独生成一条积分排行消息”的基础。
- 现有外部群积分榜已经打通 CRM 只读查询，但没有接入 `point_logs` 的时间维度统计。

### 当前还不能做什么

- 不能展示个人/群组的本周积分、本月积分。
- 不能在发送中心基于 CRM 外部群动态生成“每群单独发送”的积分排行内容。
- 不能基于 `point_logs` 自动识别“连续活跃”“突然爆发”“回归用户”等积分运营场景。
- 不能把积分运营真正做成“结构化数据分析 + 话术生成 + 一键发送”的专用流程。

### 当前 blocker

最关键 blocker 有 3 个：

1. 当前积分展示只读 `customers.points / total_points`，没有 `point_logs` 聚合层。
2. 当前发送中心的正式发送目标是本地 `wecom_ops.groups`，CRM 外部群是只读视图，缺少“CRM 群 -> 实际发送目标”的映射层。
3. 当前运营编排是固定 `Day -> Node` 心智，适合周期 SOP，不适合“每日发榜 / 每周复盘 / 冲刺阶段 / 结营当天”这种阶段触发型积分运营。

### 是否偏离蓝图

结论：

`部分新增需求会逼近现有系统边界，但可以通过“读 CRM + 本地发送映射 + 新运营模式”方式收住，不必推翻原蓝图。`

原因：

- 既有蓝图明确把 CRM 外部群定位为“只读运营观察台”，不直接当作正式发送目标。
- 本次需求新增“按群积分排行推送”，如果直接把 CRM 外部群当发送对象，会与现有边界冲突。
- 正确方向不是把 CRM 外部群改成可直发真值，而是新增**映射层**，把“谁需要被运营观察”与“往哪个正式发送群发消息”分开。目前的真实发送方式是我的系统发送到内部群，然后由真人转发到外部群中！

---

## 3. 真值口径

### 3.1 本次正式依赖表

- `customers`
- `customer_groups`
- `groups`
- `point_logs`

### 3.2 关系真值

- `customer_groups.customer_id = customers.id`
- `customer_groups.group_id = groups.id`
- `point_logs.customer_id = customers.id`

### 3.3 积分字段口径

这次需求要特别注意历史命名与本次正式口径的区别。

当前仓库旧文档里曾把：

- `points` 解释为当前可用积分
- `total_points` 解释为累计积分

但**本次需求的 official 口径**已经明确为：

- 前台仅保留一个“当前积分”列
- 该列取值来自 `customers.total_points`

因此本次升级建议统一做字段别名：

- `current_points = customers.total_points`
- `legacy_points = customers.points`

并遵守以下规则：

- 前台不再展示 `points`
- 排行默认按 `current_points` 排
- 群总积分默认按成员 `current_points` 汇总
- `points` 仅作为 support 字段保留在后端，不进入正式 UI 口径

### 3.4 周积分 / 月积分口径

周积分和月积分都来自 `point_logs`，按积分变动时间窗口统计。

建议正式口径如下：

- 周积分：当前周一 `00:00:00` 到下周一 `00:00:00` 之间的净积分变化
- 月积分：当前月 1 日 `00:00:00` 到下月 1 日 `00:00:00` 之间的净积分变化
- 当前时间判断使用服务端配置时区，现阶段按 `Asia/Shanghai` 处理

为了避免消费积分被误算为正数，建议后端统一使用净增量公式：

```sql
CASE
  WHEN point_logs.type = 0 THEN COALESCE(point_logs.num, 0)
  WHEN point_logs.type = 1 THEN -COALESCE(point_logs.num, 0)
  ELSE 0
END
```

说明：

- 如果业务后续确认“周积分 / 月积分只看获得积分，不看消费”，可以再切换成 earned-only 口径。
- 但当前从“积分变动”语义出发，优先用净增量更稳。

### 3.5 群组维度口径

群组的 3 个指标都来自成员汇总：

- `group_current_points = SUM(member.current_points)`
- `group_week_points = SUM(member.week_points)`
- `group_month_points = SUM(member.month_points)`

---

## 4. 方案总览

### 4.1 总体方案

建议拆成三层：

1. `积分指标层`
2. `积分洞察层`
3. `积分运营执行层`

### 4.2 三层职责

#### A. 积分指标层

负责做确定性聚合：

- 当前积分
- 本周积分
- 本月积分
- 群汇总
- 个人榜 / 群榜 / 群成员榜

这层只解决“算得对”。

#### B. 积分洞察层

负责从 `point_logs` 识别运营场景：

- 头部领先
- 连续活跃
- 近期暴涨
- 久未活跃后回归
- 断档后恢复
- 群 PK 走势

这层只解决“该夸谁、该提醒谁、为什么”。

#### C. 积分运营执行层

负责把指标和洞察转成可发送内容：

- 积分排行消息
- 固定风格话术
- 群消息
- 配套 1v1 跟进动作

这层只解决“怎么发、发给谁、发几条”。

---

## 5. 群管理 - 外部群积分展示升级

### 5.1 当前问题

当前实现存在 4 个问题：

1. 个人榜同时展示 `points` 和 `total_points`，与本次正式口径冲突。
2. 群榜同时展示“当前总积分 / 累计总积分”，本质冗余。
3. 成员列表没有周积分 / 月积分。
4. 所有接口都没接入 `point_logs`，导致没有时间维度。

### 5.2 升级后的正式展示字段

#### 个人榜 / 群成员列表

- 当前积分 `current_points`
- 本周积分 `week_points`
- 本月积分 `month_points`
- 所属群组

#### 群榜

- 群总积分 `group_current_points`
- 本周积分 `group_week_points`
- 本月积分 `group_month_points`
- 成员数

### 5.3 后端实现建议

不要继续把所有逻辑堆在 `crm_group_directory.py` 里。

建议拆层：

- `app/services/crm_points_metrics.py`
- `app/services/crm_group_directory.py`

职责建议：

- `crm_points_metrics.py`
  - 负责计算当前周/月时间窗口
  - 负责个人周/月积分聚合
  - 负责群周/月积分聚合
  - 负责输出可复用的榜单查询 SQL
- `crm_group_directory.py`
  - 保留群列表、搜索、群成员、榜单等聚合装配职责
  - 调用指标层服务

### 5.4 API 调整建议

建议保留现有路由前缀，扩展返回字段：

- `GET /api/v1/crm-groups/leaderboard/individual`
- `GET /api/v1/crm-groups/leaderboard/group`
- `GET /api/v1/crm-groups/{group_id}/members`
- `GET /api/v1/crm-groups/stats`

返回字段新增：

- `current_points`
- `week_points`
- `month_points`

同时废弃前台对以下字段的正式展示：

- `points`
- `points_sum`
- `total_points_sum`

内部可以暂时兼容返回，前台不再显示。

### 5.5 前端升级建议

主要改动点：

- `frontend/src/views/Groups/CrmLeaderboard.vue`
- `frontend/src/views/Groups/CrmGroupView.vue`

界面建议：

- 个人榜只保留 3 列：当前积分 / 本周 / 本月
- 群榜只保留 3 列：群总积分 / 本周 / 本月
- 摘要区也补“本周积分总和 / 本月积分总和”
- 对空姓名做兜底，避免继续出现 `30. : 81分` 这类脏展示

兜底建议：

- `display_name = customers.name || CONCAT('未命名成员#', customers.id)`

---

## 6. 发送中心新增“积分排行推送”

### 6.1 目标

新增一种发送逻辑：

`按 CRM 群组生成积分排行消息，并按群逐条发送`

### 6.2 正式规则

- 每个群单独生成 1 条消息
- 只推送有积分的成员
- 默认按 `current_points` 降序
- 只展示积分大于 0 的成员
- 群里如果没有任何正积分成员，则该群不生成排行消息

建议增加可配置项：

- `top_n`
- `rank_metric`
- `speech_style`
- `include_week_month_summary`
- `skip_empty_groups`

其中默认值建议：

- `top_n = 50`
- `rank_metric = current_points`
- `speech_style = professional`
- `include_week_month_summary = true`
- `skip_empty_groups = true`

### 6.3 消息结构建议

每个群的消息由 3 段组成：

1. 群标题与群总分摘要
2. 成员排行榜
3. 固定补充话术

示例结构：

```text
📊 {群名称}
群总分: {group_current_points} (本周: {group_week_points}, 本月: {group_month_points})

🏆 成员排行榜:
{排行正文}

{补充话术}
```

排行正文规则：

- 前三名用奖牌 emoji
- 第 4 名开始用数字序号
- 空名成员要用兜底名称

### 6.4 关键系统边界

这里必须明确：

- CRM 的 `groups` 现在是只读运营观察对象
- 发送中心真正发送的是本地 `wecom_ops.groups`

因此本次要想稳定落地，必须新增：

`CRM 群发送映射层`

建议新增本地表，例如：

`crm_group_send_bindings`

建议字段：

- `id`
- `crm_group_id`
- `crm_group_name_snapshot`
- `local_group_id`
- `enabled`
- `remark`
- `created_at`
- `updated_at`

正式规则：

- CRM 外部群决定“看哪个群的数据”
- 本地发送群决定“往哪里发”
- 两者不能混成一个真值

### 6.5 发送中心交互建议

建议在发送中心新增一种内容来源：

`积分排行`

用户流程建议：

1. 选择“积分排行”
2. 选择 CRM 群范围
3. 选择推送配置
4. 系统自动生成批量队列
5. 用户逐条预览 / 微调
6. 批量发送或定时发送

这里可以直接复用当前发送中心已有的：

- 预览能力
- 批量队列
- 定时发送
- 审批开关

### 6.6 预计改动点

- `frontend/src/views/SendCenter/composables/useSendLogic.ts`
- `frontend/src/views/SendCenter/components/ContentSelector.vue`
- 发送中心主视图相关组件
- 新增后端接口，例如：
  - `POST /api/v1/crm-points/preview-ranking-batch`
  - `POST /api/v1/crm-points/create-ranking-batch`

---

## 7. 基于 point_logs 的积分洞察能力

### 7.1 为什么不能只做简单排行榜

用户给的 Excel 已经说明，这次不是“固定模板 + 直接发榜”。

真实需求是：

- 先发积分
- 再结合榜单变化与近期行为，补上运营话术

也就是说：

`积分运营 = 榜单数据 + 行为识别 + 固定风格话术`

### 7.2 建议抽一个积分洞察服务

建议新增：

- `app/services/crm_points_insights.py`

职责：

- 读取积分窗口数据
- 解析 `point_logs.des`
- 识别典型运营场景
- 输出结构化洞察结果

### 7.3 第一批建议支持的洞察场景

#### 场景 1：头部领先

识别规则：

- 当前积分榜 Top3 / Top6 / Top10

用途：

- 头部激励
- 冲刺期稳排名

#### 场景 2：连续稳定活跃

识别规则：

- 连续 N 天存在积分增长
- 或最近 7 天有较稳定的正向积分流水

用途：

- 表扬自律型成员

#### 场景 3：异常增长 / 突然爆发

识别规则：

- 最近 3 天积分显著高于前 7 天 / 前 14 天基线

用途：

- “黑马”表扬
- 带动群氛围

#### 场景 4：久未活跃后回归

识别规则：

- 前一段时间无正向积分流水
- 最近重新出现连续正向积分流水

用途：

- 回归欢迎
- 放大“现在开始也不晚”的信号

#### 场景 5：断档后重新跟上

识别规则：

- 曾有活跃记录
- 中间出现明显断档
- 最近恢复

用途：

- 温和鼓励

#### 场景 6：群 PK 走势

识别规则：

- 群当前积分
- 群本周积分
- 群本月积分
- 跨群排行变化

用途：

- 团队竞赛感

### 7.4 point_logs.des 的利用建议

从文档看，`des` 已包含业务线索，例如：

- `weight_checkin`
- `habit_checkin`
- `courseId=xx`
- `issue`
- `meal_upload`

建议做一个轻量解析器，提取最近几天积分上涨的主要原因：

- 体重打卡
- 习惯打卡
- 看课
- 餐食上传
- 提交阻碍

这样后面的话术才能从：

“XX 积分涨了”

升级成：

“XX 这几天连续打卡、认真学课、积极上传餐食，所以积分明显上涨”

---

## 8. 运营编排应该怎么改

### 8.1 结论

推荐：

`新增运营编排模式选项，而不是继续把积分运营硬塞进现有纯 Day 模式。`

但不建议一上来重建整套新系统。

最稳的路线是：

`Plan 新增 mode，底层尽量复用现有 Plan / PlanDay / PlanNode，只在 points 模式下改变解释方式并补结构化配置。`

### 8.2 为什么不建议继续纯复用现在的 Day 模型

因为积分运营不是“第 1 天做什么、第 2 天做什么”的单一节奏。

它至少同时包含：

- 每日发榜
- 每周复盘
- 冲刺阶段
- 结营前 1 天
- 结营当天

而且每个节点不是静态文案，而是：

- 先算榜单
- 再识别人群
- 再选话术风格
- 最后生成群发内容和 1v1 配套动作

如果继续强行塞进当前 `Day -> Node`：

- UI 会越来越别扭
- 导入导出规则会越来越硬编码
- “积分相关发布”会继续变成一个大杂烩节点

### 8.3 推荐方案

在 `plans` 上新增：

- `plan_mode`

建议枚举：

- `day_flow`
- `points_campaign`

解释规则：

#### `day_flow`

保持现有模式不变：

- 适合周期 SOP
- 适合早餐提醒 / 午餐提醒 / 晚安总结这类固定节奏

#### `points_campaign`

用于积分运营：

- `PlanDay` 不再强调“第几天”，而是解释为“阶段块 / 投送阶段”
- `day_number` 仅作为排序值
- `title` 显示阶段名
- `focus` 显示阶段目标
- 增加 `trigger_rule_json` 表示触发规则

建议 `trigger_rule_json` 支持：

- `trigger_type = daily`
- `trigger_type = weekly`
- `trigger_type = countdown_range`
- `trigger_type = final_day`
- `trigger_type = manual`

例如：

```json
{
  "trigger_type": "weekly",
  "weekday": 7,
  "time": "19:30"
}
```

### 8.4 节点层建议

`PlanNode` 在 `points_campaign` 模式下不要再只是普通消息节点。

建议 `content_json` 结构化，至少补这些字段：

- `generator_type`
- `scene_rules`
- `top_n`
- `rank_metric`
- `speech_style`
- `include_group_summary`
- `include_1v1_actions`
- `followup_rule`

建议新增的生成器类型：

- `group_ranking_publish`
- `weekly_points_review`
- `surge_user_highlight`
- `comeback_user_welcome`
- `dropout_reactivation`
- `group_pk_broadcast`

### 8.5 为什么推荐“新增 mode + 复用底层”而不是直接上新表

因为当前项目已经有：

- 计划列表
- 计划详情
- 节点引用
- 发送中心桥接
- 导入导出

如果立刻上全新表结构，改动面太大，收口难度高。

所以建议：

- 第一阶段先补 `plan_mode`
- 第二阶段让 `points_campaign` 复用现有三层模型
- 第三阶段如果后续场景继续变复杂，再抽专用表

这是更稳的渐进式方案。

---

## 9. 参考 Excel 的落地方式

### 9.1 两个 sheet 的角色

这份 Excel 实际上已经给出两个层次：

#### sheet 1：话术库

它回答的是：

- 遇到什么运营场景
- 用什么风格的话术

#### sheet 2：投送阶段节点

它回答的是：

- 在什么阶段
- 什么时候发
- 这次发什么类型的内容
- 需要配套什么 1v1 动作

### 9.2 在系统里的映射建议

建议系统内拆成两个对象：

#### A. 积分话术模板库

按 scene + style 管理：

- `scene_key`
- `scene_name`
- `style_key`
- `template_text`

#### B. 积分运营阶段剧本

按 stage + trigger + action 管理：

- `stage_key`
- `stage_name`
- `trigger_rule_json`
- `action_nodes`

这样就不会把“话术库”和“运营阶段”混在一起。

---

## 10. 推荐实施顺序

### Phase A：积分指标层打通

目标：

- 群管理页先展示对

交付：

- 周积分 / 月积分聚合
- 个人榜 / 群榜 / 群成员列表字段升级
- 统一 `current_points` 口径

### Phase B：发送中心积分排行批量生成

目标：

- 能按群逐条生成并发送积分排行

交付：

- CRM 群发送映射
- 排行批量预览接口
- 批量发送接入

### Phase C：积分洞察与动态话术

目标：

- 从“只发榜”升级成“发榜 + 场景运营”

交付：

- `point_logs` 场景识别
- 话术模板库
- 组合生成逻辑

### Phase D：运营编排新增 points_campaign 模式

目标：

- 让积分运营成为可配置、可复用、可发布的正式编排模式

交付：

- `plan_mode`
- 阶段触发配置
- 结构化积分节点编辑器

---

## 11. 验收标准

### 群管理页验收

- 个人榜只显示当前积分 / 本周 / 本月
- 群榜只显示群总积分 / 本周 / 本月
- 数据结果与 `point_logs` 窗口统计一致

### 发送中心验收

- 可按群生成积分排行批量队列
- 每个群单独预览
- 0 分成员不会进入排行正文
- 未配置发送映射的 CRM 群不会误发

### 积分运营验收

- 至少支持 3 类洞察场景自动识别
- 可将排行榜与固定话术拼接成正式发送内容
- 可为不同风格输出不同版本文案

### 启动验收

后续进入开发阶段后，必须补以下验证：

- 后端启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 前端启动：`cd frontend && npm run dev`

---

## 12. 当前最值得继续推进的三条线

### 第一优先级

先做积分指标层。

原因：

- 这是所有展示、排行、运营分析的基础真值。

### 第二优先级

补 CRM 群发送映射。

原因：

- 不解决发送目标映射，发送中心的积分排行只能停在预览层。

### 第三优先级

做 `points_campaign` 模式的最小可用版。

原因：

- 现有 `score_publish` 节点已经明显不够用，但也没必要直接重做整套系统。

---

## 13. 本轮结论

这次升级不能只理解成“给榜单多加两列”。

它实际上是一次从：

`静态积分展示`

升级到：

`积分指标 + 积分洞察 + 积分运营执行`

的能力扩展。

最稳的落地方式不是推翻当前系统，而是：

1. 先把 `point_logs` 聚合层补起来
2. 再把发送中心接成“按群批量生成”
3. 最后给运营编排新增 `points_campaign` 模式

这样能在不破坏现有 Day 流程型运营的前提下，把积分运营做成正式能力，而不是继续堆在一个通用节点里。
