# CRM 用户全景档案与 AI 问答集成方案评审稿

> 日期：2026-04-24
>
> 文档状态：评审后修订 / candidate design
>
> 结论口径：本文档用于指导后续研发拆分和评审，不代表功能已经正式完成；本文中的数据字段、表关系与业务口径以 `docs/CRM/mfgcrmdb_database_explanation.md` 为 support 依据，落地前仍需在真实 CRM 库上做抽样查询、性能验证和权限校验。

---

## 1. 评审结论

### 1.1 方向是否合理

整体方向合理，值得推进。

真正有价值的不是“把 CRM 500 多个字段塞给 AI”，而是把教练日常最耗时的三件事系统化：

1. 看见：快速看到某个客户当前健康状态、风险点、目标、近期执行情况。
2. 理解：把散落在 CRM 多张表里的指标压缩成稳定、可解释的客户上下文。
3. 决策：让教练在系统内直接问“基于这个客户，下一步怎么说/怎么跟/怎么调整”，不再手工拼 Prompt。

这条线如果落地得当，可以把当前企微群运营后台从“消息发送工具”升级成“教练决策辅助台”。方向成立。

### 1.2 原稿的主要问题

原稿最大的问题不是想得太小，而是把“字段全景罗列”误当成“功能落地方案”。

需要收口的点：

1. 字段明细过多，占据主体，但没有明确哪些字段进入 MVP、哪些只是长期 support。
2. 没有区分 `official / support / candidate / formal / overlay`：CRM 字段清单是 support，不是本系统已实现的 official 能力。
3. 对 AI 能力写得偏理想化，例如“毫秒级响应”“function calling 回调”目前都不是仓库里的正式真值。
4. 缺少权限、隐私、医疗安全、审计和人工复核规则。
5. 缺少接口、schema、缓存、降级和验收标准，开发团队很难直接排期。
6. 没有和当前仓库真值对齐：现在已有的是 `ai_polish.py` 的 aihubmix 调用、CRM 群/积分只读聚合、CRM admin 登录镜像；还没有 customer 360 或客户级 AI 会话模块。

### 1.3 修订后的产品定义

本功能建议定义为：

> 在运营后台内新增“CRM 客户 360 档案 + AI 教练助手”。系统只读聚合 CRM 客户上下文，生成版本化、可预览、可剪枝的 `CustomerProfileContext`，再通过 aihubmix 生成教练可复核的建议草稿。AI 输出永远是 coach-facing draft，不直接写回 CRM，也不直接面向客户自动发送。

---

## 2. 当前正式真值

### 2.1 仓库中已经存在的能力

1. AI 配置已存在：
   - `app/config.py`
   - `ai_base_url = https://aihubmix.com/v1`
   - `ai_model = gpt-4o-mini`
   - `ai_api_key` 由环境变量配置

2. AI 调用样板已存在：
   - `app/services/ai_polish.py`
   - 使用 OpenAI-compatible `/chat/completions`
   - 当前只服务企业微信群消息润色，不包含客户上下文注入

3. CRM 外部库只读查询已存在：
   - `app/services/crm_group_directory.py`
   - `app/routers/api_crm_groups.py`
   - `app/routers/api_crm_points.py`
   - 目前正式覆盖群、成员、积分排行、积分洞察

4. CRM 管理员登录镜像已存在：
   - `app/services/crm_admin_auth.py`
   - 外部 CRM admin 登录成功后同步到本地 `users`
   - 本地 `users.id` 仍是后台权限和审计主键

### 2.2 仓库中尚未存在的能力

以下都还不是 official 能力：

1. 客户级 360 档案页面。
2. 客户级 profile 聚合 API。
3. 客户级 AI 上下文 schema。
4. 客户级 AI 会话、审计、token 预算和安全门禁。
5. 按教练负责关系限制可查看客户范围。
6. AI 输出后的一键复制/进入发送中心/生成跟进动作链路。

### 2.3 数据依据状态

`docs/CRM/mfgcrmdb_database_explanation.md` 是当前最完整的 support 材料。它已经覆盖：

1. `customers` 是客户主实体。
2. `customer_info` 更像画像版本表，当前有效记录需按 `is_archived = 0` 和最新记录取值。
3. 健康、设备、习惯、计划、课程、AI 会话、提醒、服务、积分都存在各自事实表。
4. CRM 库几乎没有强外键，很多关系只能按业务字段推断。

因此本报告不再重复 500 多个字段清单，而是定义“哪些字段在什么阶段被系统正式使用”。

---

## 3. 目标与边界

### 3.1 本期目标

本期目标不是做一个万能医疗 AI，也不是复制 CRM 后台。

本期目标是打通最小闭环：

1. 教练能搜索并打开某个 CRM 客户。
2. 系统能展示客户基础档案、关键风险、目标、近期健康和执行摘要。
3. 教练能看到 AI 将要使用的上下文预览。
4. 教练能向 AI 提问，获得可复核的建议草稿。
5. 系统能记录调用日志、上下文版本、token 用量、安全拦截和人工复核状态。

### 3.2 明确不做

本期不做：

1. 不写回 CRM 客户资料。
2. 不替代医生诊断或处方。
3. 不把 AI 输出自动发送给客户。
4. 不把 30+ 张表的全量原始 JSON 直接塞进 Prompt。
5. 不做 CRM 全量数据同步入本地库。
6. 不承诺 aihubmix function calling 已可用；第一期按普通 chat completion 设计，工具回调作为 P2 candidate。
7. 不把账号凭证与无业务含义的系统标识传给 AI（密码、盐、session token、openid/unionid 原值、登录 IP、头像原始 URL）。业务身份字段（姓名、称呼、手机号、城市、地址、紧急联系人等）允许进入 AI context 以保证结果的相关性与可用性；第一期不做值级脱敏（例如不做手机号掩码），只做字段白名单控制。

### 3.3 成功标准

功能可视为本期可验收，需要同时满足：

1. 客户档案首屏能在 2 秒内返回核心摘要。
2. 标准 AI 问答的上下文控制在可解释预算内，默认不超过约 30000 tokens。
3. 教练能在 UI 上看到“AI 使用了哪些模块”，并可手动勾选展开 1-2 个重点模块。
4. 有过敏、禁忌、疾病风险时，AI 输出必须显式尊重这些限制。
5. AI 输出被标记为“建议草稿”，需要教练确认后才能复制或进入发送链路。
6. 所有调用都有审计记录，包括操作者、本地用户、CRM customer_id、上下文版本、模型、token 用量、耗时和安全结果。

---

## 4. 用户场景

### 4.1 场景 A：教练给单个客户写次日跟进话术

教练在客户档案页输入：

```text
基于他最近 3 天的血糖、睡眠和饮食情况，帮我写一段明早发给他的提醒，语气温和一点。
```

系统自动注入：

1. 基础信息：年龄、性别、BMI、目标。
2. 安全底线：疾病史、过敏、运动损伤、医学禁忌。
3. 近期摘要：近 3 天血糖、饮食、睡眠、运动。
4. 执行状态：最近打卡、积分、任务完成。

AI 返回教练可编辑草稿，不直接发送。

### 4.2 场景 B：教练快速理解一个新接手客户

教练打开客户 360 页，系统展示：

1. 这个客户是谁。
2. 当前目标是什么。
3. 最需要注意的风险是什么。
4. 最近 7 天执行得怎样。
5. 哪些数据缺失或过期。

AI 支持一键问题：

1. “总结这个客户的当前服务重点。”
2. “列出本周最值得跟进的 3 个问题。”
3. “把注意事项整理成教练交接备注。”

### 4.3 场景 C：运营从群积分榜跳到个人跟进

当前系统已经有 CRM 群积分排行和 1v1 跟进动作。后续可以在某个成员旁边增加“查看档案 / AI 跟进建议”。

这条链路不要让 AI 重新查询全量群，而是只携带当前客户上下文和当前运营场景：

```json
{
  "entry_scene": "points_ranking_followup",
  "crm_group_id": 1017,
  "customer_id": 12345,
  "reason": "最近 3 天积分回暖，但饮食记录缺失"
}
```

---

## 5. 数据分层设计

### 5.1 原则

客户 360 的取数必须按“业务问题”分层，不按“表数量”堆叠。

正式原则：

1. 宽度保留：每个关键维度至少给 AI 一句摘要，避免只看单点指标。
2. 深度可选：只有当前问题相关的 1-2 个模块展开明细。
3. 数据可追溯：每个模块都返回 `source_tables`、`range`、`freshness`。
4. 缺失要显式表达：不能把“没查到”写成“正常”。
5. 白名单而非脱敏：第一期采用字段白名单控制 AI 可见字段，不做值级脱敏。业务身份字段（姓名、手机号、地址、紧急联系人等）允许进入上下文，以保证教练话术的具体性；凭证与无业务含义的系统标识（密码、盐、openid/unionid 原值、登录 IP、avatar URL、原始 JSON）一律排除。

### 5.2 MVP 数据域

P0 必须纳入：

| 数据域 | 推荐来源 | 用途 | 默认深度 |
|---|---|---|---|
| 基础档案 | `customers` | 身份、年龄、性别、身高体重、状态 | 精简 |
| 当前画像 | `customer_info` 当前有效记录 | 疾病、过敏、目标、偏好、运动损伤、处方摘要 | 精简 + 风险字段完整 |
| 最近健康摘要 | `customer_health` | 体重、血压、血糖、饮食、睡眠、运动、症状 | 近 7 天统计 |
| 体成分摘要 | `body_comp` | BMI、体脂、肌肉、内脏脂肪、身体评分 | 最新 + 30 天趋势 |
| 积分与活跃 | `point_logs` + `customers.points/total_points` | 参与度、打卡活跃、近期行为 | 近 14 天聚合 |
| 所属群 | `customer_groups` + `groups` | 当前服务场景和运营入口 | 精简 |
| 负责教练 | `customer_staff` + `admins` | 权限与服务关系 | 当前有效关系 |

P1 建议纳入：

| 数据域 | 推荐来源 | 用途 |
|---|---|---|
| 习惯执行 | `customer_habits` + `customer_checkin_records` | 判断依从性和卡点 |
| 干预计划 | `customer_plans` + `customer_todos` | 判断当前阶段任务 |
| 课程学习 | `customer_course_plan` + `customer_course_record` | 判断教育内容完成情况 |
| 服务问题 | `service_issues` + `service_log` | 判断未解决问题 |
| 标签画像 | `customer_label_values` + `label_definition` | 补充用户特征和匹配逻辑 |

P2 再考虑：

| 数据域 | 推荐来源 | 说明 |
|---|---|---|
| 设备原始数据 | `device_*` / `huami_*` | 点位多、体量大，默认只做聚合摘要 |
| AI 历史对话 | `chats` + `messages` | 涉及旧系统语义和隐私，需要单独审计 |
| 餐食识别 | `meal_tasks` | 可用于饮食明细，但要注意图片 URL 和识别置信度 |

### 5.3 当前有效 `customer_info` 取值规则

`customer_info` 不应简单按 `customer_id` 取第一条。

建议规则：

```sql
SELECT *
FROM customer_info
WHERE customer_id = ?
  AND (is_archived = 0 OR is_archived IS NULL)
ORDER BY id DESC
LIMIT 1
```

如果未命中，再降级取同客户最新一条，并在 `source_status` 中标记：

```json
{
  "module": "customer_info",
  "status": "fallback_latest_archived_or_unknown",
  "warning": "未找到明确未归档画像，已取最新记录作为参考"
}
```

### 5.4 AI 上下文字段绑定分级

本节锁定第一版可以进入 AI 上下文的预备字段。后续开发时必须按这里的白名单实现，不允许因为附录 A 里字段存在就直接传给 AI。

字段分级：

| 分级 | 含义 | 是否进入 AI | 典型用途 |
|---|---|---|---|
| `always` | 安全底线和最小身份画像 | 必传 | 过敏、疾病、年龄、性别、BMI、当前目标 |
| `default` | 标准问答默认摘要 | 默认传 | 近期健康趋势、执行状态、积分活跃 |
| `expandable` | 教练勾选或场景命中后展开 | 按需传 | 7 天饮食明细、血糖明细、任务明细 |
| `display_only` | 页面可展示或权限判断，但不进入 AI | 不传 | 内部主键（负责教练 ID、所属群 ID）、avatar 原始 URL |
| `never` | 禁止进入 AI（凭证与无业务含义的系统标识） | 不传 | 密码、盐、session token、openid/unionid 原值、登录 IP、未经解析的原始 JSON |

### 5.5 P0 AI 上下文绑定字段白名单

P0 字段目标是覆盖“教练看客户 + 写跟进建议”的最小闭环。字段要先被加载到本地模块 payload，再经过字段白名单校验、聚合和规范化后进入 `CustomerProfileContext`。

| 模块 key | 源表 | 源字段 | 规范化上下文字段 | 绑定级别 | 加载与转换规则 |
|---|---|---|---|---|---|
| `basic_profile` | `customers` | `id`, `name`, `title`, `gender`, `birthday`, `height`, `weight`, `status`, `tags`, `current_plan_id`, `is_cgm`, `compliance_level`, `survey_done`, `points`, `total_points`, `severity`, `created_at`, `updated_at` | `basic.customer_ref`, `basic.display_name`, `basic.age`, `basic.gender`, `basic.height_cm`, `basic.weight_kg`, `basic.bmi`, `basic.crm_status`, `basic.tags`, `basic.current_plan_id`, `basic.has_cgm`, `basic.compliance_level`, `basic.severity`, `engagement.points_current`, `engagement.points_total`, `data_freshness.basic` | `always` | `birthday` 转年龄；`height/weight` 计算 BMI；`name/title` 只生成教练可识别称呼，不传手机号；状态码转枚举文本。 |
| `safety_profile` | 当前有效 `customer_info` | `health_condition`, `health_condition_user`, `genetic_history`, `allergies`, `medical_history`, `sport_injuries`, `recipel`, `doctor_recipel`, `food_recipel`, `sport_recipel`, `sleep_recipel`, `nutrition_recipel`, `updated_at` | `safety.health_condition_summary`, `safety.medical_history`, `safety.genetic_history`, `safety.allergies`, `safety.sport_injuries`, `safety.prescription_summary`, `safety.contraindications`, `safety.missing_critical_fields`, `data_freshness.safety` | `always` | 安全字段不参与剪枝；JSON 处方字段只做摘要，不展开完整原文；缺失疾病/过敏/运动损伤时写入 `missing_critical_fields`。 |
| `goals_preferences` | 当前有效 `customer_info` | `goals`, `goal_weight`, `goal_hr`, `goal_gluc`, `goal_bp`, `diet_preference`, `sport_preference`, `sport_interests`, `sleep_quality`, `remark` | `goals.primary_goals`, `goals.target_weight_kg`, `goals.target_heart_rate`, `goals.target_glucose`, `goals.target_blood_pressure`, `preferences.diet`, `preferences.exercise`, `preferences.sleep`, `preferences.notes_summary` | `default` | `remark` 只能摘要化，禁止把长 JSON 原样传入；目标值保留单位。 |
| `health_summary_7d` | `customer_health` | `record_date`, `weight`, `waist`, `blood_sbp`, `blood_dbp`, `fbs`, `pbs`, `hba1c`, `rbs`, `water_ml`, `sleep_min`, `sleep_des`, `step_count`, `symptoms`, `tonic`, `food_intake`, `kcal`, `cho`, `fat`, `protein`, `fiber`, `kcal_out`, `stress`, `medication`, `meal_plans`, `created_at`, `updated_at` | `recent_trends.health_7d`, `recent_trends.glucose`, `recent_trends.blood_pressure`, `recent_trends.weight`, `recent_trends.sleep`, `recent_trends.activity`, `recent_trends.diet`, `recent_trends.symptoms`, `recent_trends.medication_summary` | `default` | 默认只传近 7 天聚合：均值、最大、最小、异常天数、最近值、趋势；`medication/meal_plans` 只摘要，不给用药调整建议。 |
| `health_detail_expansion` | `customer_health` | `breakfast_data`, `lunch_data`, `dinner_data`, `snack_data`, `blood_suger`, `pressure_data`, `sleep_data`, `sports` | `selected_expansions[].payload` | `expandable` | 只有教练勾选或场景命中时加载；每次最多展开 2 类；每类只取近 7 天，优先转统计和代表性样本，不传完整原始 JSON。 |
| `body_comp_latest_30d` | `body_comp` | `date`, `weight`, `bmi`, `bmi_std`, `bmr`, `body_fat`, `body_fat_std`, `vis_fat`, `vis_fat_std`, `muscle`, `muscle_std`, `skeletal`, `smi`, `whr`, `heart_rate`, `body_type`, `body_health`, `body_age`, `body_score`, `kcal`, `water_pct`, `protein_pct`, `updated_at` | `current_status.body_comp_latest`, `recent_trends.body_comp_30d` | `default` | 默认传最新一次 + 30 天趋势摘要；不传四肢分段脂肪/肌肉明细，除非后续新增专门场景。 |
| `points_engagement_14d` | `customers`, `point_logs` | `customers.points`, `customers.total_points`, `point_logs.type`, `point_logs.num`, `point_logs.source`, `point_logs.des`, `point_logs.category`, `point_logs.created_at` | `engagement.points_current`, `engagement.points_total`, `engagement.points_14d`, `engagement.active_days_14d`, `engagement.activity_category_counts`, `engagement.latest_positive_events` | `default` | 只看近 14 天，默认传聚合；明细最多 10 条最新正向事件。多群排行联动时可复用现有积分洞察口径。 |
| `service_scope` | `customer_groups`, `groups`, `customer_staff`, `admins` | `customer_groups.group_id`, `customer_groups.role`, `customer_groups.joined_at`, `groups.name`, `customer_staff.admin_id`, `customer_staff.star_level`, `customer_staff.start_at`, `customer_staff.end_at`, `admins.real_name`, `admins.nick_name`, `admins.username` | `service_context.group_names`, `service_context.group_count`, `service_context.current_coach_names`, `service_context.staff_assignment`, `permissions.assignment_basis` | `default` / `display_only` | `group_id/admin_id` 用于权限和溯源；AI 默认只拿群名摘要、负责教练称呼和服务关系，不拿内部 ID。 |

