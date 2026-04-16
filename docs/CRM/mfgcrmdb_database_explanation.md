# mfgcrmdb 数据库业务解释说明（面向数据分析机器人）

> 目标：让机器人不仅知道“有哪些表和字段”，更知道**它们在业务上分别扮演什么角色、如何关联、什么口径该怎么取、哪些地方容易误解**。  
> 数据依据：你上传的 MySQL 8.0.36 结构导出文件 `mfgcrmdb.sql`。fileciteturn0file0


## 0. 这份数据库在业务上的总体定位

从表结构看，`mfgcrmdb` 不是单一的“销售 CRM”，而是一个**健康管理/慢病管理/教练服务平台**的综合业务库。它至少覆盖了以下几条业务主线：

1. **客户主数据与身份体系**：客户基础资料、账号、微信 OAuth 身份、家庭、渠道来源、负责人分配。
2. **健康监测与设备接入**：体成分、血糖、血压、睡眠、心率、压力、运动，以及第三方华米设备/体脂秤/血压计原始数据。
3. **习惯养成与干预计划**：锚点、习惯模板、客户习惯、打卡、阻碍、If-Then 对策、客户任务、客户计划、待办。
4. **课程与内容学习**：课程素材、课程计划、客户学习计划、学习进度、课件体系。
5. **AI/自动化能力**：助手配置、对话会话、消息记录、餐食识别任务、异步工作流任务。
6. **标签画像与智能决策**：用户标签、教练标签、标签定义、用户-教练匹配逻辑。
7. **服务运营闭环**：提醒、通知、服务问题、服务日志、积分经验、商品推荐。
8. **后台组织与权限**：管理员、部门、角色、菜单、公告。

这一判断完全来自你上传的建表 SQL dump，本回答中的所有字段、约束、关系说明都以该结构为依据。fileciteturn0file0

## 1. 机器人理解这个库时必须先记住的 12 条规则

### 1.1 这个库**几乎没有显式外键**
表之间没有真正的 `FOREIGN KEY` 约束，大部分关系只能依赖字段命名、唯一键、索引和业务注释去推断。  
所以机器人必须把“**逻辑关联**”和“**数据库强约束**”区分开：

- 数据库强约束：主键、唯一键、索引；
- 逻辑关联：`customer_id`、`admin_id`、`coach_id`、`plan_id` 等命名约定推断出的关系。

### 1.2 `customers` 是全库最核心的业务主实体
绝大多数业务事实都围绕 `customers.id` 发生：健康记录、设备数据、习惯、课程、提醒、群组、服务问题、积分、聊天等。  
所以做数分时，默认从 `customers` 出发建客户视角宽表。

### 1.3 “教练”没有单独的 coach 表，通常就是 `admins`
库里有大量 `coach_id`，但没有 `coaches` 表；因此绝大多数情况下：
- `coach_id` 逻辑上对应 `admins.id`
- 教练只是 `admins` 中某类角色/人员

这是本库最重要的隐式关系之一。fileciteturn0file0

### 1.4 同一业务往往同时存在“主表 + 汇总表 + 原始表 + JSON 扩展”
例如健康数据：
- `customer_health`：按天汇总宽表
- `body_comp`：体成分按天快照
- `device_bp_data` / `device_fat_data`：设备原始数据
- `customer_glucose` / `customer_heartrate` / `customer_sleep` / `customer_sport` / `customer_stress`：专项明细或点位
- `huami_*`：第三方源数据

所以分析时必须先确认你要的是：
- **业务口径汇总**（优先 `customer_health` 等业务表）
- 还是**设备原始口径**（优先 `device_*`, `huami_*`）

### 1.5 本库有大量 JSON 字段
JSON 字段广泛存在于健康、课程、消息、提醒、任务等表中。  
这意味着一部分关键业务信息并不在传统列里，而在 JSON 内部；机器人回答数分问题时要能识别“字段在列里”还是“字段在 JSON 里”。

### 1.6 存在明显的历史/遗留/重复体系
最典型的有：

- `course` 与 `lesson`：两套课程内容体系并存
- `course_copy1`：明显是历史副本/备份性质的表
- `customer_star`：字段命名用 camelCase（`adminId`, `customerId`, `createdAt`），和全库主流 snake_case 不一致
- `customer_health.glucose_data` 与 `blood_suger` 同时存在，且注释表明前者“弃用”

所以机器人不能假设“同名业务只有一套表”。

### 1.7 `customer_info` 不是严格 1:1 静态扩展表，更像客户画像版本表
虽然表名像“客户扩展表”，但它有：
- `is_archived`
- `archived_at`
- `archived_by`
- `archive_reason`
- 索引 `idx_customer_archived_id(customer_id, is_archived, id)`

这说明一个客户可能有多条画像记录，通常要选：
- 当前有效：`is_archived = 0`
- 或最近一条：同 `customer_id` 下最大 `id` / 最新 `created_at`

### 1.8 多张表是桥接关系表
例如：
- `customer_groups`：客户-群组
- `group_coachs`：群组-教练
- `sys_admin_role`：管理员-角色
- `sys_role_menu`：角色-菜单

这些表不能当“主实体”理解，而要当**多对多桥表**。

### 1.9 多个 `business_id` / `business_type` 字段是多态关联
`document`、`work_tasks` 等表里的 `business_id` 不能单独解读，必须结合 `business_type` 一起判断它指向哪张业务表。  
这是一个很典型的“应用层多态关联”设计。

### 1.10 日期粒度并不统一
有的表按 `date`，有的按 `record_date`，有的按 `assign_date`，有的按 `created_at` / `completed_at` / `start_date` / `todo_date`。  
做分析前必须先定义时间口径，例如：
- 注册时间
- 渠道进入时间
- 干预开始时间
- 健康记录日期
- 设备测量时间
- 消息发送时间

### 1.11 很多事实表天然是“宽表 + 状态码”模型
如 `customer_health`、`customer_course_record`、`customer_reminders`、`service_issues`、`work_tasks`，核心含义往往是：
- 谁（customer/admin/assistant）
- 在什么时候
- 发生了一件什么事情
- 当前状态是什么

### 1.12 不要默认所有 `customer_id` 都能直接对齐成 1 条“当前状态”
因为同一客户可能同时拥有：
- 多条计划
- 多个习惯
- 多个提醒
- 多次服务记录
- 多段负责人历史
- 多个第三方设备绑定
- 多个会话
- 多个课程/学习记录

机器人做分析时必须先确认数据粒度。fileciteturn0file0

## 2. 建议机器人采用的总体业务地图

### 2.1 客户生命周期主线
可按下面这条主线理解：

`渠道 channels -> 客户 customers -> 负责人 customer_staff/admins -> 健康画像 customer_info -> 干预计划 customer_plans -> 每日待办 customer_todos / 习惯 customer_habits -> 打卡 customer_checkin_records / 学习 customer_course_record / 健康记录 customer_health -> 服务问题 service_issues / 消息 chats+messages / 提醒 customer_reminders -> 积分 point_logs`

### 2.2 设备与健康数据主线
`customers -> customer_device -> device_* 原始数据`
以及
`customers -> huami_users -> huami_* 第三方明细`
再汇总或映射进：
`customer_health / body_comp / customer_sleep / customer_sport / customer_glucose / customer_heartrate`

### 2.3 课程学习主线
`course_plans -> course_plan_days -> course`
再分配到：
`customer_course_plan -> customer_course_record`

### 2.4 习惯养成主线
`anchors -> habits -> customer_habits -> customer_checkin_records`
若有阻碍：
`customer_habits -> customer_obstacles -> obstacles`

### 2.5 AI/自动化主线
`assistants -> chats -> messages`
以及  
`work_tasks -> meal_tasks`
说明平台中存在 AI 助手聊天与异步自动处理能力。

## 3. 适合机器人直接使用的标准事实表 / 维表划分

### 3.1 核心维表（dimension）
- `customers`
- `admins`
- `channels`
- `groups`
- `assistants`
- `anchors`
- `habits`
- `course`
- `course_plans`
- `product_category`
- `label_definition`
- `sys_dept`
- `sys_role`
- `sys_menu`

### 3.2 核心事实表（fact）
- `customer_health`
- `body_comp`
- `customer_glucose`
- `customer_heartrate`
- `customer_sleep`
- `customer_sport`
- `customer_checkin_records`
- `customer_course_record`
- `customer_todos`
- `messages`
- `point_logs`
- `service_issues`
- `device_bp_data`
- `device_fat_data`
- `meal_tasks`
- `work_tasks`

### 3.3 桥表（bridge）
- `customer_groups`
- `group_coachs`
- `sys_admin_role`
- `sys_role_menu`
- `customer_staff`
- `customer_star`

## 4. 机器人回答数分问题时推荐优先使用的口径

1. **客户基础画像**：`customers` + 当前有效 `customer_info`
2. **客户健康日报**：优先 `customer_health`
3. **体成分变化趋势**：优先 `body_comp`
4. **设备原始测量**：`device_bp_data` / `device_fat_data` / `huami_*`
5. **习惯执行情况**：`customer_habits` + `customer_checkin_records`
6. **课程学习情况**：`customer_course_plan` + `customer_course_record`
7. **干预计划执行**：`customer_plans` + `customer_todos` + `coach_todos`
8. **AI 对话分析**：`chats` + `messages`
9. **提醒触达分析**：`customer_reminders` + `customer_reminder_times` + `notify`
10. **服务过程分析**：`service_issues` + `service_log`
11. **积分行为分析**：`point_logs`
12. **标签匹配分析**：`label_definition` + `customer_label_values` + `coach_label_values`

## 5. 高风险歧义与分析注意事项

### 5.1 `users` vs `customers`
- `users` 更像账号表
- `customers` 是业务客户主表
- 两者通过 `users.customer_id` 和 `customers.user_id` 相互关联，但并无强约束
- 分析“客户数”时应以 `customers` 为主；分析“注册账号数”时才以 `users` 为主

### 5.2 `course` vs `lesson`
这两张表都属于内容体系，但定位并不相同：
- `course` 更像标准化课程素材
- `lesson` 更像复杂课件/互动内容体系，含 `contents`、`branchs`、`tags` 等 JSON 结构
如果问题是“课程学习进度”，优先沿 `course` 体系；如果问题是“课件内容管理”，再考虑 `lesson`。

### 5.3 `customer_health` vs 专项健康表 vs 设备原始表
- 想看“业务端每日综合记录” -> `customer_health`
- 想看“某项生理指标的日汇总/点位” -> `customer_glucose` / `customer_sleep` / `customer_heartrate` / `customer_sport`
- 想看“设备级原始上传” -> `device_*` / `huami_*`

### 5.4 `customer_plans` vs `course_plans`
- `customer_plans`：客户干预/服务计划
- `course_plans`：课程学习计划模板
这两个 `plan` 不是一回事。

### 5.5 `coach_id` 的真实含义
没有独立教练表，通常将其解释为 `admins.id`，但最好结合角色表 `sys_role` / `sys_admin_role` 进一步判断该 admin 是否属于教练角色。

### 5.6 JSON 字段中可能藏着真正的业务明细
例如：
- `customer_health.breakfast_data/lunch_data/dinner_data/snack_data`
- `customer_health.medication`
- `meal_tasks.food_data`
- `messages.action_data`
- `work_tasks.params/result`
- `plan_tpl.items`
- `customer_todos.items`

如果机器人只看结构化列，会漏掉大量业务信息。  


## 6. 表级数据字典（按业务域分组）


## 一、后台组织与权限

### `admins`
- **定位**：后台管理员/教练主表。系统里“教练”并没有单独建表，绝大多数 coach_id 实际都应映射到 admins.id。
- **表注释**：admins-lwp
- **推荐理解粒度**：1 行 = 1 个后台账号/教练账号。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `dept_id`：所属部门 -> sys_dept.id
  - `mentor_id`：导师/师傅 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `username` | `varchar(32)` | Y | NULL |  |  |
