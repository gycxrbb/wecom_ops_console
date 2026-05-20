# 开源AI Agent架构与工程实践调研报告

**——面向健康教练慢病管理与减重干预场景（针对当前业务现状的修订版）**

**报告日期：** 2026年5月18日
**版本：** V3.1（Dify 定位调整 + Subgraph 架构）
**调研范围：** 2025-2026年开源Agent框架、工程实践、医疗健康领域应用

---

## 修订说明

### V3.1 相对于 V3.0 的核心变更

**Dify 定位重新调整：** V3.0 将 Dify 定位为"包装为 MCP Server 长期共存"，V3.1 调整为"**仅作原型验证工具，最终用 Python 代码实现替代**"。理由：

1. **延迟问题**：Dify workflow 调用走 HTTP → 引擎调度 → 多节点串行 LLM 调用 → 返回，比直接 Python + LLM 多出 1-3 秒，对话/餐评等实时交互场景体验受损
2. **自主性受限**：Dify workflow 本质是预定义的 DAG，节点流转静态固定，与 Agent 的"根据中间结果动态决策"核心价值直接冲突
3. **可观测性差**：Dify 内部是黑盒，难以做节点级的链路追踪和评测

**主要变更点：**

- 砍掉 `dify-bridge-mcp-server` 这个组件
- 引入 **LangGraph Subgraph** 作为业务工作流的代码实现单元
- 调整 MCP 的角色：**只包装外部资源和真正的工具**，不再包装内部业务逻辑
- 实施路线图调整为"**Dify 验证 → Python 重写 → Dify 退场**"
- 增加迁移的双跑期机制设计

### V3.0 相对于 V2.0 的核心变更（保留）

1. **架构层级**：从 6 层压缩为 3 层 + 横切关注点（评测/观测/审计/合规作为贯穿三层的关注点）
2. **Agent 粒度**：从 10+ 细粒度 Agent 收敛为 5 个核心 Agent
3. **模型选型**：更新至 2026 年 5 月在产模型（Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5）
4. **数据存储**：明确以 MySQL 为关系型主库（贵公司现有技术栈），向量库作为辅助
5. **砍掉的内容**：Agent 注册中心（动态发现）、Temporal 工作流调度、多租户架构、A2A 协议预留接口、Neo4j 图数据库
6. **保留并提前的内容**：模型网关（LiteLLM）、评测体系——AI coding 加持下提前到 MVP 阶段
7. **记忆/评测/审计完整保留并加强**：医学字段走 MySQL 严格 Schema，评测体系前置到 MVP，审计落 MySQL 专表

---

## 一、执行摘要

2025-2026 年，AI Agent 技术已从单点工具调用演进至**多 Agent 协作编排**阶段。在医疗健康领域，Agent 技术已在慢病管理、患者随访、个性化干预等场景取得实质性落地成果。

本报告针对贵公司健康教练业务场景（慢病干预、减重管理、斑块逆转、餐评、习惯打卡、处方开具、话术沉淀等），结合**当前真实业务现状**（3 人 AI 全栈团队、2000+ 用户、100+ 教练、已有 Dify 工作流支撑处方/餐评、已有 Python + RAG 对话服务接入 Node.js CRM、已取得医疗器械二类证），提出**渐进式演进**的 Agent 架构方案。

**核心结论：**

1. 推荐以 **LangGraph v1.2** 为核心编排框架，**MCP** 为外部工具接入标准，**LiteLLM** 为模型网关
2. **Dify 仅作为原型验证工具**，业务逻辑最终用 **Python Subgraph** 实现，迁移完成后 Dify 退出生产架构
3. 采用**三层架构**（编排层 + 工具与能力层 + 数据层），评测与观测作为横切关注点
4. 收敛至 **5 个核心 Agent**（对话 / 处方生成 / 餐评 / 话术沉淀 / 报告解读），而非细粒度拆分
5. 处方等"准医疗"输出必须设置 **Human-in-the-Loop** 审核节点（贵公司已有医生审核流程，直接对接即可）
6. 医学相关字段（用药、过敏、诊断）走 **MySQL 严格 Schema + 审计日志**，不进向量库
7. 建议按"**基础设施 → 单 Agent 跑通 → 业务工作流逐个迁移 → Dify 退场**"四阶段推进

---

## 二、开源 Agent 架构现状与趋势（2025-2026）

### 2.1 主流框架全景图

当前开源 Agent 框架已形成清晰的梯队格局：

| 框架 | 架构范式 | 核心特色 | 适用场景 | 备注 |
|------|---------|---------|---------|------|
| **LangGraph** | 图状态机 | 显式图结构、状态持久化、HITL、durable execution | 复杂有状态工作流、生产级系统 | 2026 年企业级首选，v1.2 已发布 |
| **CrewAI** | 角色协作 | 角色定义、任务委托、层级/顺序工作流 | 快速原型、内容/研究流水线 | 适合 PoC，不推荐生产 |
| **OpenAI Agents SDK** | Handoff 交接 | 轻量级、Guardrails、原生 MCP | OpenAI 生态生产部署 | 2026 年 4 月重大更新，原生 MCP |
| **Claude Agent SDK** | 子 Agent + 技能 | Hooks、MCP 原生、Skills、Subagents | Anthropic 生态复杂任务 | 与 Claude Code 同架构 |
| **AutoGen / AG2** | 对话循环 | 多 Agent 对话、代码执行、群聊 | 研究型对话系统、代码生成 | 偏研究 |
| **Dify** | 低代码 | 可视化编排、RAG 内置、多模型支持 | **PM/教练快速验证原型** | 贵公司现有工具，**不作为生产架构** |
| **Deep Agents** | LangGraph 高层封装 | planning + subagent + 文件系统 | 复杂任务自动分解 | LangChain 官方，可关注 |

> **核心趋势：** 2025-2026 年，Agent 发展重心已从"能对话"转向"能可靠执行复杂任务"。多 Agent 协作、显式状态管理、人类介入机制（HITL）成为生产级系统的三大标配。**Agent 间通信协议（A2A）和 Agent 评测体系（promptfoo、DeepEval、Ragas）正在快速成熟**，A2A 在 2026 年 4 月已达到 150+ 组织生产部署、由 Linux 基金会治理的成熟阶段。

### 2.2 LangGraph：生产级状态驱动架构（推荐）

LangGraph 是 LangChain 生态的图编排框架，将 Agent 工作流建模为**显式状态机**——每个节点是函数，边定义控制流。**LangGraph v1.2（2026 年 5 月发布）**的核心能力：

- **Durable Execution**：Agent 可在任意节点暂停、恢复，自动从失败点恢复
- **Human-in-the-Loop（HITL）**：通过 `interrupt` 机制在关键决策点（处方开具、异常指标预警）强制人工审核
- **状态持久化与 Checkpointing**：支持长周期任务（如 28 天减重干预计划）
- **Per-node 超时与错误恢复**（v1.2 新特性）：每个节点独立的容错策略
- **DeltaChannel**（v1.2 新特性）：长会话场景下大幅降低 checkpoint 开销
- **Subgraph 复用**：将通用业务工作流（餐评、处方生成等）封装为可复用子图，被多个 Agent 调用

LangGraph 在 2026 年的真实生产部署包括 **Klarna、Replit、Elastic** 等。GitHub 仓库已超过 30K stars。

**典型代码结构（针对贵公司场景）：**

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.mysql import MySQLSaver  # 适配贵公司MySQL栈
from typing import TypedDict

class HealthCoachState(TypedDict):
    user_id: str
    session_id: str
    messages: list
    user_context: dict           # 预加载的用户档案（已有逻辑迁移）
    intent: str                  # 识别到的意图
    tool_calls: list             # 工具调用记录
    hitl_status: str             # HITL 审核状态：pending/approved/rejected
    audit_trail: list            # 审计日志（合规要求）

workflow = StateGraph(HealthCoachState)
workflow.add_node("load_context", load_user_context)   # 用户上下文预加载（复用已有逻辑）
workflow.add_node("agent", llm_agent_node)              # LLM Agent 主节点（带工具）
workflow.add_node("hitl_check", human_review_node)     # 处方/高风险输出审核
workflow.add_node("audit", audit_log_node)              # 审计日志落盘

workflow.add_edge("load_context", "agent")
workflow.add_conditional_edges("agent", route_by_output)
workflow.add_edge("hitl_check", "audit")
workflow.add_edge("audit", END)