### 5.6 P1/P2 可扩展绑定字段

P1 字段在 P0 稳定后纳入，优先服务“为什么这个客户执行不好”和“下一步怎么跟”。

| 模块 key | 源表 | 源字段 | 规范化上下文字段 | 绑定级别 | 加载与转换规则 |
|---|---|---|---|---|---|
| `habit_execution_14d` | `customer_habits`, `customer_checkin_records`, 可选 join `habits` | `customer_habits.habit_id`, `status`, `target_min`, `fallback_info`, `current_streak`, `fallback_days`, `customer_checkin_records.checkin_status`, `checkin_date`, `notes` | `execution.habits_14d`, `execution.current_streaks`, `execution.missed_habits`, `execution.blockers_summary` | `default` in P1 | 默认传完成率、连续天数、漏打卡项；`notes` 只摘要，最多保留 3 条代表性备注。 |
| `plan_todos_14d` | `customer_plans`, `customer_todos` | `customer_plans.id`, `title`, `description`, `status`, `total_days`, `start_date`, `pause_date`, `resume_date`, `customer_todos.todo_date`, `type`, `status`, `day_num`, `items`, `comp_at` | `execution.current_plan`, `execution.todos_14d`, `execution.todo_completion_rate`, `execution.overdue_items_summary` | `default` in P1 | 以当前计划和近 14 天待办为主；`items` JSON 不原样传，先转任务标题/完成状态摘要。 |
| `course_learning_30d` | `customer_course_record`, 可选 join `course` | `course_id`, `status`, `start_at`, `completed_at`, `study_seconds`, `assign_date` | `education.course_progress_30d`, `education.completed_courses`, `education.pending_courses` | `optional` in P1 | 默认只传学习进度摘要；课程标题需 join `course` 后再进入上下文。 |
| `service_issues_open` | `service_issues`, `service_log` | `service_issues.name`, `description`, `status`, `solution`, `admin_id`, `completed_at`, `created_at`; `service_log.msg`, `type`, `created_at` | `service_context.open_issues`, `service_context.recent_service_logs`, `service_context.resolved_issue_summary` | `optional` in P1 | 默认只传未解决问题数量和最近 3 条摘要；内部处理人 ID 不传 AI。 |
| `ai_decision_labels` | `customer_label_values`, `label_definition` | `label_key`, `label_value`, `sample_data`, `label_definition.is_ai_decision`, `ai_decision_reason` | `labels.ai_decision_labels`, `labels.behavior_traits`, `labels.coach_matching_hints` | `optional` in P1 | 只允许 `label_definition.is_ai_decision=1` 或白名单 label 进入 AI；`sample_data` 默认不传，除非已脱敏摘要。 |
| `device_summary` | `customer_device`, `device_bp_data`, `device_fat_data`, `huami_*` | 设备绑定、血压、体脂、活动、睡眠、心率等核心统计字段 | `devices.connected_devices`, `recent_trends.device_metrics` | `expandable` in P2 | 只做设备级聚合，不传分钟级点位；默认不纳入 P0/P1。 |
| `ai_history_summary` | `chats`, `messages` | `title`, `mode`, `role`, `action`, `content`, `created_at` | `ai_history.recent_topics`, `ai_history.previous_advice_summary` | `optional` in P2 | 需要单独隐私评审；不传历史对话全文，只传摘要和最近主题。 |

### 5.7 禁止进入 AI 的字段

第一期采用字段白名单而非值级脱敏。姓名、手机号、城市、地址、紧急联系人等业务身份字段**允许进入 AI context**，以保证教练话术的可用性。以下字段仍然禁止进入 AI prompt，原因是凭证安全或对 AI 无业务价值：

| 来源 | 禁传字段 | 禁传原因 |
|---|---|---|
| `customers` | `last_login_ip`, `user_id` 原值, `huami_user_id` 原值, `avatar` 原始 URL | 系统内部标识或无业务语义 |
| `users` | 密码、盐、session token、登录态相关字段 | 凭证 |
| `oauth_users` | `openid`, `unionid`, `avatar` 原始 URL | 第三方身份凭证，AI 不需要 |
| `admins` | `password`, `salt`, `wxwork`, `settings` | 凭证与配置 |
| `notify` | `raw_data` 中的原始投递 payload | 可能含未脱敏的第三方 token |
| 任意 JSON 字段 | 未经解析、摘要的原始 JSON 整体 | 不可控长度与结构，易污染 prompt |

说明：

1. 本清单只管控“字段是否进入 prompt”，不对值做掩码处理；第二期若上线对外分享/截图能力再考虑值级脱敏。
2. 如果后续确实需要放开新字段给 AI，仅需改本章白名单与 `ContextFieldBinding` 注册表，不需要改安全门禁代码。
3. admin 角色与教练角色在字段白名单上一致；角色差异只体现在“可见客户范围”，见第 11 章。

### 5.8 绑定字段到上下文的最终形态

最终实现中不要把“数据库字段”直接绑定到 prompt，而是绑定到稳定的上下文路径：

```text
CRM source field -> ContextFieldBinding -> ModulePayload -> CustomerProfileContextV1 -> Prompt serializer
```

落地文件（见 §7.1 独立子包）：

```text
app/crm_profile/
  schemas/
    context.py              # CustomerProfileContextV1 / ModulePayload / SourceStatus
    bindings.py             # ContextFieldBinding / ContextModuleSpec
  services/
    bindings_registry.py    # CONTEXT_MODULES
    profile_loader.py       # CRM 查询与聚合
    context_builder.py      # 构建上下文与预算控制
```

字段绑定对象建议：

```python
@dataclass(frozen=True)
class ContextFieldBinding:
    source_table: str
    source_field: str
    context_path: str
    ai_policy: Literal["always", "default", "expandable", "display_only", "never"]
    sensitivity: Literal["normal", "health", "pii", "internal"]
    transform: str
    phase: Literal["P0", "P1", "P2"]
```

模块绑定对象建议：

```python
@dataclass(frozen=True)
class ContextModuleSpec:
    key: str
    phase: Literal["P0", "P1", "P2"]
    default_mode: Literal["required", "summary", "optional", "expandable"]
    source_tables: tuple[str, ...]
    field_bindings: tuple[ContextFieldBinding, ...]
    loader: str
    cache_ttl_seconds: int
    timeout_ms: int
    token_budget: int
    max_rows: int | None = None
```

第一版固定采用代码注册表，不做数据库可配置字段绑定。原因：

1. 健康和隐私字段需要强管控，不能让后台运营自由勾选字段直连 AI。
2. 代码注册表更容易 code review、测试和审计。
3. 后续若要做可配置，也应只配置“模块开关”和“场景 preset”，不开放任意字段。

---

## 6. `CustomerProfileContext` 版本化 Schema

### 6.1 顶层结构

建议后端以 Pydantic schema 固定输出结构，禁止路由层手拼松散 dict。

```json
{
  "schema_version": "customer_profile_context.v1",
  "binding_version": "context_binding_registry.v1",
  "customer_id": 12345,
  "generated_at": "2026-04-24T16:00:00+08:00",
  "generated_by_user_id": 7,
  "entry_scene": "customer_profile",
  "build_plan": {
    "required_modules": ["basic_profile", "safety_profile"],
    "summary_modules": ["goals_preferences", "health_summary_7d", "body_comp_latest_30d", "points_engagement_14d", "service_scope"],
    "expansion_modules": []
  },
  "token_budget": {
    "prompt_budget": 30000,
    "estimated_prompt_tokens": 2200
  },
  "data_freshness": {
    "basic": "2026-04-24T09:12:00+08:00",
    "health_7d": "2026-04-23",
    "points_14d": "2026-04-24T08:30:00+08:00"
  },
  "basic": {},
  "safety": {},
  "goals": {},
  "current_status": {},
  "recent_trends": {},
  "engagement": {},
  "service_context": {},
  "selected_expansions": [],
  "module_status": [],
  "source_status": [],
  "redactions": []
}
```

### 6.2 必传的 safety block

任何 AI 问答都必须携带 safety block，即使用户问题只是在写鼓励话术。

```json
{
  "safety": {
    "medical_history": ["2型糖尿病"],
    "allergies": ["虾蟹"],
    "sport_injuries": ["膝关节不适"],
    "contraindications": ["避免高强度跳跃类运动"],
    "medication_summary": "近期用药记录存在，但不展开剂量",
    "risk_level": "medium",
    "missing_critical_fields": []
  }
}
```

规则：

1. 过敏、禁忌、严重疾病字段不参与 token 剪枝。
2. 如果关键安全字段缺失，必须写入 `missing_critical_fields`，并要求 AI 保守回答。
3. AI 不允许输出诊断、处方、停药建议或替代医生判断。

### 6.3 展开模块结构

UI 允许教练选择展开模块：

1. `glucose_detail_7d`
2. `diet_detail_7d`
3. `sleep_detail_14d`
4. `exercise_detail_14d`
5. `points_logs_14d`
6. `todo_detail_14d`

展开模块必须有预算上限。例如：

```json
{
  "selected_expansions": [
    {
      "key": "glucose_detail_7d",
      "range": "7d",
      "budget": "compact",
      "payload": {
        "fasting_glucose": {
          "avg": 7.1,
          "min": 6.4,
          "max": 8.2,
          "trend": "slightly_high",
          "exception_days": 2
        }
      }
    }
  ]
}
```

---

## 7. Context Builder 设计

### 7.0 架构一页图

一张图概括本功能从 UI 到 AI 的端到端链路，帮助负责人与跨团队评审快速对齐：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 前端 frontend/src/views/crm_profile/                                         │
│   搜索 → 客户 360 → AI 侧边栏（模块勾选 / 上下文预览 / 草稿动作）             │
└────────────┬─────────────────────────────────────────────────────────────────┘
             │  HTTP (本地后台鉴权)
             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ app/crm_profile/router.py  （唯一 HTTP 入口 / 无业务逻辑）                   │
└────────────┬─────────────────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ services/permission.py                                                       │
│   local users.id → users.crm_admin_id → CRM admins.id                        │
│     → customer_staff ∪ group_coachs×customer_groups                          │
│     → visible_customer_ids (set[int])  ［5min TTL cache］                    │
└────────────┬─────────────────────────────────────────────────────────────────┘
             │  通过 assert_can_view
             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ services/context_builder.py                                                  │
│   resolve_context_plan(entry_scene, expansions)                              │
│     → required + summary + expansion 模块列表                                │
│                                                                              │
│ services/profile_loader.py ← CRM 只读连接（每模块独立超时 / TTL cache）      │
│   ContextModule × {basic, safety, goals, health_7d, body_comp,               │
│                    points_14d, service_scope, expansions...}                 │
│                                                                              │
│ validate_field_whitelist()   ← §5.7 禁传字段扫描（不做值级脱敏）             │
│ compact_serialize()          ← 预算裁剪 + schema_version + binding_version   │
│                             → CustomerProfileContextV1 + context_hash        │
└────────────┬─────────────────────────────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ services/ai_coach.py                                                         │
│   前门禁（safety 必须存在 / 禁传字段 / token 预算）                          │
│     → app/clients/ai_chat_client.py → aihubmix /chat/completions             │
│       ← 输出                                                                 │
│   后门禁（过敏食材 / 处方表达 → requires_medical_review）                    │
│     → audit.py → 本地 crm_ai_sessions / _messages / _context_snapshots /     │
│                        _guardrail_events                                     │
└────────────┬─────────────────────────────────────────────────────────────────┘
             │
             ▼
            教练在 UI 上看到结构化草稿 + 安全提示 + 可执行动作（复制 / 转发送中心 / 标记复核）
```

几个架构要点再强调一遍：

1. `app/crm_profile/` 是**唯一一处新增代码聚集地**，对外只导出 router。
2. 所有外部 CRM 查询集中在 `profile_loader.py`，其他层不直接拿 CRM 连接。
3. AI 上下文经过 `ContextBuildPlan → ModulePayload → CustomerProfileContextV1 → compact_json` 四跳，每跳可审计、可回放。
4. 审计与 CRM 解耦，落本地 `crm_ai_*` 表；拔掉功能时只需删子包 + drop 表。

### 7.1 服务拆分与独立子包

本功能以**独立子包**的形式落地，所有新增模块集中在 `app/crm_profile/` 路径下，与现有的群/积分/消息润色功能在目录上完全隔离，由一个模块边界文件对外暴露。

目录结构建议：

```text
app/
  crm_profile/                     # 客户 360 + AI 教练助手子包（独立）
    __init__.py                    # 对外出口：只暴露 router 和一小组 schema
    router.py                      # == 原 api_crm_customers.py，唯一 HTTP 入口
    schemas/
      __init__.py
      context.py                   # CustomerProfileContextV1 / ModulePayload
      bindings.py                  # ContextFieldBinding / ContextModuleSpec
      api.py                       # 请求/响应 Pydantic 模型
      enums.py                     # §9.6 枚举定义（单一来源）
    services/
      __init__.py
      permission.py                # 权限判定：resolve_visible_customers / assert_can_view
      profile_loader.py            # CRM 只读查询与聚合（内部使用）
      context_builder.py           # 构建 CustomerProfileContextV1
      bindings_registry.py         # CONTEXT_MODULES 注册表
      modules/                     # 每个 ContextModule 一个文件
        basic_profile.py
        safety_profile.py
        goals_preferences.py
        health_summary.py
        body_comp.py
        points_engagement.py
        service_scope.py
      ai_coach.py                  # Prompt 编排 + 安全门禁 + 审计
      audit.py                     # 审计落库（本地表）
    models.py                      # crm_ai_sessions / crm_ai_messages 等本地 ORM
  clients/
    ai_chat_client.py              # 通用 aihubmix/OpenAI-compatible 客户端（新增）
