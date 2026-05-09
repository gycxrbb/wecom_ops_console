# CRM AI 意图识别与提示词自动路由计划

> 日期：2026-04-30
>
> 文档状态：plan / candidate design
>
> 适用范围：`CRM 客户档案 + AI 教练助手`
>
> 关联文档：`docs/CRM_AI_PROMPT_ARCHITECTURE_PLAN.md`、`docs/CRM_AI_CHAT_RESPONSE_FEEDBACK_PLAN.md`、`docs/CURRENT_STATUS.md`

---

## 1. 结论先行

你的思路是对的，而且是 AI 教练助手从“配置型工具”走向“智能工作台”的关键一步。

当前让教练手动选择场景策略和风格模板，有两个明显问题：

1. 教练在真实工作里通常先想到“我要做什么”，而不是先想“我该选哪个 prompt 分支”。
2. 场景和风格选错后，AI 不是完全不能答，而是会输出“方向差一点”的结果，这类问题最难被系统自动发现。

建议新增一层：

`AI 意图识别与提示词自动路由层`

它的职责不是替代正式 prompt builder，而是在正式回答前，根据教练本次问题先判断：

1. 应该走哪个 `scene_key`
2. 应该走哪个 `output_style`
3. 是否需要附加参考模块
4. 判断置信度是多少
5. 是否需要保留人工覆盖

核心原则：

> 自动识别负责推荐和默认选择，人工选择负责覆盖和纠错，最终进入正式回答的 scene/style 必须可追溯。

---

## 2. 当前真实现状

结合当前仓库代码，已有 official 能力：

1. 后端 prompt 拼装在 `app/crm_profile/services/prompt_builder.py`。
2. 当前正式拼装支持：
   - `scene_key`
   - `output_style`
   - `context_text`
   - `profile_note`
   - `rag_context_text`
3. 场景模板来自 `app/crm_profile/prompts/scenes/` 或 DB：
   - `meal_review`
   - `data_monitoring`
   - `abnormal_intervention`
   - `qa_support`
   - `period_review`
   - `long_term_maintenance`
4. 风格模板来自 `app/crm_profile/prompts/styles/` 或 DB：
   - `customer_reply`
   - `coach_brief`
   - `handoff_note`
   - `detailed_report`
   - `bullet_list`
5. `app/crm_profile/prompts/registry.py` 已支持从 DB 动态读取 active scenes / styles。
6. `GET /api/v1/crm-customers/{customer_id}/ai/config` 已返回 scenes 和 styles。
7. 前端 `AiCoachPanel.vue` 当前在“已加载参考信息”区域提供手动下拉选择。
8. `useAiCoach.ts` 当前把 `currentScene` 和 `outputStyle` 随 `chat-stream` / `thinking-stream` 请求传给后端。

当前还不能写成 official 的能力：

1. 还没有发起回答前的意图识别。
2. 还不能根据“我要给用户做一个餐评”自动选择 `meal_review + customer_reply`。
3. 还不能把自动选择结果和置信度写入审计。
4. 还没有“自动推荐，但教练可手动覆盖”的交互。

---

## 3. 要解决的问题

### 3.1 教练视角的问题

教练真实输入更像：

1. “我要给用户做一个餐评”
2. “帮我看看她这周血糖为什么波动”
3. “她最近睡不好，我应该怎么跟进”
4. “帮我写一段今晚发给客户的话”
5. “帮我总结本周复盘”
6. “这个月要给她做个阶段性反馈”

这些问题天然包含意图，但不一定包含系统里的模板 key。让教练每次手动选择，会增加心智成本。

### 3.2 系统视角的问题

当前后端相信前端传来的 `scene_key` 和 `output_style`。如果前端仍停在默认值：

```text
scene_key = qa_support
output_style = coach_brief
```

那么“餐评 + 客户话术”的问题也可能被当成普通答疑 + 教练简报处理。

这会导致：

