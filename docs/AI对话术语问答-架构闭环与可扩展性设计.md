下面是完整内容，你可以直接复制粘贴到 `docs/AI对话术语问答-架构闭环与可扩展性设计.md`。

---

```markdown
# AI 对话术语问答 — 架构闭环与可扩展性设计

> 日期：2026-05-15  
> 上游报告：`docs/AI对话-PHGG专有名词问答异常调研报告.md`  
> 视角：Agent 工程师视角，聚焦"如何把这个能力做成可闭环、可扩展、可审计的工程体系"，而不是临时止血  
> 真值口径：客户档案是 `official customer truth`；术语知识卡是 `formal knowledge`；外部搜索是 `support evidence`；模型常识是 `unverified support`，**任何向客户输出的医疗/补剂/药品建议**都必须有证据来源链

---

## 0. 一句话定位

PHGG 这个 case 暴露的不是某个 Prompt 写漏了一句，而是**当前 AI 对话系统只有一种问答模式（"围绕当前客户的画像问答"），缺少另一种正交模式（"围绕健康教育的术语问答"）**。  

要做的不是再加一条规则，而是**把"答疑"重构成一个 Agent Pipeline：意图分流 → 证据召回 → 答案合成 → 安全门禁 → 审计反馈**，每一步都模块化、可观测、可降级、可扩展。

---

## 1. Agent 工程师视角的关键判断

### 1.1 当前系统是 RAG-augmented LLM，不是 Agent

现状：
- 单一管线：`prepare → prompt assemble → LLM stream → safety gate → audit`
- 没有"判断当前问题该走哪条证据路径"的能力
- 没有"证据不足时主动拒答或转人工"的能力
- 没有"调用外部工具"的能力（搜索、计算、查产品库等）

要做术语问答稳定落地，必须升级为**轻量 Agent 模式**：

```
用户问题
   ↓
[意图路由器] —— 判断是 客户事实 / 术语解释 / 补剂用法 / 医疗边界 / 运营话术
   ↓
[证据规划器] —— 决定调用哪些证据源（Profile / RAG / 知识卡 / 搜索工具 / 产品库）
   ↓
[证据执行器] —— 并行调用，统一证据格式
   ↓
[证据评估器] —— 充分性 + 安全等级 + 适用性判断
   ↓
[答案合成器] —— 基于证据生成回答，强制带来源
   ↓
[安全门禁]   —— 医疗边界、剂量、停换药拦截
   ↓
[审计与反馈] —— 记录证据链、教练点踩、回流到知识库
```

每一步都是**独立 service**，可单测、可替换、可监控。

### 1.2 Profile 与 Knowledge 必须正交

当前最大的混乱：把"客户事实"和"通用知识"混在同一组 system message 里给模型，模型自己分不清边界。

正交化原则：

| 维度 | Profile（客户事实） | Knowledge（通用知识） |
|------|---------------------|------------------------|
| 真值身份 | `official customer truth` | `formal knowledge` 或 `support evidence` |
| 来源 | CRM 数据库 | 知识卡 / RAG / 搜索 |
| 用途 | 安全个性化 + 客户场景判断 | 解释术语、给一般原则 |
| 触发条件 | 几乎所有问题 | 只在涉及通用概念时 |
| Prompt 区位 | "客户事实区" | "参考知识区" |
| 缺失时的态度 | 标注 missing，不能猜 | 明示"知识库无证据"，不能用 Profile 替代 |

这件事在工程上必须靠**结构化 Prompt 区段** + **强约束的回答合约**来落地，光靠自然语言描述模型不够稳。

### 1.3 必须有"答案合约"，不能让模型自由发挥

补剂、药品、医疗边界场景下，**回答的形态必须被约束**，不允许模型自由组织。建议引入答案合约（Answer Contract）：

```yaml
contract: supplement_usage_answer
required_sections:
  - term_definition       # 必须先解释是什么
  - general_usage         # 一般使用原则（不是个体化剂量）
  - customer_safety_note  # 结合 safety_profile 的注意事项
  - boundary              # 需要医生/产品说明确认的边界
