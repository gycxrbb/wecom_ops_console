# CRM 用户档案健康摘要升级开发报告

## 1. 背景

当前“用户档案”中的“近7天健康摘要”已经接入运行时代码，但实现明显偏轻，只覆盖了 `customer_health` 宽表中的少量聚合字段，还没有真正把 CRM 里已经存在的每日体重、饮水、三餐记录、营养素摄入、连续血糖日曲线这些正式数据资产用起来。

结合 [docs/CRM/mfgcrmdb_database_explanation.md](</d:/惯能/群机器人定时推送/wecom_ops_console/docs/CRM/mfgcrmdb_database_explanation.md>)、[docs/CRM/mfgcrmdb_schema_knowledge.json](</d:/惯能/群机器人定时推送/wecom_ops_console/docs/CRM/mfgcrmdb_schema_knowledge.json>) 和当前代码真值 [app/crm_profile/services/modules/health_summary.py](</d:/惯能/群机器人定时推送/wecom_ops_console/app/crm_profile/services/modules/health_summary.py>)，这一块需要从“近7天静态摘要”升级成“可切换 7/14/30 天的健康摘要中枢”，同时兼顾：

- 用户档案界面的可读性
- AI 教练助手的上下文质量
- 后续可扩展性
- 与当前 `health_summary_7d` 口径的兼容迁移

## 2. 当前真值与主要问题

### 2.1 当前正式实现

当前 `health_summary.py` 的正式行为是：

- 固定只取近 7 天
- 只查询 `customer_health`
- 只使用 `weight / blood_sbp / blood_dbp / fbs / pbs / hba1c / water_ml / sleep_min / step_count / kcal / cho / fat / protein / fiber / symptoms / medication` 等标量字段
- 返回的是一组轻量趋势摘要

当前没有接入的正式数据包括：

- `customer_health.breakfast_data / lunch_data / dinner_data / snack_data`
- `customer_health.food_intake` 之外的三餐结构化内容
- `customer_health.water_ml` 的连续日趋势展示
- `customer_glucose.points` 的日血糖曲线
- 14 天与 30 天视角

### 2.2 当前实现的核心差距

1. **餐食信息丢失过多**  
   现在只保留总热量和三大营养素，没有把“吃了什么、哪餐缺失、哪天吃得更容易导致血糖波动”展示出来。

2. **血糖口径偏弱**  
   当前主要依赖 `customer_health.fbs / pbs`，这更像业务宽表里的摘要字段，不足以支撑“全天波动、峰值时段、午餐后明显冲高”这类教练真正关心的判断。

3. **窗口写死在 7 天**  
   不利于教练做短期干预和周期复盘的切换，也不利于 AI 在“问题答疑”和“月度复盘”之间切换不同上下文粒度。

4. **AI 上下文仍然偏薄**  
   目前 `health_summary_7d` 还不够像“教练可用的健康摘要”，更像一段轻量统计结果。

## 3. 数据源角色与关系判断

### 3.1 `customer_health` 的正式角色

根据 CRM 文档，`customer_health` 是**按天汇总的业务宽表**，适合承载“业务端每日综合记录”。这张表在健康摘要里应该是第一主表。

它最适合承载的内容是：

- 每日体重
- 每日饮水量
- 每日睡眠、步数、症状
- 每日总热量和营养素摄入
- 每日早中晚餐与加餐的业务记录

建议在健康摘要中将 `customer_health` 定位为：

- **official daily summary source**
- 即：健康摘要的“每日概览真值”

### 3.2 `customer_glucose` 的正式角色

根据 CRM 文档，`customer_glucose` 是**客户连续/离散血糖日数据表**，其中 `points` 是日曲线点集合。

这张表最适合承载：

- 全天血糖曲线
- 峰值、低值、波动幅度
- 早晚时段变化
- 餐后冲高特征

建议在健康摘要中将 `customer_glucose` 定位为：

- **official glucose curve source**
- 即：血糖趋势、波动和异常判断的正式来源

不建议再把 `customer_health.glucose_data` 当作正式真值使用，因为文档已明确该字段存在弃用痕迹。

### 3.3 两张表的关系

两张表没有必要在数据库层做强绑定，它们的自然关系是：