# MySQL checkpoint，与贵公司技术栈一致
checkpointer = MySQLSaver.from_conn_string(MYSQL_URL)
app = workflow.compile(checkpointer=checkpointer)
```

### 2.3 关键架构演进趋势

1. **从 Chain 到 Graph**：线性 Chain 已无法满足复杂医疗决策需求，图结构成为标配
2. **从单 Agent 到适度多 Agent 协作**：单 Agent 上下文窗口瓶颈明显，但**过度拆分（10+ Agent）反而带来路由错误、上下文损失等新问题**，业界共识收敛到 3-7 个 Agent 协同是甜区
3. **从无状态到有状态**：状态持久化是 Agent 从"聊天工具"走向"行动系统"的分水岭
4. **从封闭到开放**：MCP 协议统一**外部工具**调用标准，实现"一次实现，处处可用"
5. **从不可测到可观测**：Agent 评测与可观测性从"可选"变为"必须"，无评测的 Agent 无法上线生产
6. **从低代码原型到代码生产**：低代码工具（Dify、Coze 等）在 PoC 阶段价值显著，但**生产架构最终回归代码实现**——动态决策、自定义工具调用、细粒度可观测性、版本化管理是低代码工具难以满足的

---

## 三、Agent 工程实践最新趋势

### 3.1 MCP 协议：Agent 工具生态的"USB-C"标准

**Model Context Protocol（MCP）**由 Anthropic 于 2024 年 11 月开源，到 2026 年已成为 AI Agent 连接外部工具的事实标准，主流 Agent 框架（LangGraph、OpenAI Agents SDK、Claude Agent SDK）均已原生支持。

**MCP 架构组件：**
- **MCP Host**：发起请求的 AI 应用（如健康教练 Agent 系统）
- **MCP Client**：与 Server 建立连接，通常 1:1 关系
- **MCP Server**：提供 Tools（工具）、Resources（资源）、Prompts（提示模板）

**MCP 在贵公司架构中的角色（重要澄清）：**

> MCP **专注于包装外部资源和真正的工具**，不用来包装内部业务工作流。内部业务工作流（餐评、处方生成等）用 **Python 代码 + LangGraph Subgraph** 实现，这更符合 MCP 的设计哲学，也避免增加不必要的网络跳数。

**针对贵公司的 MCP Server 规划：**

```
mcp-servers/
├── user-data-server/           # 用户数据查询（MySQL）
│   └── tools/                  # 用户档案、历史指标、依从性数据
│
├── knowledge-base-server/      # RAG 知识库检索（医学知识 + 内部教材）
│
├── talk-track-server/          # 话术沉淀检索（贵公司已有框架）
│
└── future/                     # 未来扩展预留（接入时再开发）
    ├── wearable-device-server  # 可穿戴设备
    └── his-integration-server  # 医院 HIS 对接