forbidden:
  - specific_dosage_for_this_customer
  - drug_interaction_conclusion
  - replacement_for_medication
must_include_when_applicable:
  - evidence_source       # 引用知识卡或证据 ID
  - "知识库未收录"提示    # 当 evidence_count == 0 时
```

合约由代码强制（生成后 post-validate），不是仅靠 Prompt 期望。

---

## 2. 闭环架构设计

### 2.1 总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                   AI 对话术语问答闭环架构                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ① 用户问题                                                           │
│       ↓                                                              │
│  ② Intent Router（意图路由器）                                         │
│     ├─ NER：识别英文缩写、补剂名、药品名、品牌名                          │
│     ├─ Pattern：是什么/怎么吃/能不能/和XX一起                            │
│     ├─ Domain Classifier：customer_fact / term / supplement / drug   │
│     └─ 输出：QueryIntent { domain, entities[], answer_contract }     │
│       ↓                                                              │
│  ③ Evidence Planner（证据规划器）                                       │
│     根据 intent.domain 决定调用哪些 retriever：                         │
│       customer_fact     → Profile only                               │
│       term_definition   → KnowledgeCard + RAG                        │
│       supplement_usage  → KnowledgeCard + RAG + (External Search)    │
│       drug_question     → KnowledgeCard + Doctor Boundary（强转医生）  │
│       operational       → RAG (talkscript)                           │
│       ↓                                                              │
│  ④ Evidence Executor（证据执行器）                                      │
│     并行调用各 retriever，统一返回 EvidenceItem 格式                     │
│       ↓                                                              │
│  ⑤ Evidence Evaluator（证据评估器）                                     │
│     ├─ 证据充分性：count、quality_score、safety_level                  │
│     ├─ 适用性：是否覆盖当前问题语义                                      │
│     └─ 决策：proceed / fallback_to_search / refuse_with_explain      │
│       ↓                                                              │
│  ⑥ Answer Synthesizer（答案合成器）                                     │
│     ├─ 选择 Answer Contract                                          │
│     ├─ 组装结构化 Prompt（事实区 / 知识区 / 合约约束）                    │
│     └─ LLM Stream                                                    │
│       ↓                                                              │
│  ⑦ Contract Validator（合约校验器）                                     │
│     ├─ 必含段落是否齐全                                                 │
│     ├─ 是否含禁用内容（如个体化剂量）                                    │
│     └─ 不通过 → 回退到模板化降级回答                                     │
│       ↓                                                              │
│  ⑧ Safety Gate（安全门禁，已有）                                        │
│       ↓                                                              │
│  ⑨ Audit & Feedback Loop（审计与反馈闭环）                              │
│     ├─ 完整证据链入库（query → intent → evidence_ids → answer）        │
│     ├─ 教练反馈（点踩/纠错）                                            │
│     └─ 回流：未命中术语 → 知识缺口表 → 人工补卡 → 重新索引                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 闭环的"闭"在哪里

很多团队做到 ⑥ 就停了，结果是"看起来能用，永远不会变好"。真正闭环的关键在 ⑨：

| 闭环节点 | 输入 | 输出 | 落库 |
|---------|------|------|------|
| 意图未识别（unknown） | 问题文本 | 加入 `term_intent_miss` | 每周聚合，人工新增意图规则 |
| 证据为 0 | query + intent | `knowledge_gap` 记录 | 每日 Top N 待补术语清单 |
| 教练点踩 + 备注 | 答案 + 反馈 | `qa_correction` | 进知识卡候选，标注 reviewer |
| 合约校验失败 | 模型输出 | `contract_violation` | 用于 prompt 调优样本 |
| 外部搜索触发 | query | `search_event` | 监控成本 + 来源分布 |

**没有这个闭环，任何 Prompt 改动和知识库扩充都是单次行为，不会累积。**

---

## 3. 工程细节设计

### 3.1 数据模型（4 张核心表）

按 AGENTS.md 工程规范，在 `app/rag/` 下扩展：

#### 3.1.1 `knowledge_terms` — 术语注册表（formal knowledge）

```python
class KnowledgeTerm(Base):
    __tablename__ = "knowledge_terms"
    id: int
    term: str                # "PHGG"，唯一
    canonical_name: str      # "部分水解瓜尔胶"
    aliases_json: Text       # ["partially hydrolyzed guar gum", "瓜尔胶水解物"]
    category: str            # supplement / drug / device / brand / concept
    domain_tags_json: Text   # ["fiber", "prebiotic", "gut_health"]
    safety_level: str        # general / nutrition_education / medical_sensitive / doctor_review
    answer_contract: str     # supplement_usage / drug_boundary / term_explain
    review_status: str       # candidate / approved / archived
    primary_card_id: int     # 指向 knowledge_cards 主卡
    created_at, updated_at, reviewer_id
