# CRM AI 对话回复格式与教练反馈闭环优化计划

> 日期：2026-04-29
>
> 文档状态：plan / candidate design
>
> 适用范围：`CRM 客户档案 + AI 教练助手`
>
> 关联现状：`docs/CRM_AI_PROMPT_ARCHITECTURE_PLAN.md`、`docs/AI_COACH_FRONTEND_RENDERING_OPTIMIZATION_SPEC.md`、`docs/CURRENT_STATUS.md`

---

## 1. 本计划解决什么问题

当前 AI 教练助手已经具备客户级对话、提示词分层、客户专属补充信息、Markdown 渲染和历史会话能力，但还缺少三类关键闭环：

1. **回复格式闭环**：无论教练问什么场景，AI 都必须给出一段可直接转给客户的沟通话术，并且这段话术要稳定包在 `txt` 代码块里，方便前端渲染成独立可复制区域。
2. **教练反馈闭环**：AI 回复下方不能只有复制按钮，还需要点赞、点踩、重新生成、追问等操作；点踩时必须收集原因和教练心中的标准作答。
3. **后台复盘闭环**：admin 账号需要能看到“教练问题 - AI 初答复 - 教练反馈 - 教练标准作答”，后续用于优化提示词架构。

这次不是单纯加几个按钮，而是要把“AI 生成结果是否符合教练预期”沉淀成可查询、可复盘、可迭代的数据资产。

---

## 2. 当前真实现状

结合当前仓库代码，已有 official 能力是：

1. 后端 AI 主编排在 `app/crm_profile/services/ai_coach.py`。
2. 提示词已经拆到 `app/crm_profile/prompts/`，由 `app/crm_profile/services/prompt_builder.py` 做分层拼装。
3. `customer_reply` 输出风格已存在，位于 `app/crm_profile/prompts/styles/customer_reply.md`。
4. AI 审计表已存在：
   - `crm_ai_sessions`
   - `crm_ai_messages`
   - `crm_ai_context_snapshots`
   - `crm_ai_guardrail_events`
5. 前端 AI 消息已拆出 `AiCoachAssistantMessage.vue`、`AiCoachMessageList.vue`，并已接入 `MarkdownRenderer`。
6. 当前 assistant 消息下方已有复制按钮和“标记需医生确认”按钮。
7. 当前还没有 AI 消息点赞 / 点踩 / 反馈原因 / 标准作答 / 重新生成 / 引用追问的正式数据模型和后台页面。

不能写成 official 的能力：

1. 不能保证所有 AI 回复都包含客户沟通话术。
2. 不能保证客户沟通话术一定被包进 ` ```txt ... ``` `。
3. 不能在 admin 后台集中查看教练反馈。
4. 不能把点踩原因自动沉淀为提示词优化依据。

---

## 3. 产品目标

### 3.1 回复必须包含客户沟通话术

无论当前场景是餐评、数据监测、异常干预、问题答疑、周期复盘、长期维护，AI 正式回复都必须包含一段教练可二次编辑后转给客户的沟通话术。

建议统一输出契约：

````markdown
## 给教练的判断

...

## 可发送给客户的话术

```txt
张姐，看了您最近的数据，晚餐后的血糖波动比前两天稳了一些，说明您这两天主食量和进食顺序控制得不错。今晚可以继续先吃蔬菜和蛋白质，米饭保持半碗左右，饭后散步 10 分钟就很好。我们先把这个节奏稳住，明天再一起看数据变化。
```

## 下一步建议

...
````

强规则：

1. 代码块语言必须使用 `txt`。
2. 代码块内只放可发给客户的话术，不混入内部分析、风险标签、引用来源、token 信息。
3. 若涉及医疗风险，话术也必须温和提醒“遵循医生建议 / 需要医生确认”，不能给处方级结论。
4. 如果信息不足，也要给出保守可用话术，例如“我这边还需要再看一下您今天的具体饮食和餐后数据，先不急着调整方案”。
5. 事实直读类快捷回答也要遵守该输出契约，不能再只返回一句“当前客户叫 XX”。

### 3.2 AI 回复下方的动作区

每条 AI 正式回复下方建议提供这些操作：