| `password` | `varchar(64)` | Y | NULL |  |  |
| `nick_name` | `varchar(16)` | Y | NULL |  |  |
| `real_name` | `varchar(16)` | Y | NULL |  |  |
| `avatar` | `varchar(64)` | Y | NULL |  |  |
| `salt` | `char(6)` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 0 |  |  |
| `type` | `tinyint(1)` | Y | 0 |  |  |
| `assignable` | `tinyint(1)` | Y | 0 | 是否允许分配用户 |  |
| `wxwork` | `varchar(16)` | Y | NULL |  |  |
| `settings` | `varchar(128)` | Y | NULL |  |  |
| `dept_id` | `int` | Y | NULL |  | 所属部门 -> sys_dept.id |
| `is_mentor` | `tinyint(1)` | Y | 0 | 是否师傅 0否1是 |  |
| `mentor_id` | `int` | Y | NULL | 师傅id | 导师/师傅 -> admins.id |
| `last_login_time` | `datetime` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `sys_dept`
- **定位**：部门表。
- **表注释**：dept -lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `pid`：父部门 -> sys_dept.id（自关联）

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(16)` | Y | NULL |  |  |
| `pid` | `int` | Y | 0 |  | 父部门 -> sys_dept.id（自关联） |
| `status` | `tinyint(1)` | Y | 1 |  |  |
| `sort` | `int` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `sys_role`
- **定位**：后台角色表。
- **表注释**：role -lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `admin_id`：角色创建人/负责人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `code` | `varchar(16)` | Y | NULL |  |  |
| `name` | `varchar(16)` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 1 |  |  |
| `admin_id` | `int` | Y | NULL |  | 角色创建人/负责人 -> admins.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `sys_admin_role`
- **定位**：管理员与角色多对多关系表。
- **表注释**：admin-role -lwp
- **推荐理解粒度**：1 行 = 1 个管理员与 1 个角色的关系。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`admin_id`, `role_id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `admin_id`：管理员 -> admins.id
  - `role_id`：角色 -> sys_role.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `admin_id` | `int` | N |  |  | 管理员 -> admins.id |
| `role_id` | `int` | N |  |  | 角色 -> sys_role.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `sys_menu`
- **定位**：后台菜单/权限资源表。
- **表注释**：menu -lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `pid`：父菜单 -> sys_menu.id（自关联）

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(16)` | Y | NULL |  |  |
| `path` | `varchar(32)` | Y | NULL |  |  |
| `component` | `varchar(64)` | Y | NULL |  |  |
| `pid` | `int` | Y | 0 |  | 父菜单 -> sys_menu.id（自关联） |
| `permission` | `varchar(32)` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 1 |  |  |
| `hidden` | `tinyint(1)` | Y | 0 |  |  |
| `type` | `tinyint(1)` | Y | 0 |  |  |
| `icon` | `varchar(32)` | Y | NULL |  |  |
| `sort` | `int` | Y | NULL |  |  |
| `keep_alive` | `tinyint(1)` | Y | 0 |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `sys_role_menu`
- **定位**：角色与菜单多对多授权关系表。
- **表注释**：role-menu -lwp
- **推荐理解粒度**：1 行 = 1 个角色与 1 个菜单的授权关系。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`role_id`, `menu_id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `role_id`：角色 -> sys_role.id
  - `menu_id`：菜单 -> sys_menu.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `role_id` | `int` | N |  |  | 角色 -> sys_role.id |
| `menu_id` | `int` | N |  |  | 菜单 -> sys_menu.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `sys_notices`
- **定位**：系统公告表。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `admin_id`：发布者 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `title` | `varchar(255)` | Y | NULL | 标题 |  |
| `content_type` | `tinyint(1)` | Y | 0 | 内容类型0文字 1链接 |  |
| `content` | `varchar(255)` | Y | NULL | 内容 |  |
| `type` | `tinyint(1)` | Y | 0 | 类型 0系统通知 1更新 |  |
| `role_ids` | `json` | Y |  | 可查看的角色 |  |
| `admin_id` | `int` | Y | NULL | 发布者id | 发布者 -> admins.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `sys_notice_reads`
- **定位**：系统公告阅读记录表。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `notice_id`：公告 -> sys_notices.id
  - `admin_id`：阅读者 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `notice_id` | `int` | Y | NULL |  | 公告 -> sys_notices.id |
| `admin_id` | `int` | Y | NULL | 阅读者id | 阅读者 -> admins.id |
| `read_at` | `datetime` | Y | NULL | 阅读时间 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `channels`
- **定位**：客户来源渠道树，支持父子渠道层级和负责人。
- **表注释**：渠道表-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `pid`：父渠道 -> channels.id（自关联）
  - `admin_id`：渠道负责人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(16)` | Y | NULL | 名称 |  |
| `pid` | `int` | Y | NULL | 父id | 父渠道 -> channels.id（自关联） |
| `level` | `tinyint` | Y | 1 | 1 顶级，2 二级 |  |
| `path` | `varchar(16)` | Y | NULL | 层级路径 |  |
| `admin_id` | `int` | Y | NULL | 负责人 | 渠道负责人 -> admins.id |
| `wx_qrcode` | `varchar(64)` | Y | NULL | 微信二维码 |  |
| `is_del` | `tinyint(1)` | Y | 0 | 是否删除 |  |
| `cover` | `varchar(64)` | Y | NULL | 封面 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



## 二、客户主数据与身份体系

### `customers`
- **定位**：客户主表，是全库最核心的业务实体。
- **表注释**：客户表-lwp
- **推荐理解粒度**：1 行 = 1 个客户主档。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `ix_customers_total_points`(`total_points` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `channel_id`：客户来源渠道 -> channels.id
  - `current_plan_id`：客户当前计划 -> customer_plans.id
  - `user_id`：C 端账号 -> users.id
  - `huami_user_id`：第三方华米用户标识，语义上对应 huami_users.huami_user_id，不是 huami_users.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(16)` | Y | NULL | 姓名 |  |
