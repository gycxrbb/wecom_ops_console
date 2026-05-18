# AI 对话多模态 Agent 化总体开发文档

> 日期：2026-05-16  
> 面向对象：CRM AI 对话、健康教练工作台、RAG 素材/话术体系、发送中心  
> 上游参考：`docs/AI对话架构评审与优化方向报告.md`、`docs/AI对话术语问答-架构闭环与可扩展性设计.md`、`docs/AI对话RAG检索逻辑调研与改进报告.md`、`docs/AI对话体验优化方案-附件异步上传与动态进度提示.md`  
> 核心目标：把当前 AI 对话从“文本问答 + RAG 参考”升级为“文本回答 + 客户沟通话术 + 可视化知识卡片 + RAG 素材 + 审计反馈闭环”的轻量 Agent 工作流。  
> 真值口径：客户档案是 `official customer truth`；内部知识卡和审核通过的素材是 `formal knowledge/material`；RAG 召回与外部搜索是 `support evidence`；AI 生成图片先是 `candidate visual asset`，通过安全/内容门禁后才能作为可发送素材。

---

## 1. 一句话结论

这个需求不是“在 AI 回复里多生成一张图”，而是要给 AI 对话补上一条**异步可视化工具链**。

当前主链路仍保持：

```text
教练提问
  ↓
Profile + RAG + Prompt
  ↓
Thinking / Answer 流式回复
  ↓
安全门禁 + 审计
```

新增支线：

```text
教练提问
  ↓
Visual Intent Router 判断是否适合可视化
  ↓
按置信度分流：高置信自动生成 / 低置信进入人工干预节点
  ↓
Visual Planner 生成知识卡片 brief
  ↓
异步直接调用 gpt-image-2 生成图片直出
  ↓
安全/准确性校验
  ↓
以 reference message / generated visual asset 返回前端
  ↓
教练可预览、复制、发送到发送中心、反馈
```

这样主回答流不会被图片生成拖慢，同时又能让教练拿到“可直接发给客户的图文知识点卡片”。

---

## 2. 当前系统现状

### 2.1 已经能做什么

| 能力 | 当前状态 | 代码/文档依据 |
| --- | --- | --- |
| AI 对话流式回答 | 已运行 | `app/crm_profile/services/ai/__init__.py` |
| Thinking + Answer 双流 | 已运行 | `ai/chat-stream`、`ai/thinking-stream` |
| Profile 预加载 | 已运行 | `profile_context_cache.py` |
| 5 层 Prompt 架构 | 已运行 | `prompt_builder.py`、`app/crm_profile/prompts/` |
| RAG 参考语料召回 | 已运行 | `app/rag/retriever.py` |
| RAG 推荐素材 | 已有基础 | `recommended_assets`、material phase 检索 |
| 动态进度事件 | 已有基础 | answer stream 已有 `progress` 事件 |
| 前端 reference message | 已有基础 | `AiChatMessage` 已区分 `rag_reference` / `rag_attachment` |
| 附件/图片分析 | 已运行 | `CrmAiAttachment`、`vision_analyzer.py` |
| 发送中心 | 已运行 | `frontend/src/views/SendCenter/` |

说明：部分历史调研文档描述的是当时状态。当前代码里已经出现了 `progress`、reference message、素材推荐等改动雏形，因此本方案以**当前代码为准**继续设计。

### 2.2 半能做什么

| 能力 | 当前基础 | 缺口 |
| --- | --- | --- |
| 可视化素材推荐 | RAG 已能推荐素材 | 只推荐库存素材，不能按问题实时生成知识卡 |
| 参考语料独立展示 | 前端已有 `reference` 类型 | 历史恢复、审计、发送中心闭环还需统一规范 |
| 动态进度提示 | 已有 `progress` 事件 | `AiStreamEvent` 类型声明未同步包含 `progress`，需补齐 |
| Agent 化调度 | 有 prepare/RAG/prompt 的固定链路 | 缺少 tool registry、planner、job、trace |
| 术语/补剂问答 | 有设计文档 | 尚未形成统一 Agent Pipeline |

### 2.3 还不能做什么

1. 不能自动判断“这个问题适合生成图片/卡片”。
2. 不能异步生成“可直接发给客户的健康知识卡”。
3. 不能把生成图作为素材入库、复用、审核和反馈。
4. 不能把“RAG 召回素材”和“AI 生成素材”放进统一的交付协议。
5. 不能记录一次图片生成背后的意图、证据、提示词、模型、审核结果。
6. 不能形成“被频繁生成的主题 -> 沉淀为正式素材”的运营闭环。

---

## 3. 产品定位

### 3.1 业务场景

健康教练日常管理用户时，经常需要把复杂知识点讲得更好懂：

1. 出差/外食怎么选餐。
2. 血糖波动怎么看。
3. 膳食纤维、PHGG、益生元是什么。
4. 运动后为什么血糖可能短暂升高。
5. 晚餐怎么搭配更稳。
6. 低血糖风险信号有哪些。
7. 每周复盘时用一张图强化正反馈。

这些内容如果只发文字，用户理解成本高，转发吸收差；如果用图文卡片，教练显得更专业，用户也更容易保存、转发、执行。

### 3.2 目标输出形态

教练提问：

```text
用户要出差了，推荐下餐食
```

最终前端应出现：

```text
1. AI 正式回复
   - 给教练看的判断
   - 给客户可复制的话术 txt 代码块

2. RAG 参考话术
   - 出差外食外卖指导话术
   - 低卡放心食材参考

3. RAG 推荐素材
   - 已入库的图片/视频/文件

4. AI 生成知识卡片
   - 主题：出差外食三步选餐法
   - 状态：生成中 / 已生成 / 需审核 / 可发送
   - 操作：预览、重新生成、发送到发送中心、保存到素材库、反馈
```

### 3.3 与普通图片生成的区别

这不是通用绘图功能，而是**健康教练可交付素材生成工具**。