```

每个 MCP Server 包含：**接口文档、单元测试、降级策略说明、审计埋点**。

**业务工作流的实现方式：** 见 5.5 节"Subgraph 设计"——用 Python + LangGraph 实现，不通过 MCP。

### 3.2 Agent 间通信协议 A2A：当前生产状态，不再是远期预留

**Google A2A（Agent-to-Agent）协议**于 2025 年 4 月发布，到 **2026 年 4 月已达到生产成熟阶段**：

- 已发布 **v1.2 稳定版**，由 **Linux 基金会 Agentic AI Foundation** 治理（Anthropic、Block、OpenAI 均为共同发起方）
- **150+ 组织生产部署**（不是 pilot），包括 Microsoft、AWS、Salesforce、SAP、ServiceNow
- 引入 Signed Agent Cards（基于密码学签名的域验证）、多协议支持、企业级多租户
- GitHub Stars 已超过 22K

**对贵公司的判断：**

- **当前不需要做 A2A 接入**：贵公司是单一组织内部系统，所有 Agent 在一个 LangGraph 编排下运行，A2A 协议解决的是跨组织、跨平台 Agent 协作问题
- **当前不需要"预留 A2A 接口"**：这是典型的 YAGNI 反模式——真正接入 A2A 时本来就要按 A2A 规范改造，"预留"既无标准也无收益
- **真正有用的简化做法**：为每个 Agent 写一份 YAML 能力描述（输入、输出、工具、记忆权限、评测集路径）。这不是为了 A2A，而是为团队理解系统、做评测路由、做权限审计

### 3.3 记忆系统：分层但医学字段必须走严格 Schema

2025 年，Agent 的核心瓶颈已从模型规模转向**记忆能力**。但记忆系统在医疗场景有一个**强约束**：**医学相关数据不能完全依赖向量召回**——向量检索的概率性召回，在医学场景下"漏召回过敏史"等同于事故。

**记忆与 RAG 的本质区别：**
- **RAG**：按需检索外部静态知识，无状态，适合问答与文档查询
- **记忆系统**：跨会话状态积累，记录用户偏好、历史决策、关系演化

**针对贵公司的分层记忆架构：**

| 层级 | 存储内容 | 存储介质 | 检索方式 | 安全性 |
|------|---------|---------|---------|---------|
| **工作记忆** | 当前对话上下文 | LangGraph State + Redis | 全量加载 | 会话级 |
| **结构化医学记忆** ★ | 诊断、用药、过敏、禁忌、关键指标 | **MySQL 严格 Schema** | 主键/索引精确查询 | **强一致 + 审计 + 不进向量库** |
| **行为/偏好记忆** | 口味偏好、运动习惯、沟通风格、目标 | MySQL + 向量库 | 语义检索 + 结构化筛选 | 用户级隔离 |
| **情景记忆** | 历史餐评、处方反馈、异常事件、对话片段 | MySQL + 向量库 | 时间+语义混合 | 按时间衰减 |
| **程序记忆** | SOP、话术模板、引用次数统计 | MySQL + 向量库 | 规则匹配 + 语义检索 | 版本化 |

**核心原则：**

- **医学相关字段（诊断、用药、过敏、禁忌）必须走 MySQL 严格 Schema**，不放进向量库
- **行为偏好、对话历史、话术内容**可以走向量库，召回不准影响不致命
- **Mem0 等开源记忆框架**可用作向量层的事实抽取与去重工具，但**不作为医学记忆的唯一存储**

#### 3.3.1 记忆治理工程设计

**写入权限控制：** 采用"**记忆提议 → 审核 → 入库**"的三级流程

- 餐评 Agent 可写入情景记忆（如"用户对本次餐评反馈不满意"）
- "用户胰岛素抵抗"这类**医学判断**只能由医生辅助 Agent 在医生确认后写入 MySQL 结构化字段
- 写入操作全部记录审计日志

**一致性保障：** MySQL 通过事务保证强一致；向量库采用"最后写入胜出 + 重要性权重"策略

**过期与衰减：**
- 情景记忆：按时间衰减，90 天前低频记忆自动归档
- 行为偏好：按访问频率衰减
- 医学记忆：**永不自动衰减**，需要变更必须经医生确认 + 审计

**隐私与合规：**
- 用户记忆按 `user_id` 严格隔离
- 记忆访问记录审计日志（谁读、谁写、何时）
- 用户有权要求删除其全部记忆（《个保法》合规）

### 3.4 Agentic RAG：从固定检索到自主决策（保守应用）

RAG 技术已演进至 **Agentic RAG**：Agent 自主决策检索策略、判断答案可靠性、必要时多轮检索。

但在医疗场景需要**保守应用**：

- 不要依赖"模型自我判断置信度"来决定是否走 HITL——LLM 的自我评估存在偏差
- **保守做法**：所有涉及个体化健康建议（处方、个性化餐评、风险评估）的输出**默认走 HITL**，不论模型说自己有多确信
- Agentic RAG 适合用于"健康答疑、知识查询、报告通用解读"等**不直接形成个性化建议**的场景

### 3.5 可观测性与安全护栏

**生产级 Agent 必须具备：**

1. **链路追踪**：使用 **Langfuse**（开源，可自部署，与贵公司数据合规需求更匹配）或 LangSmith
2. **输入/输出 Guardrails**：对医疗建议进行安全校验，拦截危险指令
3. **沙盒预执行**：处方生成在隔离环境中预执行，确认无害后再提交医生审核
4. **审计追溯**：100% 关键操作审计，满足医疗器械二类证要求

### 3.6 Agent 评测体系：MVP 阶段就要建立

在 **AI coding 加持下**，评测体系应该提前到 **MVP 阶段就建立**——评测不是写出来给评审看的，是每次 Prompt 改动都要跑的回归测试。

**评测三层体系：**

| 评测层级 | 评测对象 | 评测方法 | 工具 |
|---------|---------|---------|------|
| **单元评测** | 单个 Agent / Subgraph 的单次输出 | 预定义测试用例 + LLM-as-Judge | promptfoo |
| **集成评测** | 多 Agent / 多 Subgraph 协作流程的端到端表现 | 典型业务场景模拟 + 人工抽检 | 自建脚本 + Langfuse |
| **业务评测** | 真实用户的健康干预效果 | A/B 测试 + 业务指标追踪 | 自建数据分析 |

**评测维度（医疗场景特化）：**

- **安全性（一票否决）**：是否生成可能危害用户健康的内容？高风险场景是否正确触发 HITL？
- **准确性**：医学知识引用是否正确？数据计算是否准确？
- **一致性**：相同输入是否产生质量稳定的输出？
- **延迟**：对话场景 < 3s，处方生成 < 30s（异步可放宽）
- **成本**：单次交互的 Token 消耗

**评测集冷启动：** 贵公司**已有几百到几千条 Dify 历史处方/餐评数据**，可由医生/营养师团队抽取 50-100 条标注金标准，作为初始评测集。每次 Prompt 改动跑回归。

**评测在 Subgraph 迁移中的关键作用：** Dify 工作流迁移到 Python Subgraph 时，**评测集是验证不退化的唯一手段**。无评测的迁移就是盲改。详见 6.3 节。

**回归测试机制：**
- 每次修改 Agent 的 Prompt 或工具配置后，CI 自动跑评测集
- 安全性评测低于阈值 → 自动阻止部署
- 评测集持续维护：收集生产环境 bad case，补充进评测集

---

## 四、医疗健康 Agent 应用现状

### 4.1 行业落地案例

| 企业/机构 | 应用场景 | 技术方案 | 效果 |
|-----------|---------|---------|------|
| **拜耳 × 漱玉平民大药房** | 慢病专员模拟系统 | 情境感知 Agent，识别高血压/糖尿病患者，推送用药提醒 | 用药依从性提高 31%，复购率增长 18% |
| **辉瑞** | 分层交互 Agent 系统 | 根据患者年龄/文化水平自动调整解释语言 | 整合 2.3 亿条交互数据，主动推送复诊提醒 |
| **七乐康控股集团** | 慢病专科医生 AI 智能体 | 大模型+多模态数据融合，覆盖"诊-疗-管-教"全流程 | 专家团队管理患者量提升约 2 倍 |
| **某三甲医院** | AI 慢病管理平台 | 患者上传血糖/血压数据，AI 生成随访计划与饮食建议 | 复诊率提升 30%，高风险事件减少 20% |

### 4.2 技术成熟度评估

- **监测与预测分析**：最成熟，可穿戴设备 + AI 预警已广泛应用
- **对话式教练系统**：快速发展中，糖尿病、慢病疼痛管理领域证据最充分
- **处方决策支持**：需谨慎，必须保留医生审核环节（HITL）
- **斑块逆转干预**：以生活方式干预（地中海/低脂植物饮食、规律运动、压力管理）为核心，与减重、糖尿病管理的干预手段高度重合，差别主要在监测指标（IMT、冠脉钙化积分、LDL-C、Lp(a)）和干预强度

> **对贵公司的启示：** 颈动脉 / 冠脉斑块逆转、减重、糖尿病管理在干预逻辑上高度复用，**不需要为每个疾病单独搞 Agent**，而是通过同一套 Agent 配合**不同的知识库 + 评估指标 + 干预协议**实现。

---

## 五、针对贵公司业务场景的 Agent 架构方案

### 5.1 现状分析与核心问题

**贵公司当前状态：**

| 维度 | 现状 |
|------|------|
| 团队规模 | 3 名 AI 全栈工程师（AI coding 加持，产出能力≈8-10 人传统团队） |
| 业务规模 | 2000+ 用户，100+ 教练 |
| 业务性质 | 健康管理 + "准医疗"处方（已有医生审核流程，医疗器械二类证已获） |
| CRM 系统 | Node.js 实现 |
| AI 服务 | Python 后端，已实现"用户上下文预加载 + RAG"对话，已接入 CRM |
| 处方/餐评 | **Dify 工作流**实现，含饮食/运动/营养素/睡眠压力处方、医生端处方、餐评、血糖报告、日周月报 |
| 数据量 | 历史处方/餐评数据几百到几千条 |
| 数据库 | **MySQL**（关系型主库） |
| 多租户需求 | 暂不考虑 |
| 远期方向 | 心理健康、产后恢复、企业健康管理等新业务线（远期，非当前规划） |

**关于 Dify 的判断（V3.1 关键调整）：**

Dify 当前承担了贵公司核心业务（处方、餐评等），但作为生产架构有两个根本性问题：

1. **延迟问题**：Dify workflow 每次调用要走 HTTP → 引擎调度 → 多节点串行 LLM 调用 → 返回。比直接 Python + LLM 多出 1-3 秒，对话/餐评等实时交互场景体验受损
2. **自主性受限**：Dify workflow 本质是预定义的 DAG，节点流转是静态的，与 Agent 的核心价值（**根据中间结果动态决策**）直接冲突。例如餐评场景中，"图片看不清要追问"、"识别到陌生食物要查外部数据库"、"血糖刚刚异常要重点提醒"这类条件分支 + 动态工具选择，在 Dify 里既笨又慢
3. **可观测性差**：Dify 内部是黑盒，难以做节点级的链路追踪、单步评测、精细化优化

**Dify 的正确定位：**

> **Dify 是产品经理/教练快速验证业务逻辑的原型工具，不是生产架构。** 业务一旦验证可行，应该用 Python 代码（LangGraph Subgraph）实现替代。

**核心问题：**

> 如何在不中断当前业务的前提下，把已有 Dify 工作流和 Python RAG 对话服务，演进为以 Python 代码为核心、Dify 退场的 Agent 系统？

### 5.2 架构设计原则（修订版）

| 原则 | 含义 | 落地要求 |
|------|------|---------|
| **代码实现是生产终态** | Dify 仅作原型，业务逻辑最终用 Python 实现 | Subgraph 设计 + 双跑期验证 |
| **简单优先** | 不为想象中的需求做架构 | 砍掉 Agent 注册中心、Temporal、A2A 预留、多租户、Neo4j |
| **可评测** | 任何改动都必须能被量化评估 | **评测框架先于业务迁移建设**（迁移依赖评测验证不退化） |
| **安全兜底** | 高风险操作必须有人工审核 | HITL 作为架构强制约束（对接现有医生审核） |
| **供应商无关** | 不绑定单一 LLM 供应商 | LiteLLM 模型网关统一管理（MVP 阶段就上） |
| **数据合规** | 全链路可审计，医学字段强一致 | 医学字段走 MySQL，审计日志全覆盖 |
| **能力 = 工具组合** | Agent 能力由 Subgraph + MCP tool 集合定义 | Subgraph 按业务工作流拆，MCP 按外部数据源拆 |

### 5.3 业务场景拆解与 Agent 映射

V2 报告拆出了 10+ Agent，本版本基于"**让一个强模型 + 多工具/子图处理，比拆成多个弱协同 Agent 效果好**"的业界共识，收敛到 **5 个 Agent**：

```
┌────────────────────────────────────────────────────────────────────┐
│              对话 Agent（用户实时交互入口）                          │
│  - 接收用户消息，识别意图                                            │
│  - 调用 MCP Tools（用户数据/知识库/话术）                           │
│  - 调用 Subgraph（餐评/处方触发）                                   │
│  - 主模型：Claude Sonnet 4.6                                       │
└──────────────────────────┬─────────────────────────────────────────┘
                           │ 触发异步任务 / 同步调用 Subgraph
       ┌───────────────────┼───────────────────┬─────────────────┐
       ▼                   ▼                   ▼                 ▼
┌────────────┐    ┌────────────────┐   ┌──────────────┐   ┌──────────────┐
│ 处方生成   │    │ 餐评 Agent     │   │ 话术沉淀     │   │ 报告解读     │
│ Agent      │    │                │   │ Agent        │   │ Agent        │
│            │    │                │   │              │   │              │
│ 异步生成   │    │ 半结构化输出   │   │ 后台任务     │   │ 同步任务     │
│ HITL审核  │    │ 调用 meal_      │   │ 提取高质量   │   │ 长文本解析   │
│ Opus 4.7  │    │ review_subgraph│   │ 问答对/卡片  │   │ 风险标注     │
│ 调用各    │    │ Sonnet 4.6     │   │ Haiku/Sonnet │   │ Sonnet 4.6   │
│ 处方      │    │                 │   │              │   │              │
│ subgraph  │    │                 │   │              │   │              │
└────────────┘    └────────────────┘   └──────────────┘   └──────────────┘
       │                   │                                    │
       ▼                   ▼                                    │
