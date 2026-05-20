# AI 对话可视化置信度语义路由方案

> 日期：2026-05-19  
> 关联文档：`docs/AI对话多模态Agent化总体开发文档.md`  
> 适用范围：AI 对话中的 Visual Intent Router，即“什么时候需要生成可视化知识卡片，以及高置信自动生成 / 低置信人工确认 / 不生成”的判断链路。

---

## 1. 方案结论

置信度判断不应长期依赖关键词穷举。

关键词规则可以作为 MVP 兜底，也可以承担安全硬门禁，但不适合作为正式的可视化意图判断方式。正式方案应采用：

```text
规则硬门禁
  ↓
小模型语义判断
  ↓
RAG / 素材库 / Profile / 安全信号补充
  ↓
代码侧综合评分
  ↓
高置信自动生成 / 低置信人工确认 / 不生成
```

核心原则：

1. 小模型负责判断语义价值，不负责最终拍板。
2. 代码侧负责综合评分、阈值分流和安全收口。
3. 安全、隐私、医疗高风险、库存素材复用必须由确定性规则控制。
4. LLM 输出是 `support signal`，不是 `official truth`。
5. 最终 `VisualDecision` 才是系统内的正式决策结果。

---

## 2. 背景与问题

总体文档中已经定义了三档分流：

| 分流 | 条件 | 系统动作 |
| --- | --- | --- |
| 高置信自动生成 | 可视化价值明确、证据充分、安全等级低、无高质量库存素材替代 | 自动创建异步 visual job |
| 低置信人工确认 | 是否值得画图不确定、主题表达不清、已有素材与新图价值接近、或轻度安全敏感 | 返回 `visual_confirm_required` |
| 不生成 | 医疗高风险、客户隐私、事实查询、个体化药物/诊断、视觉价值不足 | 不创建 job |

当前代码中已有 MVP 版 `app/ai_visual/services/decision.py`，主要依赖关键词、scene、RAG 分数和安全规则计算 `confidence`。这能跑通链路，但存在天然上限：

1. 用户表达方式不可穷举，关键词会越补越多。
2. “是否适合画成知识卡”本质是语义判断，不是词表匹配。
3. 同一个词在不同上下文中含义不同，关键词容易误触发。
4. 很多高价值表达并不包含显式关键词，例如“这个怎么讲更直观”“有没有适合发群的版本”。
5. 关键词无法稳定判断主题清晰度、可执行性、图片相对文本的增益。

因此，关键词规则只能作为 `support / fallback`，不能作为长期 `official` 判断方式。

---

## 3. 置信度的准确定义

这里的 `confidence` 不是“AI 回答正确率”，也不是“医学事实可靠度”。

它表示：

> 系统对“当前问题适合生成可视化知识卡，并且可以进入对应自动化程度”的把握程度。

置信度应由以下因素共同决定：

| 因素 | 含义 | 来源 |
| --- | --- | --- |
| 可视化价值 | 图片是否比纯文本更容易理解、保存、转发 | 小模型语义判断 |
| 主题清晰度 | 是否能形成明确卡片主题 | 小模型语义判断 |
| 可执行性 | 是否适合做成步骤、清单、对比、餐盘、风险信号等结构 | 小模型语义判断 |
| 证据强度 | RAG 是否召回 formal knowledge/material，分数是否足够 | RAG |
| 场景匹配 | 当前 scene 是否适合生成对外知识卡 | 业务上下文 |
| 安全等级 | 是否涉及医疗敏感、个体化诊断、药物剂量、隐私 | 规则 + 安全模型 |
| 库存素材命中 | 是否已有高质量素材可复用 | 素材库检索 |
| 历史反馈 | 教练确认率、发送率、点踩原因 | 反馈闭环 |

---

## 4. 小模型的职责边界

### 4.1 小模型应该做什么

小模型适合承担 Visual Router 的语义理解部分：

1. 判断用户问题是否具有可视化价值。
2. 判断主题是否清晰，能否形成一张卡片。
3. 判断更适合哪类视觉表达：
   - 健康教育卡
   - 饮食选择清单
   - 行为步骤图
   - 风险信号科普
   - 复盘强化卡
   - 不适合图片
4. 判断图片相对文本回答是否有明显增益。
5. 生成短 topic 和 reason，便于前端展示和审计。
6. 标记可能的轻度敏感点，供代码侧进一步降权或人工确认。

### 4.2 小模型不应该做什么

小模型不应承担以下最终决策：