| 普通绘图 | 本系统知识卡生成 |
| --- | --- |
| 用户想画什么就画什么 | 系统判断是否适合可视化 |
| 只追求好看 | 必须准确、可解释、可发送 |
| 一次性产物 | 可入库、可复用、可反馈 |
| 不关心证据 | 必须记录知识来源和安全边界 |
| 不区分身份 | 必须面向教练，输出给客户需教练复核 |

---

## 4. 总体架构

### 4.1 目标架构图

```text
┌─────────────────────────────────────────────────────────────────────┐
│                      CRM AI Coach Agent 总体链路                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  用户输入                                                           │
│    ↓                                                                │
│  Chat Orchestrator                                                  │
│    ├─ Profile Context Loader          当前客户 official truth        │
│    ├─ RAG Retriever                   内部 support/formal knowledge │
│    ├─ Intent Router                   事实/术语/运营/可视化判断       │
│    ├─ Answer Synthesizer              Thinking + Answer             │
│    └─ Tool Planner                    决定是否开启异步工具           │
│            ↓                                                        │
│       ┌─────────────────────────────────────────────────────────┐   │
│       │                  Async Tool Lane                         │   │
│       │                                                         │   │
│       │  Visual Intent Router                                   │   │
│       │    ↓                                                    │   │
│       │  Visual Brief Builder                                   │   │
│       │    ↓                                                    │   │
│       │  Evidence Binder                                        │   │
│       │    ↓                                                    │   │
│       │  Render Strategy                                        │   │
│       │    ├─ Template Renderer（文字准确优先）                   │   │
│       │    └─ Image Model Generator（视觉表达增强）                │   │
│       │    ↓                                                    │   │
│       │  Visual Safety & QA Gate                                │   │
│       │    ↓                                                    │   │
│       │  Storage / Material Registry                            │   │
│       │    ↓                                                    │   │
│       │  SSE visual events / status polling                     │   │
│       └─────────────────────────────────────────────────────────┘   │
│                                                                     │
│  前端消息区                                                         │
│    ├─ user message                                                  │
│    ├─ rag_reference / rag_attachment                                │
│    ├─ assistant_answer                                              │
│    └─ generated_visual                                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 两条流必须解耦

主回答流：

```text
目标：快速回答教练问题
SLA：首 token 体验优先
失败策略：可无 RAG 降级，但要提示
```

图片/卡片流：

```text
目标：生成可发送视觉素材
SLA：允许 10-120 秒异步完成
失败策略：不影响 AI 正式回复，只返回“图片生成失败/待重试”
```

强规则：

1. 生成图片不能阻塞 answer stream。
2. 生成图片不能影响 thinking stream。
3. 生成图片失败不能导致 AI 文本回答失败。
4. 图片结果必须以独立 reference message 出现，不能混进 assistant 正文。
5. 图片进入发送中心前必须经过安全与准确性门禁。

---

## 5. Agent 化路径

### 5.1 当前系统到 Agent 的演进方式

当前系统是固定管线：

```text
prepare -> RAG -> prompt -> model -> safety -> audit
```

目标不是一次性重写为复杂多 Agent，而是演进为轻量 Agent：

```text
orchestrator -> planner -> tools -> trace -> feedback
```

| 阶段 | 形态 | 说明 |
| --- | --- | --- |
| Stage A | 自研 Orchestrator | 保留现有 FastAPI + SSE，先建立工具调用抽象 |
| Stage B | Tool Registry | RAG、Profile、Visual Generation、Search 都成为工具 |
| Stage C | Trace / Evidence Chain | 每次工具调用可审计、可复盘 |
| Stage D | 可选接入 Responses/Agents SDK | 当 provider、成本、治理成熟后迁移编排层 |

从本文档开始，AI 对话新增功能默认按 Agent 化方式落地：先有 Orchestrator、Tool Registry、异步 job 和 trace，再接入具体工具。也就是说，可视化生图不是孤立功能，而是第一批正式进入 Agent 工作流的工具能力。

OpenAI 当前官方推荐的新项目可使用 Responses API，它支持内置工具、函数调用、多模态输入输出，也支持 image generation 工具；Agents SDK 则提供工具、handoff、stream、trace 等 Agent 能力。对本项目而言，短期不应推倒现有链路，应该先把“工具注册 + 异步 job + trace”在本系统内跑通；图片生成本身先采用直接调用 `gpt-image-2` 的方式直出，不在 MVP 阶段依赖 Responses image generation tool 或 Agents SDK 编排。

### 5.2 Agent 的职责拆分

| 组件 | 职责 | 是否必须 LLM |
| --- | --- | --- |
| Intent Router | 判断问题域和是否需要工具 | 不必须，规则优先 |
| Evidence Planner | 决定用 Profile/RAG/Search/Visual | 不必须 |
| Answer Synthesizer | 生成文字回答和客户话术 | 需要 |
| Visual Planner | 判断是否需要生成知识卡，输出视觉 brief | 可规则 + LLM |
| Visual Renderer | 直接调用 `gpt-image-2` 生成图片直出 | 工具 |
| Safety Gate | 医疗、安全、可发送边界 | 规则 + 可选模型 |
| Feedback Collector | 收集教练反馈，回流素材/知识库 | 不必须 |

### 5.3 Tool Registry

建议引入内部工具协议：

```python
class AgentTool(Protocol):
    name: str
    version: str
    async def run(self, input: dict, trace: AgentTrace) -> dict: ...