1. `复制`：复制整条 AI 回复或复制客户话术代码块，优先支持代码块内单独复制。
2. `喜欢`：记录本条回答对教练有帮助。
3. `不喜欢`：弹出反馈弹窗，收集不满意原因和更好的标准作答。
4. `重新生成`：基于同一条教练问题、同一客户上下文、同一场景重新生成新回答。
5. `追问`：引用当前 AI 回复作为上下文，继续对话。

点踩弹窗建议字段：

1. `不满意原因`：多行文本，必填。
2. `更好的答复应该是什么样`：多行文本，必填，作为教练标准作答候选。
3. `问题类型`：可选枚举，便于 admin 统计。
   - 事实不准
   - 话术不好用
   - 太空泛
   - 不够温和
   - 医疗边界不稳
   - 没结合客户数据
   - 输出格式不对
   - 其他

### 3.3 admin 后台可复盘

admin 需要能看到一个 AI 反馈复盘页面，至少包含：

1. 教练原问题
2. AI 初答复
3. AI 生成的客户话术代码块
4. 教练点赞 / 点踩
5. 点踩原因
6. 教练标准作答
7. 客户、教练、场景、输出模式、模型、prompt version、生成时间
8. 管理员处理状态

建议页面名：

`AI 反馈复盘`

建议路径：

`/ai-feedback`

后台结论口径：

1. 教练反馈是 `official feedback record`。
2. 教练标准作答是 `candidate answer`，不能自动成为 formal prompt。
3. 后续提示词调整必须经过人工 review、测试和版本发布，不能把单条反馈直接写成 live truth。

---

## 4. 数据模型设计

### 4.1 新增表：crm_ai_message_feedback

建议新增 ORM 模型：

`CrmAiMessageFeedback`

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| feedback_id | string(64) | 对外稳定 ID |
| session_id | string(64) | 关联 AI 会话 |
| message_id | string(64) | 被反馈的 assistant message |
| user_message_id | string(64), nullable | 对应的教练问题 message |
| crm_customer_id | int | 客户 ID |
| coach_user_id | int | 提交反馈的本地用户 ID |
| crm_admin_id | int, nullable | CRM admin ID |
| rating | string(16) | `like / dislike` |
| reason_category | string(64), nullable | 不满意类型 |
| reason_text | text, nullable | 不满意原因 |
| expected_answer | text, nullable | 教练标准作答 |
| user_question_snapshot | text | 教练原问题快照 |
| ai_answer_snapshot | text | AI 初答复快照 |
| customer_reply_snapshot | text, nullable | 从 `txt` 代码块提取的话术快照 |
| scene_key | string(32), nullable | 场景 |
| output_style | string(32), nullable | 输出模式 |
| prompt_version | string(16), nullable | prompt 版本 |
| prompt_hash | string(128), nullable | prompt hash |
| model | string(64), nullable | 模型 |
| status | string(24) | `new / reviewed / used_for_prompt / ignored` |
| admin_note | text, nullable | 管理员处理备注 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

建模原则：

1. 既关联 `crm_ai_messages`，也冗余保存问题和回答快照，避免后续消息变更或清理后反馈失去语义。
2. 点赞和点踩都进同一张表，便于统计满意度。
3. 一条 assistant message 对同一 coach 原则上只保留一条最新反馈；再次点击可更新。
4. `expected_answer` 是教练候选标准作答，不自动替换 AI 回复，也不自动进入 prompt。

### 4.2 不建议直接复用 guardrail 表

`crm_ai_guardrail_events` 适合记录安全门禁事件，不适合记录教练主观质量反馈。反馈数据应该是独立业务对象，否则后续统计满意度、筛选场景、提炼 prompt 样本都会变得混乱。

---

## 5. 后端接口设计

### 5.1 提交或更新反馈

`POST /api/v1/crm-customers/{customer_id}/ai/messages/{message_id}/feedback`

请求体：

```json
{
  "rating": "dislike",
  "reason_category": "话术不好用",
  "reason_text": "语气太像报告，不像教练发给客户的话",
  "expected_answer": "张姐，今天晚餐整体搭配比昨天清爽很多，青菜和蛋白质都有照顾到..."
}
```

返回：

```json
{
  "feedback_id": "fb_xxx",
  "message_id": "msg_xxx",
  "rating": "dislike",
  "status": "new",
  "created_at": "2026-04-29T23:40:00"
}
```

规则：

1. `like` 可以不填原因。
2. `dislike` 必须填写 `reason_text` 和 `expected_answer`。
3. 后端根据 `message_id` 回查 session、客户、上一条 user message、prompt version、模型等信息并写入快照。
4. 如果 assistant message 不属于当前客户，返回 404 或权限错误。