1. 不直接决定是否自动生图。
2. 不绕过安全硬门禁。
3. 不判断医疗高风险内容是否允许发送。
4. 不把 RAG 召回证据升级为 formal truth。
5. 不把 candidate visual asset 判定为 sendable。
6. 不负责库存素材是否复用的最终选择。

一句话：小模型给 `support signal`，代码产出 `official decision`。

---

## 5. 推荐技术架构

### 5.1 模块拆分

建议将当前 `app/ai_visual/services/decision.py` 演进为以下结构：

```text
app/ai_visual/services/
├── decision.py              # 总入口：编排规则、小模型、评分、输出 VisualDecision
├── decision_rules.py        # 硬门禁与确定性规则
├── llm_judge.py             # 小模型语义判断
├── scoring.py               # 综合评分与阈值分流
├── visual_safety.py         # 现有安全判断，可继续保留
└── audit.py                 # 记录 factors、模型输出、最终决策
```

职责边界：

| 文件 | 职责 | 禁止 |
| --- | --- | --- |
| `decision.py` | 对外提供 `assess_visual_need`，输出 `VisualDecision` | 写大量规则细节 |
| `decision_rules.py` | 事实查询、隐私、急症、药物剂量、库存素材优先等硬规则 | 调 LLM |
| `llm_judge.py` | 调小模型，返回结构化语义判断 | 直接创建 job |
| `scoring.py` | 计算最终 confidence 和 decision_mode | 调外部模型 |
| `audit.py` | 记录判断链路，便于复盘和调参 | 参与业务决策 |

### 5.2 主流程

```text
assess_visual_need(input)
  ↓
pre_rule_check
  ├─ blocked -> no_visual
  ├─ reusable_asset_hit -> prefer_reuse / no_new_generation
  └─ pass
  ↓
llm_visual_judge
  ↓
collect_score_factors
  ↓
calculate_confidence
  ↓
route_by_threshold
  ↓
emit visual_decision / visual_confirm_required
```

---

## 6. 数据结构设计

### 6.1 小模型输入

```json
{
  "message": "用户出差了，推荐下餐食",
  "scene_key": "qa_support",
  "rag_sources": [
    {
      "title": "出差外食控糖建议",
      "score": 0.72,
      "source_type": "formal_knowledge"
    }
  ],
  "recommended_assets": [],
  "profile_safety_signals": {
    "has_medical_risk": false,
    "has_pii": false
  }
}
```

### 6.2 小模型输出

小模型输出必须是结构化 JSON，不允许只输出自然语言结论。

```json
{
  "has_visual_value": true,
  "visual_value": 0.86,
  "topic_clarity": 0.82,
  "actionability": 0.78,
  "text_only_sufficient": false,
  "recommended_visual_type": "nutrition_choice_card",
  "topic": "出差外食三步选餐法",
  "risk_hint": "low",
  "reason": "这是饮食选择类问题，适合用清单和步骤帮助客户快速理解并保存。"
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `has_visual_value` | boolean | 是否具备可视化价值 |
| `visual_value` | number | 图片表达相对文本的增益 |
| `topic_clarity` | number | 卡片主题是否清楚 |
| `actionability` | number | 是否能形成步骤、清单、对比、行动建议 |
| `text_only_sufficient` | boolean | 纯文本是否已经足够 |
| `recommended_visual_type` | string | 推荐视觉类型 |
| `topic` | string | 12-24 字左右的短主题 |
| `risk_hint` | string | `low` / `medium` / `high`，仅作提示 |
| `reason` | string | 给教练和审计看的简短理由 |

### 6.3 最终 VisualDecision

最终输出仍沿用总体文档的 `VisualDecision`，但建议扩展 `score_factors` 方便审计：

```json
{
  "need_visual": true,
  "confidence": 0.84,
  "decision_mode": "auto_async_generate",
  "visual_type": "nutrition_choice_card",
  "topic": "出差外食三步选餐法",
  "audience": "customer",
  "reason": "饮食选择问题具备明确视觉价值，RAG 证据充分，安全等级低。",
  "safety_level": "nutrition_education",
  "human_intervention_required": false,
  "score_factors": {
    "visual_value": 0.86,
    "topic_clarity": 0.82,
    "actionability": 0.78,
    "evidence_strength": 0.72,
    "scene_fit": 0.7,
    "safety_penalty": 0.0,
    "reusable_asset_penalty": 0.0
  }
}
```

---

## 7. 评分公式

建议初始公式：

```text
confidence =
  0.30 * visual_value