```

首批工具：

| 工具 | 输入 | 输出 |
| --- | --- | --- |
| `profile_context.retrieve` | customer_id, window_days | Profile 摘要 |
| `rag.retrieve` | query, intent, filters | sources, assets |
| `term_knowledge.retrieve` | term, question_type | knowledge cards |
| `visual.need_assess` | message, intent, rag_sources | need_visual, reason |
| `visual.confirm` | topic, coach_decision | confirmed / declined |
| `visual.brief_build` | topic, evidence, audience | visual brief |
| `visual.generate` | visual brief, style, constraints | image_url, asset_id |
| `visual.qa` | image_url, brief | pass/fail, issues |
| `send_center.prefill` | message/asset | prefill payload |

这些工具先由代码显式调用，不让模型自由乱调。后续再开放给 LLM function calling。

---

## 6. 可视化知识卡片工作流

### 6.1 何时触发绘图

触发条件不是“用户说画一张图”才触发，而是系统判断该问题具备可视化价值。

触发后不直接等同于立刻生图，而是按置信度进入三类决策：

| 决策 | 条件 | 系统动作 | 前端表现 |
| --- | --- | --- | --- |
| 高置信自动生成 | 可视化价值明确、证据充分、安全等级低、无高质量库存素材替代 | 自动创建异步 job，直接调用 `gpt-image-2` 生图 | 显示“正在生成知识卡片” |
| 低置信人工干预 | 是否值得画图不确定、主题表达不清、已有素材与新图价值接近、或轻度安全敏感 | 不自动生图，创建 `visual_confirm_required` 节点 | 询问教练“是否需要绘制图片？” |
| 禁止/不建议生成 | 医疗高风险、客户隐私、事实查询、个体化药物/诊断 | 不创建生图 job | 不显示生图入口，或显示安全原因 |

建议初始阈值：

```text
confidence >= 0.80：高置信，自动异步生成
0.45 <= confidence < 0.80：低置信，前端人工确认
confidence < 0.45：不生成
```

阈值不是长期 truth，后续应根据教练反馈、发送率、点踩原因调整。

推荐触发：

| 场景 | 示例 | 可视化收益 |
| --- | --- | --- |
| 健康教育知识点 | `PHGG 怎么服用？` | 概念 + 注意事项更易保存 |
| 饮食选择 | `用户出差了，推荐下餐食` | 直接给出三步选择法 |
| 行为指导 | `晚餐怎么吃更稳糖？` | 餐盘比例、顺序、替代选择 |
| 风险信号科普 | `低血糖有哪些表现？` | 用图标呈现信号和处理原则 |
| 复盘强化 | `帮我总结她这周进步` | 正反馈卡片增强坚持 |
| 用户可执行清单 | `外卖怎么点？` | 清单式图片比长文更可执行 |

不推荐触发：

| 场景 | 原因 |
| --- | --- |
| 客户姓名、年龄、所属群等事实查询 | 无视觉价值 |
| 急性医疗风险、胸痛、严重低血糖等 | 先转医生/人工，不生成科普图弱化风险 |
| 个体化药物剂量、停药换药 | 禁止生成“用药指导图” |
| 数据不足的个体判断 | 不生成看似确定的图 |
| 已有高质量库存素材命中 | 优先复用素材，避免重复生成 |

### 6.2 Visual Decision Schema

Visual Intent Router 输出：

```json
{
  "need_visual": true,
  "confidence": 0.86,
  "decision_mode": "auto_async_generate",
  "visual_type": "health_education_card",
  "topic": "出差外食三步选餐法",
  "audience": "customer",
  "reason": "问题是饮食选择教育，适合用图文卡片帮助用户快速理解",
  "safety_level": "nutrition_education",
  "generation_model": "gpt-image-2",
  "generation_strategy": "direct_image",
  "reuse_first": true,
  "evidence_required": true,
  "human_intervention_required": false,
  "confirm_question": null
}
```

低置信时：

```json
{
  "need_visual": true,
  "confidence": 0.62,
  "decision_mode": "manual_confirm",
  "visual_type": "health_education_card",
  "topic": "PHGG 服用说明卡",
  "audience": "customer",
  "reason": "问题具备可视化价值，但涉及补剂服用边界，需教练确认是否生成对外图片",
  "safety_level": "medical_sensitive",
  "generation_model": "gpt-image-2",
  "generation_strategy": "direct_image",
  "reuse_first": true,
  "evidence_required": true,
  "human_intervention_required": true,
  "confirm_question": "这个问题可以生成一张科普说明卡，但涉及补剂服用边界，是否需要绘制图片？"
}
```

### 6.3 生成策略：gpt-image-2 直出

本轮开发的正式口径：**图片生成直接调用 `gpt-image-2` 模型生成直出图片**。

不再把模板渲染器或混合渲染作为 MVP 主路径。后端只负责：

1. 生成结构化 visual brief。
2. 把 brief 转成受控 prompt。
3. 调用 `gpt-image-2` 生成图片。
4. 存储图片并进入 QA Gate。
5. 把 job、prompt、模型、证据、审核结果写入 trace。

直接生图的默认流程：

```text
1. Visual Router 输出 decision
2. 高置信：自动创建 job；低置信：等待教练确认
3. Visual Brief Builder 输出卡片结构和安全边界
4. Prompt Builder 生成 gpt-image-2 prompt
5. Image Client 调用 gpt-image-2 直出图片
6. Storage Bridge 保存图片
7. QA Gate 检查图片和 brief 是否一致、是否可发送
```

说明：如果后续发现中文文字稳定性不能满足业务，可以另起 Phase N 做独立兜底增强；本轮正式开发不依赖模板渲染器，主路径保持 `gpt-image-2` 直出。

### 6.4 Visual Brief

图像生成前必须先生成结构化 brief：

```json
{
  "card_title": "出差外食三步选餐法",
  "core_message": "先看蛋白质，再选蔬菜，主食减半不空腹",
  "sections": [
    {
      "title": "1. 先选蛋白质",
      "body": "鸡蛋、鱼虾、鸡胸、豆腐优先"
    },
    {
      "title": "2. 加一份蔬菜",
      "body": "清炒、凉拌、少油更稳"
    },
    {
      "title": "3. 主食减半",
      "body": "米饭半碗，避免甜饮"
    }
  ],
  "avoid_claims": [
    "保证降糖",
    "替代医生建议",
    "极端节食"
  ],
  "visual_style": {
    "format": "vertical_card",
    "ratio": "3:4",
    "tone": "warm_professional",
    "brand": "wecom_health_coach"
  },
  "sendable_copy": "出差在外也不用太焦虑，按这个三步选餐就很稳..."
}
```

Visual Brief 是比 prompt 更重要的中间产物，必须落库审计。

### 6.5 生成任务生命周期

```text
candidate
  ↓
planned
  ↓
manual_confirm_required（低置信时）
  ↓
