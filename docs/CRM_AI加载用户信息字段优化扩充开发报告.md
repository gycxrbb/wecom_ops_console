# AI加载用户信息字段优化扩充开发报告

- 文档日期: 2026-04-26
- 适用范围: CRM客户档案 AI 教练助手（上下文加载链路）
- 文档目标: 在不引入敏感信息泄露风险的前提下，系统化扩充可加载用户字段，提升 AI 回答准确性、可执行性与个性化程度。

## 1. 背景与问题定义

当前 AI 教练助手已具备基础上下文加载能力，但上下文内容仍以静态画像和有限健康摘要为主，对客户行为执行、计划推进、提醒依从、学习进度、标签画像、服务工单等关键业务维度覆盖不足，导致以下问题：

1. 回答建议偏通用，缺少对客户执行阻碍和阶段状态的感知。
2. 对“为什么做不到”类问题解释力不足。
3. 对“下一步该做什么”类问题行动化程度不足。
4. 对客户长期服务上下文（提醒、工单、学习）的连续性利用不足。

本报告基于以下文档与当前代码实现进行调研并形成开发方案：

1. docs/CRM/mfgcrmdb_database_explanation.md
2. docs/CRM/mfgcrmdb_schema_knowledge.json
3. app/crm_profile/services/profile_loader.py
4. app/crm_profile/services/modules/*.py
5. app/crm_profile/services/ai_coach.py
6. app/crm_profile/services/context_builder.py
7. app/crm_profile/services/prompt_builder.py

## 2. 当前实现现状

### 2.1 已实现上下文模块（7个）

当前通过 profile_loader 串行加载并入上下文：

1. basic_profile（基础档案）
2. safety_profile（安全档案）
3. goals_preferences（目标与偏好）
4. health_summary_7d（近7天健康摘要）
5. body_comp_latest_30d（近30天体成分）
6. points_engagement_14d（近14天积分活跃）
7. service_scope（服务关系）

### 2.2 当前链路概述

1. 前端客户详情页调用 /profile 拉取结构化档案。
2. /profile 成功后，前端通过 fire-and-forget 调用 /ai/preload，后台预热 AI 侧 profile 缓存。
3. 后端通过 profile_cache_key(customer_id, window_days) 管理 profile 缓存，默认 key 口径为 profile:{customer_id}:hw7。
4. AI聊天请求触发 _prepare_ai_turn，当前默认读取 profile_cache_key(customer_id)，也就是 hw7 档案缓存；如果前端当前健康窗口为 14/30 天，预热 key 与 AI 默认读取 key 仍可能不一致。
5. build_context_text 将模块 payload 序列化为上下文文本，并根据 selected_expansions 做扩展模块筛选。
6. prompt_builder 组装 system prompt + context + user message。
7. chat_completion/chat_completion_stream 发起模型调用。

### 2.3 已有安全约束

1. 白名单/黑名单式字段防护，已排除 openid、unionid、last_login_ip 等敏感字段。
2. prompt 文本中明确声明已剔除敏感身份字段。

### 2.4 当前缺口

1. 缺行为执行层: 习惯打卡、阻碍、连续天数、执行稳定性。
2. 缺计划推进层: 计划状态、待办进度、延期/暂停信息。
3. 缺提醒依从层: 提醒触发与完成情况。
4. 缺学习吸收层: 课程学习状态与时长。
5. 缺标签画像层: AI可决策标签未注入。
6. 缺服务风险层: 未解决工单、关键服务日志未注入。

## 3. 字段扩充总体策略

### 3.1 目标

1. 提升回答准确性: 让 AI 知道客户“当前真实状态”。
2. 提升建议可执行性: 建议要贴合客户执行能力和阻碍。
3. 提升个性化: 用标签、服务轨迹、学习状态约束回答。
4. 保持上下文可解释、可压缩、可回退。

### 3.2 设计原则

1. 只加载高价值摘要字段，不直接注入大体积原始 JSON。
2. 先摘要后注入，优先标量和短文本。
3. 模块化扩展，保持现有 cards 结构。
4. 安全优先，持续剔除敏感身份信息。
5. 有数据才注入，空数据以 empty/partial 回退。

## 4. 字段扩充方案（按优先级）

## 4.1 P0（首批必做，直接提升回答质量）

### 模块A: habit_adherence_14d（习惯执行画像）

- 来源表: customer_habits, customer_checkin_records, customer_obstacles
- 建议字段:
  1. active_habits_count
  2. avg_checkin_completion_rate_14d
  3. failed_checkin_days_14d
  4. current_streak_max
  5. top_obstacles
  6. if_then_plan_summary
- 价值: 回答可贴近真实执行问题，不再泛化。

### 模块B: plan_progress_14d（计划推进画像）

- 来源表: customer_plans, customer_todos
- 建议字段:
  1. current_plan_title
  2. current_plan_status
  3. plan_day_progress
  4. todo_completion_rate_14d
  5. overdue_todo_count
  6. pause_resume_events
- 价值: AI 能根据计划阶段给建议，而非脱离计划。

### 模块C: reminder_adherence_14d（提醒依从画像）

- 来源表: customer_reminders, customer_reminder_times
- 建议字段:
  1. active_reminder_count
  2. reminders_by_business_type
  3. trigger_count_14d
  4. last_triggered_at
  5. estimated_follow_through_rate
- 价值: 区分“未提醒”与“提醒后未执行”。

### 模块D: learning_engagement_30d（学习吸收画像）

- 来源表: customer_course_record
- 建议字段:
  1. course_total_assigned
  2. course_in_progress
  3. course_completed
  4. completion_rate
  5. study_seconds_30d
  6. last_learning_at
- 价值: 让 AI 判断客户接受度与教育干预方式。

### 模块E: ai_decision_labels（AI决策标签画像）

- 来源表: customer_label_values + label_definition
- 建议字段:
  1. label_key
  2. label_value_summary
  3. label_definition_summary
  4. match_weight
- 策略: 仅纳入 label_definition.is_ai_decision=1 的标签。
- 价值: 明确标签驱动推理依据，减少模型臆测。

## 4.2 P1（第二批增强）

### 模块F: sleep_recovery_profile_14d

- 来源表: customer_sleep
- 建议字段: avg_sleep_min, avg_sleep_score, rem_avg, rhr_avg, hrv_avg, sleep_variance

### 模块G: sport_energy_profile_14d

- 来源表: customer_sport
- 建议字段: total_steps_14d, avg_steps, calories_14d, active_days_14d

### 模块H: stress_profile_14d

- 来源表: customer_stress
- 建议字段: high_stress_ratio, peak_stress_periods, stress_trend

### 模块I: service_risk_profile_30d

- 来源表: service_issues, service_log
- 建议字段: unresolved_issues_count, recent_issue_types, last_service_action_at

## 4.3 P2（第三批可选）

### 模块J: nutrition_execution_profile_14d

- 来源表: customer_health, customer_nutrition_plans
- 建议字段: kcal_target_gap, macro_balance_score, medication_adherence_summary

### 模块K: family_support_context

- 来源表: families
- 建议字段: family_status, support_environment_hint

## 5. 技术实现方案

### 5.1 后端目录与文件变更建议

1. 新增模块文件（建议先P0）:
   - app/crm_profile/services/modules/habit_adherence.py
   - app/crm_profile/services/modules/plan_progress.py
   - app/crm_profile/services/modules/reminder_adherence.py
   - app/crm_profile/services/modules/learning_engagement.py
   - app/crm_profile/services/modules/ai_decision_labels.py
2. 更新加载器:
   - app/crm_profile/services/profile_loader.py
3. 更新字段标签:
   - app/crm_profile/services/context_builder.py
4. 如需扩展 schema，可在:
   - app/crm_profile/schemas/context.py
   增加 build_plan 中新增模块标识。

### 5.2 context 序列化策略

1. 每模块最多输出 8-12 个字段。
2. 长文本截断到合理长度（例如每字段 120-200 字）。
3. JSON 字段先抽取关键统计再输出。
4. 对空值和异常值进行兜底，避免噪声。
5. 字段裁剪以业务相关性、隐私安全和回答聚焦度为准，不在本报告中定义模型侧上下文额度。

## 6. 已识别实现问题与修复建议

### 6.1 selected_expansions 参数链路未完全闭环

现象:

1. 路由层会把 selected_expansions 传给 chat-stream / ask_ai_coach。
2. _prepare_ai_turn 已支持 selected_expansions，并会传给 build_context_text。
3. 但当前仍存在部分未闭环路径:
   - _prepare_ai_turn_cached 在 cache miss 时调用 _prepare_ai_turn_async，未继续透传 selected_expansions。
   - 非流式 ask_ai_coach 调用 _prepare_ai_turn 时未透传 selected_expansions，且写审计快照时 build_context_text 未按选择重建上下文文本。
   - chat-stream 写审计快照时 build_context_text 未按选择重建上下文文本，selected_expansions 仍写为 None。
   - DeepSeek thinking 轻量路径当前未接收 selected_expansions。

影响:

1. 前端“扩展上下文选择”在部分命中路径可影响上下文，但首轮 miss、非流式路径、审计回放与部分 thinking 路径不稳定。
2. 审计快照无法准确还原本轮实际选择过哪些扩展模块。

修复建议:

1. _prepare_ai_turn_cached 的 miss 路径调用 _prepare_ai_turn_async 时补传 selected_expansions。
2. ask_ai_coach 非流式调用 _prepare_ai_turn 时补传 selected_expansions。
3. chat-stream / 非流式写 context snapshot 时，用 build_context_text(prepared.ctx.cards, selected_expansions=selected_expansions) 重建快照文本，并记录真实 selected_expansions。
4. DeepSeek thinking 轻量路径补充 selected_expansions 参数并传给 build_context_text。

### 6.2 profile 预热仍只是第一阶段缓存优化

现象:

1. 当前 /ai/preload 预热的是 profile cache，不写 AI 会话审计。
2. 预热结果不等于正式会话上下文快照。
3. 当前 AI prepare 默认读取 hw7 profile cache，/profile 与 /ai/preload 使用的 health_window_days 如果不是 7，仍可能出现预热成功但 AI 首问缓存未命中的情况。

影响:

1. 用户首问 prepare 等待可下降，但真正的会话上下文仍应在用户发问后正式写入 crm_ai_context_snapshots。
2. 后续如果要进一步减少 prepare 时间，需要抽出 prompt-ready 的 ai_context_cache，而不是继续把逻辑堆到 ai_coach.py。
3. 多健康窗口场景下，缓存命中率取决于 AI prepare 是否能拿到并使用当前窗口参数。

修复建议:

1. 保持 preload 只作为 support cache。
2. 后续新增 ai_context_cache 时，必须与真实对话复用同一套上下文构建函数。
3. 不在 preload 阶段写 crm_ai_sessions、crm_ai_messages、crm_ai_context_snapshots。
4. 将 health_window_days 明确纳入 AI chat/chat-stream 请求与 prepare cache key，或者在前端预热时同时预热 AI 默认读取的 hw7 key，避免窗口不一致造成缓存未命中。

## 7. 数据安全与合规要求

1. 禁止加载手机号、openid、unionid、last_login_ip、密码、salt 等敏感字段。
2. 对 customer_label_values 的自由文本值做长度与内容过滤。
3. 对 service_log/notes/action_data 类字段做隐私脱敏。
4. 审计表仅保存必要上下文快照，避免原始隐私内容过量落库。

## 8. 验收标准

### 8.1 功能验收

1. 新增模块可在 /profile 返回 cards 中看到。
2. AI 会话审计表中 used_modules 包含新增模块。
3. 不同场景下 selected_expansions 可影响最终上下文。

### 8.2 质量验收

1. AI回答准确性提升（人工评估集）:
   - 目标: 相较当前版本提升 15% 以上。
2. 行动建议可执行性评分提升:
   - 目标: 提升 20% 以上。
3. 幻觉率下降:
   - 目标: 下降 20% 以上。

### 8.3 性能验收

1. /profile P95 时延增加不超过 120ms（首批模块）。
2. chat-stream 首个流式 delta 返回时间增加不超过 250ms。
3. 上下文构建失败率小于 0.5%。

## 9. 开发排期建议

### 阶段1（2-3天）

1. 实现 P0 的 A/B/C 模块。
2. 修复 selected_expansions 透传问题。
3. 完成模块字段标签与序列化压缩。

### 阶段2（2天）

1. 实现 P0 的 D/E 模块。
2. 增加回归测试与审计验证。

### 阶段3（2-3天）

1. 推进 P1 模块。
2. 做 A/B 对比评估与参数调优。

## 10. 测试计划

1. 单元测试:
   - 各模块 load 函数（有数据、空数据、异常回退）。
2. 集成测试:
   - /profile、/ai/chat、/ai/chat-stream 链路。
3. 安全测试:
   - 敏感字段阻断测试。
4. 回归测试:
   - 既有7模块输出不回归。
5. 启动验证:
   - 后端服务可启动。
   - 若涉及前端扩展控制，前端 dev 可编译运行。

## 11. 风险与应对

1. 风险: 新模块导致查询变慢。
   - 应对: 增加索引利用、限制时间窗、先聚合后注入。
2. 风险: 上下文过长导致回答聚焦度下降。
   - 应对: 强摘要策略 + 优先级裁剪。
3. 风险: 标签值噪声影响回答质量。
   - 应对: 仅纳入 is_ai_decision 标签并做清洗。
4. 风险: 行为字段口径不一致。
   - 应对: 在模块注释中固定统计口径与时间窗。

## 12. 结论

本次优化应从“补齐执行与服务语义”出发，而不仅是继续堆叠生理字段。建议优先完成 P0 五个模块与 selected_expansions 生效修复，这将以最小改动带来最大回答质量收益，并为后续个性化推理建立稳定上下文基座。
