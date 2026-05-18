
# AI 对话审计与故障诊断 — 落地架构与开发 Plan

> 日期：2026-05-15  
> 上游：`docs/AI对话审计与故障诊断优化调研报告.md`（你的初步报告）  
> 视角：Agent 工程师视角，对照现有代码定位"哪些已有/哪些缺/怎么落"，给出可拆分到执行线程的开发 plan  
> 真值口径：审计表是 `official` 调用真相；诊断结果是 `support` 排障证据；浏览器探针是 `support` 辅助判断，不能写成 `official`

---

## 0. 一句话定位

你的初步报告方向已经对，结论也合理。这份 plan 解决的是**"怎么落地"**的问题：

1. 审计采用 **trace + step 双层模型**：一张 `crm_ai_invocations` 调用级总账（trace）+ 一张 `crm_ai_trace_steps` 步骤明细（step），P0 单轮模式每次只写 1 行 step，未来 Agent 化（意图识别 / 工具调用 / function call）零破坏新增
2. 现有 5 张审计模型（session / message / context_snapshot / guardrail_event / rag_log）保留，但**作为附属证据，不再各自为营**
3. 错误处理改造为**"分阶段错误码 + call_id 贯穿 + 失败必落账"**三件套；`stage` 用开放注册表（可扩展 Agent 阶段），`error_code` 用 Enum + 命名空间约束
4. 诊断服务做成**独立 Probe Pipeline**，输出 `DiagnosticReport` 而不是散落代码里的 if-else
5. 前端 SSE 走**统一错误协议**，不再用 `fetch` 自己解码 401

落地拆 3 个 Phase（P0 闭环 / P1 诊断 / P2 运营），共 9 条独立子线，每条线都能独立提测。

> **方案选型说明**：你原报告里方案 A（联表视图）vs 方案 B（新增总账表）的取舍是本架构的分水岭。这里直接走 B，代价是"多一张表 + 一个 writer"，收益是后续所有功能基于稳定主表，不需要 join 5 张表拼"一次调用"视图。同时把 B 升级为 trace + step 双层，为未来 Agent 化预留出口。

---

## 1. 现状代码对照清单

| 你提到的能力 | 现有代码真值 | 缺口 |
|------------|------------|------|
| 会话主线 | `CrmAiSession`（`models.py`）+ `audit.write_session` | ✅ 已有，无需动 |
| 用户/AI 消息 | `CrmAiMessage` + `audit.write_message` | ⚠️ 失败时 assistant message 不一定写入 |
| 上下文快照 | `CrmAiContextSnapshot` + `audit.write_context_snapshot` | ✅ 已有；缺 `cache_key` 显式列 |
| 安全事件 | `CrmAiGuardrailEvent` + `audit.write_guardrail_event` | ✅ 已有 |
| RAG 检索日志 | `RagRetrievalLog`（`app/models_rag.py`）+ `app/rag/audit.py` | ⚠️ 与 AI 调用审计未硬关联 |
| 反馈 | `CrmAiMessageFeedback`（侧边栏方案里也涉及） | ✅ 已有 |
| 错误分类 | `_classify_ai_error` 5 类（`ai/_helpers.py`） | ❌ 粒度粗、不分阶段、不落库 |
| SSE 错误事件 | `event="error"` + `{message, code}` | ❌ 缺 `call_id`、`stage`、`diagnostics` |
| 前端错误展示 | `assistantMessage.errorCode/errorMessage`（`useAiCoach.ts`） | ❌ 401/403 走不到这里；无 `call_id` |
| 调用级"总账" | **不存在** | ❌ 这是核心缺口 |
| 故障诊断服务 | **不存在** | ❌ 完全要新建 |
| 管理员审计页 | `FeedbackReview/`、`RagManage/` 各管一段 | ❌ 缺统一入口 |
| 浏览器侧网络诊断 | **不存在** | ❌ P1 才需要 |

**关键判断**：70% 数据已有，但**缺一张"调用级总账表"和"统一错误协议"**。这两件事不做，再多审计页面都是补丁。

---

## 2. 落地架构（与初步报告的差异说明）

### 2.1 你方案 A vs 方案 B 的取舍

你的报告里说"P0 联表视图、P1 再加调用表"。我建议**P0 直接做 `crm_ai_invocations` 表，但写入采用最小侵入策略**，原因：

- 联表视图查询逻辑会很快变成迷宫（join 5 张表，过滤失败状态时 left join 处理空值），技术债比新增表大
- 失败持久化必须依赖独立表，否则失败调用永远没记录可联（assistant_message_id 为空时 join 不出来）
- `call_id` 这个字段一旦贯穿全链路，就**必须**有一个主表持有它，否则它只是个 SSE 字段