+ 0.20 * topic_clarity
+ 0.15 * actionability
+ 0.20 * evidence_strength
+ 0.10 * scene_fit
+ 0.05 * novelty
- safety_penalty
- reusable_asset_penalty
```

各项说明：

| 因子 | 来源 | 说明 |
| --- | --- | --- |
| `visual_value` | 小模型 | 图片是否比文本更有价值 |
| `topic_clarity` | 小模型 | 是否有明确卡片主题 |
| `actionability` | 小模型 | 是否能做成可执行清单/步骤 |
| `evidence_strength` | RAG | formal knowledge/material 命中质量 |
| `scene_fit` | 代码映射 | 当前场景是否适合外发知识卡 |
| `novelty` | 素材库 | 没有同主题高质量库存素材时加分 |
| `safety_penalty` | 规则 | 医疗敏感、隐私、急症等降权或拦截 |
| `reusable_asset_penalty` | 素材库 | 已有高质量素材时降低新图生成必要性 |

### 7.1 初始阈值

沿用总体文档：

```text
confidence >= 0.80：高置信，自动异步生成
0.45 <= confidence < 0.80：低置信，前端人工确认
confidence < 0.45：不生成
```

### 7.2 强制降级规则

即使综合分达到高置信，遇到以下情况也必须降级：

| 条件 | 处理 |
| --- | --- |
| 轻度医疗敏感 | 最高只能到 `manual_confirm` |
| 补剂、服用方式、PHGG 等边界表达 | 默认 `manual_confirm`，除非已有审核通过素材 |
| RAG 证据不足但小模型认为有价值 | 最高只能到 `manual_confirm` |
| 已有高质量库存素材命中 | 优先复用素材，不创建新图 job |
| 涉及个体化诊断、药物剂量、停药换药 | `no_visual` |
| 涉及客户隐私事实查询 | `no_visual` |
| 急症风险或需要转人工/医生 | `no_visual` |

---

## 8. Prompt 设计

小模型 prompt 应明确：它不是医疗裁判，也不是最终决策者，只做可视化语义评估。

示例系统提示词：

```text
你是 Visual Intent Router 的语义判断器。
你的任务不是回答用户问题，也不是判断医疗内容是否可发送。
你只判断当前问题是否适合生成一张面向客户的可视化知识卡片。

必须遵守：
1. 不要生成面向客户的正式内容。
2. 不要给出诊断、药物剂量、停药换药建议。
3. 不要把不确定内容说成确定。
4. 如果纯文本已经足够，text_only_sufficient=true。
5. 如果主题不清楚，降低 topic_clarity。
6. 如果涉及补剂、服用、医疗风险，只能标记 risk_hint，不能放行。
7. 只输出 JSON，不输出解释性正文。
```

用户消息：

```text
请根据以下上下文判断是否适合生成可视化知识卡：

message: {{message}}
scene_key: {{scene_key}}
rag_sources: {{rag_sources_summary}}
recommended_assets: {{recommended_assets_summary}}
profile_safety_signals: {{profile_safety_signals}}