manual_confirmed / manual_declined
  ↓
queued
  ↓
generating
  ↓
qa_pending
  ↓
ready
  ↓
sent / saved / rejected / regenerated
```

状态含义：

| 状态 | 含义 |
| --- | --- |
| `candidate` | 系统判断适合生成，但还未创建任务 |
| `planned` | visual brief 已生成 |
| `manual_confirm_required` | 低置信或轻度敏感，需要教练确认是否绘制图片 |
| `manual_confirmed` | 教练确认需要绘制，允许进入异步队列 |
| `manual_declined` | 教练选择不绘制，本轮不创建生图任务 |
| `queued` | 进入异步队列 |
| `generating` | 正在调用 `gpt-image-2` 生成图片 |
| `qa_pending` | 图片已生成，等待安全/准确性校验 |
| `ready` | 可给教练预览和发送 |
| `sent` | 已进入发送中心或已发送 |
| `saved` | 已沉淀到素材库 |
| `rejected` | 安全/准确性不通过 |
| `regenerated` | 教练触发重新生成 |

---

## 7. 后端设计

### 7.1 模块放置

建议新增独立模块 `app/ai_visual/`，原因：

1. 它当前由 CRM AI 对话触发，但未来也可能被话术管理、发送中心、运营计划复用。
2. 它包含决策、brief、`gpt-image-2` 调用、素材入库、QA Gate，不应塞进 `crm_profile/services/ai/` 继续膨胀。
3. 它可作为 Agent Tool 被多个业务模块调用。

目录建议：

```text
app/ai_visual/
├── models.py
├── router.py
├── routers/
│   ├── __init__.py
│   ├── jobs.py
│   └── assets.py
├── schemas/
│   ├── __init__.py
│   ├── jobs.py
│   └── assets.py
├── services/
│   ├── __init__.py
│   ├── decision.py
│   ├── brief_builder.py
│   ├── job_service.py
│   ├── prompt_builder.py
│   ├── image_client.py
│   ├── qa_gate.py
│   ├── storage_bridge.py
│   └── audit.py
└── prompts/
    ├── visual_decision.md
    ├── visual_brief.md
    └── visual_qa.md
```

路由聚合器保持 AGENTS.md 规范：

```python
router = APIRouter(prefix="/api/v1/ai-visual", tags=["ai-visual"], route_class=UnifiedResponseRoute)
router.include_router(routers.jobs.router)
router.include_router(routers.assets.router)
```

CRM AI 对话只调用 service，不直接写图片生成业务逻辑。

### 7.2 核心数据表

#### 7.2.1 `ai_visual_jobs`

```python
class AiVisualJob(Base):
    __tablename__ = "ai_visual_jobs"

    id: int
    job_id: str
    session_id: str | None
    user_message_id: str | None
    assistant_message_id: str | None
    crm_customer_id: int | None
    requested_by: int

    source: str                 # ai_chat / manual_confirm / send_center / material_center
    topic: str
    visual_type: str            # health_education_card / checklist / comparison / timeline
    status: str                 # planned / manual_confirm_required / queued / generating / qa_pending / ready / rejected / failed
    safety_level: str

    decision_json: Text
    brief_json: Text
    evidence_json: Text
    prompt_hash: str
    model_provider: str
    model_name: str
    generation_strategy: str    # direct_image
    confidence: float
    human_intervention_required: bool

    error_code: str | None
    error_message: Text | None
    created_at, updated_at, completed_at
```

#### 7.2.2 `ai_visual_assets`

```python
class AiVisualAsset(Base):
    __tablename__ = "ai_visual_assets"

    id: int
    asset_id: str
    job_id: str
    material_id: int | None

    title: str
    public_url: str
    storage_provider: str
    storage_key: str
    width: int
    height: int
    mime_type: str
    file_size: int
    content_hash: str

    review_status: str          # candidate / approved / rejected / saved_as_material
    sendable: bool
    rejection_reason: Text | None
    created_at, updated_at
```

#### 7.2.3 `ai_visual_feedback`

```python
class AiVisualFeedback(Base):
    __tablename__ = "ai_visual_feedback"

    id: int
    feedback_id: str
    asset_id: str
    job_id: str
    coach_user_id: int
    rating: str                 # like / dislike
    reason_category: str | None # inaccurate / ugly / unsafe / not_relevant / text_error
    reason_text: Text | None
    status: str                 # new / reviewed / used_for_material / ignored
    created_at, updated_at
```

#### 7.2.4 扩展证据链

现有 `rag_retrieval_logs` 和 `crm_ai_context_snapshots` 可以保留。建议新增或扩展 Agent 级 trace：

```python
class AiAgentTrace(Base):
    __tablename__ = "ai_agent_traces"

    id: int
    trace_id: str
    session_id: str
    message_id: str
    tool_name: str              # rag.retrieve / visual.need_assess / visual.confirm / visual.generate / visual.qa
    tool_version: str
    input_json: Text
    output_json: Text
    status: str
    latency_ms: int
    created_at
```

### 7.3 服务职责

| 服务 | 职责 | 禁止 |
| --- | --- | --- |
| `decision.py` | 判断是否生成视觉卡 | 不调用图像模型 |
| `brief_builder.py` | 生成结构化 brief | 不直接调用图像模型 |
| `job_service.py` | 创建、推进、查询 job 状态 | 不拼模型 prompt |
| `prompt_builder.py` | 将 brief 转成 `gpt-image-2` prompt | 不做安全最终裁决 |
| `image_client.py` | 直接调用 `gpt-image-2` 并返回图片结果 | 不处理业务安全 |
| `qa_gate.py` | 检查安全、准确性、可发送边界 | 不写入素材库 |
| `storage_bridge.py` | 上传七牛/本地、转素材库 | 不生成内容 |
| `audit.py` | 写 trace、job、feedback | 不参与业务决策 |

### 7.4 图像模型接入

正式口径：本轮开发直接调用 OpenAI `gpt-image-2` 生成图片直出。代码里仍保留配置项，便于环境切换、灰度和审计，但默认模型就是 `gpt-image-2`，不规划 fallback 模型作为 MVP 主路径。

```python
ai_visual_enabled: bool = False
ai_visual_provider: str = "openai"
ai_visual_model: str = "gpt-image-2"
ai_visual_generation_strategy: str = "direct_image"
ai_visual_auto_generate_confidence: float = 0.80
ai_visual_manual_confirm_confidence: float = 0.45
ai_visual_max_jobs_per_session: int = 2
ai_visual_generation_timeout_seconds: int = 120
ai_visual_auto_sendable: bool = False
```

`ai_visual_model` 不应在业务代码里散落硬编码；只允许 `image_client.py` 从配置读取。`gpt-image-2` 生成失败时，MVP 只标记 job failed 并允许重试，不自动降级到其他模型，避免不同模型输出风格和安全表现漂移。

### 7.5 异步执行方式

MVP 可先用后台任务：

```text
visual decision
  ↓