1. 场景策略不够贴合。
2. 输出风格不够像教练真正要的结果。
3. 后续反馈统计会混乱，因为差评可能源于路由错，而不是 prompt 本身差。

---

## 4. 产品目标

### 4.1 自动识别

当教练发送问题时，系统自动识别：

```json
{
  "scene_key": "meal_review",
  "output_style": "customer_reply",
  "confidence": 0.91,
  "reason": "用户明确提到餐评，且目标是给用户生成可发送内容",
  "route_source": "auto"
}
```

### 4.2 可解释

前端应展示轻量提示：

```text
已自动识别：餐评 / 客户话术
```

鼠标悬停或展开时显示：

```text
因为你的问题里提到“给用户做一个餐评”，系统自动使用餐评场景和客户话术风格。
```

### 4.3 可覆盖

教练仍然可以手动改成：

1. 场景：数据监测
2. 风格：详细报告

此时本轮请求应记录：

```json
{
  "auto_scene_key": "meal_review",
  "auto_output_style": "customer_reply",
  "final_scene_key": "data_monitoring",
  "final_output_style": "detailed_report",
  "route_source": "manual_override"
}
```

### 4.4 可追溯

每次 AI 对话审计里必须知道：

1. 自动识别原始结果
2. 最终使用结果
3. 是否人工覆盖
4. 置信度
5. 使用的 active prompt 候选列表
6. 意图识别版本

---

## 5. 推荐架构

建议新增一层服务：

`app/crm_profile/services/intent_router.py`

它位于正式 prompt builder 之前：

```text
教练输入
  ↓
Intent Router
  ↓  scene_key / output_style / confidence / reason
Prompt Builder
  ↓
AI Coach Answer
```

职责边界：

1. `intent_router` 只负责判断该用哪个 prompt 分支。
2. `prompt_builder` 仍只负责按最终 scene/style 拼装 prompt。
3. `ai_coach.py` 负责协调路由、上下文加载、模型调用、审计写入。
4. 前端负责展示自动识别结果和人工覆盖入口。

不要把意图识别规则散落到前端，也不要直接写死在 `prompt_builder.py`。

---

## 6. 识别策略设计

### 6.1 P0：规则 + 轻量语义词典

第一阶段不建议一上来就每次多调用一次大模型。原因：

1. 会增加一次请求延迟。
2. 会增加成本。
3. 大量教练输入其实可以用规则稳定识别。
4. 规则结果更可解释，便于冷启动。

建议先实现规则路由：

| 输入线索 | scene_key | output_style |
|----------|-----------|--------------|
| 餐评、点评这餐、早餐/午餐/晚餐、这顿饭、吃了、餐后 | `meal_review` | 默认 `customer_reply` 或 `coach_brief` |
| 血糖、血压、睡眠、体重、体脂、趋势、波动、数据 | `data_monitoring` | `coach_brief` |
| 低血糖、头晕、不舒服、异常、风险、疼痛、平台期 | `abnormal_intervention` | `coach_brief` |
| 为什么、能不能、可不可以、怎么解释、客户问 | `qa_support` | `customer_reply` 或 `coach_brief` |
| 周复盘、本周、这周总结、月复盘、本月、阶段总结 | `period_review` | `customer_reply` 或 `detailed_report` |
| 长期、维持、维护、接下来一个月、习惯巩固 | `long_term_maintenance` | `coach_brief` |
| 写一段、发给客户、回复客户、沟通话术、用户话术 | 保留识别出的 scene | `customer_reply` |
| 列清单、要点、bullet、简短列一下 | 保留识别出的 scene | `bullet_list` |
| 交接、给其他教练、内部备注、转交 | 保留识别出的 scene | `handoff_note` |
| 详细分析、完整报告、展开说 | 保留识别出的 scene | `detailed_report` |

规则原则：

1. 场景识别和风格识别分开打分。
2. 风格词“写给客户/发给客户/话术”优先影响 `output_style`，不直接覆盖 `scene_key`。
3. 如果识别不到场景，默认 `qa_support`。
4. 如果识别不到风格，默认 `coach_brief`。
5. 只从当前 active scenes / styles 中选择；如果对应模板不存在或未启用，就降级到默认值。