成本：多写一张表 + 一个写入函数。收益：所有后续功能都基于稳定主表，不需要联 5 张表。

### 2.2 总账与证据的关系：trace + step 双层模型

```
┌─────────────────────────────────────────────────────────────┐
│   crm_ai_invocations（调用级总账，trace，official truth）      │
│   PK: call_id（= trace_id 概念）                              │
│   ┌──── execution_mode: single_turn | agent | tool_use       │
│   ┌──── 聚合指标：total_tokens / step_count / tool_call_count │
│   ├──── session_id ────→ CrmAiSession（会话主数据）           │
│   ├──── user_message_id ──→ CrmAiMessage（用户问题）          │
│   ├──── assistant_message_id ──→ CrmAiMessage（AI 回复）      │
│   ├──── context_snapshot_id ──→ CrmAiContextSnapshot         │
│   ├──── rag_log_id ──→ RagRetrievalLog                       │
│   └──── guardrail_event_ids[] ──→ CrmAiGuardrailEvent        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│   crm_ai_trace_steps（执行步骤明细，1:N，按 step_index 顺序）  │
│   call_id + step_index 唯一                                   │
│   kind: llm_call / rag_retrieval / tool_call /               │
│         intent_classification / agent_plan /                 │
│         safety_check / context_assembly                      │
│   每行有：input_json / output_json / status / latency / token │
│                                                              │
│   ★ P0 单轮模式：每次调用只写 1 行 step（kind=llm_call）       │
│   ★ Agent 化：每次 LLM、tool call、planning 都写一行 step      │
└─────────────────────────────────────────────────────────────┘
```

总账只存**调用过程的状态机、聚合指标和指针**，详情仍走原表 + step 表。这样：
- 现有 5 张表保持不变（不破坏现有逻辑）
- 总账表轻、查询快
- 任何失败都能在总账有记录，至少知道"谁、哪个客户、什么时候、卡在哪一步"
- **Agent 化时只增 step 行，不改 schema**（详见 §3.4 演进路径）

### 2.3 状态机与错误阶段：开放注册表（不锁 Enum）

每次单轮调用经过 7 个阶段，任意一个失败都要在总账写入对应错误阶段：

```
┌──────────────────┬──────────────────────────┬──────────────────────────┐
│ 阶段（stage 名）  │ 关键动作                   │ 可能错误码                │
├──────────────────┼──────────────────────────┼──────────────────────────┤
│ auth             │ 鉴权、权限、客户可见性      │ auth_expired / permission_denied
│ prepare          │ 加载 profile、组装 prompt  │ profile_cache_not_ready / ai_disabled
│ rag              │ embedding + 向量检索       │ rag_unavailable
│ persist_user_msg │ 写 user_message + snapshot │ db_write_error
│ model            │ 调用 LLM 流式              │ provider_timeout / provider_rate_limited / provider_overloaded / provider_auth_failed / network_unreachable
│ stream           │ SSE 流式推送给前端         │ stream_interrupted
│ persist_asst_msg │ 写 assistant_message       │ db_write_error
└──────────────────┴──────────────────────────┴──────────────────────────┘
```

**为 Agent 化预留的 stage 命名空间**（P0 不实现，但写进注册表占位）：
```
intent_classification   # 意图识别
agent_plan              # Agent 规划
tool_call               # 工具调用
tool_observation        # 工具结果观察
agent_synthesize        # Agent 最终合成
vision_analyze          # 视觉/附件分析
```

**约束**：
- `stage` **不用 Enum**，用开放注册表 + `validate_stage()` 校验：未知 stage 仅 log warn 不阻塞，避免 Agent 化迭代时被 Enum 卡死。详见 §5.2。
- `error_code` **强制 Enum**，因为前后端必须严格映射用户文案与推荐动作。命名空间分组见 §5.1。

### 2.4 诊断服务架构

诊断不要写成"一个大函数判断 N 件事"，要做成 **Probe Pipeline**：

```python
class DiagnosticProbe(Protocol):
    name: str               # "config" / "auth" / "profile_cache" / "rag" / "network" / ...
    severity_on_fail: str   # "critical" / "warning" / "info"
    timeout_ms: int
    async def run(self, ctx: DiagnosticContext) -> ProbeResult: ...

# 编排器并行跑所有 probe，按 severity 收敛
async def diagnose(ctx) -> DiagnosticReport:
    probes = registry.list_active()
    results = await asyncio.gather(*[p.run(ctx) for p in probes], return_exceptions=True)
    return DiagnosticReport.from_results(results)
```