```

**作用**：
- 是术语 NER 的真值字典
- 是答案合约的路由依据
- 是安全等级的源头
- 教练在后台维护，不依赖代码发版

#### 3.1.2 `knowledge_cards` — 知识卡内容表

```python
class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"
    id: int
    term_id: int             # FK → knowledge_terms
    card_type: str           # definition / usage / contraindication / interaction
    content_md: Text         # Markdown 正文
    evidence_level: str      # support / formal
    source_url: str
    source_type: str         # clinical_trial / guideline / product_spec / textbook
    applicable_population_json: Text  # ["adult", "ibs"] 等
    review_status: str
    embedding_chunk_id: str  # 同步到 Qdrant 的 chunk id
```

**作用**：
- 一个术语可有多张卡（定义 / 用法 / 禁忌 / 相互作用）
- 每张卡独立 embedding，独立 retrieve
- 评审状态 `approved` 才进入 Qdrant 索引

#### 3.1.3 `knowledge_gaps` — 知识缺口表（闭环核心）

```python
class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"
    id: int
    detected_term: str       # 被识别但未命中的术语
    sample_query: str        # 触发的原始问题
    sample_session_id: str
    detected_count: int      # 累计被问次数
    last_seen_at: datetime
    status: str              # open / claimed / fulfilled / rejected
    assigned_to: int         # 待补卡的责任人
```

**作用**：是闭环的"待办池"。每周/每天自动聚合，最多被问的 N 个术语进入运营视图。

#### 3.1.4 `qa_evidence_chain` — 证据链审计表

```python
class QaEvidenceChain(Base):
    __tablename__ = "qa_evidence_chain"
    id: int
    session_id: str
    message_id: str
    intent_domain: str
    entities_json: Text      # NER 出的实体
    evidence_sources_json: Text  # [{type, id, score}, ...]
    contract_used: str
    contract_validation: str # passed / failed / degraded
    used_external_search: bool
    safety_triggered: bool
    answer_kind: str         # full / partial / refused / boundary_only
```

**作用**：
- 任何一次回答可被完整复盘
- 教练反馈可关联到证据链
- 离线分析"哪种证据组合质量最高"

### 3.2 模块拆分（严格按 AGENTS.md 红线）

```
app/agents/                              # 新顶级目录，与 rag/ 同级
├── __init__.py
├── intent_router/
│   ├── __init__.py                      # 公开 API
│   ├── _ner.py                          # 实体识别（regex + 字典 + 可选 LLM）
│   ├── _classifier.py                   # domain 分类
│   ├── _patterns.py                     # 问句模式
│   └── types.py                         # QueryIntent dataclass
├── evidence/
│   ├── __init__.py
│   ├── planner.py                       # 决定调哪些 retriever
│   ├── executor.py                      # 并行执行
│   ├── evaluator.py                     # 充分性评估
│   ├── retrievers/
│   │   ├── _profile.py                  # 复用 profile_loader
│   │   ├── _knowledge_card.py           # 知识卡精确召回
│   │   ├── _rag.py                      # 复用 rag/retriever
│   │   └── _external_search.py          # 受控搜索（P2）
│   └── types.py                         # EvidenceItem dataclass
├── synthesizer/
│   ├── __init__.py
│   ├── contracts/                       # YAML 答案合约
│   │   ├── supplement_usage.yaml
│   │   ├── drug_boundary.yaml
│   │   └── term_explain.yaml
│   ├── prompt_assembler.py              # 结构化 Prompt 区段
│   └── validator.py                     # 合约校验
└── feedback/
    ├── __init__.py
    ├── gap_collector.py                 # 知识缺口聚合
    └── correction_intake.py             # 教练纠错入库