### 6.2 P1：LLM 小模型分类

当规则置信度低、多个场景打平、或问题较复杂时，再调用一次轻量分类模型。

触发条件：

1. 最高分低于阈值，例如 `confidence < 0.65`。
2. 最高两个场景分差小于 `0.15`。
3. 输入同时包含多个强场景，例如“做餐评并总结本周血糖”。
4. 教练开启“智能自动选择”并允许增加少量延迟。

分类提示词只输出 JSON：

```json
{
  "scene_key": "meal_review",
  "output_style": "customer_reply",
  "confidence": 0.84,
  "reason": "用户要给客户做餐评，并且要求生成可发送内容",
  "secondary_scene_key": "data_monitoring"
}
```

强规则：

1. LLM 只能从 active scenes / styles 列表中选。
2. JSON 解析失败必须降级到规则结果。
3. 置信度低时不强行切换，保留默认或上次人工选择。
4. 分类调用不应携带完整客户隐私上下文，只需要教练本次问题、候选模板 key/label/description。

### 6.3 P2：基于反馈的路由优化

结合 `docs/CRM_AI_CHAT_RESPONSE_FEEDBACK_PLAN.md` 中的反馈数据，后续可以分析：

1. 哪些自动路由最容易被教练手动覆盖。
2. 哪些 scene/style 组合点踩率高。
3. 哪些关键词导致误判。
4. 是否需要新增场景模板或风格模板。

但反馈只能用于改进路由策略，不能自动改 live prompt。

---

## 7. 自动路由决策对象

建议定义：

`AiIntentRouteDecision`

字段：

| 字段 | 说明 |
|------|------|
| message | 教练本次输入 |
| auto_scene_key | 自动识别的场景 |
| auto_output_style | 自动识别的风格 |
| final_scene_key | 最终使用场景 |
| final_output_style | 最终使用风格 |
| confidence | 置信度 |
| reason | 识别理由 |
| matched_signals | 命中的关键词/规则 |
| route_source | `auto / manual_override / default / fallback` |
| router_version | 路由器版本 |
| available_scenes | 本次可选 active scenes |
| available_styles | 本次可选 active styles |

注意：

1. `auto_*` 是 candidate route。
2. `final_*` 才是本次正式使用的 prompt 分支。
3. `manual_override` 代表教练覆盖，不代表自动识别错误，只代表最终以人工选择为准。

---

## 8. 后端接口设计

### 8.1 预识别接口

建议新增：

`POST /api/v1/crm-customers/{customer_id}/ai/intent-route`

请求：

```json
{
  "message": "我要给用户做一个餐评",
  "current_scene_key": "qa_support",
  "current_output_style": "coach_brief"
}
```

返回：

```json
{
  "auto_scene_key": "meal_review",
  "auto_scene_label": "餐评",
  "auto_output_style": "customer_reply",
  "auto_output_style_label": "客户话术",
  "confidence": 0.91,
  "reason": "命中“餐评”和“给用户”意图，优先使用餐评场景和客户话术风格",
  "matched_signals": ["餐评", "给用户"],
  "route_source": "auto",
  "router_version": "intent-router-v1"
}
```

用途：

1. 前端输入停顿后可预判并更新 UI。
2. 发送前可再次确认。
3. 不调用正式回答模型。

### 8.2 对话请求扩展

建议扩展 `AiChatRequest`：

```json
{
  "message": "我要给用户做一个餐评",
  "scene_key": "meal_review",
  "output_style": "customer_reply",
  "route_decision": {
    "auto_scene_key": "meal_review",
    "auto_output_style": "customer_reply",
    "confidence": 0.91,
    "route_source": "auto",
    "router_version": "intent-router-v1"
  }
}
```

后端不能完全信任前端 route_decision，应在服务端重新计算或校验：