### 5.2 查询当前消息反馈状态

AI 会话详情和消息列表返回时，应把当前用户对每条 assistant message 的反馈状态带回前端：

```json
{
  "message_id": "msg_xxx",
  "role": "assistant",
  "content": "...",
  "feedback": {
    "rating": "like",
    "feedback_id": "fb_xxx"
  }
}
```

### 5.3 重新生成

建议新增：

`POST /api/v1/crm-customers/{customer_id}/ai/messages/{message_id}/regenerate`

职责：

1. 找到该 assistant message 对应的上一条 user message。
2. 使用同一 session、scene_key、output_style、selected_expansions、health_window_days 重新生成。
3. 不删除旧回答，生成一条新的 assistant message。
4. 新回答记录 `regenerated_from_message_id`，便于 admin 对比。

P0 可先由前端复用现有 `sendChat()`，但正式方案建议后端提供 regenerate endpoint，避免前端猜测上一条 user message。

### 5.4 引用追问

建议扩展 `AiChatRequest`：

```json
{
  "message": "基于刚才这条回复，帮我改得更温和一点",
  "quoted_message_id": "msg_xxx"
}
```

后端拼装时：

1. 校验 `quoted_message_id` 属于同一客户和同一会话。
2. 将被引用 assistant message 作为“本次追问引用内容”加入 user message 或单独 system/user context。
3. 不把引用内容写成 official 客户档案，只作为本轮对话上下文。

---

## 6. Prompt 与输出契约设计

### 6.1 平台底线层新增规则

建议在 `app/crm_profile/prompts/base/platform_guardrails.md` 或更适合的输出规范 prompt 中追加：

```text
无论当前问题属于哪个场景，你的正式回复都必须包含一段“可发送给客户的话术”。
这段话术必须放在 Markdown fenced code block 中，语言标记必须是 txt。
代码块中只能包含教练可转发给客户的自然语言话术，不得包含内部分析、Markdown 标题、风险标签、来源说明或 token 信息。
```

### 6.2 customer_reply 风格增强

`app/crm_profile/prompts/styles/customer_reply.md` 已经定义了客户话术质量标准。建议增强为：

1. 当输出模式为 `customer_reply` 时，主输出可以更短，但仍必须使用 ` ```txt ... ``` ` 包裹最终话术。
2. 当输出模式不是 `customer_reply` 时，也必须额外给出“可发送给客户的话术”代码块。
3. 代码块内话术建议 80-200 字，特殊复杂场景可放宽到 300 字。

### 6.3 后端兜底校验

只靠 prompt 约束不够，建议新增轻量后处理：

1. 在 AI 完成后检测是否存在 ` ```txt ... ``` `。
2. 如果不存在，先不要把这条结果标记为格式合格。
3. P0 可追加一个兜底代码块，把模型回答中最像客户话术的段落包入 `txt`。
4. P1 建议增加一次低成本修复调用或本地规则修复，让输出格式稳定。

注意：

1. 兜底修复只能改变展示格式，不能伪造新的健康建议。
2. 如果原回答完全没有客户话术，应在后台记录 `output_contract_violation`，供 prompt 优化复盘。

---

## 7. 前端交互设计

### 7.1 AI 消息动作区

`AiCoachAssistantMessage.vue` 的动作区建议从文字按钮升级为图标按钮组：

1. 复制：`CopyDocument`
2. 喜欢：`CaretTop` 或引入更合适的点赞图标
3. 不喜欢：`CaretBottom`
4. 重新生成：`RefreshRight`
5. 追问：`ChatLineRound`

交互要求：

1. 每个图标按钮都有 tooltip。
2. 点赞后按钮进入 active 状态。
3. 点踩后弹出反馈弹窗，提交成功后点踩按钮进入 active 状态。
4. 已反馈后允许改选，但要覆盖更新同一条反馈记录。
5. `requiresMedicalReview` 不隐藏反馈按钮；教练仍可反馈“医疗边界不稳”。

### 7.2 客户话术代码块

当前已有 `MarkdownRenderer`，应让 `txt` 代码块渲染成独立区域：

1. 顶部显示 `txt` 或 `客户话术`。
2. 右上角提供复制按钮。
3. 内容区域保留纯文本换行，不渲染为富文本。
4. 长话术可提供展开 / 收起或横向滚动，但默认不要撑破 AI 抽屉。