```

每个文件保持 < 300 行，子包用 `_` 前缀文件做内部实现，符合 AGENTS.md "代码组织规则"。

### 3.3 关键接口设计

#### 3.3.1 IntentRouter

```python
@dataclass
class QueryIntent:
    domain: Literal["customer_fact", "term_definition", "supplement_usage",
                    "drug_question", "operational", "unknown"]
    entities: list[Entity]              # NER 结果，每个含 term/category/safety_level
    answer_contract: str | None         # 由 domain + entities 决定
    confidence: float
    fallback_reason: str | None

def classify(message: str, scene_key: str, profile: ModulePayloadList) -> QueryIntent: ...
```

NER 实现策略（按成本递增）：
1. **dict-based**：先查 `knowledge_terms.term + aliases`，O(N) 子串匹配 + AC 自动机
2. **regex**：英文大写 2-6 字母缩写 + 中文长度 ≤ 8 名词短语
3. **LLM-based**（可选，仅 unknown 时触发）：小模型一次性抽取，缓存结果

第 1 步必须做，第 2、3 步按需启用。

#### 3.3.2 EvidencePlanner

```python
def plan(intent: QueryIntent) -> EvidencePlan:
    plans = {
        "customer_fact":     [profile],
        "term_definition":   [knowledge_card, rag],
        "supplement_usage":  [knowledge_card, rag, external_search_if_empty],
        "drug_question":     [knowledge_card, doctor_boundary_template],
        "operational":       [rag_talkscript],
        "unknown":           [profile, rag, gap_recorder],   # 兜底 + 闭环记录
    }
    return EvidencePlan(retrievers=plans[intent.domain], parallelism=3)
```

**核心约束**：
- 每个 retriever 都返回统一的 `EvidenceItem`（type, id, content, score, source_meta, safety_level）
- 调用是声明式的，加新源只需注册一个新 retriever

#### 3.3.3 EvidenceEvaluator

```python
@dataclass
class EvidenceVerdict:
    decision: Literal["proceed", "fallback_external", "refuse", "doctor_boundary"]
    reason: str
    sufficient_count: int
    max_safety_level: str

def evaluate(plan: EvidencePlan, items: list[EvidenceItem],
             intent: QueryIntent) -> EvidenceVerdict: ...
```

判断规则示例：
- `supplement_usage` 且 `formal evidence count == 0` 且未触发 search → `fallback_external`
- `drug_question` 且无 `doctor_review` 边界条目 → `doctor_boundary`（直接走模板答）
- `term_definition` 且总分 < 阈值 → `refuse`（明示"知识库无收录"）

#### 3.3.4 PromptAssembler（结构化 Prompt 区段）

```python
def assemble(intent: QueryIntent, profile: ProfileContext,
             evidence: list[EvidenceItem], contract: AnswerContract,
             user_message: str) -> list[Message]:
    return [
        Message(role="system", content=BASE_GUARDRAILS),
        Message(role="system", content=role_and_scene_block(intent)),
        Message(role="system", content=customer_fact_block(profile)),  # ← 客户事实区
        Message(role="system", content=knowledge_block(evidence)),     # ← 参考知识区
        Message(role="system", content=contract_to_prompt(contract)),  # ← 合约约束
        Message(role="user", content=user_message),
    ]
