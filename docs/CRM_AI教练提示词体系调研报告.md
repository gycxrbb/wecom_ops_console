# CRM AI 教练提示词体系调研报告

> 调研日期：2026-04-28

## 概览

AI 教练助手采用 **5 层提示词 + 运行时输入** 的分层架构。最终发送给模型的 `messages` 数组由 3 条消息组成：

```
messages[0] = system  →  L1 平台底线 + L2 核心角色 + L3 场景策略
messages[1] = system  →  L4 客户上下文 + L4.5 RAG 参考 + L5 教练补充
messages[2] = user    →  L6 用户提问 + 输出风格提示
```

---

## 各层详细说明

### L1：平台底线（Platform Guardrails）

| 项目 | 说明 |
|------|------|
| 文件 | `app/crm_profile/prompts/base/platform_guardrails.md` |
| 加载 | `registry.py` → `get_platform_guardrails()`（LRU 缓存） |
| 状态 | **生效** — 每次对话必定包含 |

核心内容（9 条规则）：
1. 服务对象是教练，不是客户
2. 不诊断、不开药、不停药
3. 药物/异常指标必须提醒遵循医生意见
4. 优先尊重客户过敏、禁忌、损伤、风险信息
5. 信息不足必须指出，不允许编造
6. 输出是工作草稿，不是医疗结论
7. 代词默认指当前客户
8. 只有用户明确问 AI 身份时才介绍自己
9. 不在回答中反复提醒缺失字段

### L2：健康教练核心角色（Health Coach Core）

| 项目 | 说明 |
|------|------|
| 文件 | `app/crm_profile/prompts/base/health_coach_core.md` |
| 加载 | `registry.py` → `get_health_coach_core()`（LRU 缓存） |
| 状态 | **生效** — 每次对话必定包含 |

核心内容：
- **职责**：帮教练理解客户状态、生成餐评/跟进/异常提醒/复盘/维护建议、把数据翻译成可执行话术
- **分析原则**：先安全边界 → 再目标匹配 → 再执行可行性；先结论 → 再依据 → 再建议
- **输出风格**：专业、清晰、温和、结论优先、可执行

### L3：场景策略（Scene Strategy）

| 项目 | 说明 |
|------|------|
| 文件目录 | `app/crm_profile/prompts/scenes/` |
| 加载 | `registry.py` → `get_scene_prompt(scene_key)` |
| 状态 | **生效** — 根据 `scene_key` 条件加载，默认 `qa_support` |

共 6 个场景文件：

| 文件 | scene_key | 场景名 |
|------|-----------|--------|
| `meal_review.md` | `meal_review` | 餐评 |
| `data_monitoring.md` | `data_monitoring` | 数据监测 |
| `abnormal_intervention.md` | `abnormal_intervention` | 异常干预 |
| `qa_support.md` | `qa_support` | 问题答疑（默认） |
| `period_review.md` | `period_review` | 周月复盘 |
| `long_term_maintenance.md` | `long_term_maintenance` | 长期维护 |

每个场景文件包含：当前场景名称、核心关注维度、输出要求。

**合并方式**：L1 + L2 + L3 用双换行拼接，构成 `messages[0]` 的 content。

---

### L4：客户上下文（Customer Context）

| 项目 | 说明 |
|------|------|
| 构建文件 | `app/crm_profile/services/context_builder.py` |
| 缓存文件 | `app/crm_profile/services/profile_context_cache.py` |
| 数据来源 | `services/modules/` 下 13 个模块加载器 |
| 状态 | **生效** — 构成 `messages[1]` 的主体 |

加载的 13 个数据模块：

| 模块名 | 中文说明 |
|--------|----------|
| `basic_profile` | 基础档案（姓名、年龄、性别等） |
| `safety_profile` | 安全档案（过敏、禁忌、运动损伤等） |
| `goals_preferences` | 目标与偏好 |
| `health_summary_7d` | 近 7 天健康摘要 |
| `health_summary_14d` | 近 14 天健康摘要 |
| `health_summary_30d` | 近 30 天健康摘要 |
| `body_comp_latest_30d` | 近 30 天体成分 |
| `points_engagement_14d` | 近 14 天积分活跃度 |
| `service_scope` | 服务范围 |
| `habit_adherence_14d` | 近 14 天习惯执行 |
| `plan_progress_14d` | 近 14 天计划进度 |
| `reminder_adherence_14d` | 近 14 天提醒执行 |
| `learning_engagement_30d` | 近 30 天学习参与 |
| `ai_decision_labels` | AI 决策标签 |
| `service_issues` | 用户阻碍（含详情摘要） |

上下文头部注入了代词消歧指令：

```
当前客户的真实姓名是：{customer_name}。
若用户使用"你"来提问，除非明确说明是在问 AI，
自然语言里的"你"默认指当前客户「{customer_name}」。
```

有 token 预算控制（默认 30,000），超限时截断后面的模块。

### L4.5：RAG 话术与知识库参考（可选）

| 项目 | 说明 |
|------|------|
| 检索逻辑 | `app/rag/retriever.py` → phase 1 搜索话术/知识卡 |
| 注入位置 | `prompt_builder.py` 第 107-116 行，追加到 L4 上下文尾部 |
| 状态 | **生效** — `settings.rag_enabled=True` 时注入 |

注入时附带说明：
```
【公司话术与知识库参考】
- 以下内容来自内部话术库/知识库，是辅助参考，不等于客户档案事实。
- 回答时优先结合客户档案和安全档案。
- 可借鉴话术风格，但不要机械照抄。
- 医疗敏感内容只做风险提醒，不做诊断。
```

RAG phase 2 检索的素材不会注入 prompt，只通过 `recommended_assets` 推送到前端展示。