1. scene/style 是否 active。
2. final scene/style 是否允许。
3. route_source 是否合理。
4. 不一致时以后端计算结果为准，并写审计。

### 8.3 审计扩展

建议给 `crm_ai_sessions` 或新增 `crm_ai_route_decisions` 表记录路由信息。

更推荐新增表：

`crm_ai_route_decisions`

原因：

1. 一个 session 内可能多轮对话，每轮意图不同。
2. session 级字段不足以记录每一轮路由。
3. 后续要统计误判率、覆盖率、场景分布，需要 turn-level 数据。

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| session_id | string | 会话 |
| user_message_id | string | 本轮用户消息 |
| assistant_message_id | string, nullable | 对应 AI 回复 |
| crm_customer_id | int | 客户 |
| local_user_id | int | 教练 |
| user_message_snapshot | text | 教练问题快照 |
| auto_scene_key | string | 自动场景 |
| auto_output_style | string | 自动风格 |
| final_scene_key | string | 最终场景 |
| final_output_style | string | 最终风格 |
| confidence | float | 置信度 |
| reason | text | 理由 |
| matched_signals | text/json | 命中信号 |
| route_source | string | auto/manual_override/default/fallback |
| router_version | string | 路由版本 |
| created_at | datetime | 创建时间 |

---

## 9. 前端交互设计

### 9.1 默认体验

输入框附近显示轻量策略条：

```text
智能选择：餐评 / 客户话术
```

交互：

1. 教练输入停顿 300-500ms 后触发预识别。
2. 识别完成后更新策略条。
3. 发送时使用该推荐结果。
4. 如果教练打开“已加载参考信息”侧栏，仍可手动选择。

### 9.2 手动覆盖

当教练手动改场景或风格后：

```text
已手动指定：数据监测 / 详细报告
```

并提供“恢复智能选择”按钮。

状态建议：

1. `auto`：自动识别并应用。
2. `manual`：教练手动指定。
3. `default`：无法识别，使用默认。

### 9.3 低置信度展示

当置信度低时，不要强行制造确定感：

```text
可能是：数据监测 / 教练简报
```

如果置信度很低：

```text
未识别明确场景，按普通答疑处理
```

### 9.4 不要取消手动选择

自动识别上线后，不建议移除手动下拉。

更好的产品形态是：

1. 默认收起高级设置。
2. 自动选择先行。
3. 教练有需要时可以展开并覆盖。
4. 覆盖行为反过来沉淀为路由优化数据。

---

## 10. 场景与风格映射建议

初始推荐映射：

| 教练意图 | scene_key | output_style |
|----------|-----------|--------------|
| 给客户做餐评 | `meal_review` | `customer_reply` |
| 只让 AI 分析这餐问题 | `meal_review` | `coach_brief` |
| 看血糖/体重/睡眠趋势 | `data_monitoring` | `coach_brief` |
| 给客户解释数据变化 | `data_monitoring` | `customer_reply` |
| 处理低血糖/不适/异常 | `abnormal_intervention` | `coach_brief` |
| 给客户写异常安抚话术 | `abnormal_intervention` | `customer_reply` |
| 回答客户一个问题 | `qa_support` | `customer_reply` |
| 教练自己问知识点 | `qa_support` | `coach_brief` |
| 周复盘/月复盘 | `period_review` | `customer_reply` |
| 内部阶段性分析报告 | `period_review` | `detailed_report` |
| 长期维护策略 | `long_term_maintenance` | `coach_brief` |
| 交接给别的教练 | 根据主题判断 | `handoff_note` |
| 要点列表 | 根据主题判断 | `bullet_list` |

规则优先级：

1. 安全风险词优先提高 `abnormal_intervention` 权重。
2. “发给客户 / 回复客户 / 用户话术”优先选择 `customer_reply`。
3. “详细 / 报告 / 展开”优先选择 `detailed_report`。
4. “交接 / 内部备注”优先选择 `handoff_note`。
5. “餐评”强命中 `meal_review`，除非同时出现明确异常风险。