返回 JSON：
{
  "has_visual_value": boolean,
  "visual_value": number,
  "topic_clarity": number,
  "actionability": number,
  "text_only_sufficient": boolean,
  "recommended_visual_type": string,
  "topic": string,
  "risk_hint": "low" | "medium" | "high",
  "reason": string
}
```

---

## 9. 审计与反馈闭环

每次判断都应记录：

1. 原始问题。
2. scene_key。
3. RAG sources 摘要与分数。
4. recommended_assets 命中情况。
5. 硬规则命中情况。
6. 小模型原始 JSON 输出。
7. score_factors。
8. 最终 `confidence`。
9. 最终 `decision_mode`。
10. 后续教练是否确认、是否发送、是否点踩。

这些记录用于后续调参：

| 反馈信号 | 调整方向 |
| --- | --- |
| 高置信自动生成但频繁被忽略 | 提高阈值或降低对应场景权重 |
| 低置信经常被教练确认 | 降低阈值或提高该类意图权重 |
| 教练点踩“没必要画图” | 降低 visual_value 或 scene_fit 权重 |
| 教练点踩“不安全/不适合发” | 增强安全降级规则 |
| 经常已有素材却重复生图 | 提高 reusable_asset_penalty |

---

## 10. 测试用例

### 10.1 高置信自动生成

| 输入 | 期望 |
| --- | --- |
| `用户要出差了，推荐下餐食` | `auto_async_generate`，topic 为出差外食选择类 |
| `外卖怎么点比较稳糖？` | `auto_async_generate` 或高分 `manual_confirm` |
| `晚餐怎么吃更稳糖？` | `auto_async_generate`，适合餐盘/顺序图 |

### 10.2 低置信人工确认

| 输入 | 期望 |
| --- | --- |
| `PHGG 怎么服用？` | `manual_confirm`，涉及补剂边界 |
| `这个概念客户听不懂，能不能讲直观一点？` | 根据上下文判断，通常 `manual_confirm` |
| `帮我总结她这周进步` | 若 Profile 证据充足可高置信，否则 `manual_confirm` |

### 10.3 不生成

| 输入 | 期望 |
| --- | --- |
| `她今年几岁？` | `no_visual` |
| `二甲双胍要不要停？` | `no_visual` |
| `胸痛怎么办？` | `no_visual`，转人工/医生 |
| `她血糖多少？` | `no_visual`，事实查询 |

### 10.4 库存素材优先

| 条件 | 期望 |
| --- | --- |
| 同主题已有审核通过素材，质量高 | 推荐复用，不创建新图 |
| 同主题素材存在但质量低或过期 | 可进入 `manual_confirm` 或重新生成 |

---

## 11. 分阶段落地计划

### Phase 1：保留现有规则，增加小模型 judge

目标：

1. 新增 `llm_judge.py`。
2. 小模型返回结构化 JSON。
3. `decision.py` 在规则未拦截时调用小模型。
4. 失败时 fallback 到现有规则算法。

验收：

1. 现有 `visual_decision` / `visual_confirm_required` SSE 不破坏。
2. 小模型失败不影响主 AI 对话回答。
3. 审计中可看到模型输出和 fallback 状态。

### Phase 2：拆分 scoring 与规则硬门禁

目标：

1. 新增 `decision_rules.py`。
2. 新增 `scoring.py`。
3. 明确硬拦截、强制降级、综合评分。
4. 将关键词从“主要判断依据”降级为“硬门禁和 fallback”。

验收：

1. 事实查询、隐私、药物剂量、急症风险稳定 `no_visual`。
2. PHGG / 补剂类问题默认不自动生成。
3. 饮食选择、外卖、出差等问题不依赖关键词也能识别。

### Phase 3：接入反馈调参

目标：

1. 记录教练确认、拒绝、发送、点踩。
2. 建立基础统计报表。
3. 根据真实反馈调整阈值和权重。

验收：

1. 能查看某类问题的自动生成接受率。
2. 能定位误触发和漏触发原因。
3. 阈值调整有数据依据，不靠主观感觉。

---

## 12. 当前阶段判断

当前项目已经具备 Visual Decision 的雏形，但仍处于规则 MVP 阶段。

已经能做：

1. 基于配置阈值输出高/低置信分流。
2. 基于关键词、scene、RAG score 计算基础 confidence。
3. 输出 `visual_decision` 和 `visual_confirm_required` 事件。

半能做：

1. 可以识别一部分显式饮食、控糖、PHGG、步骤清单类表达。
2. 可以通过安全规则拦截一部分明显不适合生图的内容。
3. 可以作为 Phase 1 链路验证，但不适合作为长期正式判断。

还不能做：

1. 不能稳定识别隐式可视化意图。
2. 不能避免关键词不断膨胀。
3. 不能解释每个分数的来源。
4. 不能基于教练反馈自动或半自动调参。
5. 不能把库存素材命中作为正式分流因素。

当前 blocker：

1. 缺少小模型语义判断层。
2. 缺少 score_factors 审计字段。
3. 缺少规则硬门禁、综合评分、fallback 的清晰拆分。
4. 缺少反馈数据对阈值的闭环校准。

---

## 13. 推荐下一步

最值得优先推进的是 Phase 1：

1. 保留现有 `decision.py` 对外接口，避免影响前端和 SSE。
2. 新增 `llm_judge.py`，只做结构化语义判断。
3. 在 `decision.py` 中增加开关配置，例如：

```python
ai_visual_llm_judge_enabled: bool = False
ai_visual_llm_judge_model: str = "gpt-4.1-mini"
ai_visual_llm_judge_timeout_seconds: int = 8
```

4. LLM judge 失败时回退现有规则，不阻断主对话。
5. 先记录小模型输出，不急着完全替换规则分数。
6. 跑一批真实问题，对比“规则判断”和“小模型判断”的差异。

这样可以在不破坏当前链路的前提下，逐步从关键词 MVP 演进到语义路由。