---

### L5：教练补充的客户专属信息（Profile Note）

| 项目 | 说明 |
|------|------|
| DB 模型 | `app/crm_profile/models.py` → `CustomerAiProfileNote` |
| API | `GET/PUT /api/v1/crm-customers/{id}/ai/profile-note` |
| 构建函数 | `prompt_builder.py` → `build_profile_note_text()` |
| 状态 | **生效** — 有内容时追加到 `messages[1]` 尾部 |

包含 5 个文本字段：

| 字段 | 中文标签 |
|------|----------|
| `communication_style_note` | 沟通风格补充 |
| `current_focus_note` | 当前阶段重点 |
| `execution_barrier_note` | 执行障碍 |
| `lifestyle_background_note` | 作息/家庭/工作背景 |
| `coach_strategy_note` | 教练内部策略备注 |

有一个字段 `preferred_scene_hint`（首选场景提示）存了但 **不注入 prompt**，仅作为前端下拉框的默认选中值返回。

---

### L6：用户提问 + 输出风格提示

| 项目 | 说明 |
|------|------|
| 组装位置 | `prompt_builder.py` 第 124-128 行 |
| 状态 | **生效** — 构成 `messages[2]` |

输出风格选项（5 种）：

| style_key | 提示文本 |
|-----------|----------|
| `coach_brief` | 输出格式：简洁教练简报，结论优先。 |
| `customer_reply` | 输出格式：直接发给客户的话术草稿，语气亲切自然。 |
| `handoff_note` | 输出格式：交接备注，结构化分点。 |
| `bullet_list` | 输出格式：要点列表。 |
| `detailed_report` | 输出格式：详细分析报告，结构化分节，充分展开所有分析和建议。 |

用户消息和风格提示用双换行拼接：`user_message + "\n\n" + style_hint`。

---

## 旁路：可见思考（Visible Thinking）

用于前端"思考过程"面板的独立 prompt 组装，与主 prompt 并行。

| 项目 | 说明 |
|------|------|
| 文件 | `prompts/base/visible_thinking_core.md` |
| 组装函数 | `prompt_builder.py` → `assemble_visible_thinking_prompt()` |
| 状态 | **生效** — DeepSeek thinking-stream 模式下使用 |

差异：
- 用 `visible_thinking_core.md` 替代 `health_coach_core.md`
- 用户消息追加"请输出给界面展示的简短思考摘要"
- 无输出风格提示
- temperature 0.4（主 prompt 是 0.7），max_tokens 4096（主 prompt 是 15000）

---

## 旁路：快捷直答

| 项目 | 说明 |
|------|------|
| 文件 | `app/crm_profile/services/ai_coach.py` 第 31-87 行 |
| 状态 | **生效** — 匹配到简单事实问题时绕过所有 AI 调用 |

对"叫什么名字""几岁""性别""客户状态""负责教练""所属群"等简单问题，直接从已加载档案返回答案，不走任何提示词层。

---

## 组装流程代码追踪

```
ai_coach.py: _prepare_ai_turn_async()
  ├─ profile_context_cache.py → 读取/构建客户档案（L4 数据）
  ├─ rag/retriever.py → RAG 检索话术 + 素材（L4.5）
  ├─ _load_profile_note() → 读取教练补充（L5）
  └─ prompt_builder.py: assemble_prompt()
       ├─ L1: get_platform_guardrails()
       ├─ L2: get_health_coach_core()
       ├─ L3: get_scene_prompt(scene_key)
       ├─ L4: context_text (客户上下文)
       ├─ L4.5: rag_context_text (RAG 参考)
       ├─ L5: build_profile_note_text(profile_note)
       └─ L6: user_message + style_hint
       → 输出 messages 数组

ai_coach.py: _compose_ai_messages()
  ├─ 插入 messages[0] (system: L1+L2+L3)
  ├─ 插入 messages[1] (system: L4+L4.5+L5)
  ├─ 插入历史对话 (如有 reuse_session)
  └─ 插入 messages[N] (user: L6)
  → 传入 ai_chat_client.py → OpenAI/DeepSeek API
```

---

## 关键文件索引

| 文件 | 职责 |
|------|------|
| `app/crm_profile/prompts/base/platform_guardrails.md` | L1 平台底线提示词 |
| `app/crm_profile/prompts/base/health_coach_core.md` | L2 核心角色提示词 |
| `app/crm_profile/prompts/base/visible_thinking_core.md` | 可见思考提示词 |
| `app/crm_profile/prompts/scenes/*.md` | L3 场景策略（6 个） |
| `app/crm_profile/prompts/registry.py` | 提示词加载与缓存 |
| `app/crm_profile/services/prompt_builder.py` | 提示词组装核心逻辑 |
| `app/crm_profile/services/context_builder.py` | L4 客户上下文构建 |
| `app/crm_profile/services/profile_context_cache.py` | L4 上下文缓存（L1/L2/DB） |
| `app/crm_profile/services/ai_coach.py` | AI 教练服务主入口 |
| `app/crm_profile/models.py` | CustomerAiProfileNote（L5 DB 模型） |
| `app/rag/retriever.py` | L4.5 RAG 检索 |

---

## 发现的问题

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| 1 | `preferred_scene_hint` 存而不用 | 低 | 该字段仅作为前端下拉默认值，不注入 prompt，属于 UI 逻辑而非 prompt 内容，设计合理但需确认 |
| 2 | `exeplanation.md` 拼写错误 | 低 | 文件名应为 `explanation.md`，且该文件是文档不会被代码引用 |
| 3 | 快捷直答绕过全部提示词 | 信息 | 对简单事实问题不走 AI 调用，属于优化行为但教练可能不理解为何某些回答风格不受提示词控制 |