如果后续使用自定义 fence，也可以引入：

````markdown
```customer-reply
...
```
````

但 P0 优先遵守用户明确要求的 `txt` 代码块，不把 `customer-reply` fence 写成 official。

### 7.3 点踩反馈弹窗

建议新增组件：

`frontend/src/views/CrmProfile/components/AiCoachFeedbackDialog.vue`

职责：

1. 展示当前教练问题摘要。
2. 展示 AI 初答复摘要。
3. 收集不满意原因。
4. 收集标准作答。
5. 提交到 feedback endpoint。

### 7.4 追问

点击追问后：

1. 输入框聚焦。
2. 输入框上方出现引用条，显示“正在追问这条 AI 回复”。
3. 用户输入补充问题后发送。
4. 请求体携带 `quoted_message_id`。
5. 引用条可取消。

不要把整条 AI 回复直接塞进输入框，避免污染教练本次问题。

---

## 8. Admin 复盘页面

建议新增页面：

`frontend/src/views/AiFeedback/index.vue`

建议新增后端资源路由：

`app/routers/api/ai_feedback.py`

如果当前路由结构暂不方便，也可以先放在 CRM Profile router 中，但正式方向应按资源拆分，避免继续堆大路由。

页面能力：

1. 筛选：时间、教练、客户、场景、输出模式、rating、reason_category、status。
2. 列表：客户、教练、问题摘要、反馈类型、原因类型、时间、处理状态。
3. 详情抽屉：
   - 教练原问题
   - AI 初答复
   - 客户话术代码块
   - 教练反馈原因
   - 教练标准作答
   - prompt version / prompt hash / model
   - 管理员备注
4. 处理动作：
   - 标记已查看
   - 标记已用于提示词优化
   - 标记忽略
   - 写 admin note

权限：

1. admin 可查看全部反馈。
2. coach 只可提交反馈，默认不进入全局复盘页。
3. 如后续需要教练查看自己的反馈历史，可另开个人视图。

---

## 9. 分阶段实施计划

### P0：先打通输出契约和反馈记录

目标：教练能看到稳定的客户话术代码块，并能对每条 AI 回复点赞 / 点踩。

任务：

1. Prompt 层加入“必须输出 `txt` 代码块话术”的规则。
2. 后端新增 `CrmAiMessageFeedback` 模型、schema、迁移保障和 feedback service。
3. 新增 `POST message feedback` 接口。
4. 前端 `AiCoachAssistantMessage.vue` 增加点赞 / 点踩图标按钮。
5. 新增点踩反馈弹窗，提交原因和标准作答。
6. 会话恢复时带回当前用户 feedback 状态。

验收：

1. 任意场景 AI 回复都包含 ` ```txt ... ``` `。
2. `txt` 代码块可独立复制。
3. 点赞能落库。
4. 点踩必须填写原因和标准作答后才能提交。
5. 数据库能查到“教练问题 - AI 初答复 - 教练反馈”。
6. 后端启动验证通过，前端启动验证通过。

### P1：补重新生成和追问

目标：教练能围绕不满意回答继续快速修正。

任务：

1. 新增 regenerate endpoint 或稳定复用 sendChat 方案。
2. 新增 `quoted_message_id` 请求字段。
3. 前端增加重新生成按钮。
4. 前端增加追问引用条。
5. 审计中记录新回答与旧回答的关系。

验收：

1. 重新生成不删除旧回答。
2. 新回答能追溯到被重新生成的原 message。
3. 追问不会把引用内容污染到输入框正文。
4. 后端能校验 quoted message 权限和归属。

### P2：admin 反馈复盘

目标：admin 能集中看反馈，开始支持提示词优化工作流。

任务：

1. 新增 admin feedback list/detail API。
2. 新增 `AI 反馈复盘` 页面。
3. 支持筛选、详情抽屉、处理状态、admin note。
4. 增加反馈统计：点踩率、场景分布、原因分布、prompt version 分布。

验收：

1. admin 能看到所有反馈。
2. 详情里能完整看到教练问题、AI 初答复、客户话术、反馈原因和标准作答。
3. 标记状态后可持久化。
4. coach 无权查看全局反馈列表。

### P3：提示词优化闭环

目标：把反馈数据转成提示词迭代依据，但不自动改 live prompt。