- 关联键：`customer_id + 日期`
- `customer_health.record_date`
- `customer_glucose.date`

这意味着健康摘要的推荐编排方式是：

1. 先取时间窗口内的 `customer_health`
2. 再按同一客户、同一时间窗口补取 `customer_glucose`
3. 在服务层按“天”做轻量对齐

这类关系更像：

- `customer_health` 提供“这一天发生了什么”
- `customer_glucose` 提供“这一天血糖怎么波动”

## 4. 字段探索与使用建议

### 4.1 `customer_health` 中应正式纳入摘要的字段

建议纳入健康摘要主视图的字段：

- `record_date`
- `weight`
- `water_ml`
- `sleep_min`
- `sleep_des`
- `step_count`
- `symptoms`
- `kcal`
- `cho`
- `fat`
- `protein`
- `fiber`
- `breakfast_data`
- `lunch_data`
- `dinner_data`
- `snack_data`

建议作为 support 信息使用的字段：

- `medication`
- `meal_plans`
- `stress`
- `tonic`

原因是这些字段对教练有价值，但不是健康摘要卡片的第一层主信息，更适合作为 AI 扩展上下文或明细展开。

### 4.2 餐食 JSON 的结构判断

以 `breakfast_data` 为例，当前 JSON 结构已经足够支持业务展示和 AI 总结：

- `des`：本餐简述
- `name`：更完整的餐食名称与份量
- `time`：用餐时间
- `imgs`：餐食图片
- `kcal / cho / fat / protein`：本餐营养摘要
- `vits`：维生素微量结构
- `diet_assessment`：已有文案型评估

### 推荐使用方式

1. **用于档案界面展示的正式字段**

- `name`
- `des`
- `time`
- `kcal / cho / fat / protein`

2. **用于 AI 默认上下文的正式字段**

- 每日三餐是否有记录
- 每餐名称摘要
- 每餐热量与宏量营养结构
- 用餐时间是否过晚/过早

3. **仅作为 support，不建议默认塞入 AI 主上下文的字段**

- `imgs`
- `vits`
- `diet_assessment`

原因：

- `imgs` 是展示资产，不适合默认进入文本上下文
- `vits` 太细，默认注入会拉高噪音
- `diet_assessment` 大概率已经是历史生成文本或半结构化建议，容易和当前 AI 教练助手的输出互相污染

结论：  
`diet_assessment` 可以作为 support evidence 或“历史参考点评”，但不应作为 AI 默认正式上下文真值。

### 4.3 `customer_glucose.points` 的结构判断

`points` 是一个按时间排列的点位数组，单点包含：

- `time`
- `val`

这已经足够支持构建：

- 日均血糖
- 日最低 / 日最高
- 波动幅度
- 峰值时间
- 高值点数量
- 低值点数量
- 早餐后 / 午餐后 / 晚餐后波动特征

如果结合 `customer_health` 当天的三餐时间，还可以进一步做：

- 餐后 2 小时内峰值
- 哪一餐后冲高最明显
- 哪几天晚餐后恢复最慢

这类分析应该放在服务层做衍生，不建议把完整 `points` 原样直接塞到 UI 主卡片或 AI 默认上下文里。

## 5. 健康摘要的信息架构重设计

### 5.1 组件命名调整

当前“近7天健康摘要”建议改为统一名称：

- `健康摘要`

在右上角提供时间窗口切换：

- `近7天`
- `近14天`
- `近30天`

不要把标题写死成“近7天”，否则切换能力会和组件名冲突。

### 5.2 档案页推荐展示层次

建议把健康摘要拆成三层：

### 第一层：窗口总览

显示本窗口最关键的 4-6 个结论：

- 体重：最近值、相对窗口起点变化
- 饮水：日均饮水、达标天数
- 饮食：平均热量、三餐记录完整度
- 血糖：平均水平、最高峰值、异常天数
- 睡眠 / 步数：日均时长、活跃天数

### 第二层：趋势卡片

按主题分卡片展示：

- 体重与饮水
- 血糖趋势
- 饮食与营养摄入
- 睡眠与活动

### 第三层：代表性明细

只展示最值得看、最像“教练会继续点开”的内容：

- 最近 3 天餐食摘要
- 血糖波动最明显的 1-2 天
- 缺失记录较多的天