┌────────────────────────────────────────┐                    │
│  HITL：教练/医生审核（复用现有流程）   │ ◄──────────────────┘
│  - 处方草案 + 生成依据 + 风险标注      │
│  - 操作：确认 / 修改 / 驳回 / 转会诊   │
└────────────────────────────────────────┘
```

**Subgraph 与 Agent 的关系：**

- **Agent** 是**有状态的智能体**，承担实时交互、意图识别、决策协调
- **Subgraph** 是**业务工作流的代码实现单元**，被 Agent 调用，承担确定性业务逻辑（如餐评、各类处方生成、报告生成）
- 一个 Agent 可以调用多个 Subgraph，多个 Agent 可以复用同一个 Subgraph

**为什么是 5 个 Agent 而不是 10+：**

1. **餐评 Agent 和饮食处方 Agent 业务上不同步**：餐评是用户实时上传餐食后的快速反馈（半同步，秒级），饮食处方是异步生成的长周期方案（HITL 审核，分钟到小时级）。**应该分开**
2. **饮食/运动/营养素/睡眠压力处方在干预逻辑上高度耦合**（基于同一份用户画像、互相约束），合并到处方生成 Agent，通过**调用不同 Subgraph**实现能力拆分
3. **健康问答、习惯打卡、随访管理可以由对话 Agent 直接处理**：意图明确时调对应 MCP tool 即可
4. **报告解读独立**：因为是同步请求、依赖独立解析逻辑
5. **话术沉淀独立**：离线后台任务，处理对话日志，不参与实时业务流

**未来扩展：** 心理健康、产后恢复等新业务线，**不需要新增 Agent**，而是通过：新增对应的 Subgraph + 扩展处方生成 Agent 的 Prompt + 新增对应的 MCP Server（评估工具、知识库）+ 新增评测集，即可在现有 Agent 集合中支持新业务。

### 5.4 三层可演进架构设计

```
┌────────────────────────────────────────────────────────────────────┐
│  应用接入层：保持不变                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ 教练工作台    │ │ 医生端        │ │ 用户小程序    │               │
│  │ (Node.js CRM)│ │ (审核/管理)  │ │ (微信/App)   │               │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘               │
│         └────────────────┴────────────────┘                        │
│                          │ HTTP API                                │
└──────────────────────────┼─────────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────────┐
│  第 1 层：编排层 (Orchestration Layer)                             │
│                                                                    │
│  ┌──────────────────────────────────────────────────────┐          │
│  │  Python FastAPI 服务（贵公司已有，扩展即可）          │          │
│  │                                                       │          │
│  │  ┌────────────────────────────────────────────────┐   │          │
│  │  │  LangGraph v1.2 编排                           │   │          │
│  │  │  - 5 个 Agent 的 StateGraph 定义                │   │          │
│  │  │  - Subgraph 集合（业务工作流代码实现）          │   │          │
│  │  │    · meal_review_subgraph                      │   │          │
│  │  │    · diet_prescription_subgraph                │   │          │
│  │  │    · exercise_prescription_subgraph            │   │          │
│  │  │    · supplement_prescription_subgraph          │   │          │
│  │  │    · sleep_stress_subgraph                     │   │          │
│  │  │    · report_generation_subgraph                │   │          │
│  │  │  - HITL interrupt 机制                         │   │          │
│  │  │  - MySQL Checkpointer（durable execution）     │   │          │
│  │  └────────────────────────────────────────────────┘   │          │
│  │                                                       │          │
│  │  ┌────────────────────────────────────────────────┐   │          │
│  │  │  LiteLLM 模型网关                              │   │          │
│  │  │  - Claude Sonnet 4.6（主力对话/餐评/话术）     │   │          │
│  │  │  - Claude Opus 4.7（处方/高风险推理）          │   │          │
│  │  │  - Claude Haiku 4.5（简单分类/打卡提醒）       │   │          │
│  │  │  - Qwen3 / DeepSeek-V3.x（备用 fallback）      │   │          │
│  │  └────────────────────────────────────────────────┘   │          │
│  └──────────────────────────────────────────────────────┘          │
└──────────────────────────┬─────────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────────┐
│  第 2 层：工具与能力层 (Tools & Capabilities)                       │
│                                                                    │
│  ┌──────────────────────────────────────────────────────┐          │
│  │  MCP Server 集合（仅包装外部资源和真正的工具）        │          │
│  │                                                       │          │
│  │    user-data-server（MySQL 用户数据查询）             │          │
│  │    knowledge-base-server（医学知识 RAG）              │          │
│  │    talk-track-server（话术沉淀检索）                  │          │
│  │                                                       │          │
│  │    未来扩展：                                          │          │
│  │      wearable-device-server（可穿戴设备）             │          │
│  │      his-integration-server（医院 HIS 对接）          │          │
│  │                                                       │          │
│  │  ※ 业务工作流不通过 MCP，用 Subgraph 实现             │          │
│  └──────────────────────────────────────────────────────┘          │
│                                                                    │
│  ┌──────────────────────────────────────────────────────┐          │
│  │  共享 Python 工具函数（utils）                         │          │
│  │  - 用户上下文加载、LLM 调用封装、审计日志写入等        │          │
│  │  ※ 不做成 Subgraph，避免过度抽象                       │          │
│  └──────────────────────────────────────────────────────┘          │
└──────────────────────────┬─────────────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────────────┐
│  第 3 层：数据层 (Data Layer)                                       │
│                                                                    │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────┐      │
│  │ MySQL（主库）    │ │ 向量数据库       │ │ Redis            │      │
│  │ ★ 医学字段       │ │ - 话术库         │ │ - 会话状态       │      │
│  │ - 用户档案       │ │ - 医学知识       │ │ - 缓存           │      │
│  │ - 处方/餐评记录  │ │ - 历史对话        │ │ - 限流           │      │
│  │ - HITL 队列      │ │ Milvus 或        │ │                  │      │
│  │ - LangGraph     │ │ Qdrant（开源）    │ │                  │      │
│  │   checkpoint    │ │                   │ │                  │      │
│  │ - 审计日志       │ │                   │ │                  │      │
│  │ - 评测结果       │ │                   │ │                  │      │
│  └─────────────────┘ └─────────────────┘ └──────────────────┘      │
│  ┌─────────────────┐                                                │
│  │ 对象存储（OSS）  │                                                │
│  │ - 餐食图片       │                                                │
│  │ - 报告 PDF       │                                                │
│  └─────────────────┘                                                │
└────────────────────────────────────────────────────────────────────┘

横切关注点（贯穿三层）：
┌────────────────────────────────────────────────────────────────────┐
│  · 可观测性：Langfuse（开源自部署，链路追踪 + 成本分析）              │
│  · 评测：promptfoo + 自建评测脚本 + CI 集成                          │
│  · 安全护栏：输入/输出 Guardrails + HITL 强制审核                    │
│  · 审计：所有关键操作落 MySQL audit_log 表                           │
└────────────────────────────────────────────────────────────────────┘

【独立组件 / 过渡期保留】
┌────────────────────────────────────────────────────────────────────┐
│  Dify（独立部署，逐步淘汰）                                          │
│  - 阶段 1-2：跑现有生产业务（不动）                                  │
│  - 阶段 3：被 Python Subgraph 逐个替换                              │
│  - 阶段 4：完全退场，仅作 PM/教练做新功能原型验证                    │
└────────────────────────────────────────────────────────────────────┘
```

### 5.5 核心组件详细设计

#### 5.5.1 模型网关（LiteLLM）

模型网关在 MVP 阶段就要上，原因：

- LiteLLM 是开源现成项目，AI coding 加持下半天集成完
- 提前抽象后，后续切换模型零代码改动
- 自动获得成本统计、用量监控、限流能力

```
                    ┌─────────────────────────────────┐
                    │      LiteLLM 模型网关            │
                    │                                 │
  Agent/Subgraph ──►│  1. Prompt 模板渲染              │
  请求              │  2. 模型路由决策                 │
                    │  3. 请求发送 + 超时/重试          │
                    │  4. 响应校验（Guardrails）       │
                    │  5. Token 用量统计 → MySQL       │
                    │  6. 审计日志记录                 │
                    └──────────┬──────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
   │ Claude       │      │ Claude       │      │ Claude       │
   │ Opus 4.7     │      │ Sonnet 4.6   │      │ Haiku 4.5    │
   │ (处方/高风险) │      │ (主力)       │      │ (简单/廉价)   │
   └──────────────┘      └──────────────┘      └──────────────┘
                                                       │
                                                       ▼
                                              ┌──────────────┐
                                              │ Qwen3 等     │
                                              │ (备用/降级)   │
                                              └──────────────┘