---

## 11. 与现有反馈计划的关系

本计划和 `CRM_AI_CHAT_RESPONSE_FEEDBACK_PLAN.md` 是互补关系：

1. 意图路由决定“本轮应该用哪个 prompt 分支”。
2. 回复格式与反馈计划决定“本轮回答是否好用，并如何沉淀反馈”。
3. 点踩原因里如果出现“场景不对 / 风格不对”，应回流给 intent router。
4. admin 后台后续可以增加“自动路由是否被覆盖”的统计。

建议在反馈表中补充两个字段或关联 route decision：

1. `route_decision_id`
2. `route_mismatch_reason`

这样可以区分：

1. prompt 写得不好。
2. route 选错了。
3. 客户上下文不足。
4. 教练想要的风格与系统推断不同。

---

## 12. 分阶段实施计划

### P0：规则路由 + 自动推荐

目标：不增加模型调用成本，先让系统能自动判断常见意图。

任务：

1. 新增 `intent_router.py`，实现规则词典和打分。
2. 从 `registry.list_scenes()` / `list_styles()` 读取 active 候选，保证只选存在的模板。
3. 新增 `POST /ai/intent-route` 预识别接口。
4. 扩展 `AiChatRequest`，支持 `route_decision` 或 `route_source`。
5. 前端输入停顿后调用预识别接口，显示“智能选择：场景 / 风格”。
6. 发送时默认使用自动识别结果。
7. 保留手动下拉，并支持“恢复智能选择”。

验收：

1. 输入“我要给用户做一个餐评”，自动推荐 `meal_review + customer_reply`。
2. 输入“帮我看看她这周血糖为什么波动”，自动推荐 `data_monitoring + coach_brief`。
3. 输入“帮我写一段回复客户的话”，自动推荐 `qa_support + customer_reply` 或结合主题选择更具体 scene。
4. 手动覆盖后，发送请求使用人工选择。
5. 模板不存在或未启用时，自动降级到 `qa_support + coach_brief`。
6. 后端启动验证通过，前端启动验证通过。

### P1：路由审计 + 误判可复盘

目标：让每轮自动选择可追溯。

任务：

1. 新增 `crm_ai_route_decisions` 表。
2. 每轮写入 auto/final scene/style、置信度、route_source、matched_signals。
3. 历史会话详情返回本轮使用的路由结果。
4. 前端在消息 meta 中展示“本轮使用：餐评 / 客户话术”。
5. admin 反馈复盘页关联 route decision。

验收：

1. 数据库能查到每轮自动识别和最终使用结果。
2. 手动覆盖能记录为 `manual_override`。
3. 后续点踩能定位是否可能是路由问题。

### P2：低置信度 LLM 分类

目标：提升复杂输入识别准确率。

任务：

1. 新增轻量 LLM classifier。
2. 仅在低置信度或多场景冲突时触发。
3. 分类 prompt 只携带候选模板摘要和本次问题，不携带完整客户隐私上下文。
4. JSON 解析失败时降级到规则路由。
5. 增加分类耗时和命中率统计。

验收：

1. 复杂输入能返回更合理的 scene/style。
2. 分类失败不影响正式回答。
3. 额外延迟可控。

### P3：基于反馈持续优化路由

目标：利用真实教练反馈优化规则和模板体系。

任务：

1. 统计自动路由覆盖率。
2. 统计不同 scene/style 组合的点踩率。
3. 汇总高频误判关键词。
4. 为新增模板提供数据依据。
5. 将路由版本与 prompt version 一起纳入效果评估。

验收：

1. admin 能看到“自动识别准确性”趋势。
2. 路由规则变更有版本记录。
3. 路由优化不会自动改 official prompt。

---

## 13. 多线程拆分建议

第一轮建议拆 3 条线：

1. **后端路由器线**
   - 写集：`app/crm_profile/services/intent_router.py`、`app/crm_profile/schemas/api.py`
   - 任务：规则识别、候选模板校验、返回 route decision。