任务：

1. 按场景汇总高频差评原因。
2. 从 `expected_answer` 中提炼候选样例。
3. 建立 prompt 变更记录，关联使用了哪些反馈样本。
4. 支持 prompt version 前后反馈率对比。

验收：

1. 单条反馈不会自动进入 official prompt。
2. prompt 变更能追溯使用的 feedback_id。
3. 新 prompt 发布后能对比满意度变化。

---

## 10. 多线程拆分建议

第一轮建议控制在 3 条执行线：

1. **输出契约线**
   - 负责 prompt 修改、`txt` 代码块要求、后端格式检测与兜底。
   - 写集：`app/crm_profile/prompts/`、`app/crm_profile/services/ai_coach.py` 或独立 output contract service。

2. **反馈数据线**
   - 负责模型、schema、service、API、迁移保障。
   - 写集：`app/crm_profile/models.py`、`app/crm_profile/schemas/api.py`、`app/crm_profile/services/audit.py` 或新增 `feedback.py`、`app/schema_migrations.py`、相关 router。

3. **前端交互线**
   - 负责消息按钮、反馈弹窗、反馈状态展示、代码块复制体验。
   - 写集：`frontend/src/views/CrmProfile/components/`、`frontend/src/views/CrmProfile/composables/useAiCoach.ts`、必要的 markdown code block 组件。

收口时必须统一检查：

1. 是否所有场景输出都满足 `txt` 代码块契约。
2. 点踩反馈是否正确绑定到对应 assistant message 和上一条 user message。
3. 是否把教练标准作答误写成 official prompt。
4. 后端和前端是否都能启动。

---

## 11. 风险与边界

1. **只靠 prompt 不稳定**：必须有后端格式检测，否则模型偶发不输出代码块时前端无法保证体验。
2. **反馈不是事实真值**：教练反馈代表使用体验和候选标准作答，不等于客户健康事实。
3. **点踩不等于模型错误**：可能是语气、场景、数据缺口、教练偏好导致，需要 admin 分类复盘。
4. **重新生成不要覆盖历史**：旧回答要保留，才能比较哪版更好。
5. **追问引用不是客户档案**：引用上下文只服务本轮对话，不写入 profile note 或 CRM 主数据。
6. **医疗边界仍最高优先级**：即使教练标准作答写得更激进，也不能绕过医疗安全红线。

---

## 12. 面向项目负责人的当前阶段判断

当前阶段：

> 已具备 AI 教练对话底座，正在从“能回答”升级到“可复制、可反馈、可优化”。

已经能做什么：

1. AI 能读取客户档案并回答教练问题。
2. AI 已支持场景和输出模式。
3. 前端已经能渲染 Markdown，并展示 AI 消息动作区。
4. 客户专属补充信息已经有入口。

半能做什么：

1. 能生成客户话术，但还不能保证每次都以 `txt` 代码块独立呈现。
2. 能复制整条回复，但还没有完整的“复制话术块 + 点赞点踩 + 追问”工作流。
3. 有 AI 审计表，但还没有教练质量反馈表。

还不能做什么：

1. admin 还不能集中查看教练对 AI 答复的反馈。
2. 还不能按场景统计哪些 AI 回复最不符合教练预期。
3. 还不能把反馈样本和 prompt 版本迭代关联起来。

当前 blocker：

1. 缺少 `CrmAiMessageFeedback` 这类正式反馈对象。
2. 当前输出契约还没有后端兜底检测。
3. 前端消息动作区还没有反馈弹窗和引用追问状态。

下一步最值得推进：

1. 先做 P0：`txt` 话术代码块契约 + 点赞点踩落库。
2. 再做 P1：重新生成和追问。
3. 最后做 P2：admin 反馈复盘后台。

---

## 13. 开发完成验证要求

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
python -m py_compile app\crm_profile\services\ai_coach.py
python -m py_compile app\crm_profile\services\prompt_builder.py
python -m py_compile app\crm_profile\models.py
npx vue-tsc --noEmit
npm run build
```

4. 手工验收：

1. 餐评场景输出包含 `txt` 代码块话术。
2. 问题答疑场景输出包含 `txt` 代码块话术。
3. 数据监测场景输出包含 `txt` 代码块话术。
4. 点赞刷新后状态仍保留。
5. 点踩不填原因无法提交。
6. admin 能看到该反馈记录。