**收益**：
- 每个 probe 独立可测、可禁用、可超时控制
- 加新探针（如未来加"客户档案完整性"诊断）只要新建一个文件，注册即可
- 可以**复用**到三个不同入口：用户主动诊断 / 管理员诊断 / 失败调用自动诊断

### 2.5 前端协议统一

前端三件事：

1. SSE 错误统一格式 `{ event: "error", data: { code, stage, message, call_id, retriable, recommended_action, diagnostics_summary? } }`
2. SSE 链路接入 token refresh（当前 `sseStream.ts` 用 `fetch` 完全绕过 `request.ts` 的 401 拦截，必须修）
3. 错误卡片分层展示：用户语言 + 推荐动作 + `call_id`（折叠展示）

---

## 3. 数据模型设计

### 3.1 新增 `crm_ai_invocations` 表（trace 总账）

按 AGENTS.md "幂等迁移" 模式，加到 `app/schema_migrations.py`：

```python
class CrmAiInvocation(Base):
    """一次用户提问的完整 trace 总账（一问 = 一行）。"""
    __tablename__ = "crm_ai_invocations"

    id: int                         # autoinc
    call_id: str                    # = trace_id 概念，uuid，唯一索引
    session_id: str                 # 索引
    user_message_id: Optional[str]
    assistant_message_id: Optional[str]
    context_snapshot_id: Optional[int]
    rag_log_id: Optional[int]

    # ★ 执行模式（Agent 化关键开关）
    execution_mode: str = "single_turn"   # single_turn / agent / tool_use

    # 业务上下文
    local_user_id: int
    crm_admin_id: Optional[int]
    crm_customer_id: int            # 索引
    entry_scene: Optional[str]
    scene_key: Optional[str]
    output_style: Optional[str]
    prompt_version: Optional[str]
    prompt_hash: Optional[str]
    health_window_days: Optional[int]
    cache_key: Optional[str]

    # 状态机
    status: str                     # pending / success / partial / error / blocked
    error_stage: Optional[str]      # 失败时的最后 stage 名（开放注册表，见 §5.2）
    error_code: Optional[str]       # ErrorCode Enum 字符串值
    error_message: Optional[str]    # 用户可读
    error_detail: Optional[str]     # 异常摘要（脱敏，禁止存 token/key）

    # RAG 状态摘要（避免每次详情都 join）
    rag_status: Optional[str]       # disabled / ok / no_hit / unavailable / error
    rag_hit_count: int = 0

    # ★ 聚合指标（多 step 累加，单轮就是单 step 的值）
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    primary_model: Optional[str]    # 最后一次（或主回复）LLM 的 model
    primary_provider: Optional[str]

    # ★ 执行特征（Agent 化时用，单轮默认 step_count=1, tool_call_count=0）
    step_count: int = 1
    tool_call_count: int = 0

    # 性能
    latency_ms: Optional[int]
    first_token_ms: Optional[int]
    prepare_ms: Optional[int]

    # 诊断
    diagnostics_json: Optional[str]   # 仅失败/警告时写

    # 时间
    started_at: datetime
    finished_at: Optional[datetime]
```

**索引**：`call_id`（唯一）、`session_id`、`crm_customer_id, started_at DESC`、`status, started_at DESC`、`local_user_id, started_at DESC`、`error_code`、`execution_mode`。

**保留期**：建议 90 天滚动，超期归档（用 Celery 定时任务，复用现有 beat 配置）。

### 3.2 新增 `crm_ai_trace_steps` 表（执行步骤明细）

```python
class CrmAiTraceStep(Base):
    """trace 下的执行步骤明细。
    
    P0 单轮模式：每次调用只写 1 行（kind=llm_call, step_index=0）。
    Agent 化：每次 LLM call、tool call、planning 都写一行。
    """
    __tablename__ = "crm_ai_trace_steps"

    id: int                         # autoinc
    call_id: str                    # FK → crm_ai_invocations.call_id，索引
    step_index: int                 # 顺序 0,1,2...
    parent_step_index: Optional[int]  # 嵌套步骤（agent 子规划时用）

    # ★ 关键：step 类型可扩展，用 string + 注册表校验，不用 Enum 锁死
    kind: str                       # llm_call / rag_retrieval / tool_call /
                                    # intent_classification / agent_plan /
                                    # safety_check / context_assembly / vision_analyze
    name: Optional[str]             # 具体名称：tool_call.create_reminder / llm_call.synthesize

    # 通用状态
    status: str                     # success / error / timeout / skipped
    error_code: Optional[str]
    error_message: Optional[str]

    # 输入输出（按 kind 各异，结构化 JSON 摘要，禁止存 token/key）
    input_json: Optional[str]
    output_json: Optional[str]

    # 性能
    started_at: datetime
    finished_at: Optional[datetime]
    latency_ms: Optional[int]

    # ★ LLM step 专用（其他 kind 留空）
    model: Optional[str]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0

    # ★ tool step 专用（P0 不用，Agent 化时用）
    tool_name: Optional[str]
    tool_input_hash: Optional[str]   # 用于去重 / 缓存判断
```