2. **API 与审计线**
   - 写集：`app/crm_profile/router.py` 或后续独立 resource router、`app/schema_migrations.py`、`app/crm_profile/models.py`
   - 任务：新增预识别接口、请求扩展、P1 route decision 表。

3. **前端体验线**
   - 写集：`frontend/src/views/CrmProfile/components/AiCoachPanel.vue`、`frontend/src/views/CrmProfile/composables/useAiCoach.ts`
   - 任务：输入停顿预识别、智能选择提示条、手动覆盖和恢复智能选择。

收口重点：

1. 自动识别结果是否真的进入最终请求。
2. 手动覆盖是否优先于自动识别。
3. 未启用模板是否会被错误选中。
4. route decision 是否能在审计中复盘。

---

## 14. 风险与边界

1. **不要取消人工选择**：自动判断一定会有误判，人工覆盖是必要安全阀。
2. **不要让路由器越权生成回答**：它只选 scene/style，不输出业务建议。
3. **不要把 candidate route 写成 formal truth**：自动识别只是候选，最终使用结果才进入正式回答。
4. **不要每次都强制 LLM 分类**：会增加延迟和成本，P0 应先用规则。
5. **不要携带完整客户上下文做分类**：意图识别只需要本次问题和候选模板，减少隐私暴露和 token 成本。
6. **不要把默认值伪装成智能识别**：无法识别时要明确 `route_source=default` 或 `fallback`。

---

## 15. 面向项目负责人的状态说明

当前阶段：

> AI 教练助手已经有提示词分层，但选择分支仍偏手动；下一步要让系统能先理解教练本次要做什么，再自动进入合适的提示词分支。

已经能做什么：

1. 系统已有餐评、数据监测、异常干预、答疑、复盘、长期维护等场景模板。
2. 系统已有客户话术、教练简报、交接备注、详细报告等风格模板。
3. 教练当前可以手动选择场景和风格。

半能做什么：

1. AI 能根据当前选择生成对应结果，但不能自动判断该选哪个。
2. 配置接口能返回 active 模板，但还没有自动路由逻辑。
3. 前端有选择控件，但还没有“智能推荐 / 手动覆盖”的状态区分。

还不能做什么：

1. 不能根据“我要给用户做餐评”自动选择 `meal_review + customer_reply`。
2. 不能统计自动路由是否准确。
3. 不能区分一条差评到底是 prompt 差，还是路由选错。

当前 blocker：

1. 缺少 `intent_router` 服务。
2. 缺少 route decision 审计对象。
3. 前端发送前没有预识别流程。

下一步最值得做：

1. 先做 P0 规则路由，把常见 80% 意图自动识别起来。
2. 再做 P1 审计，让每次自动选择可复盘。
3. 最后再用 P2 LLM 分类补复杂边界。

---

## 16. 开发完成验证要求

每一阶段完成后必须执行：

1. 后端启动验证：

```powershell
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

2. 前端启动验证：

```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port 5174
```

3. focused validation：

```powershell
python -m py_compile app\crm_profile\services\intent_router.py
python -m py_compile app\crm_profile\services\ai_coach.py
python -m py_compile app\crm_profile\services\prompt_builder.py
npx vue-tsc --noEmit
npm run build
```

4. 手工验收用例：

| 输入 | 期望 scene | 期望 style |
|------|------------|------------|
| 我要给用户做一个餐评 | `meal_review` | `customer_reply` |
| 帮我分析她这周血糖为什么波动 | `data_monitoring` | `coach_brief` |
| 她说今天头晕，我怎么跟进 | `abnormal_intervention` | `customer_reply` |
| 帮我写一段回复客户的话 | `qa_support` 或更具体场景 | `customer_reply` |
| 做一份本周复盘发给她 | `period_review` | `customer_reply` |
| 给接班教练写个交接备注 | 按主题判断 | `handoff_note` |