高置信：create job / 低置信：等待前端确认
  ↓
asyncio.create_task / ThreadPool
  ↓
status endpoint + SSE event
```

生产建议使用 Celery 或现有任务体系：

```text
visual decision
  ↓
高置信或教练确认后 create job
  ↓
Celery queue: ai_visual
  ↓
worker call gpt-image-2
  ↓
storage upload
  ↓
qa gate
  ↓
job ready
```

原因：

1. 图片生成可能 10-120 秒。
2. 需要重试、超时、限流。
3. 不能占住 Web worker。
4. 需要批量运营和失败恢复。

---

## 8. AI 对话链路集成

### 8.1 Chat Stream 中的接入点

建议在 `_prepare_ai_turn_cached` 完成后、模型调用前后都可以判断，但最佳位置是：

```text
RAG 检索完成
  ↓
Profile context ready
  ↓
Intent / Evidence 已知
  ↓
Visual Router 输出高/低置信决策
  ↓
高置信：创建 visual job（异步）
低置信：返回人工确认节点，不创建 job
  ↓
继续 model_call，不等待 visual job
```

这样 Visual Router 可以使用：

1. 原始用户问题。
2. scene_key。
3. RAG sources / recommended_assets。
4. Profile 安全信号。
5. 是否已有同主题素材。

### 8.2 SSE 事件扩展

建议新增事件：

| 事件 | 时机 | 示例 payload |
| --- | --- | --- |
| `visual_decision` | 判断完成 | `{need_visual, confidence, decision_mode, reason, topic}` |
| `visual_confirm_required` | 低置信需人工干预 | `{topic, confidence, confirm_question, safety_level}` |
| `visual_confirmed` | 教练确认绘制 | `{topic, confirmed_by, job_id?}` |
| `visual_declined` | 教练拒绝绘制 | `{topic, reason?}` |
| `visual_job` | job 创建 | `{job_id, status, topic}` |
| `visual_progress` | 生成中 | `{job_id, status, text}` |
| `visual_ready` | 图片可用 | `{job_id, asset_id, url, title, sendable}` |
| `visual_error` | 失败 | `{job_id, code, message}` |

如果 answer stream 已结束，前端可以通过二选一继续拿结果：

1. 保持 SSE 连接直到 visual job 结束。
2. answer stream 只返回 `visual_job`，前端轮询 `/api/v1/ai-visual/jobs/{job_id}` 或打开独立 SSE。

推荐 MVP 用轮询，生产用独立 SSE：

```text
answer stream: 负责文本体验
visual stream: 负责异步工具结果
```

### 8.3 前端消息类型

扩展 `AiChatMessage`：

```ts
type GeneratedVisualMessage = {
  role: 'reference'
  messageType: 'generated_visual'
  jobId?: string
  assetId?: string
  title: string
  topic: string
  status: 'manual_confirm_required' | 'queued' | 'generating' | 'qa_pending' | 'ready' | 'failed' | 'manual_declined'
  confidence?: number
  confirmQuestion?: string
  previewUrl?: string
  sendable: boolean
  safetyLevel: string
  evidenceSummary?: string
  errorMessage?: string
}
```

展示顺序建议：

```text
用户问题
RAG 参考话术
AI 正式回复
AI 生成知识卡片（生成中 -> 已生成）
RAG 推荐素材
```

也可根据体验调整为：

```text
用户问题
AI 正式回复
可发送内容区：
  - 客户话术
  - 低置信生图确认
  - 生成知识卡
  - 推荐素材
  - 参考话术
```

### 8.4 发送中心集成

发送中心需要支持三类来源：

| 来源 | 发送类型 | 前置条件 |
| --- | --- | --- |
| assistant txt 话术 | markdown/text | 已生成 |
| rag_attachment | image/file/material | `customer_sendable=true` |
| generated_visual | image/material | `sendable=true` 且 QA 通过 |

生成图片进入发送中心时，建议先转成素材：

```text
generated_visual asset
  ↓
save_as_material
  ↓
material_id
  ↓
send_center prefill
```

这样发送中心不需要支持临时图片 URL，后续也能追踪发送记录。

---

## 9. 安全与真值规则

### 9.1 医疗安全边界

禁止生成：

1. 个体化药物剂量图。
2. 停药、换药、减药指导图。
3. 疾病诊断结论图。
4. 使用客户隐私数据的对外图片。
5. 强承诺疗效的图片，例如“保证降糖”“一定瘦”。
6. 将 support evidence 写成 official conclusion 的图片。

高风险问题处理：

```text
用户问：二甲双胍能不能停？
  ↓
不生成“停药指导图”
  ↓