```

**路由策略：**

| 场景 | 推荐模型 | 原因 |
|------|---------|------|
| 餐评生成、对话主流程、话术推荐 | **Claude Sonnet 4.6** | 性价比首选，agent 能力强 |
| 处方草案生成、复杂风险评估 | **Claude Opus 4.7** | 旗舰，self-verification 强，xhigh effort 模式适合高风险推理 |
| 打卡提醒、简单意图分类、批量后台任务 | **Claude Haiku 4.5** | 延迟低、成本低 |
| 主模型不可用 / 数据合规要求 | **自动 Fallback 到国内模型** | 保障可用性 |

**容灾策略：**
- 主模型响应超时（>15s）→ 自动切换备模型
- 主模型连续 3 次失败 → 自动降级并告警
- 所有模型不可用 → 返回预设安全回复 + 人工通知

**成本优化：**
- 按 Agent/Subgraph 类型配置不同的模型等级
- Token 预算控制：单次请求和日累计上限
- Langfuse + LiteLLM 联动，按 Agent / Subgraph / 用户 / 时段做成本报表

#### 5.5.2 Subgraph 设计（V3.1 新增核心章节）

**Subgraph 的设计哲学：** 用代码（Python + LangGraph）实现业务工作流，替代 Dify。每个 Subgraph 是一个独立的、可单独评测、可单独 checkpoint、可被多个 Agent 复用的业务单元。

**Subgraph vs 普通工具函数的边界：**

- **做成 Subgraph**：有独立业务语义、需要多步骤 LLM 调用、需要状态持久化、需要单独评测、有条件分支
- **做成普通 Python 函数（utils）**：单步骤调用、纯数据处理、跨业务通用（如用户上下文加载、LLM 调用封装、审计日志写入）

**核心 Subgraph 清单：**

```
subgraphs/
├── meal_review_subgraph/           # 餐评（优先迁移：用户实时交互，延迟最敏感）
│   ├── nodes/
│   │   ├── image_understanding.py      # VLM 图像理解
│   │   ├── user_context_load.py        # 加载用户医学约束（MySQL）
│   │   ├── nutrition_analysis.py       # 营养分析（带工具调用）
│   │   ├── follow_up_check.py          # 条件分支：是否需要追问
│   │   └── generate_advice.py          # 生成餐评建议
│   ├── prompts/
│   ├── eval_set/                        # 独立评测集（≥ 50 用例）
│   └── graph.py                         # Subgraph 定义
│
├── diet_prescription_subgraph/     # 饮食处方
│   ├── nodes/
│   │   ├── medical_constraint_check.py # 医学约束检查（用药/过敏，MySQL）
│   │   ├── glucose_data_load.py        # 血糖/体检数据加载
│   │   ├── draft_generation.py         # 草案生成（Opus 4.7 + extended thinking）
│   │   ├── safety_precheck.py          # 安全预检（药物/营养交互）
│   │   └── output_to_hitl.py           # 输出到 HITL 队列
│   └── ...
│
├── exercise_prescription_subgraph/      # 运动处方
├── supplement_prescription_subgraph/    # 营养素处方
├── sleep_stress_subgraph/               # 睡眠压力处方
├── report_generation_subgraph/          # 血糖报告、日周月报
└── shared/                              # 跨 Subgraph 共享的节点
    ├── audit_log_node.py
    └── llm_call_node.py
```

**Subgraph 代码骨架示例（以餐评为例）：**

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Literal

class MealReviewState(TypedDict):
    user_id: int
    image_url: Optional[str]
    text_description: Optional[str]
    image_analysis: dict        # VLM 解析结果
    user_constraints: dict       # 用户医学约束
    nutrition_data: dict         # 营养分析结果
    needs_followup: bool         # 是否需要追问
    followup_question: Optional[str]
    review_output: dict          # 最终餐评建议
    audit_trail: list

def build_meal_review_subgraph():
    sg = StateGraph(MealReviewState)

    sg.add_node("image_understanding", image_understanding_node)
    sg.add_node("load_user_context", user_context_load_node)
    sg.add_node("nutrition_analysis", nutrition_analysis_node)
    sg.add_node("followup_check", followup_check_node)
    sg.add_node("generate_advice", generate_advice_node)

    sg.set_entry_point("image_understanding")
    sg.add_edge("image_understanding", "load_user_context")
    sg.add_edge("load_user_context", "nutrition_analysis")
    sg.add_edge("nutrition_analysis", "followup_check")

    # 条件分支：是否需要追问
    sg.add_conditional_edges(
        "followup_check",
        lambda state: "ask_followup" if state["needs_followup"] else "generate",
        {
            "ask_followup": END,         # 中断，返回给对话 Agent 追问
            "generate": "generate_advice"
        }
    )
    sg.add_edge("generate_advice", END)

    return sg.compile()

# 在对话 Agent 中调用
meal_review_graph = build_meal_review_subgraph()
result = await meal_review_graph.ainvoke({
    "user_id": user_id,
    "image_url": image_url,
    ...
})
```

**Subgraph 的关键特性：**

1. **独立评测**：每个 Subgraph 有自己的 `eval_set/`，promptfoo 可以单独跑
2. **独立 Checkpoint**：异常恢复粒度更细，长流程也能精确恢复
3. **跨 Agent 复用**：对话 Agent 和处方生成 Agent 都能调同一个 Subgraph
4. **版本化管理**：Subgraph 代码在 git 里，每次变更可 review 和回滚
5. **节点级可观测**：Langfuse 看到的链路是节点级的，比 Dify 的黑盒清楚一个数量级

**Subgraph 设计的几个关键原则：**

1. **Subgraph 之间不要硬耦合**。例如"饮食处方 Subgraph" 不要直接调用"营养素处方 Subgraph"，各自独立输出，由上层处方生成 Agent 来组合协调。否则迁移和测试会很痛
2. **共享逻辑提取成普通 Python 函数，不要做成 Subgraph**。比如"加载用户上下文"、"调用 LiteLLM"、"写审计日志"——这些是工具函数
3. **Subgraph 输入输出 Schema 必须严格定义**（TypedDict / Pydantic），方便上层 Agent 编排和评测

**Dify 工作流到 Subgraph 的迁移要点：** 见 6.3 节。

#### 5.5.3 处方开具流程设计（HITL 关键场景）

```
用户提交需求（或定期触发）
    │
    ▼
对话 Agent 识别意图 → "需要生成处方"
    │
    ▼
触发处方生成 Agent（异步任务，存入 MySQL 任务队列）
    │
    ▼
处方生成 Agent 加载用户上下文：
  - MCP user-data-server：用户档案、医学字段（用药/过敏/禁忌）、近期处方
  - MCP knowledge-base-server：相关医学知识
  - 调用各处方 Subgraph 并行生成草案
    ├── diet_prescription_subgraph
    ├── exercise_prescription_subgraph
    ├── supplement_prescription_subgraph
    └── sleep_stress_subgraph
    │
    ▼
处方生成 Agent 综合输出处方草案 + 生成依据 + 风险标注
（草案生成 Subgraph 内使用 Claude Opus 4.7 + extended thinking）
    │
    ▼
【安全预检查 Guardrails（在 Subgraph 内或 Agent 层）】
  - 药物/营养素交互作用检查（基于结构化医学字段）
  - 剂量合理性检查
  - 禁忌症交叉检查
  - 任一项异常 → 标记高风险，提升审核优先级
    │
    ▼
┌────【Human-in-the-Loop】教练/医生审核（对接现有审核流程）────┐
│                                                              │
│  审核工作台展示：处方草案 + 生成依据 + 风险标注 + 历史依从性 │
│                                                              │
│  操作选项：                                                   │
│  ✅ 确认通过 → 下发给用户                                     │
│  ✏️  修改后通过 → 记录修改原因（重要：作为下次优化反馈）      │
│  ❌ 驳回 → 返回 Agent 重新生成（附驳回原因）                  │
│  📋 转会诊 → 进入多医生会诊流程                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
LangGraph 通过 interrupt 机制等待审核结果
    │
    ▼
用户接收处方 → 后续依从性监测（对话 Agent 跟进打卡）
    │
    ▼
评测系统记录：处方质量评分 + 用户依从率 + 健康指标变化
（作为下一轮 Prompt 优化的依据）
```

**HITL 设计要点：**
- 审核队列存 MySQL，支持优先级排序（高风险用户优先）
- 超时机制：处方审核超过 N 小时未处理，自动升级通知
- 所有审核决策（确认/修改/驳回 + 修改原因）落 MySQL，作为审计证据 + 反馈语料
- **驳回时的修改原因**喂回 Prompt 优化语料库——重要的反馈闭环

#### 5.5.4 记忆系统设计（MySQL 主导）

**用户结构化医学记忆（MySQL Schema 示例）：**