| `avatar` | `varchar(64)` | Y | NULL | 头像 |  |
| `title` | `varchar(16)` | Y | NULL | 称呼 |  |
| `gender` | `tinyint` | Y | 0 | 0其他 1男 2女 |  |
| `birthday` | `date` | Y | NULL | 生日 |  |
| `height` | `int` | Y | NULL | 身高 |  |
| `weight` | `int` | Y | NULL | 体重 |  |
| `phone` | `varchar(16)` | Y | NULL | 电话 |  |
| `status` | `tinyint` | Y | 0 | 状态0默认 1干预中 2已付费 3潜客 4流失 5暂停 |  |
| `prev_status` | `tinyint(1)` | Y | NULL | 上一状态 |  |
| `tags` | `json` | Y |  |  |  |
| `city` | `varchar(16)` | Y | NULL | 城市 |  |
| `channel_time` | `datetime` | Y | NULL | 渠道时间 |  |
| `channel_id` | `int` | Y | NULL | 渠道id | 客户来源渠道 -> channels.id |
| `current_plan_id` | `int` | Y | NULL | 当前计划 | 客户当前计划 -> customer_plans.id |
| `cgm` | `json` | Y |  | cgm具体信息 |  |
| `is_cgm` | `tinyint(1) UNSIGNED ZEROFILL` | Y | 0 | 是否绑定了血糖仪 |  |
| `is_recipel` | `tinyint(1)` | Y | NULL | 是否需要医生线上问诊 |  |
| `is_sale` | `tinyint(1)` | Y | NULL | 是否预约销转 |  |
| `compliance_level` | `tinyint(1)` | Y | NULL | 依从度等级(1-低 2-中 3-高) |  |
| `is_miniprogram` | `tinyint(1)` | Y | NULL | 是否注册小程序 |  |
| `adviser_phone` | `varchar(11)` | Y | NULL | 顾问电话 |  |
| `urgent_name` | `varchar(16)` | Y | NULL | 紧急联系人姓名 |  |
| `urgent_phone` | `varchar(11)` | Y | NULL | 紧急联系人电话 |  |
| `sale_level` | `tinyint(1)` | Y | NULL | 销转等级 |  |
| `address` | `varchar(64)` | Y | NULL | 地址 |  |
| `contract_no` | `varchar(32)` | Y | NULL | 合同编号 |  |
| `advisor` | `varchar(16)` | Y | NULL | 顾问 |  |
| `survey_done` | `tinyint(1)` | Y | 0 | 完成注册问卷0否 1是 |  |
| `points` | `int` | Y | 0 | 积分 |  |
| `total_points` | `int` | Y | 0 | 总积分 |  |
| `exp` | `int` | Y | 0 | 经验 |  |
| `severity` | `tinyint` | Y | 0 | 病情严重程度 1 2 3 低中高 |  |
| `is_del` | `tinyint` | Y | 0 | 是否删除0否1是 |  |
| `user_id` | `int` | Y | NULL |  | C 端账号 -> users.id |
| `last_login_ip` | `varchar(32)` | Y | NULL |  |  |
| `last_login_at` | `datetime` | Y | NULL |  |  |
| `huami_user_id` | `int` | Y | NULL |  | 第三方华米用户标识，语义上对应 huami_users.huami_user_id，不是 huami_users.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `users`
- **定位**：C 端用户账号表，与 customers 形成账号-客户双实体。
- **表注释**：users-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `idx_phone`(`phone` ASC) USING BTREE`
  - `INDEX `idx_customer_id`(`customer_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int UNSIGNED` | N |  |  |  |
| `phone` | `varchar(16)` | Y | NULL |  |  |
| `phone_verified` | `tinyint(1)` | Y | 0 |  |  |
| `nick_name` | `varchar(32)` | Y | NULL |  |  |
| `avatar` | `varchar(255)` | Y | NULL |  |  |
| `gender` | `tinyint(1)` | Y | 0 |  |  |
| `birthday` | `date` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 1 |  |  |
| `last_login_at` | `datetime` | Y | NULL |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `oauth_users`
- **定位**：微信/小程序/服务号 OAuth 身份表，与 customers 建立外部身份映射。
- **表注释**：oauth_users-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `idx_openid_source`(`openid` ASC, `source` ASC) USING BTREE`
  - `INDEX `idx_user_id`(`customer_id` ASC) USING BTREE`
  - `INDEX `idx_unionid`(`unionid` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int UNSIGNED` | N |  |  |  |
| `nick_name` | `varchar(32)` | Y | NULL |  |  |
| `openid` | `varchar(64)` | Y | NULL |  |  |
| `avatar` | `varchar(255)` | Y | NULL |  |  |
| `gender` | `tinyint(1)` | Y | NULL |  |  |
| `city` | `varchar(16)` | Y | NULL |  |  |
| `unionid` | `varchar(64)` | Y | NULL |  |  |
| `source` | `tinyint(1)` | Y | 1 | 1小程序 2服务号 |  |
| `subs` | `tinyint(1)` | Y | 1 |  |  |
| `customer_id` | `int UNSIGNED` | Y | NULL |  | 客户 -> customers.id |
| `plat` | `tinyint(1)` | Y | 1 |  |  |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_info`
- **定位**：客户静态/半静态画像、健康背景、目标、处方、干预地图与归档状态表。
- **表注释**：客户情况表-lwp
- **推荐理解粒度**：更像“客户画像版本表/扩展信息表”，通常 1 个客户可有多条，当前有效记录常取 is_archived=0 且最新 id。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_archived_id`(`customer_id` ASC, `is_archived` ASC, `id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `archived_by`：归档操作人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `health_condition` | `text` | Y |  | 身体指标及疾病情况 |  |
| `health_condition_user` | `text` | Y |  | 身体指标及疾病情况(用户版) |  |
| `genetic_history` | `varchar(1024)` | Y | NULL | 遗传病史 |  |
| `allergies` | `varchar(500)` | Y | NULL | 过敏原 |  |
| `goals` | `varchar(500)` | Y | NULL | 健康目标 |  |
| `goal_weight` | `int` | Y | NULL | 目标体重 |  |
| `goal_hr` | `varchar(16)` | Y | NULL | 目标心率 |  |
| `goal_gluc` | `varchar(16)` | Y | NULL | 目标血糖 |  |
| `goal_bp` | `varchar(16)` | Y | NULL | 目标血压 |  |
| `diet_preference` | `varchar(500)` | Y | NULL | 口味偏好 |  |
| `sport_injuries` | `varchar(500)` | Y | NULL | 运动损伤史 |  |
| `sport_preference` | `varchar(500)` | Y | NULL | 运动偏好 |  |
| `sport_interests` | `varchar(500)` | Y | NULL | 运动爱好 |  |
| `sleep_quality` | `varchar(500)` | Y | NULL | 睡眠情况 |  |
| `remark` | `json` | Y |  | 个性化信息备注 |  |
| `day_form` | `json` | Y |  | 日报表格 |  |
| `week_form` | `json` | Y |  | 周报表格 |  |
| `month_form` | `json` | Y |  | 月报表格 |  |
| `medical_history` | `varchar(1000)` | Y | NULL | 医疗史 |  |
| `recipel` | `json` | Y |  | 处方信息 |  |
| `intervention_map` | `json` | Y |  | 干预地图 |  |
| `doctor_recipel` | `json` | Y |  | 医生端处方 |  |
| `food_recipel` | `json` | Y |  | 饮食处方 |  |
| `sleep_recipel` | `json` | Y |  | 睡眠处方 |  |
| `sport_recipel` | `json` | Y |  | 运动处方 |  |
| `nutrition_recipel` | `json` | Y |  | 营养素处方 |  |
| `is_archived` | `tinyint` | Y | 0 | 是否归档0否1是 |  |
| `archived_at` | `datetime` | Y | NULL | 归档时间 |  |
| `archived_by` | `int` | Y | NULL | 归档人 | 归档操作人 -> admins.id |
| `archive_reason` | `varchar(64)` | Y | NULL | 归档原因 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_health_condition_history`
- **定位**：customer_info.health_condition 的归档历史表。
- **表注释**：客户身体指标及疾病情况历史记录表
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_id`(`customer_id` ASC) USING BTREE`
  - `INDEX `idx_operator_id`(`operator_id` ASC) USING BTREE`
  - `INDEX `idx_created_at`(`created_at` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `operator_id`：归档操作人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  | 主键ID |  |
| `customer_id` | `int` | N |  | 客户ID | 客户 -> customers.id |
| `health_condition` | `text` | N |  | 归档时的身体指标及疾病情况 |  |
| `operator_id` | `int` | N |  | 归档操作人ID（管理员ID） | 归档操作人 -> admins.id |
| `remark` | `text` | Y |  | 归档备注 |  |
| `created_at` | `timestamp` | N | CURRENT_TIMESTAMP | 创建时间（归档时间） |  |
| `updated_at` | `timestamp` | N | CURRENT_TIMESTAMP | 更新时间 |  |



### `customer_staff`
- **定位**：客户与后台负责人/服务人员的分配关系表，可追踪生效区间。
- **表注释**：customer_staff-lwp
- **推荐理解粒度**：1 行 = 1 次客户与服务人员的绑定区间。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `admin_id`：负责人/服务人员 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `admin_id` | `int` | Y | NULL | 负责人id | 负责人/服务人员 -> admins.id |
| `star_level` | `int` | Y | NULL | 星标等级 |  |
| `start_at` | `datetime` | Y | NULL | 开始时间 |  |
| `end_at` | `datetime` | Y | NULL | 结束时间 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_star`
- **定位**：教练与客户的星标关系表（字段命名为 camelCase）。
- **表注释**：教练与客户星标关系表
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_admin_customer`(`adminId` ASC, `customerId` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `adminId`：教练 -> admins.id
  - `customerId`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint UNSIGNED` | N |  | 主键ID |  |
| `adminId` | `bigint UNSIGNED` | N |  | 教练ID | 教练 -> admins.id |
| `customerId` | `bigint UNSIGNED` | N |  | 客户ID | 客户 -> customers.id |
| `createdAt` | `datetime` | N | CURRENT_TIMESTAMP | 创建时间 |  |



### `families`
- **定位**：家庭/家庭组主表。
- **表注释**：families-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_invite_code`(`invite_code` ASC) USING BTREE`
  - `INDEX `idx_owner`(`owner_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `owner_id`：家庭主人 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(64)` | Y | NULL | 家庭名称 |  |
| `invite_code` | `varchar(16)` | Y | NULL | 邀请码 |  |
| `owner_id` | `int` | N |  | 主人id | 家庭主人 -> customers.id |
| `status` | `tinyint` | N | 1 | 0禁用 1正常 |  |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



## 三、社群与分组

### `groups`
- **定位**：群组主表（例如训练营/批次群）。
- **表注释**：groups-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(32)` | Y | NULL | 名称 |  |
| `webhook_key` | `varchar(255)` | Y | NULL |  |  |
| `batch` | `int` | Y | NULL | 批次 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_groups`
- **定位**：客户与群组的关系表。
- **表注释**：customer_groups-lwp
- **推荐理解粒度**：1 行 = 1 个客户加入 1 个群组的关系。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_customer_group`(`customer_id` ASC, `group_id` ASC) USING BTREE`
  - `INDEX `idx_group_id`(`group_id` ASC) USING BTREE`
  - `INDEX `idx_customer_id`(`customer_id` ASC) USING BTREE`
  - `INDEX `ix_cg_group_id`(`group_id` ASC) USING BTREE`
  - `INDEX `ix_cg_customer_id`(`customer_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `group_id`：群组 -> groups.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `group_id` | `int` | Y | NULL |  | 群组 -> groups.id |
| `role` | `tinyint(1)` | Y | 0 |  |  |
| `joined_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |



### `group_coachs`
- **定位**：群组与教练关系表。
- **表注释**：group_coaches-lwp
- **推荐理解粒度**：1 行 = 1 个群组与 1 个教练的关系。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_group_coach_group_coach`(`group_id` ASC, `coach_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `group_id`：群组 -> groups.id
  - `coach_id`：教练 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `group_id` | `int` | Y | NULL |  | 群组 -> groups.id |
| `coach_id` | `int` | Y | NULL |  | 教练 -> admins.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



## 四、健康记录与生理监测

### `customer_health`
- **定位**：客户每日健康汇总表，是分析健康行为最重要的宽表之一。
- **表注释**：客户健康记录-lwp
- **推荐理解粒度**：1 行 = 1 个客户在 1 个 record_date 的健康宽表记录。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_id_record_date`(`customer_id` ASC, `record_date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `record_date` | `date` | Y | NULL | 记录日期 |  |
| `day_form` | `json` | Y |  | 日报表格 |  |
| `week_form` | `json` | Y |  | 周报表格 |  |
| `month_form` | `json` | Y |  | 月报表格 |  |
| `weight` | `int` | Y | NULL | 体重 |  |
| `waist` | `double` | Y | NULL | 腰围cm |  |
| `blood_sbp` | `int` | Y | NULL | 收缩压 |  |
| `blood_dbp` | `int` | Y | NULL | 舒张压 |  |
| `heart_rate` | `int` | Y | NULL | 心率 弃用 |  |
| `fbs` | `decimal(4,` | Y | NULL | 空腹血糖(mmol/L) |  |
| `pbs` | `decimal(4,` | Y | NULL | 餐后血糖(mmol/L) |  |
| `glucose_data` | `json` | Y |  | 血糖数据 弃用 |  |
| `blood_suger` | `json` | Y |  | 血糖 |  |
| `pressure_data` | `json` | Y |  | 压力数据 |  |
| `sleep_data` | `json` | Y |  | 睡眠数据 |  |
| `hba1c` | `decimal(3,` | Y | NULL | 糖化血红蛋白(%) |  |
| `rbs` | `varchar(255)` | Y | NULL | 随机血糖 |  |
| `water_ml` | `int` | Y | NULL | 饮水量 ml |  |
| `sleep_min` | `int` | Y | NULL | 睡眠时间（分钟） |  |
| `sleep_des` | `varchar(255)` | Y | NULL | 睡眠描述 |  |
| `step_count` | `int` | Y | NULL | 步数 |  |
| `sports` | `json` | Y |  | 运动数据 |  |
| `symptoms` | `varchar(512)` | Y | NULL | 身体症状 |  |
| `tonic` | `varchar(255)` | Y | NULL | 补剂 |  |
| `breakfast_data` | `json` | Y |  | 早餐数据 |  |
| `lunch_data` | `json` | Y |  | 中餐数据 |  |
| `dinner_data` | `json` | Y |  | 晚餐数据 |  |
| `snack_data` | `json` | Y |  | 加餐数据 |  |
| `food_intake` | `varchar(3000)` | Y | NULL | 食物摄入，冗余 |  |
| `kcal` | `int` | Y | NULL | 摄入kacl |  |
| `cho` | `int` | Y | NULL | 碳水 g |  |
| `fat` | `int` | Y | NULL | 脂肪 g |  |
| `protein` | `int` | Y | NULL | 蛋白 g |  |
| `fiber` | `int` | Y | NULL | 纤维 g |  |
| `vits` | `json` | Y |  | 维生素 |  |
| `vitamins` | `varchar(255)` | Y | NULL | 维生素 g 弃用 |  |
| `kcal_out` | `int` | Y | NULL | 消耗kcal |  |
| `stress` | `varchar(255)` | Y | NULL | 压力情况 |  |
| `medication` | `json` | Y |  | 用药情况 |  |
| `meal_plans` | `json` | Y |  | 食谱 |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `body_comp`
- **定位**：客户体成分日快照表，保存体脂秤/分析结果及每项指标的范围、状态和分值。
- **表注释**：body_comp-lwp
- **推荐理解粒度**：1 行 = 1 个客户在 1 个 date 的体成分快照；由唯一键 (customer_id, date) 保证。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_body_comp_customer_date`(`customer_id` ASC, `date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：所属客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 所属客户 -> customers.id |
| `date` | `date` | Y | NULL | 日期 |  |
| `weight` | `decimal(5,` | Y | NULL | 体重kg |  |
| `weight_std` | `tinyint(1)` | Y | NULL | 体重标准0偏低，1标准，2偏高 |  |
| `weight_range` | `json` | Y |  | 体重范围 |  |
| `skeletal` | `decimal(5,` | Y | NULL | 骨骼肌量kg |  |
| `skeletal_std` | `tinyint(1)` | Y | NULL | 骨骼肌标准0不足，1标准，2优秀 |  |
| `skeletal_range` | `json` | Y |  | 骨骼肌范围 |  |
| `smi` | `decimal(5,` | Y | NULL | 骨骼肌质量指数 |  |
| `smi_std` | `tinyint(1)` | Y | NULL | 骨骼肌质量指数状态0不足 1标准 |  |
| `smi_range` | `json` | Y |  | 骨骼肌质量指数范围 |  |
| `whr` | `decimal(5,` | Y | NULL | 腰臀比 |  |
| `whr_range` | `json` | Y |  | 腰臀比范围 |  |
| `std_whr` | `tinyint(1)` | Y | NULL | 腰臀比状态0低 1标准 2高 |  |
| `bmi` | `decimal(5,` | Y | NULL | bmi |  |
| `bmi_range` | `json` | Y |  | bmi范围 |  |
| `bmi_std` | `tinyint(1)` | Y | NULL | bmi状态0偏低，1标准，2偏高 |  |
| `bmr` | `decimal(10,` | Y | NULL | bmr |  |
| `bmr_range` | `json` | Y |  | bmr范围 |  |
| `bmr_std` | `tinyint(1)` | Y | NULL | bmr状态0偏低，1标准，2优秀 |  |
| `fat_grade` | `decimal(5,` | Y | NULL | 肥胖等级 |  |
| `obesity` | `decimal(5,` | Y | NULL | 肥胖水平 |  |
| `obesity_range` | `json` | Y |  | 肥胖水平范围 |  |
| `obesity_std` | `tinyint(1)` | Y | NULL | 肥胖水平状态0偏低，标准，1偏高 |  |
| `heart_rate` | `int` | Y | NULL | 心率 |  |
| `heart_rate_range` | `json` | Y |  | 心率范围 |  |
| `heart_rate_std` | `tinyint` | Y | NULL | 心率状态0偏低，1标准，2偏高，3过高 |  |
| `fat` | `decimal(5,` | Y | NULL | 脂肪量 |  |
| `fat_range` | `json` | Y |  | 脂肪范围 |  |
| `fat_std` | `tinyint` | Y | NULL | 脂肪状态0偏低，1标准，2偏高 |  |
| `body_fat` | `decimal(5,` | Y | NULL | 体脂率 |  |
| `body_fat_range` | `json` | Y |  | 体脂率范围 |  |
| `body_fat_std` | `tinyint` | Y | NULL | 体脂率状态0偏低，1标准，2偏高 |  |
| `sub_fat` | `decimal(5,` | Y | NULL | 皮下脂肪 |  |
| `sub_fat_range` | `json` | Y |  | 皮下脂肪范围 |  |
| `sub_fat_std` | `tinyint` | Y | NULL | 皮下脂肪状态0偏低，1标准，2偏高 |  |
| `sub_fat_pct` | `decimal(5,` | Y | NULL | 皮下脂肪率 |  |
| `sub_fat_pct_range` | `json` | Y |  | 皮下脂肪率范围 |  |
| `sub_fat_pct_std` | `tinyint` | Y | NULL | 皮下脂肪率状态0偏低，1标准，2偏高 |  |
| `fat_control` | `decimal(5,` | Y | NULL | 脂肪控制量 |  |
| `lose_fat_weight` | `decimal(5,` | Y | NULL | 去脂体重 |  |
| `lose_fat_weight_range` | `json` | Y |  | 去脂体重范围 |  |
| `lose_fat_weight_std` | `tinyint` | Y | NULL | 去脂体重状态0偏低，1标准，2优秀 |  |
| `vis_fat` | `decimal(5,` | Y | NULL | 内脏脂肪 |  |
| `vis_fat_range` | `json` | Y |  | 内脏脂肪范围 |  |
| `vis_fat_std` | `tinyint` | Y | NULL | 内脏脂肪状态0偏低，1标准，2偏高 |  |
| `muscle` | `decimal(5,` | Y | NULL | 肌肉量 |  |
| `muscle_range` | `json` | Y |  | 肌肉量范围 |  |
| `muscle_std` | `tinyint` | Y | NULL | 肌肉量状态0偏低，1标准，2优秀 |  |
| `muscle_pct` | `decimal(5,` | Y | NULL | 肌肉率 |  |
| `muscle_pct_range` | `json` | Y |  | 肌肉率范围 |  |
| `muscle_pct_std` | `tinyint(1)` | Y | NULL | 肌肉率状态0不足，1标准 2优秀 |  |
| `skeletal_pct` | `decimal(5,` | Y | NULL | 骨骼肌率 |  |
| `skeletal_pct_range` | `json` | Y |  | 骨骼肌率范围 |  |
| `skeletal_pct_std` | `tinyint(1)` | Y | NULL | 骨骼肌率状态0偏低 1标准 2优秀 |  |
| `bone` | `decimal(5,` | Y | NULL | 骨量 |  |
| `bone_range` | `json` | Y |  | 骨量范围 |  |
| `bone_std` | `tinyint(1)` | Y | NULL | 骨量状态0偏低 1标准 2优秀 |  |
| `muscle_trunk` | `decimal(5,` | Y | NULL | 躯干肌肉量 |  |
| `body_fat_trunk` | `decimal(5,` | Y | NULL | 躯干脂肪量 |  |
| `body_fat_rate_trunk` | `decimal(5,` | Y | NULL | 躯干脂肪标准比 |  |
| `muscle_left_arm` | `decimal(5,` | Y | NULL | 左臂肌肉量 |  |
| `muscle_right_arm` | `decimal(5,` | Y | NULL | 右臂肌肉量 |  |
| `body_fat_left_arm` | `decimal(5,` | Y | NULL | 左臂脂肪量 |  |
| `body_fat_right_arm` | `decimal(5,` | Y | NULL | 右臂脂肪量 |  |
| `muscle_left_leg` | `decimal(5,` | Y | NULL | 左腿肌肉量 |  |
| `muscle_right_leg` | `decimal(5,` | Y | NULL | 右腿肌肉量 |  |
| `body_fat_left_leg` | `decimal(5,` | Y | NULL | 左腿脂肪量 |  |
| `body_fat_right_leg` | `decimal(5,` | Y | NULL | 右腿脂肪量 |  |
| `water` | `decimal(5,` | Y | NULL | 体水分量 |  |
| `water_range` | `json` | Y |  | 水分量范围 |  |
| `water_std` | `tinyint(1)` | Y | NULL | 水分量状态0偏低 1标准 2优秀 |  |
| `water_pct` | `decimal(5,` | Y | NULL | 水分率 |  |
| `water_pct_range` | `json` | Y |  | 水分率范围 |  |
| `water_pct_std` | `tinyint(1)` | Y | NULL | 水分率状态0偏低 1标准2优秀 |  |
| `protein` | `decimal(5,` | Y | NULL | 蛋白质 |  |
| `protein_range` | `json` | Y |  | 蛋白质范围 |  |
| `protein_std` | `tinyint(1)` | Y | NULL | 蛋白质状态0偏低 1标准 2优秀 |  |
| `protein_pct` | `decimal(5,` | Y | NULL | 蛋白质率 |  |
| `protein_pct_range` | `json` | Y |  | 蛋白质率范围 |  |
| `protein_pct_std` | `tinyint(1)` | Y | NULL | 蛋白质率状态 0偏低 1标准 2优秀 |  |
| `cellmass` | `decimal(5,` | Y | NULL | 身体细胞量 |  |
| `cellmass_range` | `json` | Y |  | 身体细胞量范围 |  |
| `cellmass_std` | `tinyint(1)` | Y | NULL | 身体细胞量状态0偏低 1标准 2优秀 |  |
| `water_ec` | `decimal(5,` | Y | NULL | 细胞外水量 |  |
| `water_ec_range` | `json` | Y |  | 细胞外水量范围 |  |
| `water_ec_std` | `tinyint(1)` | Y | NULL | 细胞外水量状态0偏低 1标准 2偏高 |  |
| `mineral` | `decimal(5,` | Y | NULL | 无机盐量 |  |
| `mineral_range` | `json` | Y |  | 无机盐范围 |  |
| `mineral_std` | `tinyint(1)` | Y | NULL | 无机盐状态0偏低 1标准 2偏高 |  |
| `kcal` | `int` | Y | NULL | 建议摄入卡路里 |  |
| `body_type` | `varchar(16)` | Y | NULL | 身体类型 |  |
| `body_health` | `decimal(5,` | Y | NULL | 健康评价分 |  |
| `body_health_std` | `varchar(16)` | Y | NULL | 健康评价标题 |  |
| `body_age` | `int` | Y | NULL | 身体年龄 |  |
| `body_age_std` | `char(6)` | Y | NULL | 身体年龄标题 |  |
| `body_score` | `int` | Y | NULL | 健康评分 |  |
| `body_score_std` | `char(6)` | Y | NULL | 健康评分标题 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_glucose`
- **定位**：客户连续/离散血糖日数据表，points 为曲线点集合。
- **表注释**：customer_glucose-lwp
- **推荐理解粒度**：1 行 = 1 个客户在 1 个 date 的血糖点位集合。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_user_date`(`customer_id` ASC, `date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `date` | `date` | Y | NULL |  |  |
| `points` | `json` | Y |  |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_heartrate`
- **定位**：客户日心率点位表。
- **表注释**：customer_heartrate-lwp
- **推荐理解粒度**：1 行 = 1 个客户在 1 个 date 的心率点位集合。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_user_date`(`customer_id` ASC, `date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `date` | `date` | Y | NULL |  |  |
| `points` | `json` | Y |  |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_sleep`
- **定位**：客户每日睡眠明细汇总表。
- **表注释**：customer_sleep-lwp
- **推荐理解粒度**：1 行 = 1 个客户在 1 个 date 的睡眠汇总。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_user_date`(`customer_id` ASC, `date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `date` | `date` | Y | NULL |  |  |
| `deep_time` | `int` | Y | NULL | 深睡min |  |
| `shallow_time` | `int` | Y | NULL | 浅睡min |  |
| `wake_time` | `int` | Y | NULL | 清醒min |  |
| `start_time` | `datetime` | Y | NULL | 开始 |  |
| `stop_time` | `datetime` | Y | NULL | 结束 |  |
| `total_min` | `int` | Y | NULL | 总时长 |  |
| `score` | `int` | Y | NULL | 睡眠评分 |  |
| `stage` | `json` | Y |  | 主睡眠区间4为浅度睡眠状态；5为深度睡眠状态；7为清醒状态；8为REM（快速眼动睡眠） |  |
| `nap_stage` | `json` | Y |  | 零星睡区间 |  |
| `rem` | `int` | Y | NULL | REM睡眠时长min |  |
| `rhr` | `int` | Y | NULL | 静息心率 |  |
| `sleep_hrv` | `int` | Y | NULL | 睡眠心率变异 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_sport`
- **定位**：客户每日运动汇总表。
- **表注释**：customer_sport-lwp
- **推荐理解粒度**：1 行 = 1 个客户在 1 个 date 的运动汇总。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_date`(`customer_id` ASC, `date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | N |  |  | 客户 -> customers.id |
| `date` | `date` | N |  | 日期 |  |
| `items` | `json` | Y |  | 运动项 |  |
| `total_steps` | `int` | Y | NULL | 总步数 |  |
| `calories` | `int` | Y | 0 | 消耗热量 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP | 创建时间 |  |
| `updated_at` | `datetime` | Y | NULL | 更新时间 |  |



### `customer_stress`
- **定位**：客户压力点位表。
- **表注释**：customer_stress-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `date` | `date` | Y | NULL |  |  |
| `points` | `json` | Y |  |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_nutrition_plans`
- **定位**：客户营养目标/三大营养素配比表。
- **表注释**：customer_nutrition_plans-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer`(`customer_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  | 主键ID |  |
| `customer_id` | `int` | N |  | 客户ID | 客户 -> customers.id |
| `total_kcal` | `int` | N |  | 总热量 (Kcal) |  |
| `protein_g` | `int` | N |  | 蛋白质 (克) |  |
| `fat_g` | `int` | N |  | 脂肪 (克) |  |
| `carb_g` | `int` | N |  | 碳水化合物 (克) |  |
| `fib_g` | `int` | Y | NULL | 膳食纤维 |  |
| `p_ratio` | `decimal(10,` | N |  | 蛋白质系数 |  |
| `f_percent` | `decimal(10,` | N | 0.3 | 脂肪热量占比 |  |
| `active_coef` | `decimal(10,` | Y | 1.3 | 活动系数 |  |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP | 创建时间 |  |
| `updated_at` | `datetime` | N | CURRENT_TIMESTAMP | 更新时间 |  |



## 五、设备接入与第三方穿戴

### `customer_device`
- **定位**：客户已绑定的设备清单，抽象成统一设备层。
- **表注释**：customer_device-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `type` | `tinyint(1)` | Y | 0 | 1手环 2cgm 3血压计 4体脂称 |  |
| `provider` | `tinyint` | Y | NULL | 1华米 2百洋 3乐福 4三诺 |  |
| `status` | `tinyint(1)` | Y | 0 | 0断开 1连接 |  |
| `device_id` | `varchar(32)` | Y | NULL | sn |  |
| `device_name` | `varchar(16)` | Y | NULL |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `unbind_at` | `datetime` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `device_bp_data`
- **定位**：血压设备原始测量数据表。
- **表注释**：device_bp_data-lwp
- **推荐理解粒度**：1 行 = 1 次血压设备测量记录。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_data_id`(`data_id` ASC) USING BTREE`
  - `INDEX `idx_sn_time`(`sn` ASC, `time` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id；sn 可与 customer_device.device_id 结合

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `sn` | `varchar(32)` | Y | NULL | 设备编码 |  |
| `data_id` | `varchar(64)` | Y | NULL | 数据id |  |
| `time` | `datetime` | Y | NULL | 测量时间 |  |
| `provider` | `varchar(255)` | Y | NULL | 厂商 |  |
| `device_model` | `varchar(255)` | Y | NULL | 设备型号 |  |
| `version` | `int` | Y | NULL | 版本 |  |
| `user` | `varchar(255)` | Y | NULL | 测量用户 |  |
| `systolic_pressure` | `int` | Y | NULL | 收缩压 |  |
| `diastolic_pressure` | `int` | Y | NULL | 舒张压 |  |
| `avg_pressure` | `tinyint` | Y | NULL | 平均压 |  |
| `real_time_pressure` | `tinyint` | Y | NULL | 实时血压值 |  |
| `pulse_rate` | `int` | Y | NULL | 脉率 |  |
| `status` | `tinyint(1)` | Y | NULL | 1: 测量中, 2: 测量完成 |  |
| `imei` | `varchar(255)` | Y | NULL | IMEI号 |  |
| `iccid` | `varchar(255)` | Y | NULL | 物联网卡号 |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id；sn 可与 customer_device.device_id 结合 |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `device_fat_data`
- **定位**：体脂秤原始测量数据表。
- **表注释**：device_fat_data-lwp
- **推荐理解粒度**：1 行 = 1 次体脂秤设备测量记录。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_data_id`(`data_id` ASC) USING BTREE`
  - `INDEX `idx_sn_time`(`sn` ASC, `time` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id；sn 可与 customer_device.device_id 结合

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `sn` | `varchar(32)` | Y | NULL |  |  |
| `data_id` | `varchar(64)` | Y | NULL |  |  |
| `time` | `datetime` | Y | NULL | 测量时间 |  |
| `provider` | `varchar(255)` | Y | NULL |  |  |
| `device_model` | `varchar(255)` | Y | NULL |  |  |
| `version` | `int` | Y | NULL |  |  |
| `user` | `varchar(255)` | Y | NULL |  |  |
| `weight` | `int` | Y | NULL | 体重 |  |
| `weight_unit` | `varchar(10)` | Y | NULL | 体重单位 (kg: 千克, g: 克, jin: 斤, lb: 磅, st-lb: 英石) |  |
| `heart_rate` | `int` | Y | NULL | 心率 |  |
| `adc` | `int` | Y | NULL | 阻抗 |  |
| `imei` | `varchar(255)` | Y | NULL | IMEI号 |  |
| `iccid` | `varchar(255)` | Y | NULL | 物联网卡号 |  |
| `mac` | `varchar(32)` | Y | NULL |  |  |
| `scale_type` | `int` | Y | NULL | 设备类型（lefu） |  |
| `impedances` | `json` | Y |  | 阻抗（lefu） |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id；sn 可与 customer_device.device_id 结合 |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `huami_users`
- **定位**：华米第三方账号与客户映射表。
- **表注释**：huami_users-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `index_user_id`(`huami_user_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `huami_user_id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `gender` | `tinyint(1)` | Y | NULL | 1男 2女 |  |
| `birthday` | `date` | Y | NULL |  |  |
| `nick_name` | `varchar(32)` | Y | NULL |  |  |
| `avatar` | `varchar(512)` | Y | NULL |  |  |
| `access_token` | `varchar(512)` | Y | NULL |  |  |
| `refresh_token` | `varchar(512)` | Y | NULL |  |  |
| `expires_at` | `datetime` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `huami_devices`
- **定位**：华米设备绑定清单。
- **表注释**：huami_devices-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `huami_user_id`：第三方用户号 -> huami_users.huami_user_id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `huami_user_id` | `int` | Y | NULL |  | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `device_id` | `int` | Y | NULL |  |  |
| `device_type` | `varchar(16)` | Y | NULL |  |  |
| `device_name` | `varchar(32)` | Y | NULL |  |  |
| `mac_address` | `varchar(64)` | Y | NULL |  |  |
| `last_data_sync_time` | `timestamp` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `huami_activities`
- **定位**：华米活动日汇总数据。
- **表注释**：huami_activities-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_user_date`(`huami_user_id` ASC, `date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `huami_user_id`：第三方用户号 -> huami_users.huami_user_id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `huami_user_id` | `int` | Y | NULL |  | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `device_id` | `int` | Y | NULL |  |  |
| `date` | `date` | Y | NULL |  |  |
| `last_sync_time` | `timestamp` | Y | NULL | 上传时间戳 |  |
| `steps` | `int` | Y | NULL | 总步数 |  |
| `distance` | `int` | Y | NULL | 总距离 m |  |
| `walk_time` | `int` | Y | NULL | 步行时间 min |  |
| `run_time` | `int` | Y | NULL | 跑步时间 min |  |
| `run_distance` | `int` | Y | NULL | 跑步距离 |  |
| `calories` | `int` | Y | NULL | 总热量 |  |
| `hour` | `int` | Y | NULL | 数分段信息，即将失效 |  |
| `run_calories` | `int` | Y | NULL | 跑步热量 |  |
| `stage` | `json` | Y |  |  |  |
| `interval_type` | `varchar(16)` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `huami_heartrates`
- **定位**：华米分钟级心率明细。
- **表注释**：huami_heartrates-lwp
- **推荐理解粒度**：1 行 = 1 个华米用户在 1 天的 1 分钟心率点。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_user_date_minute`(`huami_user_id` ASC, `date` ASC, `minute` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `huami_user_id`：第三方用户号 -> huami_users.huami_user_id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `huami_user_id` | `int` | Y | NULL |  | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `device_id` | `int` | Y | NULL |  |  |
| `date` | `date` | Y | NULL |  |  |
| `minute` | `int` | Y | NULL | 分钟序号 |  |
| `timestamp` | `int` | Y | NULL | 数据生成时间 |  |
| `heart_rate_data` | `int` | Y | NULL | 心率 |  |
| `measure_type` | `varchar(16)` | Y | NULL | 测量类型：AUTO、MANUAL |  |
| `last_sync_time` | `int` | Y | NULL | AUTO时提供 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `huami_sleep`
- **定位**：华米睡眠日汇总数据。
- **表注释**：huami_sleep-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_user_date`(`huami_user_id` ASC, `date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `huami_user_id`：第三方用户号 -> huami_users.huami_user_id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `huami_user_id` | `int` | Y | NULL |  | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `device_id` | `int` | Y | NULL |  |  |
| `date` | `date` | Y | NULL |  |  |
| `last_sync_time` | `int` | Y | NULL |  |  |
| `deep_sleep_time` | `int` | Y | NULL | 深睡min |  |
| `shallow_sleep_time` | `int` | Y | NULL | 浅睡min |  |
| `wake_time` | `int` | Y | NULL | 清醒min |  |
| `start` | `int` | Y | NULL | 开始 |  |
| `stop` | `int` | Y | NULL | 结束 |  |
| `sleep_score` | `int` | Y | NULL | 睡眠评分 |  |
| `stage` | `json` | Y |  | 主睡眠区间 |  |
| `nap_stage` | `json` | Y |  | 零星睡区间 |  |
| `rem` | `int` | Y | NULL | REM睡眠时长min |  |
| `rhr` | `int` | Y | NULL | 静息心率 |  |
| `sleep_hrv` | `int` | Y | NULL | 睡眠心率变异 |  |
| `interval_type` | `varchar(16)` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `huami_sports`
- **定位**：华米单次运动轨迹/运动会话表。
- **表注释**：huami_sports-lwp
- **推荐理解粒度**：1 行 = 1 次华米运动会话/轨迹。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_user_track`(`huami_user_id` ASC, `track_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `huami_user_id`：第三方用户号 -> huami_users.huami_user_id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `huami_user_id` | `int` | Y | NULL |  | 第三方用户号 -> huami_users.huami_user_id |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `device_id` | `int` | Y | NULL |  |  |
| `track_id` | `int` | Y | NULL | 轨迹ID |  |
| `source` | `varchar(64)` | Y | NULL |  |  |
| `type` | `varchar(32)` | Y | NULL | 类型 |  |
| `sport_category` | `varchar(16)` | Y | NULL | 大类 |  |
| `start_time` | `int` | Y | NULL | 开始时间戳 |  |
| `end_time` | `int` | Y | NULL | 结束时间戳 |  |
| `sport_time` | `int` | Y | NULL | 运动时间 s |  |
| `distance` | `int` | Y | NULL | 距离 |  |
| `calories` | `int` | Y | NULL | 热量 |  |
| `location` | `varchar(255)` | Y | NULL | geohash |  |
| `average_pace` | `int` | Y | NULL | 平均配速 秒/米 |  |
| `average_step_frequency` | `int` | Y | NULL | 步频 步/分钟 |  |
| `average_stride_length` | `int` | Y | NULL | 步长 cm |  |
| `average_heart_rate` | `int` | Y | NULL | 心率 |  |
| `altitude_ascend` | `int` | Y | NULL | 海拔上升量 米 |  |
| `altitude_descend` | `int` | Y | NULL | 海拔下降，米 |  |
| `total_step` | `int` | Y | NULL | 总步数 |  |
| `second_half_start_time` | `int` | Y | NULL | 下半场开始时间，足球 |  |
| `stroke_count` | `int` | Y | NULL | 挥拍次数，网球 |  |
| `fore_hand_count` | `int` | Y | NULL | 正手挥拍，网球 |  |
| `back_hand_count` | `int` | Y | NULL | 反手挥拍，网球 |  |
| `serve_count` | `int` | Y | NULL | 发球次数，网球 |  |
| `device` | `varchar(32)` | Y | NULL | 设备类型 |  |
| `device_name` | `varchar(64)` | Y | NULL | 设备名称 |  |
| `timestamp` | `int` | Y | NULL | 时间c |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



## 六、习惯、任务与干预计划

### `anchors`
- **定位**：习惯养成中的“锚点”维表，表示触发习惯的情境或时机（系统预设或用户自定义）。
- **表注释**：anchors-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `creator_id`：创建人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `name` | `varchar(64)` | Y | NULL |  |  |
| `source` | `tinyint` | Y | 0 | 0系统预设 1用户自定义 |  |
| `creator_id` | `int` | Y | NULL |  | 创建人 -> admins.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `habits`
- **定位**：习惯模板表，描述系统或用户定义的习惯目标。
- **表注释**：habits-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `anchor_id`：默认锚点 -> anchors.id
  - `creator_id`：创建人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `anchor_id` | `int` | Y | NULL | 锚点id | 默认锚点 -> anchors.id |
| `type` | `varchar(16)` | Y | NULL | 养成习惯的类型(饮食睡眠运动压力认知饮水) |  |
| `target` | `varchar(128)` | Y | NULL | 目标 |  |
| `target_min` | `varchar(128)` | Y | NULL | 保底 |  |
| `source` | `tinyint(1)` | Y | 0 | 0系统预设 1用户自定义 |  |
| `descr` | `varchar(255)` | Y | NULL | 描述 |  |
| `creator_id` | `int` | Y | NULL | 创建者ID | 创建人 -> admins.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `obstacles`
- **定位**：阻碍模板表。
- **表注释**：obstacles-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(100)` | Y | NULL |  |  |
| `source` | `tinyint(1)` | Y | 1 | 0系统预设 1用户自定义 |  |
| `creator_id` | `int` | Y | NULL | 创建者ID |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_habits`
- **定位**：客户持有的习惯实例表，是 habits 模板在客户侧的落地。
- **表注释**：customer_habits-lwp
- **推荐理解粒度**：1 行 = 1 个客户持有的 1 个习惯实例。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `habit_id`：习惯模板 -> habits.id
  - `anchor_id`：锚点 -> anchors.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `habit_id` | `int` | Y | NULL |  | 习惯模板 -> habits.id |
| `anchor_id` | `int` | Y | NULL |  | 锚点 -> anchors.id |
| `status` | `tinyint(1)` | Y | 1 | 1开始 2暂停 3完成 |  |
| `target_min` | `varchar(128)` | Y | NULL | 保底 |  |
| `fallback_info` | `varchar(255)` | Y | NULL | 保底达成标准描述 |  |
| `current_streak` | `int` | Y | 0 | 当前连续天数 |  |
| `fallback_days` | `int` | Y | NULL | 保底达成天数 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_obstacles`
- **定位**：客户习惯执行中的阻碍及 If-Then 对策表。
- **表注释**：customer_obstacles-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `customer_habit_id`：客户习惯 -> customer_habits.id
  - `obstacle_id`：阻碍模板 -> obstacles.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `customer_habit_id` | `int` | Y | NULL |  | 客户习惯 -> customer_habits.id |
| `obstacle_id` | `int` | Y | NULL |  | 阻碍模板 -> obstacles.id |
| `if_then_plan` | `text` | Y |  | \ |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_checkin_records`
- **定位**：客户习惯打卡事实表，一条记录表示某客户某习惯在某天的打卡结果。
- **表注释**：checkin_records-lwp
- **推荐理解粒度**：1 行 = 1 个客户的 1 个习惯实例在 1 天的打卡结果；唯一键 (customer_id, customer_habit_id, checkin_date)。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `unique_checkin`(`customer_id` ASC, `customer_habit_id` ASC, `checkin_date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `customer_habit_id`：客户习惯实例 -> customer_habits.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `customer_habit_id` | `int` | Y | NULL |  | 客户习惯实例 -> customer_habits.id |
| `checkin_status` | `tinyint(1)` | Y | 0 | 1完成 2阻碍 3未完成 4超额完成 |  |
| `checkin_date` | `date` | Y | NULL | 打卡日期 |  |
| `notes` | `varchar(255)` | Y | NULL | 笔记 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_tasks`
- **定位**：客户通用任务主表，可用于重复性目标跟踪。
- **表注释**：customer_tasks-lwp
- **推荐理解粒度**：1 行 = 1 个客户任务定义。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(16)` | Y | NULL |  |  |
| `type` | `varchar(16)` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 0 | 0进行中 1已完成 |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `repeat_type` | `tinyint(1)` | Y | 0 | 0一次性  1每天 2每周 3每月 |  |
| `target_count` | `int` | Y | NULL | 目标次数（每周几次，每月几次） |  |
| `start_date` | `date` | Y | NULL | 开始日期 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_task_checkins`
- **定位**：客户任务打卡明细表。
- **表注释**：customer_task_checkins-lwp
- **推荐理解粒度**：1 行 = 1 个任务在 1 天的打卡。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_task_date`(`task_id` ASC, `checkin_date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `task_id`：客户任务 -> customer_tasks.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `task_id` | `int` | Y | NULL |  | 客户任务 -> customer_tasks.id |
| `checkin_date` | `date` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_plans`
- **定位**：客户干预计划/服务计划实例主表。
- **表注释**：customer_plans-lwp
- **推荐理解粒度**：1 行 = 1 个客户计划实例。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `title` | `varchar(32)` | Y | NULL | 名称 |  |
| `description` | `varchar(512)` | Y | NULL | 描述 |  |
| `status` | `tinyint(1)` | Y | 0 | 状态0未完成 1已完成 |  |
| `total_days` | `int` | Y | NULL | 总天数 |  |
| `payment` | `int` | Y | NULL | 付费金额（分） |  |
| `start_date` | `date` | Y | NULL | 开始日期 |  |
| `pause_date` | `date` | Y | NULL | 暂停日期 |  |
| `resume_date` | `date` | Y | NULL | 暂停恢复日期 |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_todos`
- **定位**：客户计划下的待办/日程明细表。
- **表注释**：customer_todos-lwp
- **推荐理解粒度**：1 行 = 1 个客户计划在某天/某阶段的待办明细。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_plan_id_customer_id`(`plan_id` ASC, `customer_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `plan_id`：客户计划 -> customer_plans.id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `orig_date` | `date` | Y | NULL | 计划日期 |  |
| `todo_date` | `date` | Y | NULL | 执行日期 |  |
| `plan_id` | `int` | N |  | 计划id | 客户计划 -> customer_plans.id |
| `type` | `tinyint(1)` | Y | 0 | 0每天 1区间 |  |
| `status` | `tinyint(1)` | Y | 0 | 状态0未开始 1进行中 2已完成 3暂停  |  |
| `sort_order` | `int` | Y | 0 | 排序 |  |
| `day_num` | `int` | Y | NULL | 第几天 |  |
| `items` | `json` | Y |  | 任务项 |  |
| `comp_at` | `datetime` | Y | NULL | 完成时间 |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `plan_tpl`
- **定位**：计划模板表，可生成客户计划或教练计划。
- **表注释**：plan_tpl-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `title` | `varchar(32)` | Y | NULL | 标题 |  |
| `description` | `varchar(32)` | Y | NULL | 描述 |  |
| `type` | `tinyint(1)` | Y | 0 | 类型 1干预 2已付费 |  |
| `rules` | `tinyint(1)` | Y | 1 | 类别 1每天重复 2每天不同 |  |
| `category` | `tinyint` | Y | 1 | 分类 1客户 2教练 |  |
| `total_days` | `int` | Y | NULL | 总天数 |  |
| `status` | `tinyint(1)` | Y | 0 | 状态0关闭 1启用 |  |
| `items` | `json` | Y |  | 任务项 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `coach_sched`
- **定位**：教练面向客户的日程/排期/待处理事项表。
- **表注释**：coach_sched-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_admin_dates`(`start_date` ASC, `end_date` ASC, `coach_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `coach_id`：教练 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `title` | `varchar(32)` | Y | NULL | 标题 |  |
| `content` | `varchar(64)` | Y | NULL | 内容 |  |
| `start_date` | `date` | Y | NULL |  |  |
| `end_date` | `date` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 0 | 状态0待处理 1进行中 2已处理 3未开始 |  |
| `dones` | `json` | Y |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `coach_id` | `int` | Y | NULL |  | 教练 -> admins.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `coach_tel`
- **定位**：教练电话预约/回访记录表。
- **表注释**：coach_tel-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `coach_id`：教练 -> admins.id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `status` | `tinyint(1)` | Y | 0 | 0未完成 1已完成 |  |
| `coach_id` | `int` | Y | NULL |  | 教练 -> admins.id |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `booked_date` | `date` | Y | NULL | 预约日期 |  |
| `booked_time` | `varchar(16)` | Y | NULL | 预约时间 |  |
| `completed_at` | `datetime` | Y | NULL | 完成日期 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `coach_todos`
- **定位**：教练执行的客户计划任务明细表，通常挂在 customer_plans 下。
- **表注释**：coach_todos-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `coach_id`：教练 -> admins.id
  - `customer_id`：客户 -> customers.id
  - `plan_id`：客户计划 -> customer_plans.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `coach_id` | `int` | Y | NULL | 教练id | 教练 -> admins.id |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `plan_id` | `int` | Y | NULL | 客户计划id | 客户计划 -> customer_plans.id |
| `step` | `int` | Y | NULL | 阶段 |  |
| `status` | `tinyint(1)` | Y | 0 | 状态0未开始 1进行中 2已完成 |  |
| `remark` | `varchar(255)` | Y | NULL | 备注 |  |
| `start_at` | `datetime` | Y | NULL | 开始时间 |  |
| `comp_at` | `datetime` | Y | NULL | 完成时间 |  |
| `v_type` | `tinyint(1)` | Y | NULL | 值类型 0文字 1链接 2图片 |  |
| `val` | `varchar(255)` | Y | NULL | 值 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



## 七、课程、内容与学习体系

### `course`
- **定位**：课程内容主表（偏内容素材/知识卡片），与 course_plans 组合成学习计划。
- **表注释**：course-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `title` | `varchar(32)` | Y | NULL | 标题 |  |
| `content_type` | `tinyint` | Y | 2 | 0文字 1图片 2图文 3视频 4音频 5文档 |  |
| `content` | `text` | Y |  | 内容 |  |
| `thumb` | `varchar(64)` | Y | NULL | 缩略图 |  |
| `top_img` | `varchar(64)` | Y | NULL | 头部图片 |  |
| `audio` | `varchar(64)` | Y | NULL | 音频 |  |
| `habit_type` | `tinyint(1)` | Y | NULL | 习惯类别 |  |
| `tag` | `varchar(32)` | Y | NULL | 标签 |  |
| `is_tips` | `tinyint(1)` | Y | 0 | 是否锦囊 |  |
| `remark` | `varchar(32)` | Y | NULL | 备注 |  |
| `is_del` | `tinyint(1)` | Y | 0 |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `course_copy1`
- **定位**：course 的历史副本/遗留表，结构接近但字段较少，分析时应谨慎使用。
- **表注释**：course-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `title` | `varchar(32)` | Y | NULL |  |  |
| `content_type` | `tinyint` | Y | 2 | 0文字 1图片 2图文 3视频 4音频 5文件 |  |
| `content` | `text` | Y |  |  |  |
| `tag` | `varchar(32)` | Y | NULL |  |  |
| `is_tips` | `tinyint(1)` | Y | NULL | 是否是锦囊 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `course_plans`
- **定位**：课程计划模板主表。
- **表注释**：course_plans-lwp
- **推荐理解粒度**：1 行 = 1 个课程计划模板。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(32)` | Y | NULL |  |  |
| `total_days` | `int` | Y | NULL | 天数 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `course_plan_days`
- **定位**：课程计划分天明细，把某个计划拆成第 N 天学习哪些课程。
- **表注释**：course_plan_days-lwp
- **推荐理解粒度**：1 行 = 1 个课程计划在某一天安排的 1 门课程。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_plan_day_course`(`plan_id` ASC, `day_number` ASC, `course_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `plan_id`：课程计划 -> course_plans.id
  - `course_id`：课程 -> course.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `plan_id` | `int` | Y | NULL | 计划id | 课程计划 -> course_plans.id |
| `day_number` | `int` | Y | NULL | 第几天 |  |
| `course_id` | `int` | Y | NULL | 课程id | 课程 -> course.id |
| `sort_order` | `int` | Y | NULL | 排序 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_course_plan`
- **定位**：客户被分配的课程计划实例表，记录当前学到第几天。
- **表注释**：customer_course_plan-lwp
- **推荐理解粒度**：1 行 = 1 个客户被分配的 1 个课程计划实例。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `plan_id`：课程计划 -> course_plans.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `plan_id` | `int` | Y | NULL | 计划id | 课程计划 -> course_plans.id |
| `current_day` | `int` | Y | NULL | 当前天数 |  |
| `max_pending` | `int` | Y | 10 | 待学习最大数量,大于计划里面的天数无效 |  |
| `started_at` | `date` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_course_record`
- **定位**：客户-课程学习状态事实表，记录是否开始/完成、学习时长和分配日期。
- **表注释**：customer_course_record-lwp
- **推荐理解粒度**：1 行 = 1 个客户对 1 门课程的学习状态；唯一键 (customer_id, course_id)。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_customer_course`(`customer_id` ASC, `course_id` ASC) USING BTREE`
  - `INDEX `idx_customer_status_assign`(`customer_id` ASC, `status` ASC, `assign_date` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `course_id`：课程 -> course.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `course_id` | `int` | Y | NULL | 课程id | 课程 -> course.id |
| `status` | `tinyint(1)` | Y | 0 | 0未开始 1学习中 2已完成 |  |
| `start_at` | `datetime` | Y | NULL | 开始时间 |  |
| `completed_at` | `datetime` | Y | NULL | 完成时间 |  |
| `study_seconds` | `int` | Y | NULL | 时长s |  |
| `assign_date` | `date` | Y | NULL |  |  |
| `sort_order` | `int` | Y | NULL |  |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `lesson`
- **定位**：另一套课程/课件内容体系，明显比 course 更复杂，偏互动内容与富文本内容块。
- **表注释**：课程
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `title` | `varchar(64)` | Y | NULL | 标题 |  |
| `remark` | `varchar(128)` | Y | NULL | 备注 |  |
| `thumb` | `varchar(64)` | Y | NULL | 缩略图 |  |
| `top_img` | `varchar(64)` | Y | NULL | 头图 |  |
| `type` | `tinyint` | Y | 0 | 1:1.0 2:20 3:3.0 |  |
| `habit_type` | `tinyint(1)` | Y | 0 |  |  |
| `contents` | `json` | Y |  | 内容，多个内容块 |  |
| `content` | `text` | Y |  | 内容 |  |
| `audio` | `varchar(64)` | Y | NULL | 音频 |  |
| `video` | `varchar(64)` | Y | NULL | 视频 |  |
| `more_text` | `varchar(16)` | Y | NULL | \"查看更多\"文字 |  |
| `coin` | `int` | Y | NULL | 学习富贵币 |  |
| `coin_cond` | `tinyint` | Y | 0 | 获取富贵币条件 0阅读 1答题全对 |  |
| `status` | `tinyint` | Y | 0 | 是否完善 0否1是 |  |
| `is_del` | `tinyint` | Y | 0 | 删除0否1是 |  |
| `branchs` | `json` | Y |  | 支线 |  |
| `tags` | `json` | Y |  | 标签 |  |
| `form_msg` | `tinyint(1)` | Y | 0 | 表单提醒 0否1是 |  |
| `admin_id` | `int` | Y | NULL | 管理员id |  |
| `ver` | `tinyint(1)` | Y | 1 | 版本 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `document`
- **定位**：通用文件附件表，可挂到不同业务对象。
- **表注释**：document -lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `business_id`：多态业务对象，需结合 business_type 解释
  - `creator_id`：创建人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint UNSIGNED` | N |  |  |  |
| `name` | `varchar(64)` | Y | NULL | 名称 |  |
| `type` | `varchar(16)` | Y | NULL | 类型 |  |
| `url` | `varchar(255)` | Y | NULL | 文件链接 |  |
| `path` | `varchar(255)` | Y | NULL | 路径key |  |
| `size` | `int` | Y | NULL | 大小 |  |
| `business_type` | `tinyint(1)` | Y | 0 | 业务类型 0其他 1饮食 2客户 3商品 |  |
| `group` | `tinyint(1)` | Y | 0 | 业务类型下的分组 |  |
| `business_id` | `int` | Y | NULL | 业务id | 多态业务对象，需结合 business_type 解释 |
| `creator_id` | `int` | Y | NULL | 创建者id | 创建人 -> admins.id |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



## 八、AI 助手、会话与自动化任务

### `assistants`
- **定位**：AI 助手/智能体配置表，支持系统助手、客户助手、多专家会诊等模式。
- **表注释**：assistants-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户专属助手 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `type` | `tinyint(1)` | Y | 0 | 0默认助手 1系统助手 2客户助手 3智能体 |  |
| `customer_id` | `int` | Y | NULL |  | 客户专属助手 -> customers.id |
| `name` | `varchar(16)` | Y | NULL |  |  |
| `code` | `varchar(32)` | Y | NULL |  |  |
| `avatar` | `varchar(128)` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 0 | 0关闭 1打开 |  |
| `provider` | `varchar(16)` | Y | NULL | 供应商 |  |
| `api_key` | `varchar(64)` | Y | NULL |  |  |
| `system_prompt` | `varchar(10000)` | Y | NULL |  |  |
| `description` | `varchar(255)` | Y | NULL | 简短描述 |  |
| `welcome_msg` | `varchar(255)` | Y | NULL |  |  |
| `expert` | `varchar(255)` | Y | NULL | 擅长方面 |  |
| `tag` | `varchar(255)` | Y | NULL |  |  |
| `is_mdt` | `tinyint(1)` | Y | NULL | 是否参加多专家会诊 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `chats`
- **定位**：客户与 AI 助手的会话主表，一次会话对应多条 messages。
- **表注释**：chats-lwp
- **推荐理解粒度**：1 行 = 1 个客户与 1 个助手的一次对话会话。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_id`(`customer_id` ASC) USING BTREE`
  - `INDEX `idx_ assistant_id`(`assistant_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：会话所属客户 -> customers.id
  - `assistant_id`：主助手 -> assistants.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int UNSIGNED` | N |  |  |  |
| `title` | `varchar(128)` | Y | NULL | 标题 |  |
| `status` | `tinyint(1)` | Y | 1 | 状态 0关闭 1进行 |  |
| `customer_id` | `int` | Y | NULL |  | 会话所属客户 -> customers.id |
| `assistant_id` | `int UNSIGNED` | Y | NULL |  | 主助手 -> assistants.id |
| `assistant_ids` | `json` | Y |  | 多专家会诊 |  |
| `conversation_id` | `varchar(64)` | Y | NULL |  |  |
| `mode` | `tinyint(1)` | Y | 1 |  |  |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `messages`
- **定位**：会话消息明细表，role 区分用户/助手，action 描述消息业务类型。
- **表注释**：messages-lwp
- **推荐理解粒度**：1 行 = 1 条会话消息。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_chat_id`(`chat_id` ASC) USING BTREE`
  - `INDEX `idx_user_id`(`customer_id` ASC) USING BTREE`
  - `INDEX `idx_created_at`(`created_at` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `chat_id`：会话 -> chats.id
  - `assistant_id`：发送助手 -> assistants.id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint UNSIGNED` | N |  |  |  |
| `chat_id` | `int UNSIGNED` | N |  |  | 会话 -> chats.id |
| `assistant_id` | `int` | Y | NULL |  | 发送助手 -> assistants.id |
| `customer_id` | `int UNSIGNED` | Y | NULL |  | 客户 -> customers.id |
| `role` | `varchar(16)` | N |  |  |  |
| `action` | `varchar(32)` | Y | 'chat' | chat(普通聊天) notify提醒，event事件  course课件 |  |
| `action_data` | `json` | Y |  |  |  |
| `content` | `text` | Y |  |  |  |
| `content_type` | `tinyint(1)` | Y | 0 | 0文字 1图片 2图文 3视频 4音频 5文档 |  |
| `token_count` | `int` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 1 | 0待处理 1已处理 |  |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `meal_tasks`
- **定位**：餐食识别/处理任务表，通常由 AI/工作流处理上传图片得到 food_data。
- **表注释**：餐食任务表-lwp
- **推荐理解粒度**：1 行 = 1 次餐食识别任务/上传任务。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_date_meal`(`customer_id` ASC, `record_date` ASC, `meal_type` ASC) USING BTREE`
  - `INDEX `idx_work_task_id`(`work_task_id` ASC) USING BTREE`
  - `INDEX `idx_is_aggregated`(`is_aggregated` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `work_task_id`：工作流任务 -> work_tasks.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | N |  |  | 客户 -> customers.id |
| `record_date` | `date` | N |  | 记录日期 |  |
| `meal_type` | `tinyint(1)` | N |  | 餐次类型 1早餐 2中餐 3晚餐 4加餐 |  |
| `work_task_id` | `int` | N |  |  | 工作流任务 -> work_tasks.id |
| `file_url` | `varchar(800)` | Y | NULL |  |  |
| `file_name` | `varchar(255)` | Y | NULL |  |  |
| `food_data` | `json` | Y |  | 识别出的食物数据：{name, kcal, imgs, time} |  |
| `status` | `tinyint(1)` | Y | 0 | 状态 0待处理 1处理中 2已完成 3失败 |  |
| `is_aggregated` | `tinyint(1)` | Y | 0 | 是否处理 |  |
| `aggregated_at` | `datetime` | Y | NULL | 处理时间 |  |
| `snack_index` | `int` | Y | NULL |  |  |
| `error` | `text` | Y |  |  |  |
| `created_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | N | CURRENT_TIMESTAMP |  |  |



### `work_tasks`
- **定位**：异步工作任务/工作流任务表，是 AI、识别、自动化能力的调度中心。
- **表注释**：work_tasks-lwp
- **推荐理解粒度**：1 行 = 1 个异步工作任务。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `creator_id`：任务创建人 -> admins.id
  - `business_id`：多态业务对象，需结合 business_type 解释

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `title` | `varchar(64)` | Y | NULL |  |  |
| `task_type` | `varchar(32)` | N |  |  |  |
| `provider` | `varchar(16)` | Y | NULL |  |  |
| `workflow_id` | `varchar(32)` | Y | NULL |  |  |
| `assistant_code` | `varchar(64)` | Y | NULL |  |  |
| `params` | `json` | Y |  |  |  |
| `status` | `tinyint(1)` | Y | 0 |  |  |
| `original_path` | `varchar(128)` | Y | NULL |  |  |
| `result` | `json` | Y |  |  |  |
| `error` | `text` | Y |  |  |  |
| `creator_id` | `int` | Y | NULL |  | 任务创建人 -> admins.id |
| `completed_at` | `datetime` | Y | NULL |  |  |
| `external_task_id` | `varchar(100)` | Y | NULL |  |  |
| `retry_count` | `int` | Y | 0 |  |  |
| `business_type` | `tinyint` | Y | NULL |  |  |
| `business_id` | `int` | Y | NULL |  | 多态业务对象，需结合 business_type 解释 |
| `business_date` | `date` | Y | NULL |  |  |
| `created_at` | `timestamp` | N | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `timestamp` | N | CURRENT_TIMESTAMP |  |  |



## 九、标签、匹配与智能决策

### `label_definition`
- **定位**：标签定义元数据表，定义标签 key、数据类型、适用对象与匹配权重。
- **表注释**：标签定义元数据表
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_label_key`(`label_key` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `match_target_label_key`：用于匹配另一标签定义的 label_key，形成用户标签到教练标签的映射逻辑

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int UNSIGNED` | N |  | 自增主键 |  |
| `category` | `varchar(50)` | Y | NULL | 标签分类 |  |
| `label_name_cn` | `varchar(50)` | N |  | 标签名称（中文） |  |
| `label_key` | `varchar(50)` | N |  | 英文/系统key（snake_case） |  |
| `data_type` | `varchar(20)` | N |  | 数据类型 |  |
| `field_length` | `varchar(20)` | Y | NULL | 字段长度/约束 |  |
| `label_definition` | `text` | Y |  | 标签定义 |  |
| `label_level` | `varchar(20)` | Y | NULL | 标签层级 |  |
| `typical_value` | `text` | Y |  | 典型取值 |  |
| `is_multiple_choice` | `tinyint(1)` | N | 0 | 是否多选（1-是，0-否） |  |
| `applicable_object` | `tinyint(1)` | N | 0 | 适用对象（0-用户, 1-教练） |  |
| `is_ai_decision` | `tinyint(1)` | N | 0 | 是否适合AI决策（1-是，0-否） |  |
| `ai_decision_reason` | `text` | Y |  | AI决策的具体逻辑或原因 |  |
| `match_target_label_key` | `varchar(50)` | Y | NULL | 匹配教练标签的key | 用于匹配另一标签定义的 label_key，形成用户标签到教练标签的映射逻辑 |
| `match_target_label` | `varchar(100)` | Y | NULL | 匹配关联教练标签 |  |
| `match_weight` | `int` | N | 0 | 匹配权重占比（百分数整数，如50表示50%） |  |



### `customer_label_values`
- **定位**：客户标签实例值表，结合 label_definition 形成用户画像。
- **表注释**：用户标签实例值表
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_customer_label`(`customer_id` ASC, `label_key` ASC) USING BTREE`
  - `INDEX `idx_label_key`(`label_key` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint UNSIGNED` | N |  | 自增主键 |  |
| `customer_id` | `int UNSIGNED` | N |  | 用户唯一标识（用于匹配别的表） | 客户 -> customers.id |
| `label_key` | `varchar(50)` | N |  | 关联标签定义的key |  |
| `label_value` | `text` | N |  | 该用户的实际取值 |  |
| `sample_data` | `text` | Y |  | 示例/采样数据参考 |  |
| `updated_at` | `timestamp` | N | CURRENT_TIMESTAMP |  |  |



### `coach_label_values`
- **定位**：教练标签实例值表，结合 label_definition 形成教练画像。
- **表注释**：教练侧标签实例值表
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `UNIQUE INDEX `uk_coach_label`(`coach_id` ASC, `label_key` ASC) USING BTREE`
  - `INDEX `idx_coach_id`(`coach_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `coach_id`：教练 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint UNSIGNED` | N |  | 自增主键 |  |
| `coach_id` | `int UNSIGNED` | N |  | 教练唯一标识 | 教练 -> admins.id |
| `label_key` | `varchar(50)` | N |  | 关联标签定义的key(如: core_specialty) |  |
| `label_value` | `text` | N |  | 教练的属性值 |  |
| `updated_at` | `timestamp` | N | CURRENT_TIMESTAMP |  |  |



## 十、提醒、通知、服务与积分商品

### `customer_reminders`
- **定位**：客户提醒主表，支持单次/每日/每周/每月和业务类型。
- **表注释**：customer_reminders-lwp
- **推荐理解粒度**：1 行 = 1 个提醒规则。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_status`(`customer_id` ASC, `status` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `tpl_id`：通知模板 -> notify_tpl.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `title` | `varchar(16)` | Y | NULL |  |  |
| `description` | `varchar(64)` | Y | NULL |  |  |
| `status` | `tinyint` | Y | 1 | 0关闭 1进行中 2完成 3过期 |  |
| `repeat_type` | `tinyint` | Y | 0 | 0单次,1每日,2每周,3每月 |  |
| `weekdays_mask` | `tinyint` | Y | NULL | 周星期掩码 |  |
| `month_days` | `json` | Y |  | 每月几号[] |  |
| `max_occurrences` | `int` | Y | NULL |  |  |
| `expire_after_days` | `int` | Y | NULL |  |  |
| `triggered_count` | `int` | Y | 0 |  |  |
| `last_triggered_at` | `datetime` | Y | NULL |  |  |
| `completed_at` | `datetime` | Y | NULL |  |  |
| `business_type` | `tinyint` | Y | 0 | 0其他 1喝水 2运动 3睡眠 4饮食 5血糖 6体重 7用药 8冥想 |  |
| `raw_data` | `json` | Y |  | 通知数据 |  |
| `tpl_id` | `int` | Y | NULL | 模板id | 通知模板 -> notify_tpl.id |
| `channel` | `tinyint` | Y | NULL | 提醒渠道0系统 1服务号 |  |
| `style` | `json` | Y |  | 样式{icon,color} |  |
| `created_at` | `datetime` | Y | NULL |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `customer_reminder_times`
- **定位**：提醒的具体触发时间点子表。
- **表注释**：customer_reminder_times-lwp
- **推荐理解粒度**：1 行 = 1 个提醒规则下的 1 个触发时间点。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_reminder_time`(`reminder_id` ASC, `reminder_time` ASC) USING BTREE`
  - `INDEX `idx_scan_trigger`(`reminder_time` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `reminder_id`：提醒主表 -> customer_reminders.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `reminder_id` | `int` | N |  |  | 提醒主表 -> customer_reminders.id |
| `reminder_time` | `varchar(5)` | N |  | HH:MM |  |
| `last_triggered_at` | `datetime` | Y | NULL |  |  |
| `triggered_count` | `int` | Y | 0 |  |  |
| `created_at` | `datetime` | Y | NULL |  |  |



### `notify`
- **定位**：待发送/已发送的通知任务表。
- **表注释**：notify-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `tpl_id`：通知模板 -> notify_tpl.id
  - `customer_id`：客户 -> customers.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `status` | `tinyint` | Y | 0 | 状态：0待发送 1发送中 2已发送 3发送失败 |  |
| `to_users` | `json` | Y |  |  |  |
| `type` | `tinyint` | Y | 0 | 类型 1服务号 |  |
| `raw_data` | `json` | Y |  |  |  |
| `jump_page` | `varchar(255)` | Y | NULL | 跳转链接 |  |
| `business_type` | `tinyint` | Y | NULL |  |  |
| `sched_at` | `datetime` | Y | NULL |  |  |
| `sent_at` | `datetime` | Y | NULL |  |  |
| `error_msg` | `varchar(500)` | Y | NULL |  |  |
| `tpl_id` | `int` | Y | NULL |  | 通知模板 -> notify_tpl.id |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `notify_tpl`
- **定位**：通知模板定义表。
- **表注释**：notify_tpl-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(32)` | Y | NULL |  |  |
| `status` | `tinyint(1)` | Y | 0 | 0 1 |  |
| `type` | `tinyint` | Y | NULL | 1服务号 |  |
| `wx_tpl_id` | `varchar(64)` | Y | NULL |  |  |
| `tpl_def` | `json` | Y |  |  |  |
| `jump_page` | `varchar(64)` | Y | NULL | 跳转页面 |  |



### `service_issues`
- **定位**：客户服务问题/工单表。
- **表注释**：service_issues-lwp
- **推荐理解粒度**：1 行 = 1 个服务问题/工单。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `admin_id`：处理人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(64)` | Y | NULL | 标题 |  |
| `description` | `varchar(512)` | Y | NULL | 描述 |  |
| `status` | `tinyint(1)` | Y | 0 | 状态0未解决 1已解决 |  |
| `solution` | `varchar(512)` | Y | NULL | 解决方案 |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `admin_id` | `int` | Y | NULL | 管理员id | 处理人 -> admins.id |
| `completed_at` | `datetime` | Y | NULL | 完成时间 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `service_log`
- **定位**：服务过程日志表。
- **表注释**：service_log-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `admin_id`：操作人 -> admins.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `msg` | `varchar(512)` | Y | NULL |  |  |
| `type` | `tinyint(1)` | Y | 0 | 类型0 系统 |  |
| `customer_id` | `int` | Y | NULL | 客户id | 客户 -> customers.id |
| `admin_id` | `int` | Y | NULL | 操作人id | 操作人 -> admins.id |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `point_logs`
- **定位**：积分/经验流水表。
- **表注释**：point_logs-lwp
- **推荐理解粒度**：1 行 = 1 次积分/经验变动流水。
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
  - `INDEX `idx_customer_id`(`customer_id` ASC) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `customer_id`：客户 -> customers.id
  - `creator_id`：创建人/操作人 -> admins.id 或用户侧主体（需结合 source 判断）

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `bigint` | N |  |  |  |
| `customer_id` | `int` | Y | NULL |  | 客户 -> customers.id |
| `type` | `tinyint` | Y | 0 | 0获得 1消费 |  |
| `num` | `int` | Y | NULL | 积分变化 | 一般为1，变动一次就是+1,除非系统性调整 |
| `exp` | `int` | Y | NULL | 经验变化 | 经验这个字段现在不用 |
| `source` | `tinyint` | Y | 0 | 来源 0系统 1用户 2教练 |  |
| `des` | `varchar(64)` | Y | NULL | 描述 | 这是积分变动的说明：weight_checkin是体重打卡、habit_checkin habitId=xxxx date=xxxx-xx-xx是习惯打卡、courseId=xx是完成了课程学习、issue是提交阻碍、meal_upload是餐食上传 |
| `category` | `tinyint` | Y | 0 | 0其他 1完成任务 2运动打卡 3饮食记录 4健康监测 5社群互动 6系统调整 |  |
| `creator_id` | `int` | Y | NULL | 创建人 | 创建人/操作人 -> admins.id 或用户侧主体（需结合 source 判断） |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  | 根据这个积分变动的时间就可以统计用户的周积分和月积分了，周积分就是周一到周日，月积分就是月初到月末 |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `product`
- **定位**：商品表。
- **表注释**：product-lwp
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：
  - `category_id`：商品分类 -> product_category.id

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(32)` | Y | NULL | 商品名 |  |
| `thumb` | `varchar(64)` | Y | NULL | 缩图 |  |
| `category_id` | `int` | Y | NULL | 类别id | 商品分类 -> product_category.id |
| `plat` | `varchar(16)` | Y | NULL | 平台 |  |
| `link` | `varchar(256)` | Y | NULL | 链接 |  |
| `indications` | `text` | Y |  | 适应症 |  |
| `usage_method` | `text` | Y |  | 用法用量 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |



### `product_category`
- **定位**：商品分类维表。
- **表注释**：商品分类表
- **主键/唯一键/索引**：
  - `PRIMARY KEY (`id`) USING BTREE`
- **逻辑关联（非真实 FK）**：未发现明确的 ID 型关联字段，或该表主要作为独立维表/事实表存在。

| 字段 | 类型 | 可空 | 默认值 | 说明 | 关系推断 |
|---|---|---:|---|---|---|
| `id` | `int` | N |  |  |  |
| `name` | `varchar(32)` | N |  | 分类名称 |  |
| `created_at` | `datetime` | Y | CURRENT_TIMESTAMP |  |  |
| `updated_at` | `datetime` | Y | NULL |  |  |




## 十一、存储过程说明

### `search_all_tables(search_str)`
- 作用：遍历当前数据库所有字符型字段（`char/varchar/text/tinytext/mediumtext/longtext`），搜索包含指定字符串的表和字段。
- 产出：临时表 `search_result`，返回命中的 `table_name` 与 `column_name`。
- 用途：适合做库内模糊排查、字段定位、关键词追踪。
- 风险：逐表逐字段动态 SQL 搜索，库大时成本较高；只返回“命中过至少一条数据的字段”，不返回命中数量。

### `update_lesson_content()`
- 作用：遍历 `lesson.contents` JSON 数组，把其中 `type = 2` 的内容块拼接成文本，更新回 `lesson.content`。
- 本质：这是一次“从结构化内容块冗余生成纯文本 content”的数据整理过程。
- 业务含义：说明 `lesson.content` 可能是由 `lesson.contents` 派生出来的冗余字段，而不是绝对原始来源。做内容分析时若要最准，优先研究 `contents` 结构；做全文搜索/文本分析时可直接用 `content`。fileciteturn0file0

## 十二、机器人可直接采用的 Join 策略模板

### 12.1 客户基础画像
```sql
customers c
LEFT JOIN customer_info ci
  ON ci.customer_id = c.id
 AND ci.is_archived = 0
```
说明：若一个客户存在多条 `customer_info`，还要补“取最新一条”的逻辑。

### 12.2 客户日健康宽表
```sql
customers c
LEFT JOIN customer_health ch
  ON ch.customer_id = c.id
 AND ch.record_date BETWEEN ? AND ?
LEFT JOIN body_comp bc
  ON bc.customer_id = c.id
 AND bc.date = ch.record_date
```

### 12.3 习惯执行分析
```sql
customer_habits ch
LEFT JOIN habits h
  ON h.id = ch.habit_id
LEFT JOIN customer_checkin_records ccr
  ON ccr.customer_habit_id = ch.id
```

### 12.4 课程学习分析
```sql
customer_course_plan ccp
LEFT JOIN course_plans cp
  ON cp.id = ccp.plan_id
LEFT JOIN customer_course_record ccr
  ON ccr.customer_id = ccp.customer_id
```
说明：若要追具体“计划中应该学什么课程”，还要再接 `course_plan_days -> course`。

### 12.5 AI 会话分析
```sql
chats c
LEFT JOIN messages m
  ON m.chat_id = c.id
LEFT JOIN assistants a
  ON a.id = c.assistant_id
```

### 12.6 提醒触达分析
```sql
customer_reminders cr
LEFT JOIN customer_reminder_times crt
  ON crt.reminder_id = cr.id
LEFT JOIN notify n
  ON n.customer_id = cr.customer_id
```
说明：`notify` 与 `customer_reminders` 并没有显式外键，只能按客户、模板、时间等业务规则联动分析。

## 十三、机器人回答问题时的优先级建议

1. **先判定问题属于哪个业务域**：客户、健康、设备、习惯、计划、课程、会话、提醒、服务、积分。
2. **再判定粒度**：客户级、客户-日级、客户-习惯级、客户-课程级、消息级、任务级、设备测量级。
3. **再选主表**：优先选最贴近业务口径的事实表，而不是最原始的数据表。
4. **最后才去补充扩展表**：维表、桥表、JSON 字段、第三方设备明细。

## 十四、最终结论

如果把这个库浓缩成一句话：

> `mfgcrmdb` 是一个围绕 **客户健康管理与教练服务** 展开的综合业务数据库；`customers` 是主实体，`customer_health/body_comp` 是健康数据中枢，`customer_habits/customer_checkin_records/customer_plans/customer_todos` 是干预执行中枢，`course_* / customer_course_* / lesson` 是内容学习中枢，`assistants/chats/messages/work_tasks` 是 AI 自动化中枢，`customer_device/device_* / huami_*` 是设备采集中枢，`customer_reminders/notify/service_* / point_logs` 构成运营闭环。fileciteturn0file0

只要机器人严格遵守上面的**粒度、逻辑外键、业务口径、遗留表识别、JSON 扩展字段**规则，它已经可以相当完整地理解这个数据库并回答绝大多数数据分析问题。