可生成“用药问题请医生确认”的安全边界卡，但默认需要人工审核
```

说明：这里的“人工审核”和低置信“人工干预节点”不是一回事。低置信人工干预解决“是否要画图”；医疗敏感人工审核解决“生成后是否可发送”。前者发生在创建 job 前，后者发生在 QA Gate 后。

### 9.2 客户隐私保护

生成图片 prompt 中默认不包含：

1. 客户真实姓名。
2. 手机号、openid、unionid。
3. 具体病历细节。
4. 精确体重/血糖/用药记录。
5. 群名、教练姓名等内部运营信息。

如需个性化，只使用抽象化描述：

```text
错误：张三最近空腹血糖 8.7，出差三天，给她画一张图。
正确：面向控糖/减重用户，出差外食场景，画一张通用饮食选择科普卡。
```

### 9.3 生成素材状态

| 状态 | 是否可发客户 | 说明 |
| --- | --- | --- |
| `candidate` | 否 | 系统生成候选 |
| `qa_passed` | 可配置 | 机器门禁通过 |
| `coach_approved` | 是 | 教练确认可发送 |
| `material_approved` | 是 | 管理员沉淀为正式素材 |
| `rejected` | 否 | 不得进入发送中心 |

默认建议：

```text
MVP：QA 通过后给教练预览，教练手动发送
正式：高置信低风险卡可自动异步生成并进入预览；是否直接 sendable 仍由 QA Gate、业务配置和教练确认共同决定。医疗敏感卡需人工确认。
```

---

## 10. 与 RAG/素材库的关系

### 10.1 三类内容必须区分

| 类型 | 来源 | 身份 | 是否可复用 |
| --- | --- | --- | --- |
| `rag_reference` | 话术/知识库 | support/formal knowledge | 可复用 |
| `rag_attachment` | 素材库 | formal/candidate material | 可复用 |
| `generated_visual` | 本次异步生成 | candidate visual asset | 通过审核后可复用 |

### 10.2 生成图反哺素材库

当教练点赞或发送后：

```text
generated_visual
  ↓
保存为 Material
  ↓
补充 rag_meta_json
  ↓
进入 material RAG index
  ↓