```sql
-- 用户基础档案
CREATE TABLE user_profile (
    user_id BIGINT PRIMARY KEY,
    age INT,
    gender ENUM('M', 'F', 'O'),
    height DECIMAL(5,2),
    weight DECIMAL(5,2),
    bmi DECIMAL(4,2),
    created_at DATETIME,
    updated_at DATETIME
);

-- 医学字段（强一致，写入需经医生确认）
CREATE TABLE user_medical_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    record_type ENUM('diagnosis', 'medication', 'allergy', 'contraindication'),
    content JSON,
    source ENUM('doctor_input', 'agent_proposed_and_confirmed', 'imported'),
    confirmed_by VARCHAR(64),  -- 确认医生 ID
    confirmed_at DATETIME,
    valid_from DATETIME,
    valid_to DATETIME,  -- NULL 表示长期有效
    INDEX idx_user_type (user_id, record_type)
);

-- 关键健康指标
CREATE TABLE user_health_metric (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    metric_type VARCHAR(64),  -- glucose, blood_pressure, imt, ldl_c 等
    value DECIMAL(10,3),
    unit VARCHAR(16),
    measured_at DATETIME,
    source VARCHAR(64),
    INDEX idx_user_metric_time (user_id, metric_type, measured_at)
);

-- HITL 审核队列
CREATE TABLE hitl_review_queue (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_type ENUM('prescription', 'meal_review_anomaly', 'risk_alert'),
    user_id BIGINT,
    agent_output JSON,
    risk_level ENUM('low', 'medium', 'high'),
    status ENUM('pending', 'approved', 'modified', 'rejected', 'escalated'),
    reviewer_id VARCHAR(64),
    review_comment TEXT,
    modified_content JSON,
    created_at DATETIME,
    reviewed_at DATETIME,
    INDEX idx_status_risk (status, risk_level)
);

-- 审计日志（合规要求）
CREATE TABLE audit_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    agent_name VARCHAR(64),
    subgraph_name VARCHAR(64),
    action VARCHAR(128),
    detail JSON,
    operator_id VARCHAR(64),  -- 操作人（Agent/教练/医生）
    created_at DATETIME,
    INDEX idx_user_time (user_id, created_at)
);

-- 评测结果
CREATE TABLE evaluation_result (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    target_type ENUM('agent', 'subgraph'),
    target_name VARCHAR(64),
    target_version VARCHAR(32),
    test_case_id VARCHAR(128),
    score JSON,  -- {"safety": 0.98, "accuracy": 0.87, ...}
    passed BOOLEAN,
    created_at DATETIME
);

-- Dify 双跑对比记录（迁移期使用，迁移完成后可归档）
CREATE TABLE dify_migration_diff (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    workflow_name VARCHAR(64),
    request_input JSON,
    dify_output JSON,
    subgraph_output JSON,
    diff_score DECIMAL(4,3),         -- 自动评分（语义相似度等）
    human_review_status ENUM('pending', 'subgraph_better', 'dify_better', 'equivalent'),
    created_at DATETIME,
    INDEX idx_workflow_status (workflow_name, human_review_status)
);
```

**话术沉淀机制（贵公司已有框架，本节给出建议增强）：**

1. **自动提取**：每次教练与用户对话结束后，话术沉淀 Agent 自动提取高价值问答对
2. **质量评分**：基于教练标注 + LLM-as-Judge 双重评分
3. **分类存储**：按疾病类型（糖尿病/减重/斑块逆转）、场景（餐评/运动/睡眠）入向量库
4. **使用反馈闭环**：记录每条话术被 Agent 引用后**用户的反馈和后续行为**（是否打开图片、是否完成打卡、血糖是否改善）——这比单纯的 LLM 自评重要

**记忆读写权限矩阵：**

| Agent | 工作记忆 | 医学结构化记忆 | 行为/情景记忆 | 程序记忆（话术） |
|-------|---------|---------------|--------------|----------------|
| 对话 Agent | 读写 | **只读** | 读写（情景） | 只读 |
| 处方生成 Agent | 读写 | **只读** | 只读 | 只读 |
| 餐评 Agent | 读写 | **只读** | 读写（情景） | 只读 |
| 话术沉淀 Agent | 只读 | 无 | 只读 | **读写** |
| 报告解读 Agent | 读写 | **只读** | 只写（情景） | 只读 |
| 医生端工具 | 读写 | **读写**（经审核） | 读写 | 读写 |

**核心约束：医学结构化记忆的写入权限只在医生端工具，所有 Agent 只能读。**

#### 5.5.5 评测体系设计

**评测流水线（CI 集成）：**

```
开发者提交 Prompt / Subgraph / Agent 代码变更
    │
    ▼
Git commit → CI 触发评测流水线
    │
    ├── 单元评测（promptfoo + 每个 Agent / Subgraph 的评测集）
    │     ├── 安全性测试（一票否决，<0.95 阻止部署）
    │     ├── 准确性测试
    │     ├── 边界条件测试
    │     └── 延迟测试
    │
    ├── 集成评测（端到端业务场景）
    │     ├── 典型流程测试（餐评→生成→审核→下发）
    │     ├── 异常流程测试（用户中断、数据缺失、模型超时）
    │     └── HITL 流程测试
    │
    ├── 【迁移期专项】Subgraph vs Dify 双跑对比
    │     ├── 同一输入并行调 Dify 和 Subgraph
    │     ├── 自动对比输出（语义相似度、关键字段一致性）
    │     ├── 差异大的 case 标记为待人工审核
    │     └── 通过率达标 + 人工审核通过 → 允许切流
    │
    ▼
评测报告生成（落 MySQL evaluation_result 表）
    │
    ├── 通过 → 允许部署（先灰度 10%）
    └── 未通过 → 阻止部署 + 钉钉/企微通知
```

**关键评测指标（参考值，需结合贵公司实际基线调整）：**

| 指标 | 定义 | 参考阈值 |
|------|------|---------|
| 安全性评分 | 是否生成危害性内容 | **≥ 0.95（硬约束）** |
| 准确性评分 | 医学知识引用正确率 | 需先测人工教练基线 |
| HITL 触发率 | 高风险场景正确触发审核的比例 | **≥ 0.98（硬约束）** |
| P95 延迟 | 95% 请求的响应时间 | 对话 < 3s，处方异步 |
| 单次成本 | 单次交互的 Token 费用 | 按模型分档统计，留预算 |
| 用户满意度 | 基于用户反馈评分 | 持续追踪基线 |
| **迁移一致性** ★ | Subgraph 输出与 Dify 基线的一致性 | **≥ 0.90（迁移期硬约束）** |

> **重要说明：** 具体阈值（如 0.95）**不应直接照搬**，应先：(1) 测量人工教练当前流程的基线水平；(2) 业务方决定可接受最低水位；(3) 监管/保险方的硬性要求。这部分需要医生/营养师团队介入设计具体评测题目。

### 5.6 技术选型建议（修订版）

| 组件 | 推荐方案 | 备选方案 | 选型理由 |
|------|---------|---------|---------|
| **Agent 编排框架** | **LangGraph v1.2** | Deep Agents（高层封装） | 状态持久化+HITL+生产级稳定性，2026 年企业级首选 |
| **业务工作流实现** | **Python + LangGraph Subgraph** | - | 代码版本化、可评测、低延迟、动态决策 |
| **业务原型工具** | **Dify**（仅原型，逐步退场） | - | PM/教练做新功能原型验证 |
| **LLM 主力** | **Claude Sonnet 4.6** | Qwen3 / DeepSeek-V3.x（备用） | 性价比首选，agent 能力强 |
| **LLM 旗舰（处方）** | **Claude Opus 4.7** | GPT-5 系列 | 高风险场景，self-verification + xhigh effort |
| **LLM 低成本档** | **Claude Haiku 4.5** | Qwen3-Turbo | 简单任务、批量后台 |
| **模型网关** | **LiteLLM**（开源） | 自研网关 | 开源现成、即装即用 |
| **MCP 实现** | **官方 Python SDK** | - | 标准协议 |
| **向量数据库** | **Milvus** / Qdrant | - | 开源、性能验证 |
| **关系数据库** | **MySQL**（贵公司现有） | - | 与现有技术栈一致 |
| **缓存** | **Redis** | - | 通用 |
| **记忆框架** | **MySQL Schema 自研 + Mem0（仅向量层辅助）** | 全自研 | 医学字段必须 MySQL，Mem0 仅做事实抽取/去重 |
| **RAG 引擎** | **LlamaIndex** 或自研 | LangChain RAG | 已有 RAG，渐进升级 |
| **可观测性** | **Langfuse（自部署）** | LangSmith（SaaS） | 开源可控、数据不出境 |
| **Agent 评测** | **promptfoo** | DeepEval | 开源成熟，支持 LLM-as-Judge |
| **工作流调度** | **LangGraph durable execution（不用 Temporal）** | - | 避免双套状态机 |
| **消息队列** | **Redis Stream** 或 MySQL 任务表 | RabbitMQ | 量级小，简单优先 |
| **API 网关** | 视现有架构而定 | - | 不引入新组件 |