**索引**：`call_id, step_index`（联合唯一）、`kind`、`tool_name`、`status, started_at DESC`。

**P0 行为**：每次调用 writer 写 1 个总账行 + 1 个 step 行（kind=llm_call）。代码量增加几乎为 0。

**Agent 化行为**：每个执行节点写一行 step，主表的 `total_*` / `step_count` / `tool_call_count` 由 step 自动汇总。

### 3.3 复用既有表

| 表 | 是否改动 |
|---|---------|
| `CrmAiSession` | ❌ 不动 |
| `CrmAiMessage` | ❌ 不动（status 走总账） |
| `CrmAiContextSnapshot` | ⚠️ 加显式 `cache_key` 列（当前在 compact_json 里） |
| `CrmAiGuardrailEvent` | ⚠️ 加 `call_id` 外键（关联到调用） |
| `RagRetrievalLog` | ⚠️ 已有 `session_id/message_id`，加 `call_id` 列冗余便于直查 |

### 3.4 未来 Agent 化的演进路径（schema 零破坏）

假设未来 N 个月后启动 Agent 改造（意图识别 / 工具调用 / function call），现有 schema 的演进路径是：

| 阶段 | 操作 | schema 改动 |
|------|------|------------|
| 1. 标识 Agent 调用 | 走 Agent 流程的 invocation 写入时 `execution_mode="agent"` | 0 |
| 2. 写多个 step | 每次 LLM call、tool call、planning 写一行 step，kind 取注册表新值 | 0（注册表加值） |
| 3. 聚合指标 | `total_*` / `step_count` / `tool_call_count` 从 step 汇总到 invocation | 0 |
| 4. 详情页 step 树 | 审计页详情抽屉新增"执行轨迹" tab，按 step_index 展示 | 0 |
| 5. 诊断扩展 | 新增 probe（`_tool_registry.py` / `_agent_loop_health.py`）；新增错误码（`tool_*` / `agent_*`） | 0 |
| 6. 跨 trace 分析 | "本周 tool 失败率最高" → group by step.tool_name；"Agent 平均 step 数" → avg step_count | 0 |

**任何升级都不破坏现有数据，不改前端审计列表，不改诊断 pipeline 框架**。这是这版 schema 的最大价值。

---

## 4. 模块拆分（严格按 AGENTS.md 红线）

### 4.1 后端

```
app/crm_profile/
├── models.py                              # +CrmAiInvocation
├── routers/
│   ├── ai_audit_admin.py                  # 新：管理员审计列表/详情接口
│   └── ai_diagnostics.py                  # 新：诊断接口（self / admin / per-call）
├── services/
│   ├── audit.py                           # 改：write_session/message 加 call_id 参数
│   ├── invocation_audit/                  # 新：调用级审计（trace + step）
│   │   ├── __init__.py
│   │   ├── _writer.py                     # 写入封装：start / write_step / update_stage / finish / fail
│   │   ├── _query.py                      # 列表/详情查询（管理员接口用）
│   │   ├── _stage_registry.py             # 开放 stage 注册表 + validate_stage
│   │   └── types.py                       # ErrorCode Enum + StepKind 注册表
│   └── ai_diagnostics/                    # 新：诊断 pipeline
│       ├── __init__.py                    # diagnose(ctx) 主入口
│       ├── _registry.py                   # probe 注册器
│       ├── _types.py                      # ProbeResult / DiagnosticReport
│       ├── probes/
│       │   ├── _config.py                 # API key / base_url / model 配置
│       │   ├── _auth.py                   # token / 权限 / 客户可见性
│       │   ├── _profile_cache.py          # profile cache 状态
│       │   ├── _rag.py                    # Qdrant + embedding 连通性
│       │   ├── _network.py                # 后端到 provider DNS/TCP/TLS
│       │   ├── _provider_health.py        # 轻量模型探测（带限流缓存）
│       │   └── _concurrency.py            # in-flight / 错误率统计
│       └── stats/
│           ├── _error_rate.py             # 近 5/15/60 分钟错误率聚合
│           └── _concurrency_meter.py      # in-flight 计数器（Redis）
└── schemas/
    ├── ai_audit.py                        # 新：审计列表/详情 response
    └── ai_diagnostics.py                  # 新：诊断 response
```