不要把 7/14/30 天所有原始 JSON 平铺出来，否则会显著加重阅读负担。

### 5.3 血糖卡片推荐展示口径

建议在健康摘要里优先展示：

- 窗口内平均血糖
- 窗口内最高值 / 最低值
- 高值天数
- 低值天数
- 波动最明显的一天
- 最近一天的午后或晚间峰值情况

其中“高值/低值”的阈值不要直接写死在第一版实现里，建议做成配置项或常量层统一定义。

### 5.4 饮食卡片推荐展示口径

建议展示：

- 记录天数
- 三餐完整度
- 平均热量
- 平均碳水 / 蛋白 / 脂肪
- 饮水达标天数
- 最近 3 天的代表性餐食

同时增加“餐食模式提示”，例如：

- 午餐后波动偏高的天较多
- 晚餐记录不完整
- 早餐蛋白摄入偏少

这些提示应由后端结构化生成，前端只负责展示，不要在前端写业务判断。

## 6. AI 教练助手的上下文接入建议

### 6.1 正式原则

AI 默认上下文不应直接塞原始表数据，而应塞：

- 窗口摘要
- 关键趋势
- 代表性异常
- 必要时再展开明细

否则会出现两个问题：

1. token 浪费严重
2. 模型抓不住真正重点

### 6.2 推荐上下文结构

建议把当前 `health_summary_7d` 升级为：

- `health_summary`

并在 payload 中显式带上：

- `window_days`
- `summary`
- `trend_flags`
- `meal_highlights`
- `glucose_highlights`
- `data_quality`

示意：

```json
{
  "module_key": "health_summary",
  "window_days": 14,
  "summary": {
    "weight_latest": 62.7,
    "weight_change": -1.2,
    "water_avg_ml": 1850,
    "meal_record_days": 12,
    "glucose_avg": 6.8,
    "glucose_peak": 12.1
  },
  "trend_flags": [
    "午餐后血糖峰值偏高天数较多",
    "近14天体重缓慢下降",
    "饮水达标率偏低"
  ],
  "meal_highlights": [
    {
      "date": "2026-04-24",
      "meal": "lunch",
      "time": "12:15",
      "summary": "午餐后血糖峰值 12.1，午餐主食偏集中"
    }
  ],
  "glucose_highlights": [
    {
      "date": "2026-04-24",
      "peak": 12.1,
      "peak_time": "12:46",
      "amplitude": 6.9
    }
  ],
  "data_quality": {
    "missing_meal_days": 2,
    "missing_glucose_days": 1
  }
}
```

### 6.3 默认加载与扩展加载建议

推荐规则：

1. **默认 AI 上下文仍以 7 天为主**

原因：

- 适合日常答疑
- token 更稳
- 对“餐评 / 当周干预 / 异常提醒”最有效

2. **14 天与 30 天用于场景增强**

更适合：

- 周期复盘
- 趋势归因
- 体重平台期分析
- 长期血糖与饮食行为观察

3. **明细扩展使用 selected expansions**

推荐新增或调整：

- `meal_detail_window`
- `glucose_curve_window`

并真正接入后端，而不是只停留在接口参数层。

### 6.4 AI 上下文中不建议默认注入的内容

以下内容建议只在用户显式展开或命中场景时才注入：

- 餐食图片 URL
- 全量 `points` 原始数组
- `diet_assessment` 长文本
- 全量维生素微量元素字段

这些内容适合做 support，不适合做默认 official context。

## 7. 推荐实现方案

### 7.1 后端服务层重构建议

建议把当前固定模块：

- `health_summary_7d`

重构为两层能力：

### A. 兼容层

继续保留当前对外可识别的 `health_summary_7d`，避免现有前端或 AI 模块映射立即失效。

### B. 新正式能力层

新增参数化加载器：

- `load_health_summary(conn, customer_id, window_days=7)`

支持：

- `7`
- `14`
- `30`

并在内部拆成：

- `_load_health_daily_rows_from_customer_health`
- `_load_glucose_daily_rows_from_customer_glucose`
- `_build_health_window_summary`
- `_build_meal_highlights`
- `_build_glucose_highlights`

### 7.2 数据分析规则建议