### 5.7 V2 vs V3.1 对比一览

| 维度 | V2 方案 | V3.1 方案 | 差异原因 |
|------|---------|----------|---------|
| 架构层数 | 6 层 | **3 层 + 横切关注点** | 评测/合规是横切关注点，不应独立成层 |
| Agent 数量 | 10+ 细粒度 | **5 个核心** | 多 Agent 协同有固有复杂度，业界共识 3-7 个 |
| 业务工作流实现 | （未细化） | **Python LangGraph Subgraph** | 代码版本化、低延迟、可评测、动态决策 |
| Agent 注册中心 | 必须 | **不做** | 5 个 Agent 用配置文件 + Git 即可 |
| 模型版本 | Claude 3.7 Sonnet | **Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5** | V2 模型已下线（2025-10） |
| 模型网关 | 推荐 | **MVP 阶段就上** | AI coding 加持下，半天工作量，早抽象更省事 |
| 评测体系 | 第三阶段 | **MVP 阶段就上** | 评测是回归测试基础设施，也是 Dify 迁移的安全保障 |
| 工作流调度 | Temporal + LangGraph 双套 | **仅 LangGraph durable execution** | 避免双状态机一致性问题 |
| 多租户 | 全链路 tenant_id | **不做** | 业务不需要 |
| A2A 协议 | 远期预留 | **不预留** | A2A 已成熟生产，但贵公司不需要；预留是 YAGNI |
| Neo4j 图数据库 | 推荐 | **不用** | 无图查询需求 |
| 数据库 | PostgreSQL | **MySQL** | 匹配贵公司技术栈 |
| 现有 Dify | 推翻重建 | **原型工具，逐步退场（双跑期 → 切流 → 淘汰）** | 既不推翻也不长期保留，作为新功能原型验证工具长期存在 |
| 现有 Python RAG 对话 | 重构 | **演进为 LangGraph 编排** | 复用已有逻辑 |
| 可观测性 | LangSmith 优先 | **Langfuse（自部署）优先** | 开源可控，数据不出境，更适合医疗合规 |

---

## 六、实施路线图建议（修订版）

### 6.1 阶段一：基础设施搭建（2-4 周）

**目标：** 不动现有 Dify 生产业务，先把 LangGraph + LiteLLM + Langfuse 基础设施骨架搭起来，并把现有 Python RAG 对话演进为 LangGraph 编排

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 搭建 LangGraph v1.2 基础编排，MySQL Checkpointer | P0 | 包含基础状态机、HITL interrupt 预留 |
| 接入 LiteLLM 模型网关 | P0 | 统一模型调用入口，配置 Sonnet 4.6 主力 + Opus 4.7 备 |
| 搭建 Langfuse（自部署） | P0 | 链路追踪能力就位 |
| 实现 user-data-server（MCP） | P0 | 用户档案、历史指标、依从性数据查询 |
| 现有 Python RAG 对话逻辑迁移为 LangGraph 节点 | P0 | 不改变 CRM 端 API |
| MySQL Schema 设计：medical_record / hitl_queue / audit_log / evaluation_result / dify_migration_diff | P0 | 为后续阶段预留 |
| **现有 Dify 业务保持原状** | P0 | 不动！生产稳定优先 |
| 搭建 promptfoo 评测基础设施 | P1 | 哪怕只有空框架，先把 CI 集成跑通 |

**验证指标：**
- 现有 CRM 对话功能不退化
- Langfuse 能看到完整链路
- LangGraph 可成功运行简单的 echo 流程，MySQL Checkpoint 写入成功
- Dify 现有处方/餐评业务保持稳定（监控指标对比）

### 6.2 阶段二：对话 Agent 上线 + 第一个 Subgraph 试点（4-6 周）

**目标：** 实现"对话 Agent"作为统一入口（整合健康问答、习惯打卡、调用处方流程），并完成**第一个 Subgraph（餐评）从 Dify 迁移到 Python**

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 完整实现"对话 Agent" | P0 | Claude Sonnet 4.6 + MCP tools |
| 实现 HITL 流程对接现有教练/医生审核 | P0 | LangGraph interrupt + MySQL hitl_queue + CRM 审核工作台 |
| 实现 knowledge-base-server（MCP） | P0 | 整合现有 RAG 知识库 |
| 实现 talk-track-server（MCP） | P0 | 对接已有话术沉淀框架 |
| **试点 Subgraph：meal_review_subgraph** | P0 | 餐评迁移（优先级最高，延迟最敏感） |
| 餐评评测集构建（医生/营养师标注 50-100 条） | P0 | 来自 Dify 历史数据抽样 |
| 餐评双跑期机制（Dify + Subgraph 并行）| P0 | dify_migration_diff 表记录差异 |
| CI 评测流水线 | P1 | promptfoo + GitHub Actions / GitLab CI |
| Guardrails 安全护栏 | P1 | 输入/输出安全校验 |
| 灰度发布机制 | P1 | 按用户分组切换新旧链路 |

**验证指标：**
- 对话 Agent 满意度 ≥ 4.0/5.0
- 安全性评测 ≥ 0.95
- **meal_review_subgraph 与 Dify 双跑一致性 ≥ 0.90**
- meal_review_subgraph 延迟比 Dify 降低 ≥ 30%
- HITL 触发率正确 ≥ 0.98
- P95 对话延迟 < 3s
- 餐评 Subgraph 灰度切流验证通过

### 6.3 阶段三：扩展到 5 个 Agent + 业务 Subgraph 批量迁移（2-3 个月）

**目标：** 拆出处方生成 Agent（异步 + Opus 4.7）、餐评 Agent、话术沉淀 Agent、报告解读 Agent；批量迁移剩余 Dify 工作流到 Subgraph

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 处方生成 Agent（异步） | P0 | Opus 4.7 + extended thinking |
| 餐评 Agent | P0 | 包装 meal_review_subgraph，加上对话交互层 |
| **diet_prescription_subgraph 迁移** | P0 | 饮食处方 |
| **exercise_prescription_subgraph 迁移** | P0 | 运动处方 |
| **supplement_prescription_subgraph 迁移** | P1 | 营养素处方 |
| **sleep_stress_subgraph 迁移** | P1 | 睡眠压力处方 |
| 话术沉淀 Agent（后台批处理） | P1 | 增加"使用反馈闭环"机制 |
| 报告解读 Agent + report_generation_subgraph | P1 | 同步任务，长文本解析 |
| Agentic RAG 升级（仅用于知识查询） | P2 | 多跳检索、保守输出 |
| 评测集补全（每个 Agent / Subgraph ≥ 100 用例） | P1 | 持续维护 bad case |
| 成本监控仪表盘 | P2 | Langfuse + LiteLLM 数据 |

**Subgraph 迁移的标准流程（每个 Subgraph 都走一遍）：**

```
1. 构建评测集（医生/营养师从历史 Dify 数据抽样标注，≥ 50 条）
   ↓
2. Python Subgraph 实现（参考 Dify 工作流逻辑，但允许优化）
   ↓
3. 单元评测（promptfoo 跑评测集）
   - 不达标 → 回到第 2 步优化
   - 达标 → 进入第 4 步
   ↓
4. 双跑期（1-2 周）
   - 真实流量同时调 Dify 和 Subgraph
   - dify_migration_diff 记录差异
   - 一致性 < 0.90 的 case 标记人工审核
   ↓
5. 双跑结果评估
   - Subgraph 在效果、延迟、成本上不劣于 Dify
   - 高频差异 case 已分析定位
   ↓
6. 灰度切流（10% → 50% → 100%）
   - 监控关键业务指标
   - 出问题立刻回滚
   ↓
7. 全量切流后保留 Dify 链路 1 个月作为备份
   ↓
8. 关闭 Dify 中对应工作流（仍保留 Dify 实例用于新功能原型）
```

**验证指标：**
- 5 个 Agent 完整跑通业务闭环
- 所有处方/餐评 Subgraph 完成迁移，Dify 流量降到 0
- 处方生成 Agent 在 HITL 审核通过率 ≥ X%（基于历史基线对比）
- 系统可用性 ≥ 99%
- 整体延迟显著优于原 Dify 链路（典型场景 P95 延迟降低 30%+）
- 单次交互成本可控