每个文件 < 300 行；`probes/` 子包用 `_` 前缀做内部实现，符合 AGENTS.md "三层分离 + 子包私有"约束。

### 4.2 前端

```
frontend/src/
├── router/index.ts                        # 改：注册 /admin/ai-audit
├── views/AiAudit/                         # 新
│   ├── index.vue                          # 列表 + 抽屉式详情
│   ├── components/
│   │   ├── InvocationListTable.vue
│   │   ├── InvocationDetailDrawer.vue
│   │   ├── DiagnosticsPanel.vue
│   │   └── ContextSnapshotViewer.vue      # 上下文快照可读化
│   └── composables/
│       ├── useInvocationList.ts
│       └── useInvocationTypes.ts
├── views/CrmProfile/composables/
│   ├── sseStream.ts                       # 改：401 token refresh + 结构化错误解析
│   └── useAiCoach.ts                      # 改：保存 call_id / stage / diagnostics_summary
├── views/CrmProfile/components/
│   └── AiCoachAssistantMessage.vue        # 改：错误卡片分层（用户语言/动作/call_id）
└── utils/
    ├── request.ts                         # 改：抽出 token refresh 给 SSE 复用
    └── sseRequest.ts                      # 新：复用 token refresh 的 SSE 客户端
```

`useAiCoach.ts` 当前已 600+ 行（侧边栏方案里提过），这次再加诊断字段必须**只改不加**，不再往里塞函数。诊断详情交互放到 AiAudit 页面。

---

## 5. 错误码与 Stage 注册表

### 5.1 错误码白名单（强制 Enum + 命名空间）

错误码必须严格 Enum，因为前后端要做用户文案与推荐动作的精确映射。

**命名规范**（强制）：`<domain>_<reason>`，domain 取以下命名空间之一：
```
auth / permission / ai / profile / provider / network / rag /
stream / db / concurrency / 
tool / agent / intent      ← 预留 Agent 化命名空间
```

```python
# app/crm_profile/services/invocation_audit/types.py
class ErrorCode(str, Enum):
    # ───── auth 阶段 ─────
    AUTH_EXPIRED = "auth_expired"
    PERMISSION_DENIED = "permission_denied"
    
    # ───── prepare 阶段 ─────
    AI_DISABLED = "ai_disabled"
    PROFILE_CACHE_NOT_READY = "profile_cache_not_ready"
    PROVIDER_CONFIG_MISSING = "provider_config_missing"
    
    # ───── rag 阶段 ─────
    RAG_UNAVAILABLE = "rag_unavailable"
    
    # ───── model 阶段 ─────
    PROVIDER_AUTH_FAILED = "provider_auth_failed"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_OVERLOADED = "provider_overloaded"
    NETWORK_UNREACHABLE = "network_unreachable"
    
    # ───── stream 阶段 ─────
    STREAM_INTERRUPTED = "stream_interrupted"
    
    # ───── 系统 ─────
    CONCURRENCY_LIMITED = "concurrency_limited"
    DB_WRITE_ERROR = "db_write_error"
    UNKNOWN = "unknown"
    
    # ───── 预留命名空间（P0 不实现，命名规范声明）─────
    # tool_not_found / tool_execution_failed / tool_permission_denied / tool_timeout
    # agent_max_steps_exceeded / agent_planning_failed
    # intent_classification_failed / function_call_arg_invalid
```

每个 ErrorCode 必须在前端 `aiCoachTypes.ts` 的 `ERROR_CODE_PRESENTATION` 有对应的"用户可读文案 + 推荐动作"映射，由公共 ts 文件维护，杜绝硬编码漂移。

### 5.2 Stage 开放注册表（不锁 Enum）

`stage` 与 step.kind 都用注册表 + 校验函数，不用 Enum，原因：Agent 化迭代会频繁加 stage / kind，Enum 改动要协调全栈升级；用注册表 + warn 能让新 stage 平滑进入而不阻塞主链路。