### 体重

- 最近值
- 起点到终点变化
- 最低/最高
- 连续下降 / 连续上升 / 平台

### 饮水

- 日均饮水
- 达标天数
- 最低/最高

### 餐食与营养

- 有记录天数
- 三餐完整度
- 平均热量
- 平均碳水 / 蛋白 / 脂肪
- 代表性餐食

### 血糖

- 有曲线记录天数
- 日均值
- 最低 / 最高
- 波动幅度
- 峰值时间段
- 代表性高值日

### 数据质量

- 缺失餐食天数
- 缺失血糖天数
- 缺失体重天数
- 缺失饮水天数

### 7.3 前端交互建议

在“健康摘要”卡片右上角增加时间切换器：

- `近7天`
- `近14天`
- `近30天`

切换行为建议：

1. 仅刷新健康摘要模块
2. 不整页重刷
3. 切换后标题保持“健康摘要”
4. 卡片角落显示当前窗口说明，例如“统计窗口：近14天”

如果未来 AI 抽屉要复用当前窗口，可把 `selected_health_window_days` 一并带给 AI 接口。

### 7.4 与现有 CRM AI 报告的对齐建议

当前 [docs/CRM_USER_PROFILE_AI_INTEGRATION_REPORT.md](</d:/惯能/群机器人定时推送/wecom_ops_console/docs/CRM_USER_PROFILE_AI_INTEGRATION_REPORT.md>) 中：

- `health_summary_7d` 仍主要指向 `customer_health`
- `health_detail_expansion` 也还没有正式纳入 `customer_glucose`

建议后续把这份报告中的口径同步回主报告，至少补两点：

1. 健康摘要的正式数据源是 `customer_health + customer_glucose`
2. 健康摘要窗口应从固定 7 天升级为可参数化 7/14/30 天

## 8. 分期建议

### P0：把摘要做成真正可用

- 健康摘要卡片改为可切换 7/14/30 天
- `customer_health` 正式纳入体重、饮水、餐食、营养
- `customer_glucose` 正式纳入血糖波动摘要
- AI 默认上下文仍以 7 天摘要为主

### P1：把 AI 上下文做深

- 场景化决定 7/14/30 天加载策略
- 支持餐食明细展开
- 支持血糖曲线高亮日展开
- 把 `selected_expansions` 真正接入加载链路

### P2：把洞察做智能

- 自动识别“哪餐后波动明显”
- 自动识别“体重平台期 + 饮食/血糖联动”
- 增加可复用的健康洞察规则库

## 9. 验收标准

### 9.1 用户档案页

- 可以在健康摘要右上角切换 7/14/30 天
- 切换后体重、饮水、餐食、血糖摘要一起变化
- 不展示原始 JSON 噪音
- 教练能一眼看懂“最近发生了什么”

### 9.2 AI 教练助手

- 默认能读到结构化健康摘要
- 餐评问题能基于真实三餐信息回答
- 血糖问题能基于 `customer_glucose.points` 派生结果回答
- 周期复盘类问题能根据 14/30 天趋势补充判断

### 9.3 工程侧

- 健康摘要后端实现不再写死 7 天
- `customer_health` 与 `customer_glucose` 的角色边界清晰
- `diet_assessment` 和全量 `points` 不作为默认主上下文真值
- 与现有 `health_summary_7d` 保持兼容迁移路径

## 10. 最终判断

从当前 CRM 数据资产看，这条线完全值得继续做，而且基础已经比现在页面表现出来的更强。

当前阶段判断：

- **已经能做什么**：轻量近7天摘要
- **半能做什么**：把体重、饮水、营养、餐食、血糖接成真正的教练视图
- **还不能做什么**：稳定支持 7/14/30 天切换，并把血糖曲线和餐食行为真正转成 AI 可用上下文

当前最关键的 blocker 不是数据库没有数据，而是：

- 现有服务层只做了轻聚合
- 数据角色还没分层
- AI 上下文还没接上 `customer_glucose`

最值得继续推进的下一步是：

1. 先把 `health_summary.py` 重构成参数化窗口模块
2. 再把 `customer_glucose.points` 的衍生分析接进摘要
3. 最后把前端卡片和 AI 上下文一起升级