```

职责划分：

1. `crm_profile/router.py`
   - 只处理参数、权限调用、调 service、返回 schema。不写业务逻辑。

2. `services/permission.py`
   - 封装 §11 的权限判定（本地教练映射 → 远程 CRM 关系查询）。通过 `assert_can_view(user, customer_id)` 和 `resolve_visible_customers(user)` 对外。

3. `services/profile_loader.py`
   - 负责 CRM 只读连接、SQL、字段清洗、聚合。不构造 context。

4. `services/context_builder.py`
   - 负责把聚合结果按 `bindings_registry` 转为 `CustomerProfileContextV1`。

5. `clients/ai_chat_client.py`
   - 抽出通用 aihubmix chat client。**第一期不替换 `ai_polish.py`」；等新 client 稳定后再作为 P2 追加合并动作，避免群消息润色回归。

6. `services/ai_coach.py`
   - 负责 prompt 编排、安全门禁、调用 AI、写 audit。不直接操作 CRM 连接。

#### 7.1.1 架构独立性硬规则

为保证本功能“可独立上线、可独立下线、不拖累其他模块”，所有线程必须遵守：

1. **入口单一**：`app/crm_profile/__init__.py` 只导出 `router`、对外 schema、`init_models()`。其他模块不能 `import app.crm_profile.services.*`。
2. **单向依赖**：`crm_profile` 可以 import `app/config.py`、`app/db.py`、`app/clients/*`、`app/deps/auth.py`；禁止反向 import `app/services/crm_group_directory.py`、`app/services/crm_admin_auth.py` 等其他业务模块的内部函数，必要时只走其对外 API 层或共享 `clients/*`。
3. **数据隔离**：本功能新增的本地表（`crm_ai_sessions` / `crm_ai_messages` / `crm_ai_context_snapshots` / `crm_ai_guardrail_events`）都以 `crm_ai_` 为前缀，仅在本子包内被读写；不复用其他模块的表，其他模块也不读写这几张表。
4. **配置隔离**：所有新增配置项以 `CRM_PROFILE_` / `AI_COACH_` 为前缀，与 `AI_` / `CRM_` 通用配置区分。
5. **可开关**：`app/config.py` 新增 `crm_profile_enabled`；关闭时 router 不挂载、前端隐藏入口，不影响其他功能。
6. **前端同构**：`frontend/src/views/crm_profile/` 独立目录，store / api / components 不与其他页面共享状态；可单独编译、单独删除。
7. **可拔插**：若未来决定下线该功能，只需删除 `app/crm_profile/` 目录与 `frontend/src/views/crm_profile/` 目录，drop 本地 `crm_ai_*` 表，不需要改动现有任何模块。

### 7.2 Context 模块注册表

为了未来可扩展，不建议把所有取数逻辑写在一个巨型函数里。建议用模块注册表：

```python
CONTEXT_MODULES = {
    "basic_profile": BasicProfileModule(),
    "safety_profile": SafetyProfileModule(),
    "goals_preferences": GoalsPreferencesModule(),
    "health_summary_7d": HealthSummaryModule(),
    "body_comp_latest_30d": BodyCompModule(),
    "points_engagement_14d": PointsEngagementModule(),
    "service_scope": ServiceScopeModule(),
}
```

每个模块统一实现：

```python
class ContextModule:
    key: str
    default_level: Literal["required", "summary", "optional"]

    def load(self, conn, customer_id: int, options: ContextOptions) -> ModulePayload:
        ...
```

好处：

1. 新增课程、设备、AI 历史时不破坏旧 schema。
2. 能按模块做缓存和超时。
3. 能在 UI 上展示“本次 AI 使用了哪些模块”。
4. 能给每个模块设置 token 预算和降级策略。

### 7.3 Context Binding Registry 第一版配置

第一版 `CONTEXT_MODULES` 建议固定如下，作为后端实现的正式加载边界：

| 模块 key | 阶段 | 默认模式 | loader | 缓存 | 超时 | token 预算 | 行数上限 |
|---|---|---|---|---|---|---|---|
| `basic_profile` | P0 | `required` | `load_basic_profile` | 300s | 500ms | 300 | 1 |
| `safety_profile` | P0 | `required` | `load_safety_profile` | 300s | 800ms | 600 | 1 |
| `goals_preferences` | P0 | `summary` | `load_goals_preferences` | 300s | 500ms | 350 | 1 |
| `health_summary_7d` | P0 | `summary` | `load_health_summary` | 120s | 1200ms | 700 | 7 |
| `body_comp_latest_30d` | P0 | `summary` | `load_body_comp_summary` | 120s | 1000ms | 450 | 30 |
| `points_engagement_14d` | P0 | `summary` | `load_points_engagement` | 120s | 1200ms | 450 | 200 logs 聚合后摘要 |
| `service_scope` | P0 | `summary` | `load_service_scope` | 300s | 800ms | 250 | 20 groups / 10 staff |
| `health_detail_expansion` | P0 | `expandable` | `load_health_detail_expansion` | 120s | 1500ms | 每类 700 | 每类近 7 天 |
| `habit_execution_14d` | P1 | `optional` | `load_habit_execution` | 120s | 1200ms | 500 | 14 天 |
| `plan_todos_14d` | P1 | `optional` | `load_plan_todos` | 120s | 1200ms | 500 | 14 天 |
| `course_learning_30d` | P1 | `optional` | `load_course_learning` | 300s | 1000ms | 300 | 30 天 |
| `service_issues_open` | P1 | `optional` | `load_service_issues` | 120s | 1000ms | 400 | 未解决 + 最近 5 条 |
| `ai_decision_labels` | P1 | `optional` | `load_ai_decision_labels` | 300s | 800ms | 300 | 30 labels |
| `device_summary` | P2 | `expandable` | `load_device_summary` | 120s | 2000ms | 700 | 聚合摘要 |
| `ai_history_summary` | P2 | `optional` | `load_ai_history_summary` | 300s | 1500ms | 500 | 最近主题摘要 |

注册表示例：

```python
CONTEXT_MODULES: dict[str, ContextModuleSpec] = {
    "basic_profile": ContextModuleSpec(
        key="basic_profile",
        phase="P0",
        default_mode="required",
        source_tables=("customers",),
        field_bindings=BASIC_PROFILE_BINDINGS,
        loader="load_basic_profile",
        cache_ttl_seconds=300,
        timeout_ms=500,
        token_budget=300,
        max_rows=1,
    ),
    "safety_profile": ContextModuleSpec(
        key="safety_profile",
        phase="P0",
        default_mode="required",
        source_tables=("customer_info",),
        field_bindings=SAFETY_PROFILE_BINDINGS,
        loader="load_safety_profile",
        cache_ttl_seconds=300,
        timeout_ms=800,
        token_budget=600,
        max_rows=1,
    ),
}
```

### 7.4 加载计划生成

AI 问答前，系统先生成 `ContextBuildPlan`，再按计划加载模块。不要让大模型决定查哪些表，第一版必须采用后端确定性规则。

```python
class ContextBuildPlan(BaseModel):
    customer_id: int
    entry_scene: str
    required_modules: list[str]
    summary_modules: list[str]
    expansion_modules: list[str]
    output_budget_tokens: int
    reason: str
```

场景 preset：

| `entry_scene` | 默认模块 | 自动展开 | 适用问题 |
|---|---|---|---|
| `customer_profile` | P0 required + summary | 无 | 打开档案、客户概览 |
| `coach_reply` | P0 required + summary | 按 query 命中 `glucose/diet/sleep/exercise` 展开 1 类 | 生成单次跟进话术 |
| `diet_suggestion` | P0 required + `health_summary_7d` | `diet_detail_7d` | 饮食替换、餐食建议 |
| `exercise_suggestion` | P0 required + `body_comp_latest_30d` | `exercise_detail_14d` | 运动建议、运动提醒 |
| `points_followup` | P0 required + `points_engagement_14d` | 无，除非教练手选 | 积分排行后的 1v1 跟进 |
| `handoff_summary` | P0 required + P1 service/plan/habit | 无 | 教练交接、客户复盘 |

展开规则：

1. 用户手动勾选优先，但最多 2 个展开模块。
2. 场景自动展开不能超过 1 个，避免用户无感成本膨胀。
3. 如果 query 命中多个主题，按安全优先级排序：`glucose > medication > diet > exercise > sleep > points`。
4. P1/P2 模块默认不进标准问答，除非 scene preset 或用户显式选择。

### 7.5 加载执行流程

推荐执行流程：

```text
1. api_crm_customers.py 接收 customer_id / entry_scene / selected_expansions / message
2. 权限检查：当前本地 user 是否能访问该 CRM customer
3. resolve_context_plan() 生成 ContextBuildPlan
4. 打开 CRM 只读连接
5. 串行加载 required 模块：basic_profile / safety_profile
6. 并发或分组加载 summary/optional 模块，每个模块受 timeout_ms 限制
7. loader 返回 ModulePayload，包括 payload/source_status/freshness/token_estimate
8. validate_field_whitelist() 只做字段白名单校验（扫描是否出现 §5.7 禁传字段），不做值级脱敏
9. compact_serialize() 按 token_budget 输出 CustomerProfileContextV1
10. context_hash = sha256(schema_version + compact_json)
11. AI prompt 使用 compact_json，不使用数据库原始 row
```

`ModulePayload` 建议结构：

```python
class ModulePayload(BaseModel):
    key: str
    status: Literal["ok", "empty", "partial", "timeout", "error"]
    payload: dict
    source_tables: list[str]
    source_fields: list[str]
    freshness: str | None = None
    warnings: list[str] = []
    redactions: list[str] = []
    estimated_tokens: int = 0
```

### 7.6 成本控制规则

硬性规则：

1. 标准 AI 问答默认总 prompt 预算 `30000 tokens`。
2. P0 required 模块不能超过 `12000 tokens`。
3. summary 模块总和不能超过 `12000 tokens`。
4. expansions 最多 2 个，每个默认 `700 tokens`。
5. 单模块超时后降级为 `partial/timeout`，不阻塞整个 AI 问答，除非 `safety_profile` 失败。
6. `safety_profile` 加载失败时，不允许调用 AI，只返回“关键安全上下文不可用”。
7. 禁止把附录 A 的任意表行整体 `json.dumps(row)` 后塞进 prompt。

预算超限时裁剪顺序：

1. 先裁剪 expandable 明细。
2. 再裁剪 optional P1/P2 模块。
3. 再压缩 default summary。
4. `basic_profile` 和 `safety_profile` 不裁剪，只允许摘要更短。

### 7.7 查询与缓存策略

默认策略：

1. 基础档案、画像：缓存 5 分钟。
2. 健康 7/30 天聚合：缓存 2 分钟。
3. 积分/打卡近 14 天：缓存 2 分钟。
4. AI 问答上下文：每次请求生成一个 `context_hash`，不要盲目复用旧上下文。

如果某个模块超时：

1. 不让整个客户档案失败。
2. 在 `source_status` 中标记模块失败。
3. AI prompt 中明确“该模块数据暂不可用，请不要基于它推断”。

缓存 key 规则：

```text
crm_context:{module_key}:{customer_id}:{range}:{schema_version}:{binding_version}
```

说明：

1. `binding_version` 第一版为 `context_binding_registry.v1`。
2. 字段白名单或转换规则改变时，必须提升 `binding_version`，避免旧缓存污染。
3. 不缓存最终 AI 输出作为事实，只缓存脱敏后的上下文模块 payload。
4. 如果本地部署没有 Redis，第一期可以使用进程内 TTL cache；生产化再迁 Redis。

---

## 8. AI 编排设计

### 8.1 调用方式

第一期建议复用当前仓库已有的 OpenAI-compatible chat completion 方式：

```http
POST {AI_BASE_URL}/chat/completions
Authorization: Bearer {AI_API_KEY}
```

当前 `ai_polish.py` 已经证明这条链路可以作为实现样板。

SSE 流式输出可以作为 P1 体验优化，不应阻塞 P0。function calling / tool calling 暂定为 P2 candidate，只有确认 aihubmix 侧模型和接口支持后再晋升为正式方案。

### 8.2 Prompt 结构

建议拆成三段：

1. System：角色、安全边界、输出规则。
2. Developer/context：结构化客户上下文。
3. User：教练本次问题。

System 示例：

```text
你是健康管理教练的 AI 助手。你只能生成给教练复核的建议草稿。
你不能诊断疾病，不能开具处方，不能建议停药或改药。
如涉及疾病、药物、异常指标或医疗风险，必须提示教练遵循医生意见或转医生确认。
必须严格遵守客户过敏、运动损伤和禁忌信息。
如果上下文缺失，明确说明缺失，不要编造。
输出应简洁、可执行、适合教练二次编辑。
```

Context 示例：

```text
以下是系统生成的客户上下文，schema_version=customer_profile_context.v1。
该上下文已排除手机号、openid、unionid、登录 IP、紧急联系人等敏感身份字段。

{customer_profile_context_json}
```

User 示例：

```text
教练问题：基于他最近 3 天的状况，帮我写一段明早发送的提醒话术。
输出格式：给我 1 段可直接复制的中文话术，80 字以内。
```

### 8.3 输出结构

后端不要只返回纯文本，建议返回结构化结果：

```json
{
  "answer": "张先生，早上好...",
  "safety_notes": [
    "已避开虾蟹等过敏相关饮食建议",
    "未提供药物调整建议"
  ],
  "used_modules": ["basic_profile", "safety_profile", "health_summary_7d", "diet_detail_7d"],
  "missing_data_notes": ["最近 3 天睡眠数据不完整"],
  "model": "gpt-4o-mini",
  "token_usage": {
    "prompt_tokens": 1800,
    "completion_tokens": 180
  },
  "latency_ms": 4200,
  "requires_human_review": true
}
```

### 8.4 安全门禁

需要两层门禁：

1. Prompt 前门禁
   - 检查是否有 safety block。
   - 检查是否命中 §5.7 禁传字段白名单（凭证与系统标识类）。
   - 检查上下文 token 预算。

2. Prompt 后门禁
   - 扫描输出是否命中过敏食材。
   - 扫描是否出现“停药、加药、诊断、处方”等高风险表达。
   - 高风险时标记 `requires_medical_review = true`，前端禁用“一键复制为客户话术”，只允许复制给内部复核。

---

## 9. API 规格草案

### 9.1 搜索客户

`GET /api/v1/crm-customers/search?name=张&page=1&page_size=20`

第一期只支持按 `customers.name` 做前缀/包含匹配，不提供手机号、openid 等反查入口。

响应：

```json
{
  "available": true,
  "list": [
    {
      "id": 12345,
      "name": "张先生",
      "gender": "male",
      "age": 45,
      "group_names": "首钢集团健康领航群",
      "status": "intervening",
      "total_points": 128
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

说明：

1. 搜索结果已经过 §11 权限过滤：admin 返回全库匹配，教练只返回自己可见的客户集合。
2. 搜索命中仅返回核心展示字段；具体档案与 AI 上下文通过 `GET /profile` 与 `POST /ai/*` 获取。

### 9.2 获取客户档案

`GET /api/v1/crm-customers/{customer_id}/profile?range=30d`

响应：

```json
{
  "customer": {},
  "cards": {
    "basic_profile": {},
    "safety_profile": {},
    "goals_preferences": {},
    "health_summary_7d": {},
    "body_comp_latest_30d": {},
    "points_engagement_14d": {},
    "service_scope": {}
  },
  "source_status": [],
  "available_actions": ["ai_chat", "copy_summary"]
}
```

### 9.3 预览 AI 上下文

`POST /api/v1/crm-customers/{customer_id}/ai/context-preview`

请求：

```json
{
  "entry_scene": "customer_profile",
  "selected_expansions": ["glucose_detail_7d", "diet_detail_7d"],
  "coach_query": "写一段明早提醒话术"
}
```

响应：

```json
{
  "context": {
    "schema_version": "customer_profile_context.v1",
    "binding_version": "context_binding_registry.v1"
  },
  "build_plan": {
    "required_modules": ["basic_profile", "safety_profile"],
    "summary_modules": ["goals_preferences", "health_summary_7d", "body_comp_latest_30d", "points_engagement_14d", "service_scope"],
    "expansion_modules": ["glucose_detail_7d", "diet_detail_7d"]
  },
  "estimated_tokens": 2100,
  "module_status": [
    {"key": "basic_profile", "status": "ok"},
    {"key": "safety_profile", "status": "ok"}
  ],
  "excluded_fields": ["openid", "unionid", "last_login_ip", "avatar_url"],
  "warnings": []
}
```

### 9.4 发起 AI 问答

`POST /api/v1/crm-customers/{customer_id}/ai/chat`

请求：

```json
{
  "entry_scene": "customer_profile",
  "selected_expansions": ["glucose_detail_7d"],
  "message": "基于最近 7 天情况，帮我总结 3 个跟进重点",
  "output_style": "coach_brief"
}
```

响应：

```json
{
  "session_id": "local-session-id",
  "message_id": "local-message-id",
  "answer": "1. ...",
  "safety_notes": [],
  "missing_data_notes": [],
  "used_modules": [],
  "token_usage": {},
  "requires_human_review": true
}
```

### 9.5 审计记录

建议新增本地表，而不是写回 CRM：

1. `crm_ai_sessions`
2. `crm_ai_messages`
3. `crm_ai_context_snapshots`
4. `crm_ai_guardrail_events`

注意：

1. `crm_ai_context_snapshots` 存完整 compact context JSON 与 `context_hash`，便于事后回放与质量复盘。本地库访问需通过后台鉴权，与 AI 白名单保持一致，不超过 §5.7。
2. 审计表默认保持 180 天；如需更长保留周期，再在 Phase 3 后评估是否对 snapshot 启用列级加密。

### 9.6 枚举定义

本节集中列出前后端必须对齐的所有枚举，实现时统一落在 `app/crm_profile/schemas/enums.py`，并通过 OpenAPI / TS codegen 同步给前端，不允许前后端各写一份。

#### `entry_scene`

| 值 | 说明 |
|---|---|
| `customer_profile` | 打开客户 360 页的标准访问 |
| `coach_reply` | 生成单次跟进话术 |
| `diet_suggestion` | 饮食替换/餐食建议 |
| `exercise_suggestion` | 运动建议/运动提醒 |
| `points_followup` | 积分排行后的 1v1 跟进 |
| `handoff_summary` | 教练交接/客户复盘 |

#### `selected_expansions`

| 值 | 范围 | 说明 |
|---|---|---|
| `glucose_detail_7d` | 7d | 血糖明细（空腹/餐后/随机/连续） |
| `diet_detail_7d` | 7d | 三餐+加餐明细摘要 |
| `sleep_detail_14d` | 14d | 睡眠时长/质量明细 |
| `exercise_detail_14d` | 14d | 运动记录明细 |
| `points_logs_14d` | 14d | 近期正向积分事件 |
| `todo_detail_14d` | 14d | 待办明细 |

约束：同一次请求中 `selected_expansions` 最多 2 个，且与 `entry_scene` 自动展开的模块不重复。

#### `output_style`

| 值 | 说明 | 默认模型输出长度 |
|---|---|---|
| `coach_brief` | 教练内部简报，结论优先 | ≤ 200 字 |
| `customer_reply` | 直接发给客户的话术草稿 | ≤ 120 字 |
| `handoff_note` | 交接备注，结构化分点 | ≤ 400 字 |
| `bullet_list` | 3-5 条要点 | 按要点控长度 |

#### `module_status.status`

| 值 | 说明 |
|---|---|
| `ok` | 正常加载 |
| `empty` | 无数据 |
| `partial` | 部分字段缺失 |
| `timeout` | 超时降级 |
| `error` | 加载失败 |

#### `source_status.status`

| 值 | 说明 |
|---|---|
| `ok` | 正常 |
| `fallback_latest_archived_or_unknown` | `customer_info` 未命中未归档，已降级取最新 |
| `permission_denied` | 子查询权限不足 |
| `unavailable` | 上游服务不可用 |

#### `available_actions`

| 值 | 说明 | 权限要求 |
|---|---|---|
| `ai_chat` | 可发起 AI 问答 | AI 已配置且 safety_profile 加载成功 |
| `copy_summary` | 复制客户章摘要 | 无 |
| `copy_draft` | 复制 AI 草稿 | 禁用于 `requires_medical_review=true` |
| `create_followup` | 转发送中心草稿 | Phase 3 上线后生效 |
| `mark_medical_review` | 标记需医生复核 | 由门禁结果触发或教练手动 |

#### `requires_medical_review` / `requires_human_review`

统一就一个字段：`requires_medical_review: bool`，由后端 Prompt 后门禁写入。

- `true`：命中诊断/处方/用药/过敏食材等高风险表达，前端禁用 `copy_draft` 动作，只允许 `mark_medical_review` 和内部复核复制。
- `false`：允许常规复制与转发。

旧称 `requires_human_review` 不再使用，schema 中从 v1 起已统一为 `requires_medical_review`。

#### `guardrail_event.type`

| 值 | 说明 |
|---|---|
| `prompt_field_blocked` | 前门禁拦截到禁传字段 |
| `prompt_safety_missing` | 缺少 safety block，拒绝调用 |
| `prompt_token_exceed` | 上下文超预算，裁剪后再调用 |
| `output_allergy_hit` | 输出命中过敏食材 |
| `output_medical_term` | 输出命中诊断/处方/用药表达 |

---

## 10. 前端页面设计

### 10.1 页面入口

建议入口有三处：

1. 新增侧栏菜单：`CRM 客户档案`
2. CRM 群成员列表：成员旁边的“查看档案”
3. 积分排行结果：成员洞察旁边的“AI 跟进”

### 10.2 页面结构

```text
+------------------------------------------------------------+
| 客户 360 档案                                               |
| 搜索客户 / 所属群 / 最近查看                                |
+----------------------+-----------------------+-------------+
| Profile Card         | Health & Service Tabs | AI Copilot  |
| 姓名/年龄/状态        | 健康摘要               | 问题输入     |
| 风险/过敏/禁忌        | 目标与处方             | 上下文模块   |
| 负责教练/所属群        | 近期趋势               | 输出草稿     |
| 数据新鲜度             | 执行与积分             | 安全提示     |
+----------------------+-----------------------+-------------+
```

### 10.3 AI 侧边栏必须具备

1. 当前上下文模块列表。
2. 可勾选展开模块。
3. token 预算提示。
4. 数据缺失提示。
5. 安全提示。
6. 输出后“复制草稿”“生成发送中心内容”“标记需医生确认”等动作。

### 10.4 不要做成的样子

不要做：

1. 首屏堆满全部字段表格。
2. 把 AI 聊天框藏在页面底部。
3. 默认展开全部原始 JSON。
4. 让 AI 输出看起来像系统官方医嘱。

---

## 11. 权限、隐私与审计

### 11.1 角色与可见范围

本功能只面向运营后台登录用户，不对 C 端开放。权限模型按两个维度组合：

1. 第一维度：**角色**（admin / coach）
   - `admin`：可看全库 CRM 客户，不过滤。
   - `coach`：只能看自己作为负责人或群教练关联的客户。

2. 第二维度：**可见客户集合**（只对 coach 生效）
   - 由 `services/permission.py` 的 `resolve_visible_customers(user)` 计算，返回 `set[int]` 的 CRM `customer_id`。
   - 对单点访问通过 `assert_can_view(user, customer_id)` 同一数据源判定。

### 11.2 数据源策略（本地映射 + 远程真值）

本节是本功能的架构关键点之一，必须明确写死。

**决策**：

1. **CRM 库是“教练-客户关系”的唯一真值源**。本地不冗余 `customer_staff`/`group_coachs`/`customer_groups` 这三张表的内容，也不同步客户基础信息。
2. **本地只存一件事：教练账号映射**。已有的 `app/services/crm_admin_auth.py` 在 CRM admin 登录成功时将账号镜像到本地 `users` 表；本功能复用该映射，不再新增教练相关本地表。
3. **权限判定每次请求都走远程 CRM**，但结果加 5 分钟进程内 TTL 缓存，避免每次穿透。
4. **不开发本地 CDC/同步作业**。运营后台访问量有限，直连 CRM 的成本低于同步的复杂度和正确性风险。

**具体路径**（admin 旁路，仅 coach 需要执行）：

```text
local users.id (登录用户)
  → local users.role          # admin 直接通过，不再查话
CRM
  → local users.crm_admin_id  # crm_admin_auth 镜像时写入（若缺字段则在 Phase 0 补迸1 列迁移）
  → CRM admins.id
  → 并集查询：
       A) CRM customer_staff   WHERE admin_id=? AND (end_at IS NULL OR end_at > NOW())
       B) CRM group_coachs     WHERE coach_id=? → CRM customer_groups WHERE group_id IN (...)
  → 合并得到 visible_customer_ids: set[int]
```

**实现点**：

1. `resolve_visible_customers(user)` 返回 `set[int]`；admin 返回谨慎值 `ALL`（用架构内部的 sentinel 实现，注意不要在 SQL 层面返回全库 ID）。
2. `assert_can_view(user, customer_id)` 是单点版：admin 直过，coach 先查缓存，未命中则执行上述两路并集查询。
3. 缓存 key：`crm_profile:visible:{local_user_id}:{schema_version}`，TTL 300s；登出时主动清。
4. 第一期使用进程内 TTL cache；多实例部署时再迁 Redis。
5. 性能上限：单个 coach 可见客户通常 < 2000，set[int] 缓存体积可控。如果某 admin 角色也被错配为 coach（可见 > 10w），应在返回时退化为 `ALL`，不写 set。

**本地 `users` 表需要确认/补齐的字段**（Phase 0 校验）：

1. `users.role`：区分 admin / coach（已有则复用，无则用现有角色机制）。
2. `users.auth_source`：标记是否为 CRM 镜像账号（已存在）。
3. `users.crm_admin_id`：**需要确认存在**；若仅存 `crm_admin_username`，在 Phase 0 增加整数列并回填，避免每次用 username 去 CRM 查 ID。

### 11.3 隐私字段处理

第一期采用字段白名单而非值级脱敏，详见 §5.7。总结：

1. **允许进入 AI context**：姓名、称呼、年龄、性别、手机号、城市、地址、紧急联系人、健康相关全部业务字段。
2. **禁止进入 AI context**：凭证类（密码/盐/session/openid/unionid 原值）、系统内部标识（登录 IP、avatar 原始 URL、未解析的原始 JSON）。
3. **页面展示**：第一期与 AI 白名单保持一致即可，不做额外的展示层掩码。
4. **审计落库内容**：见 §11.4；写入本地表的客户信息与传给 AI 的信息同步白名单，不超绳。

### 11.4 审计字段

每次 AI 调用至少记录：

1. 本地 `user_id`
2. CRM `admin_id`（来自 `users.crm_admin_id`）
3. CRM `customer_id`
4. 入口场景
5. selected expansions
6. context hash
7. model
8. token usage
9. latency
10. guardrail result
11. created_at

---

## 12. 性能与 token 预算

### 12.1 纠正原稿中的性能表述

“500 - 1500 tokens 且毫秒级响应”不应作为正式承诺。

更现实的目标：

1. profile 聚合接口：P50 < 1s，P95 < 2.5s。
2. context-preview：P50 < 1.5s，P95 < 3s。
3. AI 非流式完整返回：P50 < 8s，P95 < 20s。
4. AI 流式首 token：P50 < 3s。

具体表现取决于 aihubmix、模型、网络和上下文长度，必须实测。

### 12.2 默认预算

建议默认：

1. required context：8000-12000 tokens。
2. summary modules：8000-12000 tokens。
3. selected expansions：每个 4000-8000 tokens，最多 2 个。
4. coach query：20000 tokens 内。
5. completion：默认 8000 tokens 内。

标准问答目标：prompt 20000-30000 tokens；复杂分析不超过 100000 tokens。

### 12.3 长数据处理规则

禁止默认传：

1. 30 天逐日完整数组。
2. 分钟级心率/血糖/睡眠点位。
3. 原始设备 JSON。
4. 历史聊天全文。

允许传：

1. 聚合统计。
2. 趋势判断。
3. 异常天摘要。
4. 少量代表性样本。

---

## 13. 开发分期

### Phase 0：验证与真值确认

目标：把 support 数据变成可开发依据，并决定权限解析路径的可行性。

任务：

1. 抽样验证 `customers / customer_info / customer_health / body_comp / point_logs / customer_groups / customer_staff / group_coachs` 的真实数据量和字段质量。
2. 对关键 SQL 做 `EXPLAIN`，重点看 `customer_id` 与时间范围的索引命中。
3. 确认 CRM 连接账号只读权限，不写入。
4. **验证教练映射链路**：本地 `users.crm_admin_id` 是否存在；如缺失则新增迁移并调整 `crm_admin_auth` 镜像逻辑在登录时回填。
5. **验证客户权限覆盖率**：用 `customer_staff` + `group_coachs` 并集查询经验性训练样本，统计“教练 → 可见客户”平均规模与极大值。
6. 验证 `customer_info.is_archived` 的实际填充情况（否则 §5.3 的取数规则需要降级）。

交付：

1. 抽样查询结果与字段可用性清单。
2. MVP 取数字段表。
3. `users.crm_admin_id` 迁移脚本（若需）。
4. 教练级权限解析可行性结论：是否可在 Phase 1 对 coach 开放，还是需要先以 admin-only 上线。

### Phase 1：客户档案 API 与页面

目标：先让教练“看见”和“理解”。

后端：

1. `GET /api/v1/crm-customers/search`
2. `GET /api/v1/crm-customers/{customer_id}/profile`
3. `CustomerProfileContextV1` schema 初版

前端：

1. 客户搜索。
2. 客户 360 档案页。
3. 风险、目标、健康摘要、执行摘要。

验收：

1. 不接 AI 也能独立使用。
2. 无 CRM 配置时页面有清晰不可用状态。

### Phase 2：AI context preview 与问答

目标：把“手工拼 Prompt”变成系统自动注入。

后端：

1. 新增 `app/clients/ai_chat_client.py`（不替换 `ai_polish.py`）。
2. `app/crm_profile/services/context_builder.py` 支持 context-preview。
3. `app/crm_profile/services/ai_coach.py` 支持 `ai/chat`。
4. `app/crm_profile/services/ai_coach.py` 内置前/后两层安全门禁；`audit.py` 写入 `crm_ai_*` 本地表。

前端：

1. AI 侧边栏。
2. 模块勾选。
3. 上下文预览。
4. 输出草稿、安全提示、复制动作。

验收：

1. 过敏/禁忌测试通过。
2. token 预算可见。
3. AI 未配置时提示明确，不影响客户档案查看。

### Phase 3：运营入口联动

目标：让 AI 能接入现有发送中心和积分运营。

任务：

1. CRM 群成员列表跳转客户档案。
2. 积分排行洞察跳转 AI 跟进建议。
3. AI 输出可转成发送中心草稿。
4. 保留人工确认，不自动发送。

### Phase 4：长期扩展

候选能力：

1. SSE 流式输出。
2. provider/model 多模型配置。
3. tool calling / function calling。
4. 客户画像日快照。
5. 更完整的习惯、课程、服务问题、设备数据纳入。
6. AI 输出质量评估集。

---

## 14. 验证清单

### 14.1 focused validation

文档和实现都必须覆盖：

1. `customer_info` 多版本时是否取当前有效记录。
2. 关键 safety 字段是否永远进入 AI context。
3. 凭证与系统标识类字段（密码、盐、openid、unionid 原值、登录 IP、avatar 原始 URL、未解析的原始 JSON）是否不会进入 AI；业务身份字段（姓名、手机号、地址、紧急联系人）允许进入。
4. 无 CRM 配置时是否安全降级。
5. 无 AI key 时是否只禁用 AI，不影响客户档案。
6. 外部 CRM 查询慢或失败时是否按模块降级。
7. 客户权限是否可解释：admin 旁路出全库；coach 通过 `customer_staff` + `group_coachs` 并集得到可见集合；未命中则返回 403 而非 404。
8. 过敏客户测试：AI 不推荐相关食物。
9. 运动损伤客户测试：AI 不推荐禁忌运动。
10. 药物问题测试：AI 不给停药/改药建议。
11. `ContextFieldBinding` 白名单之外的字段不能进入 `CustomerProfileContext`。
12. `context_binding_registry.v1` 变更时必须同步提升 `binding_version` 或清理缓存。
13. `safety_profile` 加载失败时必须阻断 AI 调用。
14. 任意模块超预算时必须按“展开明细 -> P1/P2 optional -> summary 压缩”的顺序裁剪。
15. `context-preview` 返回的 `build_plan / module_status / excluded_fields` 必须和实际 prompt 使用一致。
16. 架构独立性：关闭 `crm_profile_enabled` 时 router 不挂载、前端入口隐藏，其他功能（消息润色 / CRM 群 / 积分洞察）无任何回归。
17. 依赖方向：执行 `grep -R "from app.services.crm_group_directory\|from app.services.crm_admin_auth" app/crm_profile/` 必须无命中（证明不拖其他业务模块内部代码）。

### 14.2 技术验证

建议测试：

1. `python -m py_compile app/crm_profile/router.py app/crm_profile/services/profile_loader.py app/crm_profile/services/context_builder.py app/crm_profile/services/ai_coach.py app/crm_profile/services/permission.py`
2. `cd frontend && npm run build`
3. 后端启动：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. 前端启动：`cd frontend && npm run dev`

### 14.3 业务验收样例

至少准备 5 个样例客户：

1. 数据完整客户。
2. 有过敏客户。
3. 有运动损伤客户。
4. 健康数据缺失客户。
5. 高活跃/低活跃对比客户。

每个样例都要验证：

1. 档案摘要是否可信。
2. 数据缺失是否显式提示。
3. AI 输出是否可直接被教练编辑使用。
4. AI 是否没有编造不存在的指标。

---

## 15. 当前 blocker

1. `users.crm_admin_id` 字段是否存在需在 Phase 0 核实；如缺失需补整数列并由 `crm_admin_auth` 在登录镜像时回填。这是教练级权限解析的前提。
2. 客户级取数接口尚未实现，当前只有群/积分方向的 CRM 只读能力。
3. aihubmix 配置虽存在，但客户级 AI 问答还没有审计和安全门禁。
4. `mfgcrmdb` 缺少强外键，落地前必须先确认 `customer_staff.end_at` 和 `group_coachs` 的活跃关系覆盖率以及 `customer_info.is_archived` 有效性。
5. 医疗健康建议存在合规风险，必须保持“教练草稿 + 人工复核”定位。

---

## 16. 下一步建议

最值得先推进的是 Phase 0 + Phase 1。

推荐顺序：

1. 先做 CRM 客户搜索和 profile 聚合 API。
2. 再做客户 360 页面。
3. 再做 context-preview，让教练看到 AI 会读什么。
4. 最后接 AI 问答和安全门禁。

这样即使 AI 暂时不可用，客户档案也已经是一个独立有价值的能力；等 AI 接入时，也不会变成“漂亮聊天框 + 空心上下文”。

---

## 17. 面向项目负责人的一句话状态

这个功能方向成立，但当前还处在 candidate 方案阶段。它的正确落点不是“把 CRM 全库丢给 AI”，而是先建设一个可审计、可剪枝、可扩展、**可独立上下线**的客户上下文服务，再让 AI 在教练复核的边界内辅助生成跟进建议。当前最值得做的是客户档案聚合和页面首版，AI 问答应作为第二阶段接入。架构上全部落在独立子包 `app/crm_profile/`，与现有群运营 / 积分 / 消息润色模块不产生双向依赖。
---

## 附录 A：CRM 用户相关字段清单（开发用 support）

这部分字段清单必须保留在本方案内，作为后续开发 `CustomerProfileContext`、查询聚合、字段白名单规则和前端信息架构的恢复锚点。

使用口径：

1. 本附录是 support 字段池，不等于所有字段都会进入 AI context。
2. P0/P1 研发时优先从第 5 章 MVP 数据域选择字段。
3. 第一期采用字段白名单而非值级脱敏，业务身份字段（姓名、手机号、地址、紧急联系人等）允许进入 AI；凭证与系统标识类字段禁传，见 §5.7。
4. 具体字段含义仍以真实 CRM 库、`docs/CRM/mfgcrmdb_schema_knowledge.json` 和抽样查询为最终校验依据。

### A.1 客户主数据与身份表

#### `customers`

- 定位：客户主表，是全库最核心的业务实体。
- 粒度：1 行 = 1 个客户主档。
- 逻辑关联：`channel_id`：客户来源渠道 -> channels.id； `current_plan_id`：客户当前计划 -> customer_plans.id； `user_id`：C 端账号 -> users.id； `huami_user_id`：第三方华米用户标识，语义上对应 huami_users.huami_user_id，不是 huami_users.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `name` | `varchar(16)` | Y | `NULL` | 姓名 |
| `avatar` | `varchar(64)` | Y | `NULL` | 头像 |
| `title` | `varchar(16)` | Y | `NULL` | 称呼 |
| `gender` | `tinyint` | Y | `0` | 0其他 1男 2女 |
| `birthday` | `date` | Y | `NULL` | 生日 |
| `height` | `int` | Y | `NULL` | 身高 |
| `weight` | `int` | Y | `NULL` | 体重 |
| `phone` | `varchar(16)` | Y | `NULL` | 电话 |
| `status` | `tinyint` | Y | `0` | 状态0默认 1干预中 2已付费 3潜客 4流失 5暂停 |
| `prev_status` | `tinyint(1)` | Y | `NULL` | 上一状态 |
| `tags` | `json` | Y | `-` | - |
| `city` | `varchar(16)` | Y | `NULL` | 城市 |
| `channel_time` | `datetime` | Y | `NULL` | 渠道时间 |
| `channel_id` | `int` | Y | `NULL` | 渠道id；客户来源渠道 -> channels.id |
| `current_plan_id` | `int` | Y | `NULL` | 当前计划；客户当前计划 -> customer_plans.id |
| `cgm` | `json` | Y | `-` | cgm具体信息 |
| `is_cgm` | `tinyint(1) UNSIGNED ZEROFILL` | Y | `0` | 是否绑定了血糖仪 |
| `is_recipel` | `tinyint(1)` | Y | `NULL` | 是否需要医生线上问诊 |
| `is_sale` | `tinyint(1)` | Y | `NULL` | 是否预约销转 |
| `compliance_level` | `tinyint(1)` | Y | `NULL` | 依从度等级(1-低 2-中 3-高) |
| `is_miniprogram` | `tinyint(1)` | Y | `NULL` | 是否注册小程序 |
| `adviser_phone` | `varchar(11)` | Y | `NULL` | 顾问电话 |
| `urgent_name` | `varchar(16)` | Y | `NULL` | 紧急联系人姓名 |
| `urgent_phone` | `varchar(11)` | Y | `NULL` | 紧急联系人电话 |
| `sale_level` | `tinyint(1)` | Y | `NULL` | 销转等级 |
| `address` | `varchar(64)` | Y | `NULL` | 地址 |
| `contract_no` | `varchar(32)` | Y | `NULL` | 合同编号 |
| `advisor` | `varchar(16)` | Y | `NULL` | 顾问 |
| `survey_done` | `tinyint(1)` | Y | `0` | 完成注册问卷0否 1是 |
| `points` | `int` | Y | `0` | 积分 |
| `total_points` | `int` | Y | `0` | - |
| `exp` | `int` | Y | `0` | 经验 |
| `severity` | `tinyint` | Y | `0` | 病情严重程度 1 2 3 低中高 |
| `is_del` | `tinyint` | Y | `0` | 是否删除0否1是 |
| `user_id` | `int` | Y | `NULL` | C 端账号 -> users.id |
| `last_login_ip` | `varchar(32)` | Y | `NULL` | - |
| `last_login_at` | `datetime` | Y | `NULL` | - |
| `huami_user_id` | `int` | Y | `NULL` | 第三方华米用户标识，语义上对应 huami_users.huami_user_id，不是 huami_users.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `users`

- 定位：C 端用户账号表，与 customers 形成账号-客户双实体。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int UNSIGNED` | N | `-` | - |
| `phone` | `varchar(16)` | Y | `NULL` | - |
| `phone_verified` | `tinyint(1)` | Y | `0` | - |
| `nick_name` | `varchar(32)` | Y | `NULL` | - |
| `avatar` | `varchar(255)` | Y | `NULL` | - |
| `gender` | `tinyint(1)` | Y | `0` | - |
| `birthday` | `date` | Y | `NULL` | - |
| `status` | `tinyint(1)` | Y | `1` | - |
| `last_login_at` | `datetime` | Y | `NULL` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `created_at` | `datetime` | N | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `oauth_users`

- 定位：微信/小程序/服务号 OAuth 身份表，与 customers 建立外部身份映射。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int UNSIGNED` | N | `-` | - |
| `nick_name` | `varchar(32)` | Y | `NULL` | - |
| `openid` | `varchar(64)` | Y | `NULL` | - |
| `avatar` | `varchar(255)` | Y | `NULL` | - |
| `gender` | `tinyint(1)` | Y | `NULL` | - |
| `city` | `varchar(16)` | Y | `NULL` | - |
| `unionid` | `varchar(64)` | Y | `NULL` | - |
| `source` | `tinyint(1)` | Y | `1` | 1小程序 2服务号 |
| `subs` | `tinyint(1)` | Y | `1` | - |
| `customer_id` | `int UNSIGNED` | Y | `NULL` | 客户 -> customers.id |
| `plat` | `tinyint(1)` | Y | `1` | - |
| `created_at` | `datetime` | N | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_info`

- 定位：客户静态/半静态画像、健康背景、目标、处方、干预地图与归档状态表。
- 粒度：更像“客户画像版本表/扩展信息表”，通常 1 个客户可有多条，当前有效记录常取 is_archived=0 且最新 id。
- 逻辑关联：`customer_id`：客户 -> customers.id； `archived_by`：归档操作人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `health_condition` | `text` | Y | `-` | 身体指标及疾病情况 |
| `health_condition_user` | `text` | Y | `-` | 身体指标及疾病情况(用户版) |
| `genetic_history` | `varchar(1024)` | Y | `NULL` | 遗传病史 |
| `allergies` | `varchar(500)` | Y | `NULL` | 过敏原 |
| `goals` | `varchar(500)` | Y | `NULL` | 健康目标 |
| `goal_weight` | `int` | Y | `NULL` | 目标体重 |
| `goal_hr` | `varchar(16)` | Y | `NULL` | 目标心率 |
| `goal_gluc` | `varchar(16)` | Y | `NULL` | 目标血糖 |
| `goal_bp` | `varchar(16)` | Y | `NULL` | 目标血压 |
| `diet_preference` | `varchar(500)` | Y | `NULL` | 口味偏好 |
| `sport_injuries` | `varchar(500)` | Y | `NULL` | 运动损伤史 |
| `sport_preference` | `varchar(500)` | Y | `NULL` | 运动偏好 |
| `sport_interests` | `varchar(500)` | Y | `NULL` | 运动爱好 |
| `sleep_quality` | `varchar(500)` | Y | `NULL` | 睡眠情况 |
| `remark` | `json` | Y | `-` | 个性化信息备注 |
| `day_form` | `json` | Y | `-` | 日报表格 |
| `week_form` | `json` | Y | `-` | 周报表格 |
| `month_form` | `json` | Y | `-` | 月报表格 |
| `medical_history` | `varchar(1000)` | Y | `NULL` | 医疗史 |
| `recipel` | `json` | Y | `-` | 处方信息 |
| `intervention_map` | `json` | Y | `-` | 干预地图 |
| `doctor_recipel` | `json` | Y | `-` | 医生端处方 |
| `food_recipel` | `json` | Y | `-` | 饮食处方 |
| `sleep_recipel` | `json` | Y | `-` | 睡眠处方 |
| `sport_recipel` | `json` | Y | `-` | 运动处方 |
| `nutrition_recipel` | `json` | Y | `-` | 营养素处方 |
| `is_archived` | `tinyint` | Y | `0` | 是否归档0否1是 |
| `archived_at` | `datetime` | Y | `NULL` | 归档时间 |
| `archived_by` | `int` | Y | `NULL` | 归档人；归档操作人 -> admins.id |
| `archive_reason` | `varchar(64)` | Y | `NULL` | 归档原因 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_health_condition_history`

- 定位：customer_info.health_condition 的归档历史表。
- 逻辑关联：`customer_id`：客户 -> customers.id； `operator_id`：归档操作人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | 主键ID |
| `customer_id` | `int` | N | `-` | 客户ID；客户 -> customers.id |
| `health_condition` | `text` | N | `-` | 归档时的身体指标及疾病情况 |
| `operator_id` | `int` | N | `-` | 归档操作人ID（管理员ID）；归档操作人 -> admins.id |
| `remark` | `text` | Y | `-` | 归档备注 |
| `created_at` | `timestamp` | N | `CURRENT_TIMESTAMP` | 创建时间（归档时间） |
| `updated_at` | `timestamp` | N | `CURRENT_TIMESTAMP` | 更新时间 |

#### `customer_staff`

- 定位：客户与后台负责人/服务人员的分配关系表，可追踪生效区间。
- 粒度：1 行 = 1 次客户与服务人员的绑定区间。
- 逻辑关联：`customer_id`：客户 -> customers.id； `admin_id`：负责人/服务人员 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `admin_id` | `int` | Y | `NULL` | 负责人id；负责人/服务人员 -> admins.id |
| `star_level` | `int` | Y | `NULL` | 星标等级 |
| `start_at` | `datetime` | Y | `NULL` | 开始时间 |
| `end_at` | `datetime` | Y | `NULL` | 结束时间 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_star`

- 定位：教练与客户的星标关系表（字段命名为 camelCase）。
- 逻辑关联：`adminId`：教练 -> admins.id； `customerId`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint UNSIGNED` | N | `-` | 主键ID |
| `adminId` | `bigint UNSIGNED` | N | `-` | 教练ID；教练 -> admins.id |
| `customerId` | `bigint UNSIGNED` | N | `-` | 客户ID；客户 -> customers.id |
| `createdAt` | `datetime` | N | `CURRENT_TIMESTAMP` | 创建时间 |

#### `families`

- 定位：家庭/家庭组主表。
- 逻辑关联：`owner_id`：家庭主人 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `name` | `varchar(64)` | Y | `NULL` | 家庭名称 |
| `invite_code` | `varchar(16)` | Y | `NULL` | 邀请码 |
| `owner_id` | `int` | N | `-` | 主人id；家庭主人 -> customers.id |
| `status` | `tinyint` | N | `1` | 0禁用 1正常 |
| `created_at` | `datetime` | N | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

### A.2 社群与分组表

#### `groups`

- 定位：群组主表（例如训练营/批次群）。

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `name` | `varchar(32)` | Y | `NULL` | 名称 |
| `webhook_key` | `varchar(255)` | Y | `NULL` | - |
| `batch` | `int` | Y | `NULL` | 批次 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_groups`

- 定位：客户与群组的关系表。
- 粒度：1 行 = 1 个客户加入 1 个群组的关系。
- 逻辑关联：`customer_id`：客户 -> customers.id； `group_id`：群组 -> groups.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `group_id` | `int` | Y | `NULL` | 群组 -> groups.id |
| `role` | `tinyint(1)` | Y | `0` | - |
| `joined_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |

#### `group_coachs`

- 定位：群组与教练关系表。
- 粒度：1 行 = 1 个群组与 1 个教练的关系。
- 逻辑关联：`group_id`：群组 -> groups.id； `coach_id`：教练 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `group_id` | `int` | Y | `NULL` | 群组 -> groups.id |
| `coach_id` | `int` | Y | `NULL` | 教练 -> admins.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

### A.3 健康记录与生理监测表

#### `customer_health`

- 定位：客户每日健康汇总表，是分析健康行为最重要的宽表之一。
- 粒度：1 行 = 1 个客户在 1 个 record_date 的健康宽表记录。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `record_date` | `date` | Y | `NULL` | 记录日期 |
| `day_form` | `json` | Y | `-` | 日报表格 |
| `week_form` | `json` | Y | `-` | 周报表格 |
| `month_form` | `json` | Y | `-` | 月报表格 |
| `weight` | `int` | Y | `NULL` | 体重 |
| `waist` | `double` | Y | `NULL` | 腰围cm |
| `blood_sbp` | `int` | Y | `NULL` | 收缩压 |
| `blood_dbp` | `int` | Y | `NULL` | 舒张压 |
| `heart_rate` | `int` | Y | `NULL` | 心率 弃用 |
| `fbs` | `decimal(4,` | Y | `NULL` | 空腹血糖(mmol/L) |
| `pbs` | `decimal(4,` | Y | `NULL` | 餐后血糖(mmol/L) |
| `glucose_data` | `json` | Y | `-` | 血糖数据 弃用 |
| `blood_suger` | `json` | Y | `-` | 血糖 |
| `pressure_data` | `json` | Y | `-` | 压力数据 |
| `sleep_data` | `json` | Y | `-` | 睡眠数据 |
| `hba1c` | `decimal(3,` | Y | `NULL` | 糖化血红蛋白(%) |
| `rbs` | `varchar(255)` | Y | `NULL` | 随机血糖 |
| `water_ml` | `int` | Y | `NULL` | 饮水量 ml |
| `sleep_min` | `int` | Y | `NULL` | 睡眠时间（分钟） |
| `sleep_des` | `varchar(255)` | Y | `NULL` | 睡眠描述 |
| `step_count` | `int` | Y | `NULL` | 步数 |
| `sports` | `json` | Y | `-` | 运动数据 |
| `symptoms` | `varchar(512)` | Y | `NULL` | 身体症状 |
| `tonic` | `varchar(255)` | Y | `NULL` | 补剂 |
| `breakfast_data` | `json` | Y | `-` | 早餐数据 |
| `lunch_data` | `json` | Y | `-` | 中餐数据 |
| `dinner_data` | `json` | Y | `-` | 晚餐数据 |
| `snack_data` | `json` | Y | `-` | 加餐数据 |
| `food_intake` | `varchar(3000)` | Y | `NULL` | 食物摄入，冗余 |
| `kcal` | `int` | Y | `NULL` | 摄入kacl |
| `cho` | `int` | Y | `NULL` | 碳水 g |
| `fat` | `int` | Y | `NULL` | 脂肪 g |
| `protein` | `int` | Y | `NULL` | 蛋白 g |
| `fiber` | `int` | Y | `NULL` | 纤维 g |
| `vits` | `json` | Y | `-` | 维生素 |
| `vitamins` | `varchar(255)` | Y | `NULL` | 维生素 g 弃用 |
| `kcal_out` | `int` | Y | `NULL` | 消耗kcal |
| `stress` | `varchar(255)` | Y | `NULL` | 压力情况 |
| `medication` | `json` | Y | `-` | 用药情况 |
| `meal_plans` | `json` | Y | `-` | 食谱 |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `body_comp`

- 定位：客户体成分日快照表，保存体脂秤/分析结果及每项指标的范围、状态和分值。
- 粒度：1 行 = 1 个客户在 1 个 date 的体成分快照；由唯一键 (customer_id, date) 保证。
- 逻辑关联：`customer_id`：所属客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 所属客户 -> customers.id |
| `date` | `date` | Y | `NULL` | 日期 |
| `weight` | `decimal(5,` | Y | `NULL` | 体重kg |
| `weight_std` | `tinyint(1)` | Y | `NULL` | 体重标准0偏低，1标准，2偏高 |
| `weight_range` | `json` | Y | `-` | 体重范围 |
| `skeletal` | `decimal(5,` | Y | `NULL` | 骨骼肌量kg |
| `skeletal_std` | `tinyint(1)` | Y | `NULL` | 骨骼肌标准0不足，1标准，2优秀 |
| `skeletal_range` | `json` | Y | `-` | 骨骼肌范围 |
| `smi` | `decimal(5,` | Y | `NULL` | 骨骼肌质量指数 |
| `smi_std` | `tinyint(1)` | Y | `NULL` | 骨骼肌质量指数状态0不足 1标准 |
| `smi_range` | `json` | Y | `-` | 骨骼肌质量指数范围 |
| `whr` | `decimal(5,` | Y | `NULL` | 腰臀比 |
| `whr_range` | `json` | Y | `-` | 腰臀比范围 |
| `std_whr` | `tinyint(1)` | Y | `NULL` | 腰臀比状态0低 1标准 2高 |
| `bmi` | `decimal(5,` | Y | `NULL` | bmi |
| `bmi_range` | `json` | Y | `-` | bmi范围 |
| `bmi_std` | `tinyint(1)` | Y | `NULL` | bmi状态0偏低，1标准，2偏高 |
| `bmr` | `decimal(10,` | Y | `NULL` | bmr |
| `bmr_range` | `json` | Y | `-` | bmr范围 |
| `bmr_std` | `tinyint(1)` | Y | `NULL` | bmr状态0偏低，1标准，2优秀 |
| `fat_grade` | `decimal(5,` | Y | `NULL` | 肥胖等级 |
| `obesity` | `decimal(5,` | Y | `NULL` | 肥胖水平 |
| `obesity_range` | `json` | Y | `-` | 肥胖水平范围 |
| `obesity_std` | `tinyint(1)` | Y | `NULL` | 肥胖水平状态0偏低，标准，1偏高 |
| `heart_rate` | `int` | Y | `NULL` | 心率 |
| `heart_rate_range` | `json` | Y | `-` | 心率范围 |
| `heart_rate_std` | `tinyint` | Y | `NULL` | 心率状态0偏低，1标准，2偏高，3过高 |
| `fat` | `decimal(5,` | Y | `NULL` | 脂肪量 |
| `fat_range` | `json` | Y | `-` | 脂肪范围 |
| `fat_std` | `tinyint` | Y | `NULL` | 脂肪状态0偏低，1标准，2偏高 |
| `body_fat` | `decimal(5,` | Y | `NULL` | 体脂率 |
| `body_fat_range` | `json` | Y | `-` | 体脂率范围 |
| `body_fat_std` | `tinyint` | Y | `NULL` | 体脂率状态0偏低，1标准，2偏高 |
| `sub_fat` | `decimal(5,` | Y | `NULL` | 皮下脂肪 |
| `sub_fat_range` | `json` | Y | `-` | 皮下脂肪范围 |
| `sub_fat_std` | `tinyint` | Y | `NULL` | 皮下脂肪状态0偏低，1标准，2偏高 |
| `sub_fat_pct` | `decimal(5,` | Y | `NULL` | 皮下脂肪率 |
| `sub_fat_pct_range` | `json` | Y | `-` | 皮下脂肪率范围 |
| `sub_fat_pct_std` | `tinyint` | Y | `NULL` | 皮下脂肪率状态0偏低，1标准，2偏高 |
| `fat_control` | `decimal(5,` | Y | `NULL` | 脂肪控制量 |
| `lose_fat_weight` | `decimal(5,` | Y | `NULL` | 去脂体重 |
| `lose_fat_weight_range` | `json` | Y | `-` | 去脂体重范围 |
| `lose_fat_weight_std` | `tinyint` | Y | `NULL` | 去脂体重状态0偏低，1标准，2优秀 |
| `vis_fat` | `decimal(5,` | Y | `NULL` | 内脏脂肪 |
| `vis_fat_range` | `json` | Y | `-` | 内脏脂肪范围 |
| `vis_fat_std` | `tinyint` | Y | `NULL` | 内脏脂肪状态0偏低，1标准，2偏高 |
| `muscle` | `decimal(5,` | Y | `NULL` | 肌肉量 |
| `muscle_range` | `json` | Y | `-` | 肌肉量范围 |
| `muscle_std` | `tinyint` | Y | `NULL` | 肌肉量状态0偏低，1标准，2优秀 |
| `muscle_pct` | `decimal(5,` | Y | `NULL` | 肌肉率 |
| `muscle_pct_range` | `json` | Y | `-` | 肌肉率范围 |
| `muscle_pct_std` | `tinyint(1)` | Y | `NULL` | 肌肉率状态0不足，1标准 2优秀 |
| `skeletal_pct` | `decimal(5,` | Y | `NULL` | 骨骼肌率 |
| `skeletal_pct_range` | `json` | Y | `-` | 骨骼肌率范围 |
| `skeletal_pct_std` | `tinyint(1)` | Y | `NULL` | 骨骼肌率状态0偏低 1标准 2优秀 |
| `bone` | `decimal(5,` | Y | `NULL` | 骨量 |
| `bone_range` | `json` | Y | `-` | 骨量范围 |
| `bone_std` | `tinyint(1)` | Y | `NULL` | 骨量状态0偏低 1标准 2优秀 |
| `muscle_trunk` | `decimal(5,` | Y | `NULL` | 躯干肌肉量 |
| `body_fat_trunk` | `decimal(5,` | Y | `NULL` | 躯干脂肪量 |
| `body_fat_rate_trunk` | `decimal(5,` | Y | `NULL` | 躯干脂肪标准比 |
| `muscle_left_arm` | `decimal(5,` | Y | `NULL` | 左臂肌肉量 |
| `muscle_right_arm` | `decimal(5,` | Y | `NULL` | 右臂肌肉量 |
| `body_fat_left_arm` | `decimal(5,` | Y | `NULL` | 左臂脂肪量 |
| `body_fat_right_arm` | `decimal(5,` | Y | `NULL` | 右臂脂肪量 |
| `muscle_left_leg` | `decimal(5,` | Y | `NULL` | 左腿肌肉量 |
| `muscle_right_leg` | `decimal(5,` | Y | `NULL` | 右腿肌肉量 |
| `body_fat_left_leg` | `decimal(5,` | Y | `NULL` | 左腿脂肪量 |
| `body_fat_right_leg` | `decimal(5,` | Y | `NULL` | 右腿脂肪量 |
| `water` | `decimal(5,` | Y | `NULL` | 体水分量 |
| `water_range` | `json` | Y | `-` | 水分量范围 |
| `water_std` | `tinyint(1)` | Y | `NULL` | 水分量状态0偏低 1标准 2优秀 |
| `water_pct` | `decimal(5,` | Y | `NULL` | 水分率 |
| `water_pct_range` | `json` | Y | `-` | 水分率范围 |
| `water_pct_std` | `tinyint(1)` | Y | `NULL` | 水分率状态0偏低 1标准2优秀 |
| `protein` | `decimal(5,` | Y | `NULL` | 蛋白质 |
| `protein_range` | `json` | Y | `-` | 蛋白质范围 |
| `protein_std` | `tinyint(1)` | Y | `NULL` | 蛋白质状态0偏低 1标准 2优秀 |
| `protein_pct` | `decimal(5,` | Y | `NULL` | 蛋白质率 |
| `protein_pct_range` | `json` | Y | `-` | 蛋白质率范围 |
| `protein_pct_std` | `tinyint(1)` | Y | `NULL` | 蛋白质率状态 0偏低 1标准 2优秀 |
| `cellmass` | `decimal(5,` | Y | `NULL` | 身体细胞量 |
| `cellmass_range` | `json` | Y | `-` | 身体细胞量范围 |
| `cellmass_std` | `tinyint(1)` | Y | `NULL` | 身体细胞量状态0偏低 1标准 2优秀 |
| `water_ec` | `decimal(5,` | Y | `NULL` | 细胞外水量 |
| `water_ec_range` | `json` | Y | `-` | 细胞外水量范围 |
| `water_ec_std` | `tinyint(1)` | Y | `NULL` | 细胞外水量状态0偏低 1标准 2偏高 |
| `mineral` | `decimal(5,` | Y | `NULL` | 无机盐量 |
| `mineral_range` | `json` | Y | `-` | 无机盐范围 |
| `mineral_std` | `tinyint(1)` | Y | `NULL` | 无机盐状态0偏低 1标准 2偏高 |
| `kcal` | `int` | Y | `NULL` | 建议摄入卡路里 |
| `body_type` | `varchar(16)` | Y | `NULL` | 身体类型 |
| `body_health` | `decimal(5,` | Y | `NULL` | 健康评价分 |
| `body_health_std` | `varchar(16)` | Y | `NULL` | 健康评价标题 |
| `body_age` | `int` | Y | `NULL` | 身体年龄 |
| `body_age_std` | `char(6)` | Y | `NULL` | 身体年龄标题 |
| `body_score` | `int` | Y | `NULL` | 健康评分 |
| `body_score_std` | `char(6)` | Y | `NULL` | 健康评分标题 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_glucose`

- 定位：客户连续/离散血糖日数据表，points 为曲线点集合。
- 粒度：1 行 = 1 个客户在 1 个 date 的血糖点位集合。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `date` | `date` | Y | `NULL` | - |
| `points` | `json` | Y | `-` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_heartrate`

- 定位：客户日心率点位表。
- 粒度：1 行 = 1 个客户在 1 个 date 的心率点位集合。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `date` | `date` | Y | `NULL` | - |
| `points` | `json` | Y | `-` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_sleep`

- 定位：客户每日睡眠明细汇总表。
- 粒度：1 行 = 1 个客户在 1 个 date 的睡眠汇总。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `date` | `date` | Y | `NULL` | - |
| `deep_time` | `int` | Y | `NULL` | 深睡min |
| `shallow_time` | `int` | Y | `NULL` | 浅睡min |
| `wake_time` | `int` | Y | `NULL` | 清醒min |
| `start_time` | `datetime` | Y | `NULL` | 开始 |
| `stop_time` | `datetime` | Y | `NULL` | 结束 |
| `total_min` | `int` | Y | `NULL` | 总时长 |
| `score` | `int` | Y | `NULL` | 睡眠评分 |
| `stage` | `json` | Y | `-` | 主睡眠区间4为浅度睡眠状态；5为深度睡眠状态；7为清醒状态；8为REM（快速眼动睡眠） |
| `nap_stage` | `json` | Y | `-` | 零星睡区间 |
| `rem` | `int` | Y | `NULL` | REM睡眠时长min |
| `rhr` | `int` | Y | `NULL` | 静息心率 |
| `sleep_hrv` | `int` | Y | `NULL` | 睡眠心率变异 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_sport`

- 定位：客户每日运动汇总表。
- 粒度：1 行 = 1 个客户在 1 个 date 的运动汇总。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | N | `-` | 客户 -> customers.id |
| `date` | `date` | N | `-` | 日期 |
| `items` | `json` | Y | `-` | 运动项 |
| `total_steps` | `int` | Y | `NULL` | 总步数 |
| `calories` | `int` | Y | `0` | 消耗热量 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | 创建时间 |
| `updated_at` | `datetime` | Y | `NULL` | 更新时间 |

#### `customer_stress`

- 定位：客户压力点位表。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `date` | `date` | Y | `NULL` | - |
| `points` | `json` | Y | `-` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_nutrition_plans`

- 定位：客户营养目标/三大营养素配比表。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | 主键ID |
| `customer_id` | `int` | N | `-` | 客户ID；客户 -> customers.id |
| `total_kcal` | `int` | N | `-` | 总热量 (Kcal) |
| `protein_g` | `int` | N | `-` | 蛋白质 (克) |
| `fat_g` | `int` | N | `-` | 脂肪 (克) |
| `carb_g` | `int` | N | `-` | 碳水化合物 (克) |
| `fib_g` | `int` | Y | `NULL` | 膳食纤维 |
| `p_ratio` | `decimal(10,` | N | `-` | 蛋白质系数 |
| `f_percent` | `decimal(10,` | N | `0.3` | 脂肪热量占比 |
| `active_coef` | `decimal(10,` | Y | `1.3` | 活动系数 |
| `created_at` | `datetime` | N | `CURRENT_TIMESTAMP` | 创建时间 |
| `updated_at` | `datetime` | N | `CURRENT_TIMESTAMP` | 更新时间 |

### A.4 设备接入与第三方穿戴表

#### `customer_device`

- 定位：客户已绑定的设备清单，抽象成统一设备层。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `type` | `tinyint(1)` | Y | `0` | 1手环 2cgm 3血压计 4体脂称 |
| `provider` | `tinyint` | Y | `NULL` | 1华米 2百洋 3乐福 4三诺 |
| `status` | `tinyint(1)` | Y | `0` | 0断开 1连接 |
| `device_id` | `varchar(32)` | Y | `NULL` | sn |
| `device_name` | `varchar(16)` | Y | `NULL` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `unbind_at` | `datetime` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `device_bp_data`

- 定位：血压设备原始测量数据表。
- 粒度：1 行 = 1 次血压设备测量记录。
- 逻辑关联：`customer_id`：客户 -> customers.id；sn 可与 customer_device.device_id 结合

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `sn` | `varchar(32)` | Y | `NULL` | 设备编码 |
| `data_id` | `varchar(64)` | Y | `NULL` | 数据id |
| `time` | `datetime` | Y | `NULL` | 测量时间 |
| `provider` | `varchar(255)` | Y | `NULL` | 厂商 |
| `device_model` | `varchar(255)` | Y | `NULL` | 设备型号 |
| `version` | `int` | Y | `NULL` | 版本 |
| `user` | `varchar(255)` | Y | `NULL` | 测量用户 |
| `systolic_pressure` | `int` | Y | `NULL` | 收缩压 |
| `diastolic_pressure` | `int` | Y | `NULL` | 舒张压 |
| `avg_pressure` | `tinyint` | Y | `NULL` | 平均压 |
| `real_time_pressure` | `tinyint` | Y | `NULL` | 实时血压值 |
| `pulse_rate` | `int` | Y | `NULL` | 脉率 |
| `status` | `tinyint(1)` | Y | `NULL` | 1: 测量中, 2: 测量完成 |
| `imei` | `varchar(255)` | Y | `NULL` | IMEI号 |
| `iccid` | `varchar(255)` | Y | `NULL` | 物联网卡号 |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id；sn 可与 customer_device.device_id 结合 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `device_fat_data`

- 定位：体脂秤原始测量数据表。
- 粒度：1 行 = 1 次体脂秤设备测量记录。
- 逻辑关联：`customer_id`：客户 -> customers.id；sn 可与 customer_device.device_id 结合

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `sn` | `varchar(32)` | Y | `NULL` | - |
| `data_id` | `varchar(64)` | Y | `NULL` | - |
| `time` | `datetime` | Y | `NULL` | 测量时间 |
| `provider` | `varchar(255)` | Y | `NULL` | - |
| `device_model` | `varchar(255)` | Y | `NULL` | - |
| `version` | `int` | Y | `NULL` | - |
| `user` | `varchar(255)` | Y | `NULL` | - |
| `weight` | `int` | Y | `NULL` | 体重 |
| `weight_unit` | `varchar(10)` | Y | `NULL` | 体重单位 (kg: 千克, g: 克, jin: 斤, lb: 磅, st-lb: 英石) |
| `heart_rate` | `int` | Y | `NULL` | 心率 |
| `adc` | `int` | Y | `NULL` | 阻抗 |
| `imei` | `varchar(255)` | Y | `NULL` | IMEI号 |
| `iccid` | `varchar(255)` | Y | `NULL` | 物联网卡号 |
| `mac` | `varchar(32)` | Y | `NULL` | - |
| `scale_type` | `int` | Y | `NULL` | 设备类型（lefu） |
| `impedances` | `json` | Y | `-` | 阻抗（lefu） |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id；sn 可与 customer_device.device_id 结合 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `huami_users`

- 定位：华米第三方账号与客户映射表。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `huami_user_id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `gender` | `tinyint(1)` | Y | `NULL` | 1男 2女 |
| `birthday` | `date` | Y | `NULL` | - |
| `nick_name` | `varchar(32)` | Y | `NULL` | - |
| `avatar` | `varchar(512)` | Y | `NULL` | - |
| `access_token` | `varchar(512)` | Y | `NULL` | - |
| `refresh_token` | `varchar(512)` | Y | `NULL` | - |
| `expires_at` | `datetime` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `huami_devices`

- 定位：华米设备绑定清单。
- 逻辑关联：`huami_user_id`：第三方用户号 -> huami_users.huami_user_id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `huami_user_id` | `int` | Y | `NULL` | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `device_id` | `int` | Y | `NULL` | - |
| `device_type` | `varchar(16)` | Y | `NULL` | - |
| `device_name` | `varchar(32)` | Y | `NULL` | - |
| `mac_address` | `varchar(64)` | Y | `NULL` | - |
| `last_data_sync_time` | `timestamp` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `huami_activities`

- 定位：华米活动日汇总数据。
- 逻辑关联：`huami_user_id`：第三方用户号 -> huami_users.huami_user_id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `huami_user_id` | `int` | Y | `NULL` | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `device_id` | `int` | Y | `NULL` | - |
| `date` | `date` | Y | `NULL` | - |
| `last_sync_time` | `timestamp` | Y | `NULL` | 上传时间戳 |
| `steps` | `int` | Y | `NULL` | 总步数 |
| `distance` | `int` | Y | `NULL` | 总距离 m |
| `walk_time` | `int` | Y | `NULL` | 步行时间 min |
| `run_time` | `int` | Y | `NULL` | 跑步时间 min |
| `run_distance` | `int` | Y | `NULL` | 跑步距离 |
| `calories` | `int` | Y | `NULL` | 总热量 |
| `hour` | `int` | Y | `NULL` | 数分段信息，即将失效 |
| `run_calories` | `int` | Y | `NULL` | 跑步热量 |
| `stage` | `json` | Y | `-` | - |
| `interval_type` | `varchar(16)` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `huami_heartrates`

- 定位：华米分钟级心率明细。
- 粒度：1 行 = 1 个华米用户在 1 天的 1 分钟心率点。
- 逻辑关联：`huami_user_id`：第三方用户号 -> huami_users.huami_user_id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `huami_user_id` | `int` | Y | `NULL` | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `device_id` | `int` | Y | `NULL` | - |
| `date` | `date` | Y | `NULL` | - |
| `minute` | `int` | Y | `NULL` | 分钟序号 |
| `timestamp` | `int` | Y | `NULL` | 数据生成时间 |
| `heart_rate_data` | `int` | Y | `NULL` | 心率 |
| `measure_type` | `varchar(16)` | Y | `NULL` | 测量类型：AUTO、MANUAL |
| `last_sync_time` | `int` | Y | `NULL` | AUTO时提供 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `huami_sleep`

- 定位：华米睡眠日汇总数据。
- 逻辑关联：`huami_user_id`：第三方用户号 -> huami_users.huami_user_id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `huami_user_id` | `int` | Y | `NULL` | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `device_id` | `int` | Y | `NULL` | - |
| `date` | `date` | Y | `NULL` | - |
| `last_sync_time` | `int` | Y | `NULL` | - |
| `deep_sleep_time` | `int` | Y | `NULL` | 深睡min |
| `shallow_sleep_time` | `int` | Y | `NULL` | 浅睡min |
| `wake_time` | `int` | Y | `NULL` | 清醒min |
| `start` | `int` | Y | `NULL` | 开始 |
| `stop` | `int` | Y | `NULL` | 结束 |
| `sleep_score` | `int` | Y | `NULL` | 睡眠评分 |
| `stage` | `json` | Y | `-` | 主睡眠区间 |
| `nap_stage` | `json` | Y | `-` | 零星睡区间 |
| `rem` | `int` | Y | `NULL` | REM睡眠时长min |
| `rhr` | `int` | Y | `NULL` | 静息心率 |
| `sleep_hrv` | `int` | Y | `NULL` | 睡眠心率变异 |
| `interval_type` | `varchar(16)` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `huami_sports`

- 定位：华米单次运动轨迹/运动会话表。
- 粒度：1 行 = 1 次华米运动会话/轨迹。
- 逻辑关联：`huami_user_id`：第三方用户号 -> huami_users.huami_user_id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `huami_user_id` | `int` | Y | `NULL` | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `device_id` | `int` | Y | `NULL` | - |
| `track_id` | `int` | Y | `NULL` | 轨迹ID |
| `source` | `varchar(64)` | Y | `NULL` | - |
| `type` | `varchar(32)` | Y | `NULL` | 类型 |
| `sport_category` | `varchar(16)` | Y | `NULL` | 大类 |
| `start_time` | `int` | Y | `NULL` | 开始时间戳 |
| `end_time` | `int` | Y | `NULL` | 结束时间戳 |
| `sport_time` | `int` | Y | `NULL` | 运动时间 s |
| `distance` | `int` | Y | `NULL` | 距离 |
| `calories` | `int` | Y | `NULL` | 热量 |
| `location` | `varchar(255)` | Y | `NULL` | geohash |
| `average_pace` | `int` | Y | `NULL` | 平均配速 秒/米 |
| `average_step_frequency` | `int` | Y | `NULL` | 步频 步/分钟 |
| `average_stride_length` | `int` | Y | `NULL` | 步长 cm |
| `average_heart_rate` | `int` | Y | `NULL` | 心率 |
| `altitude_ascend` | `int` | Y | `NULL` | 海拔上升量 米 |
| `altitude_descend` | `int` | Y | `NULL` | 海拔下降，米 |
| `total_step` | `int` | Y | `NULL` | 总步数 |
| `second_half_start_time` | `int` | Y | `NULL` | 下半场开始时间，足球 |
| `stroke_count` | `int` | Y | `NULL` | 挥拍次数，网球 |
| `fore_hand_count` | `int` | Y | `NULL` | 正手挥拍，网球 |
| `back_hand_count` | `int` | Y | `NULL` | 反手挥拍，网球 |
| `serve_count` | `int` | Y | `NULL` | 发球次数，网球 |
| `device` | `varchar(32)` | Y | `NULL` | 设备类型 |
| `device_name` | `varchar(64)` | Y | `NULL` | 设备名称 |
| `timestamp` | `int` | Y | `NULL` | 时间c |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

### A.5 习惯、任务与干预计划表

#### `customer_habits`

- 定位：客户持有的习惯实例表，是 habits 模板在客户侧的落地。
- 粒度：1 行 = 1 个客户持有的 1 个习惯实例。
- 逻辑关联：`customer_id`：客户 -> customers.id； `habit_id`：习惯模板 -> habits.id； `anchor_id`：锚点 -> anchors.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `habit_id` | `int` | Y | `NULL` | 习惯模板 -> habits.id |
| `anchor_id` | `int` | Y | `NULL` | 锚点 -> anchors.id |
| `status` | `tinyint(1)` | Y | `1` | 1开始 2暂停 3完成 |
| `target_min` | `varchar(128)` | Y | `NULL` | 保底 |
| `fallback_info` | `varchar(255)` | Y | `NULL` | 保底达成标准描述 |
| `current_streak` | `int` | Y | `0` | 当前连续天数 |
| `fallback_days` | `int` | Y | `NULL` | 保底达成天数 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_obstacles`

- 定位：客户习惯执行中的阻碍及 If-Then 对策表。
- 逻辑关联：`customer_id`：客户 -> customers.id； `customer_habit_id`：客户习惯 -> customer_habits.id； `obstacle_id`：阻碍模板 -> obstacles.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `customer_habit_id` | `int` | Y | `NULL` | 客户习惯 -> customer_habits.id |
| `obstacle_id` | `int` | Y | `NULL` | 阻碍模板 -> obstacles.id |
| `if_then_plan` | `text` | Y | `-` | \ |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_checkin_records`

- 定位：客户习惯打卡事实表，一条记录表示某客户某习惯在某天的打卡结果。
- 粒度：1 行 = 1 个客户的 1 个习惯实例在 1 天的打卡结果；唯一键 (customer_id, customer_habit_id, checkin_date)。
- 逻辑关联：`customer_id`：客户 -> customers.id； `customer_habit_id`：客户习惯实例 -> customer_habits.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `customer_habit_id` | `int` | Y | `NULL` | 客户习惯实例 -> customer_habits.id |
| `checkin_status` | `tinyint(1)` | Y | `0` | 1完成 2阻碍 3未完成 4超额完成 |
| `checkin_date` | `date` | Y | `NULL` | 打卡日期 |
| `notes` | `varchar(255)` | Y | `NULL` | 笔记 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_tasks`

- 定位：客户通用任务主表，可用于重复性目标跟踪。
- 粒度：1 行 = 1 个客户任务定义。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `name` | `varchar(16)` | Y | `NULL` | - |
| `type` | `varchar(16)` | Y | `NULL` | - |
| `status` | `tinyint(1)` | Y | `0` | 0进行中 1已完成 |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `repeat_type` | `tinyint(1)` | Y | `0` | 0一次性  1每天 2每周 3每月 |
| `target_count` | `int` | Y | `NULL` | 目标次数（每周几次，每月几次） |
| `start_date` | `date` | Y | `NULL` | 开始日期 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_task_checkins`

- 定位：客户任务打卡明细表。
- 粒度：1 行 = 1 个任务在 1 天的打卡。
- 逻辑关联：`task_id`：客户任务 -> customer_tasks.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `task_id` | `int` | Y | `NULL` | 客户任务 -> customer_tasks.id |
| `checkin_date` | `date` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_plans`

- 定位：客户干预计划/服务计划实例主表。
- 粒度：1 行 = 1 个客户计划实例。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `title` | `varchar(32)` | Y | `NULL` | 名称 |
| `description` | `varchar(512)` | Y | `NULL` | 描述 |
| `status` | `tinyint(1)` | Y | `0` | 状态0未完成 1已完成 |
| `total_days` | `int` | Y | `NULL` | 总天数 |
| `payment` | `int` | Y | `NULL` | 付费金额（分） |
| `start_date` | `date` | Y | `NULL` | 开始日期 |
| `pause_date` | `date` | Y | `NULL` | 暂停日期 |
| `resume_date` | `date` | Y | `NULL` | 暂停恢复日期 |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_todos`

- 定位：客户计划下的待办/日程明细表。
- 粒度：1 行 = 1 个客户计划在某天/某阶段的待办明细。
- 逻辑关联：`plan_id`：客户计划 -> customer_plans.id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `orig_date` | `date` | Y | `NULL` | 计划日期 |
| `todo_date` | `date` | Y | `NULL` | 执行日期 |
| `plan_id` | `int` | N | `-` | 计划id；客户计划 -> customer_plans.id |
| `type` | `tinyint(1)` | Y | `0` | 0每天 1区间 |
| `status` | `tinyint(1)` | Y | `0` | 状态0未开始 1进行中 2已完成 3暂停 |
| `sort_order` | `int` | Y | `0` | 排序 |
| `day_num` | `int` | Y | `NULL` | 第几天 |
| `items` | `json` | Y | `-` | 任务项 |
| `comp_at` | `datetime` | Y | `NULL` | 完成时间 |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `coach_sched`

- 定位：教练面向客户的日程/排期/待处理事项表。
- 逻辑关联：`customer_id`：客户 -> customers.id； `coach_id`：教练 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `title` | `varchar(32)` | Y | `NULL` | 标题 |
| `content` | `varchar(64)` | Y | `NULL` | 内容 |
| `start_date` | `date` | Y | `NULL` | - |
| `end_date` | `date` | Y | `NULL` | - |
| `status` | `tinyint(1)` | Y | `0` | 状态0待处理 1进行中 2已处理 3未开始 |
| `dones` | `json` | Y | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `coach_id` | `int` | Y | `NULL` | 教练 -> admins.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `coach_tel`

- 定位：教练电话预约/回访记录表。
- 逻辑关联：`coach_id`：教练 -> admins.id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `status` | `tinyint(1)` | Y | `0` | 0未完成 1已完成 |
| `coach_id` | `int` | Y | `NULL` | 教练 -> admins.id |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `booked_date` | `date` | Y | `NULL` | 预约日期 |
| `booked_time` | `varchar(16)` | Y | `NULL` | 预约时间 |
| `completed_at` | `datetime` | Y | `NULL` | 完成日期 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `coach_todos`

- 定位：教练执行的客户计划任务明细表，通常挂在 customer_plans 下。
- 逻辑关联：`coach_id`：教练 -> admins.id； `customer_id`：客户 -> customers.id； `plan_id`：客户计划 -> customer_plans.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `coach_id` | `int` | Y | `NULL` | 教练id；教练 -> admins.id |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `plan_id` | `int` | Y | `NULL` | 客户计划id；客户计划 -> customer_plans.id |
| `step` | `int` | Y | `NULL` | 阶段 |
| `status` | `tinyint(1)` | Y | `0` | 状态0未开始 1进行中 2已完成 |
| `remark` | `varchar(255)` | Y | `NULL` | 备注 |
| `start_at` | `datetime` | Y | `NULL` | 开始时间 |
| `comp_at` | `datetime` | Y | `NULL` | 完成时间 |
| `v_type` | `tinyint(1)` | Y | `NULL` | 值类型 0文字 1链接 2图片 |
| `val` | `varchar(255)` | Y | `NULL` | 值 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

### A.6 课程学习表

#### `customer_course_plan`

- 定位：客户被分配的课程计划实例表，记录当前学到第几天。
- 粒度：1 行 = 1 个客户被分配的 1 个课程计划实例。
- 逻辑关联：`customer_id`：客户 -> customers.id； `plan_id`：课程计划 -> course_plans.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `plan_id` | `int` | Y | `NULL` | 计划id；课程计划 -> course_plans.id |
| `current_day` | `int` | Y | `NULL` | 当前天数 |
| `max_pending` | `int` | Y | `10` | 待学习最大数量,大于计划里面的天数无效 |
| `started_at` | `date` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_course_record`

- 定位：客户-课程学习状态事实表，记录是否开始/完成、学习时长和分配日期。
- 粒度：1 行 = 1 个客户对 1 门课程的学习状态；唯一键 (customer_id, course_id)。
- 逻辑关联：`customer_id`：客户 -> customers.id； `course_id`：课程 -> course.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `course_id` | `int` | Y | `NULL` | 课程id；课程 -> course.id |
| `status` | `tinyint(1)` | Y | `0` | 0未开始 1学习中 2已完成 |
| `start_at` | `datetime` | Y | `NULL` | 开始时间 |
| `completed_at` | `datetime` | Y | `NULL` | 完成时间 |
| `study_seconds` | `int` | Y | `NULL` | 时长s |
| `assign_date` | `date` | Y | `NULL` | - |
| `sort_order` | `int` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

### A.7 AI 会话与消息表

#### `chats`

- 定位：客户与 AI 助手的会话主表，一次会话对应多条 messages。
- 粒度：1 行 = 1 个客户与 1 个助手的一次对话会话。
- 逻辑关联：`customer_id`：会话所属客户 -> customers.id； `assistant_id`：主助手 -> assistants.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int UNSIGNED` | N | `-` | - |
| `title` | `varchar(128)` | Y | `NULL` | 标题 |
| `status` | `tinyint(1)` | Y | `1` | 状态 0关闭 1进行 |
| `customer_id` | `int` | Y | `NULL` | 会话所属客户 -> customers.id |
| `assistant_id` | `int UNSIGNED` | Y | `NULL` | 主助手 -> assistants.id |
| `assistant_ids` | `json` | Y | `-` | 多专家会诊 |
| `conversation_id` | `varchar(64)` | Y | `NULL` | - |
| `mode` | `tinyint(1)` | Y | `1` | - |
| `created_at` | `datetime` | N | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `messages`

- 定位：会话消息明细表，role 区分用户/助手，action 描述消息业务类型。
- 粒度：1 行 = 1 条会话消息。
- 逻辑关联：`chat_id`：会话 -> chats.id； `assistant_id`：发送助手 -> assistants.id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint UNSIGNED` | N | `-` | - |
| `chat_id` | `int UNSIGNED` | N | `-` | 会话 -> chats.id |
| `assistant_id` | `int` | Y | `NULL` | 发送助手 -> assistants.id |
| `customer_id` | `int UNSIGNED` | Y | `NULL` | 客户 -> customers.id |
| `role` | `varchar(16)` | N | `-` | - |
| `action` | `varchar(32)` | Y | `'chat'` | chat(普通聊天) notify提醒，event事件  course课件 |
| `action_data` | `json` | Y | `-` | - |
| `content` | `text` | Y | `-` | - |
| `content_type` | `tinyint(1)` | Y | `0` | 0文字 1图片 2图文 3视频 4音频 5文档 |
| `token_count` | `int` | Y | `NULL` | - |
| `status` | `tinyint(1)` | Y | `1` | 0待处理 1已处理 |
| `created_at` | `datetime` | N | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

### A.8 标签与画像表

#### `customer_label_values`

- 定位：客户标签实例值表，结合 label_definition 形成用户画像。
- 逻辑关联：`customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint UNSIGNED` | N | `-` | 自增主键 |
| `customer_id` | `int UNSIGNED` | N | `-` | 用户唯一标识（用于匹配别的表）；客户 -> customers.id |
| `label_key` | `varchar(50)` | N | `-` | 关联标签定义的key |
| `label_value` | `text` | N | `-` | 该用户的实际取值 |
| `sample_data` | `text` | Y | `-` | 示例/采样数据参考 |
| `updated_at` | `timestamp` | N | `CURRENT_TIMESTAMP` | - |

### A.9 后台管理员与教练表

#### `admins`

- 定位：后台管理员/教练主表。系统里“教练”并没有单独建表，绝大多数 coach_id 实际都应映射到 admins.id。
- 粒度：1 行 = 1 个后台账号/教练账号。
- 逻辑关联：`dept_id`：所属部门 -> sys_dept.id； `mentor_id`：导师/师傅 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `username` | `varchar(32)` | Y | `NULL` | - |
| `password` | `varchar(64)` | Y | `NULL` | - |
| `nick_name` | `varchar(16)` | Y | `NULL` | - |
| `real_name` | `varchar(16)` | Y | `NULL` | - |
| `avatar` | `varchar(64)` | Y | `NULL` | - |
| `salt` | `char(6)` | Y | `NULL` | - |
| `status` | `tinyint(1)` | Y | `0` | - |
| `type` | `tinyint(1)` | Y | `0` | - |
| `assignable` | `tinyint(1)` | Y | `0` | 是否允许分配用户 |
| `wxwork` | `varchar(16)` | Y | `NULL` | - |
| `settings` | `varchar(128)` | Y | `NULL` | - |
| `dept_id` | `int` | Y | `NULL` | 所属部门 -> sys_dept.id |
| `is_mentor` | `tinyint(1)` | Y | `0` | 是否师傅 0否1是 |
| `mentor_id` | `int` | Y | `NULL` | 师傅id；导师/师傅 -> admins.id |
| `last_login_time` | `datetime` | Y | `NULL` | - |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `coach_label_values`

- 定位：教练标签实例值表，结合 label_definition 形成教练画像。
- 逻辑关联：`coach_id`：教练 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint UNSIGNED` | N | `-` | 自增主键 |
| `coach_id` | `int UNSIGNED` | N | `-` | 教练唯一标识；教练 -> admins.id |
| `label_key` | `varchar(50)` | N | `-` | 关联标签定义的key(如: core_specialty) |
| `label_value` | `text` | N | `-` | 教练的属性值 |
| `updated_at` | `timestamp` | N | `CURRENT_TIMESTAMP` | - |

### A.10 提醒、通知与服务表

#### `customer_reminders`

- 定位：客户提醒主表，支持单次/每日/每周/每月和业务类型。
- 粒度：1 行 = 1 个提醒规则。
- 逻辑关联：`customer_id`：客户 -> customers.id； `tpl_id`：通知模板 -> notify_tpl.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `title` | `varchar(16)` | Y | `NULL` | - |
| `description` | `varchar(64)` | Y | `NULL` | - |
| `status` | `tinyint` | Y | `1` | 0关闭 1进行中 2完成 3过期 |
| `repeat_type` | `tinyint` | Y | `0` | 0单次,1每日,2每周,3每月 |
| `weekdays_mask` | `tinyint` | Y | `NULL` | 周星期掩码 |
| `month_days` | `json` | Y | `-` | 每月几号[] |
| `max_occurrences` | `int` | Y | `NULL` | - |
| `expire_after_days` | `int` | Y | `NULL` | - |
| `triggered_count` | `int` | Y | `0` | - |
| `last_triggered_at` | `datetime` | Y | `NULL` | - |
| `completed_at` | `datetime` | Y | `NULL` | - |
| `business_type` | `tinyint` | Y | `0` | 0其他 1喝水 2运动 3睡眠 4饮食 5血糖 6体重 7用药 8冥想 |
| `raw_data` | `json` | Y | `-` | 通知数据 |
| `tpl_id` | `int` | Y | `NULL` | 模板id；通知模板 -> notify_tpl.id |
| `channel` | `tinyint` | Y | `NULL` | 提醒渠道0系统 1服务号 |
| `style` | `json` | Y | `-` | 样式{icon,color} |
| `created_at` | `datetime` | Y | `NULL` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `customer_reminder_times`

- 定位：提醒的具体触发时间点子表。
- 粒度：1 行 = 1 个提醒规则下的 1 个触发时间点。
- 逻辑关联：`reminder_id`：提醒主表 -> customer_reminders.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `reminder_id` | `int` | N | `-` | 提醒主表 -> customer_reminders.id |
| `reminder_time` | `varchar(5)` | N | `-` | HH:MM |
| `last_triggered_at` | `datetime` | Y | `NULL` | - |
| `triggered_count` | `int` | Y | `0` | - |
| `created_at` | `datetime` | Y | `NULL` | - |

#### `notify`

- 定位：待发送/已发送的通知任务表。
- 逻辑关联：`tpl_id`：通知模板 -> notify_tpl.id； `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `status` | `tinyint` | Y | `0` | 状态：0待发送 1发送中 2已发送 3发送失败 |
| `to_users` | `json` | Y | `-` | - |
| `type` | `tinyint` | Y | `0` | 类型 1服务号 |
| `raw_data` | `json` | Y | `-` | - |
| `jump_page` | `varchar(255)` | Y | `NULL` | 跳转链接 |
| `business_type` | `tinyint` | Y | `NULL` | - |
| `sched_at` | `datetime` | Y | `NULL` | - |
| `sent_at` | `datetime` | Y | `NULL` | - |
| `error_msg` | `varchar(500)` | Y | `NULL` | - |
| `tpl_id` | `int` | Y | `NULL` | 通知模板 -> notify_tpl.id |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `service_issues`

- 定位：客户服务问题/工单表。
- 粒度：1 行 = 1 个服务问题/工单。
- 逻辑关联：`customer_id`：客户 -> customers.id； `admin_id`：处理人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `name` | `varchar(64)` | Y | `NULL` | 标题 |
| `description` | `varchar(512)` | Y | `NULL` | 描述 |
| `status` | `tinyint(1)` | Y | `0` | 状态0未解决 1已解决 |
| `solution` | `varchar(512)` | Y | `NULL` | 解决方案 |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `admin_id` | `int` | Y | `NULL` | 管理员id；处理人 -> admins.id |
| `completed_at` | `datetime` | Y | `NULL` | 完成时间 |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `service_log`

- 定位：服务过程日志表。
- 逻辑关联：`customer_id`：客户 -> customers.id； `admin_id`：操作人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `int` | N | `-` | - |
| `msg` | `varchar(512)` | Y | `NULL` | - |
| `type` | `tinyint(1)` | Y | `0` | 类型0 系统 |
| `customer_id` | `int` | Y | `NULL` | 客户id；客户 -> customers.id |
| `admin_id` | `int` | Y | `NULL` | 操作人id；操作人 -> admins.id |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

### A.11 积分、餐食识别与异步任务表

#### `point_logs`

- 定位：积分/经验流水表。
- 粒度：1 行 = 1 次积分/经验变动流水。
- 逻辑关联：`customer_id`：客户 -> customers.id； `creator_id`：创建人/操作人 -> admins.id 或用户侧主体（需结合 source 判断）

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | Y | `NULL` | 客户 -> customers.id |
| `type` | `tinyint` | Y | `0` | 0获得 1消费 |
| `num` | `int` | Y | `NULL` | 积分变化 |
| `exp` | `int` | Y | `NULL` | 经验变化 |
| `source` | `tinyint` | Y | `0` | 来源 0系统 1用户 2教练 |
| `des` | `varchar(64)` | Y | `NULL` | 描述 |
| `category` | `tinyint` | Y | `0` | 0其他 1完成任务 2运动打卡 3饮食记录 4健康监测 5社群互动 6系统调整 |
| `creator_id` | `int` | Y | `NULL` | 创建人；创建人/操作人 -> admins.id 或用户侧主体（需结合 source 判断） |
| `created_at` | `datetime` | Y | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | Y | `NULL` | - |

#### `meal_tasks`

- 定位：餐食识别/处理任务表，通常由 AI/工作流处理上传图片得到 food_data。
- 粒度：1 行 = 1 次餐食识别任务/上传任务。
- 逻辑关联：`customer_id`：客户 -> customers.id； `work_task_id`：工作流任务 -> work_tasks.id

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `customer_id` | `int` | N | `-` | 客户 -> customers.id |
| `record_date` | `date` | N | `-` | 记录日期 |
| `meal_type` | `tinyint(1)` | N | `-` | 餐次类型 1早餐 2中餐 3晚餐 4加餐 |
| `work_task_id` | `int` | N | `-` | 工作流任务 -> work_tasks.id |
| `file_url` | `varchar(800)` | Y | `NULL` | - |
| `file_name` | `varchar(255)` | Y | `NULL` | - |
| `food_data` | `json` | Y | `-` | 识别出的食物数据：{name, kcal, imgs, time} |
| `status` | `tinyint(1)` | Y | `0` | 状态 0待处理 1处理中 2已完成 3失败 |
| `is_aggregated` | `tinyint(1)` | Y | `0` | 是否处理 |
| `aggregated_at` | `datetime` | Y | `NULL` | 处理时间 |
| `snack_index` | `int` | Y | `NULL` | - |
| `error` | `text` | Y | `-` | - |
| `created_at` | `datetime` | N | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `datetime` | N | `CURRENT_TIMESTAMP` | - |

#### `work_tasks`

- 定位：异步工作任务/工作流任务表，是 AI、识别、自动化能力的调度中心。
- 粒度：1 行 = 1 个异步工作任务。
- 逻辑关联：`creator_id`：任务创建人 -> admins.id； `business_id`：多态业务对象，需结合 business_type 解释

| 字段 | 类型 | 可空 | 默认值 | 说明 / 关系 |
|---|---|---|---|---|
| `id` | `bigint` | N | `-` | - |
| `title` | `varchar(64)` | Y | `NULL` | - |
| `task_type` | `varchar(32)` | N | `-` | - |
| `provider` | `varchar(16)` | Y | `NULL` | - |
| `workflow_id` | `varchar(32)` | Y | `NULL` | - |
| `assistant_code` | `varchar(64)` | Y | `NULL` | - |
| `params` | `json` | Y | `-` | - |
| `status` | `tinyint(1)` | Y | `0` | - |
| `original_path` | `varchar(128)` | Y | `NULL` | - |
| `result` | `json` | Y | `-` | - |
| `error` | `text` | Y | `-` | - |
| `creator_id` | `int` | Y | `NULL` | 任务创建人 -> admins.id |
| `completed_at` | `datetime` | Y | `NULL` | - |
| `external_task_id` | `varchar(100)` | Y | `NULL` | - |
| `retry_count` | `int` | Y | `0` | - |
| `business_type` | `tinyint` | Y | `NULL` | - |
| `business_id` | `int` | Y | `NULL` | 多态业务对象，需结合 business_type 解释 |
| `business_date` | `date` | Y | `NULL` | - |
| `created_at` | `timestamp` | N | `CURRENT_TIMESTAMP` | - |
| `updated_at` | `timestamp` | N | `CURRENT_TIMESTAMP` | - |