```python
# app/crm_profile/services/invocation_audit/_stage_registry.py
import logging
_log = logging.getLogger(__name__)

# 单轮模式 stage（P0 全部实现）
SINGLE_TURN_STAGES = frozenset({
    "auth", "prepare", "rag", "persist_user_msg",
    "model", "stream", "persist_asst_msg",
})

# Agent 模式 stage（P0 占位，未来用）
AGENT_STAGES = frozenset({
    "intent_classification", "agent_plan", "tool_call",
    "tool_observation", "agent_synthesize",
})

# 多模态/扩展 stage（P0 占位）
EXTENSION_STAGES = frozenset({
    "vision_analyze", "attachment_extract",
})

KNOWN_STAGES = SINGLE_TURN_STAGES | AGENT_STAGES | EXTENSION_STAGES

def validate_stage(stage: str) -> str:
    """未知 stage 仅 warn，不阻塞主链路。"""
    if stage not in KNOWN_STAGES:
        _log.warning("Unknown invocation stage: %s", stage)
    return stage


# step.kind 同样用注册表
KNOWN_STEP_KINDS = frozenset({
    # P0 必用
    "llm_call",
    # P0 占位 / Agent 化要用
    "rag_retrieval", "tool_call", "intent_classification",
    "agent_plan", "safety_check", "context_assembly",
    "vision_analyze",
})

def validate_step_kind(kind: str) -> str:
    if kind not in KNOWN_STEP_KINDS:
        _log.warning("Unknown step kind: %s", kind)
    return kind
```

---

## 6. 开发 Plan（按 AGENTS.md 多线程协作切分）

### Phase P0：审计闭环（5-7 天，3 条线并行）

#### Line A：数据模型与写入封装（后端，2-2.5 天）
- [ ] `models.py` 新增 `CrmAiInvocation`（含 `execution_mode / step_count / tool_call_count / total_*` 字段）
- [ ] `models.py` 新增 `CrmAiTraceStep`（P0 单轮模式只写 1 行 step，schema 已为 Agent 化预留 kind/tool_name/parent_step_index）
- [ ] `schema_migrations.py` 增加 `ensure_crm_ai_invocation_columns` + `ensure_crm_ai_trace_step_columns` + 索引（按现有 `ensure_crm_ai_attachment_indexes` 范式幂等）
- [ ] `services/invocation_audit/_writer.py` 实现 `start_invocation / write_step / update_stage / finish_invocation / fail_invocation`
- [ ] `services/invocation_audit/_stage_registry.py` 实现 stage / step kind 注册表 + 校验函数
- [ ] `services/invocation_audit/types.py` 实现 `ErrorCode` Enum（含命名空间注释）
- [ ] `CrmAiContextSnapshot` 加 `cache_key` 列、`CrmAiGuardrailEvent` / `RagRetrievalLog` 加 `call_id` 列（幂等迁移）
- [ ] **focused validation**：写一组单测，验证状态机所有合法流转（pending→success / pending→error / pending→partial）+ step 写入聚合到主表 token/step_count 正确

#### Line B：调用主链路接入（后端，2-3 天，依赖 Line A）
- [ ] `ai/__init__.py` 三个入口（`ask_ai_coach` / `stream_ai_coach_answer` / `regenerate_ai_coach_answer`）注入 `call_id` 和 `execution_mode="single_turn"`
- [ ] `_helpers.py` 的 `_classify_ai_error` 升级为返回 `(stage, code)` 二元组，code 走 `ErrorCode` Enum
- [ ] 7 个 stage 全部接 `update_stage`；每个 try/except 边界 `fail_invocation`
- [ ] LLM 流式调用结束后写 1 行 step（kind=`llm_call`，记录 model/tokens/latency），并把 token 聚合到主表 `total_*`
- [ ] SSE error event 格式升级：`{code, stage, message, call_id, retriable, recommended_action}`
- [ ] **focused validation**：手动构造 5 种失败（profile cache 没好 / provider 超时 / RAG 挂 / 模型限流 / DB 写失败），确认每种都在总账有记录、SSE 有 call_id、step 表有对应记录

#### Line C：管理员审计前端（前端，3 天，与 A/B 并行）
- [ ] 路由 `/admin/ai-audit` + 菜单注册
- [ ] 列表页：时间 / 调用人 / 客户 / 场景 / 状态 / 错误码 / 模型 / 耗时筛选
- [ ] 详情抽屉：基础信息 / 用户问题 / 上下文快照可读化 / RAG 命中详情 / AI 回复 / 错误信息 / 关联反馈
- [ ] `ContextSnapshotViewer` 把 `compact_json` 按模块折叠展示（基础档案 / 安全档案 / 健康摘要 ...）
- [ ] **focused validation**：用 mock 数据跑通三种状态（success / partial / error）的列表+详情渲染

**P0 收口验收**：
- 所有调用（含失败）都在 `crm_ai_invocations` 有记录
- 通过 `call_id` 能在审计页一键定位完整链路
- 失败状态、错误阶段、错误码区分清晰
- SSE 错误事件包含 call_id

---

### Phase P1：诊断服务（5-7 天，3 条线并行）