```

**这是 PHGG 这类问题的根本修复点**：客户事实区和参考知识区在 Prompt 里物理分离，并且每一段都有明确的"使用规则"前缀，模型不会再把它们混在一起处理。

#### 3.3.5 ContractValidator

```python
def validate(answer: str, contract: AnswerContract) -> ValidationResult:
    # 必含段落（用结构标记或语义匹配）
    for section in contract.required_sections:
        if not _has_section(answer, section):
            return ValidationResult.fail(f"missing:{section}")
    # 禁用内容（regex + 关键词）
    for forbidden in contract.forbidden_patterns:
        if forbidden.search(answer):
            return ValidationResult.fail(f"forbidden:{forbidden}")
    return ValidationResult.ok()

# 失败处理：降级为模板答 + 提示教练
```

### 3.4 SSE 事件流扩展

当前 SSE 只有 `loading / meta / delta / rag / done / error`。术语问答需要扩展：

| 新事件 | 时机 | Payload | 用途 |
|-------|------|---------|------|
| `intent` | 意图识别完成 | domain / entities / contract | 前端可视化"AI 正在解释 PHGG" |
| `evidence` | 证据收集完成 | sources、各源命中数 | 透明度，让教练知道答案依据 |
| `boundary` | 触发医生边界 | reason | 前端显眼提示 |
| `gap` | 知识缺口记录 | term | 教练可一键转入知识卡候选 |

这一层做好，前端可以渲染出非常专业的"AI 思考可视化"，而不是只看一个 loading 转圈。

### 3.5 配置化（避免硬编码）

新增 `app/config.py` 配置项：

```python
# Agent / 术语问答
agent_intent_router_enabled: bool = True
agent_ner_use_llm_fallback: bool = False
agent_external_search_enabled: bool = False
agent_external_search_whitelist: str = "pubmed.ncbi.nlm.nih.gov,efsa.europa.eu,who.int"
agent_min_evidence_count_for_supplement: int = 1
agent_contract_validation_enabled: bool = True
agent_gap_collector_enabled: bool = True
```

所有阈值、白名单、开关都走配置，不进代码。

---

## 4. 可扩展性设计

### 4.1 横向扩展：新增意图域

要点：**新增意图域只需 3 步**，不需要改主流程。

1. 在 `agents/intent_router/_classifier.py` 注册新 domain（或入库到 `intent_rules` 表）
2. 在 `agents/evidence/planner.py` 注册新 retriever 组合
3. 在 `agents/synthesizer/contracts/` 加 YAML 合约

例：将来要加"运动损伤恢复"问答 → 加 domain `injury_rehab`、复用 `knowledge_card` retriever、新合约 `injury_rehab_answer.yaml`。**主流程零改动**。

### 4.2 纵向扩展：新增证据源

每个 retriever 实现统一接口：

```python
class EvidenceRetriever(Protocol):
    name: str
    async def retrieve(self, query: str, intent: QueryIntent,
                       limit: int) -> list[EvidenceItem]: ...