下次同类问题优先召回库存素材
```

这形成闭环：

```text
没有素材 -> 生成候选图 -> 教练使用 -> 沉淀素材 -> 下次复用 -> 减少生成成本
```

### 10.3 避免重复生成

新增主题指纹：

```text
visual_topic_key = hash(intent_domain + topic + audience + safety_level + evidence_hash)
```

生成前先查：

1. 是否已有 approved material。
2. 是否已有同 session 的 ready visual。
3. 是否有近 7 天相同 topic 的缓存图。

命中则返回已有素材，不重复生成。

---

## 11. 阶段开发计划

### Phase 0：总体协议与真值修正，1-2 天

目标：先把边界定清楚，并把本轮新增能力正式纳入 Agent 化底座，避免后续实现跑偏。

任务：

1. 明确 `generated_visual` 消息协议。
2. 补齐 `AiStreamEvent` 类型中的 `progress`，并预留 `visual_*`。
3. 在 AI 对话文档中统一三类 reference：RAG 话术、RAG 素材、AI 生成图。
4. 配置项预留：`ai_visual_enabled=false`、`ai_visual_model=gpt-image-2`、高/低置信阈值。
5. 建立 visual safety 规则清单。
6. 建立最小 Agent Tool Registry 骨架，让 RAG、Profile、Visual Decision、Visual Generation 按工具身份被 orchestrator 调用。

验收：

1. 不改主业务行为。
2. 类型、文档、真值口径一致。
3. 不把 generated visual 写成 formal material。
4. 新增功能从一开始就进入 Agent trace，不再作为散落在 chat service 里的临时代码。

### Phase 1：Visual Intent Router + 人工干预节点，3-5 天

目标：先让系统判断哪些问题适合可视化，并把高置信自动生成、低置信询问教练的分流跑通。

后端：

1. 新建 `app/ai_visual/services/decision.py`。
2. 规则版 Visual Router：
   - 饮食/出差/外卖/控糖/运动/知识点/术语解释 -> 候选。
   - 药物剂量/急性风险/客户事实查询 -> 不生成。
3. 输出 `decision_mode=auto_async_generate / manual_confirm / no_visual`。
4. answer stream 返回 `visual_decision` 和必要时的 `visual_confirm_required`。
5. 写入 `AiAgentTrace` 或临时 audit log。

前端：

1. 增加 `generated_visual` 消息类型。
2. 高置信时展示“正在生成知识卡片”占位。
3. 低置信时展示“是否需要绘制图片？”确认节点。
4. 本阶段不调用图片模型。

验收问题：

| 输入 | 期望 |
| --- | --- |
| `用户要出差了，推荐下餐食` | `need_visual=true`，`decision_mode=auto_async_generate` |
| `PHGG怎么服用？` | `need_visual=true`，`decision_mode=manual_confirm`，safety_level=medical_sensitive |
| `她今年几岁？` | `need_visual=false` |
| `二甲双胍能不能停？` | `need_visual=false` 或 boundary card candidate |

### Phase 2：异步 Job + gpt-image-2 直出 + 存储预览，1-2 周

目标：跑通“高置信自动创建任务 / 低置信确认后创建任务 -> 直接调用 `gpt-image-2` -> 存储 -> 前端预览”的最小闭环。

后端：

1. 新建 `ai_visual_jobs`、`ai_visual_assets` 表。
2. 实现 `job_service.py`。
3. 实现 `brief_builder.py`。
4. 实现 `prompt_builder.py`，把 brief 转成 `gpt-image-2` prompt。
5. 实现 `image_client.py`，直接调用 `gpt-image-2`，模型名从配置读取。
6. 实现 `storage_bridge.py`，复用现有 storage facade。
7. 新增接口：
   - `POST /api/v1/ai-visual/jobs`
   - `GET /api/v1/ai-visual/jobs/{job_id}`
   - `POST /api/v1/ai-visual/jobs/{job_id}/regenerate`
   - `POST /api/v1/ai-visual/jobs/confirm`

前端：

1. `generated_visual` 卡片显示状态。
2. 低置信确认后调用 confirm 接口创建 job。
3. 轮询 job 状态。
4. ready 后展示图片。
5. 支持重新生成、隐藏、反馈。

验收：

1. answer stream 不等待图片生成。
2. 图片生成失败时文本回答不失败。
3. 图片 URL 可访问。
4. job 状态可恢复。
5. `model_name` 记录为 `gpt-image-2`。

### Phase 3：QA Gate + 发送中心闭环，1-2 周

目标：让图片真正可发客户，而不是只能预览。

后端：

1. `qa_gate.py` 校验：
   - 是否包含禁用医疗承诺。
   - 是否出现错误数字/剂量。
   - 是否使用客户隐私。
   - 是否与 brief 不一致。
2. `save_as_material` 能把图片沉淀进素材库。
3. 生成图进入 RAG material index。
4. 记录 QA 结果、教练确认、发送结果，避免 candidate 被误写成 formal。

前端：

1. generated visual 支持“发送到发送中心”。
2. 支持“保存到素材库”。
3. 支持反馈：不准确/不好看/不相关/文字错/有风险。

验收：

1. 出差餐食卡片可进入发送中心作为 image 消息。
2. 医疗敏感卡默认不可直接发送，需教练确认。
3. 已保存素材下次可被 RAG 推荐。

### Phase 4：Agent Tool Registry + 证据链闭环，2-3 周

目标：在 Phase 0 的最小 Agent 工具骨架上，把可视化生成扩展为完整可审计的 Agent 工具体系。

任务：

1. 建立 `app/agents/` 或统一 tool registry。
2. RAG、Profile、Term Knowledge、Visual Generation 全部注册为工具。
3. 新增 `ai_agent_traces`。
4. 将 `knowledge_gaps`、`visual_feedback`、`message_feedback` 串成运营看板。
5. 增加离线评估集：
   - 是否应该画图。
   - 图片内容是否安全。
   - 图片是否比库存素材更值得推荐。

验收：

1. 每次工具调用可追踪。
2. 每张图能追踪到问题、证据、brief、模型、审核结果。
3. 高频生成主题能沉淀为正式素材。
4. 新增一个工具不需要改主回答流。

### Phase 5：可选迁移到 Responses/Agents SDK

目标：当现有自研工具链稳定后，再评估平台级 Agent 能力。

可选迁移点：

1. 使用 Responses API 的 tool calling 编排部分工具。
2. 评估是否只迁移编排层；图片生成默认仍走本地 `image_client.py` 直接调用 `gpt-image-2`，除非后续另有正式决策。
3. 使用 Agents SDK 做 trace、handoff、stream。
4. 保留本地安全门禁和素材库，不把治理完全交给模型。

原则：

1. 不为追新而迁移。
2. 先把业务闭环做稳。
3. 如果迁移，先迁 Visual Lane，不动主回答链路。

---

## 12. 验收标准

### 12.1 功能验收

| 用例 | 期望 |
| --- | --- |
| `用户要出差了，推荐下餐食` | 文本回答正常；高置信自动异步生成出差外食知识卡；RAG 话术和素材仍返回 |
| `PHGG怎么服用？` | 回答先解释术语；低置信/医疗敏感时前端询问是否绘制图片；边界明确 |
| `她最近血糖怎么样？` | 不生成图；优先读取客户数据 |
| `低血糖有哪些表现？` | 可进入人工确认或生成安全边界科普卡，但不替代医生建议 |
| `二甲双胍能不能停？` | 不生成停药指导图；输出医生确认边界 |

### 12.2 技术验收

1. 主 answer stream 首 token 不因图片生成增加明显延迟。
2. 图片任务失败不影响文本回答。
3. 每个 job 有完整状态机。
4. 图片存储走现有 storage facade。
5. 生成图可转 Material 并进入发送中心。
6. 前端历史会话能恢复 generated visual 状态。
7. `AiStreamEvent`、前端 `StreamPayload`、后端 SSE 事件保持一致。
8. `gpt-image-2` 是图片生成默认模型，模型名、prompt hash、brief 和 evidence 可审计。
9. 高置信自动异步生成，低置信不创建 job，必须经前端确认后才生成。

### 12.3 安全验收

1. 不把客户隐私写入图片。
2. 不生成个体化药物剂量图。
3. 不生成诊断结论图。
4. 医疗敏感卡默认需要教练确认。
5. 生成图片的 brief、prompt、证据、模型名、审核状态可审计。

### 12.4 闭环验收

1. 教练能对生成图点赞/点踩。
2. 点赞高、发送多的图能沉淀为素材。
3. 点踩原因能进入优化队列。
4. 高频生成主题能被识别为“应制作正式素材”的运营任务。
5. 已有正式素材时优先复用，不重复生成。

---

## 13. 风险与对策

| 风险 | 表现 | 对策 |
| --- | --- | --- |
| 图片中文字不准 | 中文乱码、错字、漏字 | `gpt-image-2` 直出后走 QA Gate；失败则 rejected/重试，不自动进入发送中心 |
| 医疗风险 | 生成过度确定的健康建议 | visual safety gate + 医疗敏感默认人工确认 |
| 成本升高 | 同类问题重复生成 | topic hash 去重 + 素材库复用 |
| 延迟变长 | answer 等图片 | 图片流异步，不阻塞 answer |
| 素材污染 | 未审核图进入素材库 | candidate/approved 分层，默认不自动 formal |
| 前端混乱 | 文本、素材、图混在一起 | messageType 明确区分 |
| 审计缺失 | 不知道图怎么来的 | `ai_visual_jobs` + `ai_agent_traces` |
| prompt 注入 | RAG/外部内容影响图 | brief 结构化，外部内容只作为 support evidence |
| 法务/版权风险 | 模仿特定品牌/人物 | 禁止仿品牌/名人风格，使用原创健康科普风格 |
| 误触发 | 不该画图却自动生成 | 置信度阈值 + 低置信人工干预节点 + 反馈回调阈值 |

---

## 14. 面向项目负责人的状态翻译

### 看见

现在教练已经可以问 AI，AI 能给文本回答、客户话术、RAG 参考语料和部分素材推荐。但如果教练想把一个知识点讲得更容易懂，系统还不能自动生成一张可发给客户的图文卡片。

### 理解

健康教练真正需要的是“把知识讲清楚并交付给用户”。文字回答解决了教练理解问题，图文卡片解决用户吸收问题。AI 对话下一步要从“会说”变成“会准备交付素材”。

### 决策

不要让主回答流直接等图片生成。正确做法是把图片生成做成异步工具：

```text
文本回答马上给
高置信图片卡片后台自动生成
低置信图片卡片先问教练是否需要绘制
生成好后作为可发送素材回到对话
用过的好图沉淀进素材库
```

实现上，本轮直接调用 `gpt-image-2` 直出图片，不再把模板渲染作为主路径。

### 闭环

这条链路闭环后，系统会越来越省力：

1. 第一次没有素材，AI 生成候选图。
2. 教练觉得好，发送并保存。
3. 系统沉淀为素材库。
4. 下次同类问题优先推荐库存素材。
5. 不好的图被点踩，回流优化 prompt、brief 和 QA 规则。
6. 低置信问题会先走前端人工干预节点，而不是盲目自动生图。

### 当前 blocker

1. 还没有 `ai_visual` 模块和生成任务表。
2. 还没有 Visual Intent Router 的高/低置信分流。
3. 还没有直接调用 `gpt-image-2` 的图像生成模型封装。
4. 还没有生成图的 QA Gate。
5. 还没有 generated visual 与发送中心/素材库的正式协议。
6. 还没有最小 Agent Tool Registry 和工具调用 trace。

### 是否偏离蓝图

没有偏离。从本文档涉及的待开发功能开始，AI 对话正式进入 Agent 化演进：新能力先被定义为工具、任务和 trace，再接入主对话。关键是不要为了“看起来像 Agent”而推倒重来，应先做清楚工具边界、异步任务、审计链和素材闭环。

### 下一步最值得推进

1. 先做 Phase 0：统一协议、真值、配置、事件类型和最小 Agent Tool Registry。
2. 再做 Phase 1：Visual Intent Router，完成高置信自动生图、低置信前端确认。
3. 然后做 Phase 2：异步生成 job，直接调用 `gpt-image-2`，跑通图片生成和预览。
4. 最后做 Phase 3：QA Gate、发送中心、素材库闭环。

---

## 15. 文件变更建议清单

### 后端新增

| 文件/目录 | 类型 | 说明 |
| --- | --- | --- |
| `app/ai_visual/` | 新模块 | 视觉知识卡生成能力 |
| `app/ai_visual/models.py` | 新增 | job、asset、feedback 表 |
| `app/ai_visual/router.py` | 新增 | 路由聚合器 |
| `app/ai_visual/routers/jobs.py` | 新增 | job 创建/查询/重试 |
| `app/ai_visual/routers/assets.py` | 新增 | asset 查询/保存为素材 |
| `app/ai_visual/schemas/jobs.py` | 新增 | 请求响应结构 |
| `app/ai_visual/services/decision.py` | 新增 | 是否生成图、以及高/低置信分流 |
| `app/ai_visual/services/brief_builder.py` | 新增 | visual brief |
| `app/ai_visual/services/prompt_builder.py` | 新增 | brief 转 prompt |
| `app/ai_visual/services/image_client.py` | 新增 | `gpt-image-2` 直出封装 |
| `app/ai_visual/services/qa_gate.py` | 新增 | 安全准确性检查 |
| `app/ai_visual/services/storage_bridge.py` | 新增 | 接入 storage/material |

### 后端修改

| 文件 | 修改 |
| --- | --- |
| `app/main.py` | include `ai_visual.router` |
| `app/config.py` | 增加 `ai_visual_*` 配置（模型、阈值、开关） |
| `app/crm_profile/services/ai/_types.py` | `AiStreamEvent` 增加 `progress`、`visual_*` |
| `app/crm_profile/services/ai/__init__.py` | 输出 visual decision，创建异步 job，不等待结果 |
| `app/rag/retriever.py` | generated visual 入库后可作为 material 召回 |
| `app/models.py` | 确保新表注册 |

### 前端修改

| 文件 | 修改 |
| --- | --- |
| `frontend/src/views/CrmProfile/composables/aiCoachTypes.ts` | 增加 `generated_visual` 类型 |
| `frontend/src/views/CrmProfile/composables/useAiCoach.ts` | 处理 `visual_*` 事件 |
| `frontend/src/views/CrmProfile/composables/useAiVisualTasks.ts` | 新增 job 轮询/状态管理 |
| `frontend/src/views/CrmProfile/components/AiCoachVisualMessage.vue` | 新增视觉卡片消息组件 |
| `frontend/src/views/CrmProfile/components/AiCoachMessageList.vue` | 渲染 generated visual |
| `frontend/src/views/CrmProfile/components/AiCoachPanel.vue` | 发送中心入口接入 |
| `frontend/src/views/SendCenter/` | 支持 generated visual prefill |

---

## 16. 参考资料

1. OpenAI Image generation 文档：`https://platform.openai.com/docs/guides/image-generation`  
   要点：Image generation 适合单次图片生成/编辑；本项目正式口径是直接调用 `gpt-image-2` 直出，后续如需编排层再评估 Responses/Agents SDK，不把模板渲染作为主路径。

2. OpenAI Responses API 文档：`https://platform.openai.com/docs/api-reference/responses/create`  
   要点：Responses 是面向状态、多模态、工具调用的接口，可使用 web search、file search、image generation 等工具。

3. OpenAI Agents SDK 文档：`https://platform.openai.com/docs/guides/agents-sdk/`  
   要点：Agents SDK 面向可使用工具、上下文、handoff、stream、trace 的 Agent 应用。

4. OpenAI Web search 文档：`https://platform.openai.com/docs/guides/tools-web-search`  
   要点：支持 web search 工具、来源、域名过滤等能力；本项目如接外部搜索，应走白名单和 evidence 分级。

---

## 17. 最终目标

这次优化的最终目标不是“AI 会画图”，而是：

```text
教练提出一个管理场景
  ↓
AI 判断用户需要理解什么知识
  ↓
AI 用文本帮助教练判断
  ↓
AI 用话术帮助教练沟通
  ↓
AI 用知识卡帮助用户吸收
  ↓
系统用素材库和反馈让下次更快更准
```

这才是符合当前主流 Agent 构建路径的演进：先把业务工具做清楚，再把工具纳入可审计的编排闭环，最后再让模型获得更多自主规划能力。