### 6.4 阶段四：优化、Dify 退场、扩展（持续）

**目标：** 根据真实使用数据迭代，Dify 完全退出生产架构，为新业务扩展做好准备

| 任务 | 优先级 | 说明 |
|------|--------|------|
| 基于审核驳回原因优化 Prompt | P0 | 建立反馈闭环机制 |
| **Dify 在生产架构中完全退场** | P0 | 所有业务 Subgraph 稳定运行，Dify 仅留作 PM/教练新功能原型验证工具 |
| 性能优化 | P1 | Prompt 缓存、模型蒸馏（高频低风险场景） |
| 安全加固 | P1 | 全链路 Guardrails、内容审核、审计完整性 |
| 评测集 A/B 实验框架 | P1 | 对比不同 Prompt / 模型策略 |
| 新业务线扩展（如规划要做） | P2 | 通过新 Subgraph + 新 MCP Server + 扩展 Prompt 接入，**不改架构** |
| A2A 接入（**仅当真有跨组织 Agent 协作需求时**） | P2 | 当前不做 |

---

## 七、风险与注意事项

### 7.1 医疗安全风险

- **幻觉风险**：Agent 生成的医学建议必须经医生审核，不可直接作为诊断依据。**对策**：HITL 强制 + Guardrails 兜底 + 医学字段走 MySQL 强一致 Schema
- **数据隐私**：用户健康数据需加密存储，符合《个人信息保护法》《数据安全法》、医疗器械二类证合规要求。**对策**：全链路加密 + 数据访问审计 + 用户数据可删除
- **责任界定**：明确 Agent 辅助决策与教练/医生最终决策的责任边界。**对策**：所有外发内容都经过教练/医生审核，系统层面强制
- **可观测性合规**：选用 Langfuse 自部署而非 LangSmith SaaS，保证审计数据不出境

### 7.2 技术风险

- **模型迭代**：LLM 版本更新可能导致 Agent 行为变化。**对策**：模型版本固定 + 回归评测 + 灰度发布 + LiteLLM 统一切换入口
- **Subgraph 迁移导致效果回退**：Python 重写的 Subgraph 可能在某些 case 上不如调好的 Dify workflow。**对策**：(1) 评测集先行，每个 Subgraph 上线前必须通过评测；(2) 双跑期机制，真实流量并行验证；(3) 灰度切流，出问题立即回滚；(4) 保留 Dify 链路 1 个月作为备份
- **Subgraph 设计粒度过细 / 过粗**：过细导致组合复杂、过粗导致难以单独评测。**对策**：按"有独立业务语义 + 多步骤 LLM 调用 + 需要单独评测"的标准判断，初期可粗，后续按需要拆细
- **记忆漂移**：长期记忆可能出现信息过时。**对策**：医学字段强一致 + 用户可主动纠正 + 定期清理任务
- **供应商锁定**：过度依赖单一 LLM 供应商。**对策**：LiteLLM 统一抽象 + 定期验证备用模型效果（国内模型作为合规/降级备份）

### 7.3 团队与流程风险

- **AI coding 加持下的复杂度陷阱**：代码产出速度变快，容易过度堆砌架构。**对策**：保持 5 Agent 上限、3 层架构约束，每次新增组件先问"业务真的需要吗"
- **教练接受度**：教练可能担心被替代。**对策**：定位为"效率工具"，Agent 承担重复性工作，教练聚焦核心决策
- **评测成本**：完善评测体系需要持续投入。**对策**：MVP 50 条起步，结合 LLM-as-Judge 降低人工标注成本
- **迁移期心智负担**：双跑期同时维护 Dify 和 Subgraph 两套实现。**对策**：迁移按 Subgraph 串行推进，一次一个，不要并行迁多个；每个 Subgraph 切流后再启动下一个

### 7.4 应该避免的过度设计

以下是 V2 方案中提出但本版本砍掉的，特别强调避免在当前阶段引入：

| 反模式 | 为什么不做 |
|--------|-----------|
| Agent 注册中心 + 动态发现 | 5 个 Agent 用配置文件即可，注册中心是 20+ Agent 才有意义 |
| Temporal + LangGraph 双套状态机 | 两套独立持久化的状态机会带来一致性问题 |
| 10+ 细粒度 Agent | 多 Agent 协同的固有复杂度（路由错误、上下文损失、调试困难） |
| 多租户架构 | 业务上不需要，过早抽象损失太多 |
| A2A 协议预留接口 | YAGNI；真要接入时本来就要按 A2A 规范改造 |
| Neo4j 图数据库 | 无明确图查询场景 |
| 把医学字段塞向量库 | 向量召回的概率性在医疗场景是事故 |
| Dify 长期作为生产架构 | 延迟、自主性、可观测性都不适合生产 |
| 用 MCP 包装内部业务工作流 | 增加无谓的网络跳数，违背 MCP 设计哲学；用 Subgraph 实现更直接 |

---

## 八、总结与核心建议

1. **架构选择**：以 **LangGraph v1.2** 为编排框架，**MCP** 为外部工具接入标准，**LiteLLM** 为模型网关，构建**三层架构 + 横切关注点**

2. **业务逻辑实现**：业务工作流用 **Python LangGraph Subgraph** 实现。Dify 仅作为 PM/教练快速验证新功能的原型工具，**不作为生产架构**。已有 Dify 工作流通过"评测先行 + 双跑期 + 灰度切流"的标准流程逐个迁移到 Subgraph

3. **Agent 收敛**：5 个核心 Agent（对话 / 处方生成 / 餐评 / 话术沉淀 / 报告解读），而非细粒度拆分。新业务通过新 Subgraph + 新 MCP Server 接入，不增加 Agent

4. **模型策略**：Claude Sonnet 4.6 主力 + Opus 4.7 高风险场景 + Haiku 4.5 简单任务，国内模型作为合规/降级备份

5. **数据策略**：医学字段（诊断、用药、过敏）走 **MySQL 严格 Schema + 审计 + 不进向量库**；行为偏好、话术、对话历史可用向量库

6. **HITL 是硬约束**：处方等"准医疗"输出必须经教练/医生审核，对接现有审核流程；驳回原因作为下次优化的反馈语料

7. **评测体系前置**：MVP 阶段就建立 promptfoo + CI 集成。**评测不仅是质量保障，更是 Dify → Subgraph 迁移的安全保障**——没有评测就没法做迁移

8. **分阶段实施**：
   - 阶段 1（2-4 周）：基础设施搭建（LangGraph + LiteLLM + Langfuse + MCP 基础 Server）
   - 阶段 2（4-6 周）：对话 Agent 上线 + 第一个 Subgraph（餐评）试点迁移
   - 阶段 3（2-3 个月）：扩展到 5 Agent + 批量迁移业务 Subgraph
   - 阶段 4（持续）：Dify 退场 + 优化 + 未来扩展

9. **明确不做的事**：Agent 注册中心、Temporal 双状态机、10+ 细粒度 Agent、多租户、A2A 预留、Neo4j、医学字段进向量库、Dify 长期作为生产架构、用 MCP 包装内部业务工作流

> **最终定位：** Agent 技术对贵公司业务的价值不在于"用最新最全的架构"，而在于**承担教练 80% 的重复性工作（餐评生成、习惯督促、话术检索、报告预解读、处方草案生成），让教练和医生聚焦 20% 的核心决策与情感关怀**。技术架构的复杂度必须匹配业务规模和团队能力——3 人团队 + 2000 用户的当下，5 Agent + Subgraph 业务实现 + 3 层架构 + LangGraph + MCP（仅外部工具）+ LiteLLM + Langfuse 评测观测，是最合理的方案。Dify 作为 PM/教练原型工具长期存在，但不进生产架构。未来业务扩展（心理健康、产后恢复等）通过**增加 Subgraph + 增加 MCP Server + 扩展 Prompt + 增加评测集**实现，不需要改动核心架构。

---

**参考来源（更新）：**
- LangChain: LangGraph v1.2 Release Notes, 2026-05
- LangChain: LangGraph Subgraph Documentation
- Anthropic: Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 Model Cards, 2026
- Anthropic: Model Context Protocol Documentation, 2024-2026
- Linux Foundation: A2A Protocol v1.2 Specification, 2026-04
- promptfoo / Langfuse: Open Source LLM Evaluation & Observability
- LiteLLM: Unified LLM Gateway Documentation
- Medium @ATNO: 10 AI Agent Frameworks in 2026 Comparison
- Pharos Production: AI Agent Frameworks 2026 Comparison Guide
- 多 Agent 协作框架与系统架构综述, 2026
- 腾讯云开发者社区: 2025 医药行业 Agent 案例
- PMC: AI in Chronic Disease Self-Management