```

未来加产品库、用药数据库、临床指南库时，只要实现这个接口、在 `Planner` 注册即可。**外部搜索、内部 RAG、知识卡、Profile 都是同一接口的实现**。

### 4.3 模型层扩展：从规则到模型

```
v1（MVP）：dict + regex 做 NER + 分类
v2：训练小模型做 NER（仅术语高频时切换）
v3：意图分类走 LLM（在 unknown 兜底时使用，缓存结果）
v4：Function Calling — 让 LLM 自主决定调哪些 retriever
```

每一阶段的接口稳定，**底层算法可独立升级，不影响业务调用方**。

### 4.4 闭环数据驱动迭代

| 数据 | 用途 |
|------|------|
| `knowledge_gaps` 月度 Top N | 决定下一批补卡内容 |
| `qa_evidence_chain` + 教练反馈 | 评估每种证据组合的成功率 |
| `contract_violation` 样本 | 反向优化合约和 Prompt |
| `intent_miss` 样本 | 优化意图规则 |

**这套数据是产品迭代的真值**，不是事后再去问教练"AI 哪里不好"。

---

## 5. 与现有系统的集成路径（不推倒重来）

### 5.1 改造点最小化

| 现有模块 | 改造方式 |
|---------|---------|
| `app/rag/intent_rules.py` | 保留作为 v1 兜底，逐步迁到 `agents/intent_router/` |
| `app/rag/query_compiler.py` | 把 `_extract_keywords` 升级为 NER 调用 |
| `app/rag/retriever.py` | 包装为 `EvidenceRetriever` 实现 |
| `app/crm_profile/services/ai/_prepare.py` | 在调 prompt_builder 之前先过 IntentRouter + EvidencePlanner |
| `app/crm_profile/services/prompt_builder.py` | 引入"客户事实区/参考知识区"分段 |
| `app/crm_profile/prompts/base/context_header.md` | 加入"客户上下文不是词典"约束（PHGG 报告 P0） |

### 5.2 三阶段落地路径（与 PHGG 报告 P0/P1/P2 对齐）

#### Stage 1（P0，3-5 天）：止血 + 雏形

- [ ] Prompt 三处改动（PHGG 报告 8.1）
- [ ] 新建 `knowledge_terms` + `knowledge_cards` 表 + 迁移
- [ ] 录入第一批 30 张知识卡（PHGG、菊粉、psyllium、二甲双胍边界、肌酸、NMN ...）
- [ ] 接入 `intent_rules` 加 `term_definition` 和 `supplement_usage`
- [ ] `_prepare_ai_turn` 中：识别到 term/supplement 时优先 RAG `knowledge_card` 子集
- [ ] Prompt 拆分客户事实区 / 参考知识区

**验收**：PHGG 三个测试问题通过；不影响现有客户事实问答。

#### Stage 2（P1，1-2 周）：闭环成型

- [ ] 新建 `app/agents/` 目录，按 3.2 拆分
- [ ] IntentRouter dict-based NER + 分类
- [ ] EvidencePlanner / Executor / Evaluator 接入
- [ ] Answer Contract YAML + ContractValidator
- [ ] `qa_evidence_chain` 表 + SSE `intent` / `evidence` 事件
- [ ] `knowledge_gaps` 自动收集
- [ ] 后台增加"知识缺口待办"页面

**验收**：能稳定处理"PHGG 怎么吃"+"肌酸肾不好能吃吗"+"二甲双胍能停吗"+"她最近血糖怎么样"（不混淆）；缺口表能聚合出未命中术语。

#### Stage 3（P2，2-3 周）：可扩展性兑现

- [ ] 受控外部搜索 retriever（白名单 + 摘要层）
- [ ] LLM-based NER 兜底
- [ ] 教练纠错入库 + 知识卡候选
- [ ] 离线评估管线（每日抽样 + LLM-as-judge）
- [ ] A/B 测试钩子（不同合约/不同检索策略）

---

## 6. 验收标准（覆盖闭环每一节点）

| 维度 | 验收点 |
|------|-------|
| 意图识别 | PHGG/NMN/肌酸/菊粉等被识别为 supplement_usage；"她最近血糖" 仍为 customer_fact |
| 证据召回 | 知识卡命中时 evidence_count ≥ 1，且 source_id 可追踪 |
| 合约约束 | supplement_usage 答案必含 4 段；不含个体化剂量 |
| 安全门禁 | drug_question 强制走医生边界模板，不给停换药结论 |
| 缺口闭环 | 一个新词被问 3 次后出现在缺口表 Top |
| 审计完整性 | 任何一次回答可通过 message_id 还原 intent + evidence + contract + safety |
| 可扩展性验证 | 新增"运动康复"域：仅改配置 + 新合约，主流程零改动 |
| 性能 | 增加 IntentRouter + Planner 后，prepare 阶段总耗时 ≤ 原值 + 200ms |

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| 意图误判把 customer_fact 错判为 term | dict-based NER 仅识别术语库内的；customer 关键代词（"她/他/客户"）优先级最高 |
| 知识卡录入慢，覆盖率不够 | 缺口表驱动；外部搜索作 P2 兜底 |
| 合约校验过严，正常回答被降级 | 合约 V1 只校验"必含段落"，禁用项放宽，逐步收紧 |
| 外部搜索成本/延迟 | 仅证据为 0 时触发；结果缓存 7 天；白名单严格 |
| Agent 链路加长，TTFT 变慢 | IntentRouter 用 dict-based（μs 级）；Planner/Executor 并行；Profile 与证据并行 |
| 教练对"知识库无收录"感到困惑 | 前端明确提示 + 一键"提交补卡需求"按钮 |

---

## 8. 工程纪律（按 AGENTS.md）

- **真值规则**：知识卡 `review_status=approved` 才是 formal；外部搜索结果永远是 support；模型常识标记为 unverified support 不进 audit chain
- **代码组织**：`app/agents/` 严格分子包，每个 service 单一职责，文件 < 300 行
- **多线程协作**：IntentRouter / EvidencePlanner / Synthesizer 是天然并行边界，可拆给不同子线程并行实现
- **验证**：每个 stage 完成后必须跑 `uvicorn` 启动测试 + 前端编译 + focused validation
- **沉淀**：每次缺口闭环案例 → memory.md "经验：术语补卡周期"

---

## 9. 面向项目负责人的状态翻译

### 看见
教练问"PHGG 怎么吃"，AI 给出"基于客户档案没找到 PHGG"这种答非所问的回答。

### 理解
当前 AI 系统只会用一种思路回答问题（围绕当前客户）。它没有能力区分"这是关于客户的问题"还是"这是关于一个补剂概念的问题"。结果是把所有问题都强行塞进客户档案视角。

### 决策
不能靠加规则止血，要从单管线升级为**轻量 Agent 模式**：
- 识别问题类型 → 决定查哪些证据 → 用结构化合约组织答案 → 严格审计 → 缺口闭环回流

这套架构上线后：
1. PHGG 这类问题能稳定回答
2. 将来加任何新术语、新意图（运动康复、心理支持、设备故障等）都不需要改主流程
3. AI 答案的质量可量化、可迭代、可追溯

### 当前 Blocker
- 知识卡库存为零（需要运营协同录入第一批）
- `app/agents/` 目录尚未建立（需要架构层一次性铺好）

### 下一步最值得做什么
- **本周**：Stage 1（PHGG 报告 P0 三处 Prompt 改动 + 知识卡表 + 录入 30 张种子卡）
- **下周**：Stage 2 雏形跑通（agents 目录 + IntentRouter + 合约校验）
- **本月**：Stage 3 兑现可扩展性，把缺口闭环跑起来

### 一句话原则
**不要再加规则补漏，要做一个能持续学习的 Agent 闭环**。规则补漏的天花板是教练的耐心；闭环的天花板是知识库的覆盖率。
```

---

要点回顾（你拍板用）：

1. **核心判断**：这不是 prompt bug，是**当前系统只有一种问答模式**，需要升级为轻量 Agent 模式（意图分流 → 证据规划 → 合约约束 → 审计闭环）。
2. **架构闭环**：分 9 个独立节点，每一步可观测、可降级、可替换。**真正的"闭"在第 9 步**：知识缺口自动收集 → 人工补卡 → 重新索引，否则任何改动都是单次行为。
3. **工程细节**：4 张核心表（terms / cards / gaps / evidence_chain）、6 个核心模块（intent_router / evidence / synthesizer / feedback）、统一 EvidenceItem 接口、YAML 答案合约、SSE 事件扩展。
4. **可扩展性**：新意图域 3 步配置、新证据源实现统一 Protocol、规则到 LLM 平滑升级、数据驱动迭代。
5. **不推倒重来**：明确改造点最小化映射，与 PHGG 报告的 P0/P1/P2 阶段对齐。