#### Line D：Probe 框架与基础探针（后端，3 天）
- [ ] `services/ai_diagnostics/_registry.py` + `_types.py`
- [ ] 实现 6 个基础 probe：`_config / _auth / _profile_cache / _rag / _network / _concurrency`
- [ ] 每个 probe 独立超时（默认 800ms），并发执行
- [ ] `_provider_health` 走限流缓存（同一 provider 30s 内只跑一次轻量探测）
- [ ] **focused validation**：模拟每个 probe 的失败场景，确认 `DiagnosticReport.status` 收敛正确

#### Line E：诊断接口与失败自动诊断（后端，2 天，依赖 Line D）
- [ ] `routers/ai_diagnostics.py` 三个端点（self / admin run / per-call）
- [ ] 调用主链路在 `fail_invocation` 时**自动触发** Probe Pipeline，结果写入 `diagnostics_json`
- [ ] 错误率聚合服务（近 5/15/60 分钟）走 `stats/_error_rate.py`，从 `crm_ai_invocations` 读
- [ ] **focused validation**：跑一遍调用 → 失败 → 自动诊断 → 总账可见诊断结果

#### Line F：前端 SSE 改造与错误卡片（前端，3 天）
- [ ] `utils/request.ts` 抽出 `refreshTokenIfNeeded` 公共函数
- [ ] 新建 `utils/sseRequest.ts` 复用 token refresh
- [ ] `sseStream.ts` 处理 HTTP 401/403：401 触发刷新后重试一次，仍失败则提示重新登录
- [ ] `useAiCoach.ts` 错误处理保存 `callId / stage / diagnostics_summary`
- [ ] `AiCoachAssistantMessage.vue` 错误卡片分层：用户文案 / 推荐动作 / call_id 折叠展示
- [ ] 错误码 → 文案/动作映射放 `aiCoachTypes.ts` 的 `ERROR_CODE_PRESENTATION`
- [ ] **focused validation**：手动测 token 过期、无权限、上游限流三种场景的前端展示

**P1 收口验收**：
- token 过期能自动刷新或提示重登
- 上游 429 / 配置缺失 / RAG 挂 给出不同推荐动作
- 任意失败的 call_id 能在审计页看到对应的诊断结果

---

### Phase P2：运营化（按需推进，3-5 天）

#### Line G：日报与统计（后端 + 前端，2 天）
- [ ] 调用量 / 成功率 / 错误率 / 平均耗时 / token 消耗日报
- [ ] 按模型 / 供应商 / 客户 / 教练 / 错误码切片
- [ ] AiAudit 页加 Dashboard 区

#### Line H：跨模块跳转（前端，1 天）
- [ ] FeedbackReview 详情 → 跳到 AiAudit 调用详情
- [ ] RAG 检索日志 → 跳到 AiAudit 调用详情
- [ ] AiAudit 详情 → 跳到 FeedbackReview / RAG 日志

#### Line I：浏览器侧诊断（前端，2 天，可选）
- [ ] `/api/v1/health` ping
- [ ] 可配置外部探针（不硬编码 chatgpt/youtube）
- [ ] 文案严格按"辅助判断"措辞，禁止断言"用户使用 VPN"

---

## 7. 多线程协作纪律

按 AGENTS.md，本 plan 共 9 条线，**最佳并行度 3 条**：

```
Phase P0 并行：A → B（依赖 A） + C（独立）
   收口轮：合 PR、跑启动测试、对照 5 种失败场景
Phase P1 并行：D → E（依赖 D） + F（独立）
   收口轮：合 PR、跑启动测试、跑端到端"401 token 刷新"
Phase P2 并行：G + H + I（全独立）
```

**禁止**：
- A 没合并就开 B（会反复 rebase）
- C 越界改后端（错误码 Enum 必须由 B 拍板）
- D/E/F 之间互相 await（诊断 pipeline 与调用主链路解耦，自动诊断只在 fail_invocation 内单点接入）

每条线必须输出：
- 改动文件清单
- focused validation 截图或单测列表
- 启动验证（uvicorn + npm run dev 都过）
- 剩余缺口

---

## 8. 真值与口径纪律

按 AGENTS.md 真值规则严格区分：

| 信息 | 身份 | 落库位置 | 不允许 |
|------|------|---------|--------|
| 调用状态、错误码、错误阶段 | `official` | `crm_ai_invocations` | 散落日志 |
| 上下文快照、RAG 命中、用户问题 | `formal` | 各原表 | 在总账冗余存全文 |
| Probe 探测结果 | `support` | `diagnostics_json` | 当作"用户用 VPN"的结论 |
| 浏览器探针结果 | `support` | 不入库，仅 UI 提示 | 写成正式审计字段 |
| 模型常识 / 推断 | `unverified` | 不持久化 | 当作根因 |

`error_detail` 必须脱敏：
- 禁止存 API key、Authorization 头、完整请求体
- 异常 traceback 截断到前 2KB
- 涉及客户敏感字段（手机号 / 身份证）做掩码

---

## 9. 风险登记

| 风险 | 概率 | 缓解 |
|-----|------|------|
| `crm_ai_invocations` 写入失败导致主链路阻塞 | 中 | writer 全部用 try/except 包裹，失败只 log 不抛；每天对账 Session/Message 数量 vs Invocation 数量 |
| 自动诊断本身放大故障（上游已挂还要再调一次） | 中 | provider_health probe 30s 缓存；上游错误率 > 50% 时 5 分钟内不再跑 provider 探测 |
| 总账表 + step 表数据膨胀 | 高 | 90 天滚动归档 + 索引精确控制；详情/列表分离查询；step 表归档跟随主表级联 |
| 上下文快照在审计页泄漏敏感数据 | 高 | 管理员页面独立权限 `ai_audit`；快照展示层做字段级脱敏白名单 |
| 错误码漂移 | 中 | Enum 约束 + 命名空间规范文档化 + 前后端共享类型生成（手动维护一份 ts，加单测验证一致性） |
| Agent 化时 step 表 schema 不够用 | 低 | 预留 `parent_step_index` / `tool_name` / `tool_input_hash` / `input_json` / `output_json` 字段；新 kind 走注册表无需迁移 |
| step writer 失败但主表已写 | 中 | step 写入用独立 try/except；主表的聚合指标可在 finish_invocation 时重新从 step 表汇总；缺 step 行不影响主表 status 落库 |

---

## 10. 面向项目负责人的状态翻译

### 看见
教练用户能用 AI 对话；偶尔失败时只看到"请求失败"；管理员现在没办法定位是谁、哪个客户、为什么失败。

### 理解
现有审计数据 70% 已落库，但分散在 5 张表里，且**失败时不一定有完整记录**。要做闭环，关键是：
1. 加一张调用级总账（含 `call_id`）+ 一张 step 明细表，trace + step 双层结构
2. 失败必落账
3. 错误分类要分阶段，从 5 个粗类升级到 14+ 标准化错误码（Enum）；stage 与 step.kind 用开放注册表，给 Agent 化留口子
4. 诊断做成 Probe Pipeline，复用三个入口
5. 前端 SSE 错误协议统一，错误卡片分层显示

### 决策
- **本周 P0（5-7 天，3 线并行）**：交付审计闭环 + trace/step 雏形，解决"失败查不到"，同时为 Agent 化预埋
- **下周 P1（5-7 天，3 线并行）**：交付诊断服务，解决"不知道为什么失败"
- **本月 P2 按需**：日报、跨模块跳转、浏览器探针
- **未来 Agent 化**：零 schema 改动，只增 step 行 + 加 stage / kind / 错误码注册表条目（详见 §3.4）

### 闭环
真正的闭环路径：
```
教练发现问题 → 复制 call_id 给管理员 → 
管理员在 AI 调用审计页一键定位 → 
看到完整问题/上下文/RAG/回复/错误/诊断 → 
反向优化（权限 / 配置 / RAG / Prompt / 上下文预加载）→
观察日报错误率下降
```

### 当前 Blocker
无。`crm_ai_invocations` 是纯增量表，不影响现有调用逻辑。可立刻启动 P0。

### 下一步最值得做什么
P0 Line A（数据模型 + writer）开第一条线；前端 Line C（审计页）独立同步推。3 天后 Line A 收口，Line B 立即接入主链路。

---

## 11. 一句话原则

**审计不是加一张日志表，而是"调用即记录、失败即诊断、错误即可读、问题即可追"四件事的工程化闭环。**

`call_id` 是这套闭环的灵魂——它必须在第一时间生成、贯穿全链路、出现在每一条 SSE 错误、每一个审计字段、每一份诊断报告里。失去 `call_id` 的审计就只是好看的日志，不是工程闭环。

**trace + step 双层模型**是这套闭环的骨架——P0 单轮模式只多写 1 行 step，但未来升级到 Agent 模式（意图识别 / 工具调用 / function call）时不需要改 schema、不需要改前端列表、不需要改诊断 pipeline。这是 OpenTelemetry GenAI / LangSmith / Langfuse 等业界审计平台的共同范式，现在花 0.5 天前瞻设计，避免半年后被迫重做。

---

要点补一句：你原报告里**方案 A vs 方案 B 的取舍是这次架构最关键的分水岭**。这版 plan 直接 P0 上 B（新增总账表）并升级为 trace + step 双层，不走联表视图。代价只有"多写两张表+一个 writer"，收益是后续所有功能都基于稳定主表 + 天然支持 Agent 化扩展。

