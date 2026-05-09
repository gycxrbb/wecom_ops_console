# AI 教练 SSE 流式对话性能瓶颈调研报告

> 调研日期：2026-05-05
> 基于：thinking-stream + chat-stream 双路 SSE 架构的性能分析与优化方案

---

## 一、现状与核心数据

### 1.1 用户体感时间线（实测数据）

| 阶段 | 耗时 | 用户看到什么 |
|------|------|-------------|
| 发送消息 → thinking 首 chunk | ~8s | 骨架屏 → 思考摘要开始流式输出 |
| thinking 流输出完成 | ~7s | 300-500 字思考摘要（gpt-4o-mini） |
| **发送消息 → answer 首 chunk** | **~17s** | **空白等待，无任何反馈** |
| answer 流式输出完成 | ~6-8s | 正式回答逐字输出 |

**核心矛盾**：用户从发送到看到正式回答的第一个字需要 **17 秒**，而 DeepSeek 网页端几乎秒回。差距的根本原因在于架构差异。

### 1.2 为什么 DeepSeek 网页端能做到秒回？

| 维度 | DeepSeek 网页端 | 我们的 API 调用 |
|------|----------------|----------------|
| 提示词长度 | 系统级固定 prompt（~1K tokens），用户消息极短 | 5 层 prompt + 完整 CRM 上下文（~5-8K tokens） |
| KV Cache | 服务端持久化，同一会话复用前文 prefill | 无状态 API，每次完整 prefill |
| 模型路由 | 可能使用推理加速硬件 + 前缀缓存 | 标准推理服务，无缓存 |
| 连接 | 长连接，已建立 TLS + HTTP/2 | 每次新建请求（连接池复用但仍有 prefill 开销） |
| 输出模式 | 直接流式输出正文 | 双路流：先 thinking 再 answer |

**结论**：DeepSeek 网页端的 "秒回" 依赖于服务端 KV Cache + 轻量 prompt + 前缀缓存。我们通过 API 无法获得这些优化，每次请求都是完整的 ~8K token prefill。

---

## 二、逐层瓶颈分析

### 2.1 Profile 缓存准备（~4 秒）

**链路**：`stream_ai_coach_answer` → `_prepare_ai_turn_cached` → `_prepare_ai_turn_async` → `get_ai_ready_profile_context` → L1/L2 缓存查询

**瓶颈根因**：

1. **L1 TTL 过短**：`PROFILE_TTL = 600s`（10 分钟），而 L2 fresh TTL 是 1800s。L1 每 10 分钟失效一次，失效后需从 L2 反序列化（SQLite 查询 + JSON decode），约 50-200ms。
2. **Prepare Cache 冗余工作**：`_prepare_ai_turn_cached` 在 HIT 时仍重新调用 `build_context_text()`（对 12 个模块做文本序列化），虽然无 I/O，但增加了 ~10-50ms。
3. **RAG 检索阻塞**：`_prepare_ai_turn_async` 中 `await _rag_retrieve()` 完全阻塞后续流程（300-1800ms）。
4. **Profile Loader 串行加载**：`profile_loader.py` 中 12 个模块顺序查询 CRM 数据库，首次构建可能需要 2-4 秒。

**实测影响**：从请求进入到 `prepare done`，日志显示 4.0 秒（含缓存查询 + RAG + context 序列化）。

### 2.2 DeepSeek API 首 Chunk 延迟（~13 秒）— 最大瓶颈

**链路**：`chat_completion_stream` → httpx SSE → DeepSeek API → 首个 `data:` 行

**瓶颈根因**：

| 子阶段 | 耗时 | 说明 |
|--------|------|------|
| HTTP 连接建立 | ~1.5s | TCP + TLS 握手（连接池可复用） |
| 服务端 prefill | ~11.4s | DeepSeek 对 ~8K tokens 做完整 prefill |
| 首 chunk 到达 | — | 模型开始 decode |

**prefill 为什么这么慢？**

- DeepSeek-v4-pro 是大模型（推测 >100B 参数），每次请求需对完整 prompt 做 self-attention 计算
- 我们的 prompt ~5-8K tokens，prefill 计算量 = O(n²) 相对于 prompt 长度
- API 是无状态的，无会话级 KV Cache 复用
- DeepSeek 可能存在请求排队（rate limiting / 公共资源竞争）

**不可控因素**：这是 DeepSeek 服务端的延迟，我们无法在客户端优化。

### 2.3 Thinking 流（已优化，当前 ~2s 首 chunk）

**当前架构**：gpt-4o-mini via aihubmix，轻量 prompt ~100 tokens，max_tokens=2000。

- 首 chunk 延迟：~2.5s
- 完整输出：~7s（70 chunks，含 30ms/chunk 的节流）
- **已经足够快**，是当前体验的亮点

### 2.4 前端渲染（无明显瓶颈）

- `streamSse()` 使用 ReadableStream 直接解析 SSE，无额外缓冲
- Vue 响应式系统通过 nextTick 合并 DOM 更新，效率良好
- 思考面板 300ms 自动折叠，节奏合理
- **无优化空间**，前端不是瓶颈

---

## 三、优化方案

按 **投入产出比** 排序，从高到低。

### 3.1 [P0] Answer 流换用更快的模型/Provider

**问题**：DeepSeek prefill 13 秒是体验的致命伤。

**方案 A：Answer 也走 aihubmix**

```
ai_provider = 'aihubmix'      # 默认走 aihubmix
ai_model = 'gpt-4o'           # 或 claude-sonnet-4-6
```

- gpt-4o 首 chunk ~2-4s（实测 gpt-4o-mini ~1.3s，gpt-4o 估计 ~3s）
- prompt 不变，只换 provider
- **风险**：aihubmix 可能有速率限制，且 gpt-4o 成本高于 DeepSeek
- **预期收益**：answer TTFT 从 17s 降到 **5-7s**

**方案 B：DeepSeek + 更短 prompt**

- 压缩 base prompt（当前 ~1.5K tokens），合并 L1+L2 层
- 减少客户上下文字段数量（从 ~100 字段砍到 ~40 核心字段）
- RAG 来源从 5 个减到 3 个
- **预期收益**：prompt 从 8K 降到 ~4K，prefill 从 13s 降到 **~7s**

**方案 C：双 provider 策略（推荐）**

- 默认用 aihubmix (gpt-4o) 做日常问答，首 chunk ~3s
- DeepSeek (deepseek-v4-pro) 仅用于需要深度推理的复杂场景（如 `data_monitoring`、`abnormal_intervention`）
- 在路由层根据 scene_key 动态选择 provider
- **预期收益**：80% 的问答在 5s 内首 chunk，复杂场景仍可接受

### 3.2 [P1] 并行化 Profile 准备与 AI 调用

**当前**：串行 `prepare → AI stream`

```
请求进入 → [prepare 4s] → [AI stream 13s] → 首 chunk
总 TTFT ≈ 17s
```

**优化后**：在 prepare 过程中预建立 AI 连接

```
请求进入 → [prepare 4s] ──┐
                          ├→ [AI prefill 13s] → 首 chunk
         [预热连接 1.5s] ─┘
总 TTFT ≈ max(4s + connect, 13s) ≈ 13s（节省 ~1.5s 连接时间）
```

**更激进的方案**：在 prepare 的同时，用一个占位 user message 先发 AI 请求，等 prepare 完成后再补发真正的 messages。但 SSE 协议不支持这种操作，且模型已经开始输出。

**实际收益有限**：连接建立只占 ~1.5s，大头在 prefill。

### 3.3 [P1] Profile 缓存 TTL 优化

**改动**：
1. `PROFILE_TTL` 从 600s 提升到 1800s（与 L2 fresh TTL 对齐）
2. Prepare Cache HIT 时跳过 `build_context_text()` 重算，直接复用缓存的 `context_text`

**文件**：
- `app/crm_profile/services/cache.py` 第 22 行
- `app/crm_profile/services/ai_coach.py` 第 309/317 行

**预期收益**：
- 减少 L1 miss 频率（从每 10 分钟一次降到每 30 分钟一次）
- Prepare 阶段从 ~4s 降到 ~2-3s（减少冗余序列化）

### 3.4 [P2] Profile Loader 并行加载

**当前**：12 个模块串行查询 CRM 数据库

```python
for mod in _LOADERS:  # 12 个模块顺序执行
    card = mod.load(conn, customer_id)
```

**优化**：使用 `concurrent.futures.ThreadPoolExecutor` 并行加载

```python
with ThreadPoolExecutor(max_workers=6) as pool:
    futures = {pool.submit(mod.load, conn, customer_id): mod for mod in _LOADERS}
    for future in as_completed(futures):
        cards.append(future.result())
```

**预期收益**：
- 首次 profile 构建从 ~2-4s 降到 ~0.5-1s（取决于数据库并发能力）
- 仅影响缓存 MISS 路径，缓存 HIT 时无收益

### 3.5 [P2] RAG 异步化（不阻塞主流程）

**当前**：RAG 检索完全阻塞 answer 流

```python
rag_bundle = await _rag_retrieve(...)  # 300-1800ms 阻塞
```

**优化**：先启动 AI 流（无 RAG 上下文），RAG 结果作为后续 system message 注入

但 OpenAI API 的 messages 格式不支持流式追加 system message，所以需要换一种思路：

**替代方案**：RAG 结果提前缓存，按 customer + scene 预取

- 在用户打开 AI 面板时（preload 阶段）预取 RAG
- 缓存 RAG 结果 5 分钟，answer 流直接读取
- **预期收益**：answer prepare 阶段减少 300-1800ms

### 3.6 [P3] Prompt 压缩

**当前各层 token 估算**：

| 层 | Token 数 | 说明 |
|----|---------|------|
| L1 Platform Guardrails | ~300 | 安全边界、医疗免责 |
| L2 Health Coach Core | ~1,500 | 角色、方法论、输出结构 |
| L3 Scene Strategy | ~400-600 | 场景策略 |
| L4 Customer Context | ~500-3,000 | CRM 卡片序列化 |
| L4.5 RAG | 0-1,200 | 知识库片段 |
| L5 Profile Note | 0-300 | 教练备注 |
| L6 User Message + Style | ~100-400 | 用户问题 + 输出模式 |
| **总计** | **~3,000-7,300** | |

**优化方向**：

1. **合并 L1 + L2**：platform guardrails 和 health coach core 合并为一个 system message，减少一次 self-attention 计算
2. **精简 FIELD_LABELS**：`context_builder.py` 中 ~100 个字段标签，很多 AI 不需要（如内部 ID、时间戳），砍到 ~40 个核心字段
3. **Scene prompt 精简**：当前场景模板 ~400-600 tokens，可压缩到 ~200 tokens（只保留核心指令，去掉示例）
4. **Token 预算从 30K 降到 15K**：强制截断冗余上下文

**预期收益**：prompt 从 ~6K 降到 ~3K，DeepSeek prefill 从 ~13s 降到 **~7s**

---

## 四、综合优化路线图

### 阶段一（立即可做，1-2 小时）

| 改动 | 预期收益 | 难度 |
|------|---------|------|
| Profile L1 TTL 600s → 1800s | 减少缓存 miss | 改一行配置 |
| Prepare Cache 跳过冗余 build_context_text | 减少 ~50ms | 小改 |
| Prompt 压缩（精简字段标签） | 减 ~1K tokens | 中改 |

**预期 TTFT**：17s → **~15s**（小幅改善）

### 阶段二（核心优化，1-2 天）

| 改动 | 预期收益 | 难度 |
|------|---------|------|
| **Answer 流默认走 aihubmix (gpt-4o)** | **TTFT 从 17s 降到 ~5-7s** | 配置切换 |
| 复杂场景动态路由到 DeepSeek | 保留深度推理能力 | 路由层小改 |
| RAG 预取（preload 时触发） | 减少 prepare 阶段 300-1800ms | 中改 |

**预期 TTFT**：17s → **~5-7s**（质变级提升）

### 阶段三（锦上添花，3-5 天）

| 改动 | 预期收益 | 难度 |
|------|---------|------|
| Profile Loader 并行加载 | 首次构建 2-4s → 0.5-1s | 中改 |
| Prompt 合并 L1+L2 | 减少 ~0.5s prefill | 小改 |
| 场景化 Token 预算 | 按场景动态调整上下文量 | 需要调优 |

**预期 TTFT**：~5-7s → **~3-5s**（接近网页端体感）

---

## 五、技术决策建议

### 5.1 最核心的决策：Answer 流是否切 Provider？

**当前**：answer 用 DeepSeek-v4-pro（首 chunk 13s）
**建议**：默认切 aihubmix (gpt-4o)

| 维度 | DeepSeek-v4-pro | gpt-4o (aihubmix) |
|------|-----------------|-------------------|
| 首 chunk 延迟 | 12-13s | 3-4s |
| 输出质量 | 优秀（深度推理） | 优秀（综合能力） |
| 成本 | 低（¥0.002/1K tokens） | 中（¥0.01/1K tokens） |
| 稳定性 | 偶尔超时 | 较稳定 |
| 中文能力 | 极强 | 强 |

**推荐策略**：
- 默认 gpt-4o 做 answer（覆盖 80% 场景）
- 复杂场景（数据异常解读、深度分析）可选切 DeepSeek
- 成本增加约 5x，但用户体验从 17s 降到 5s，ROI 极高

### 5.2 为什么不继续优化 DeepSeek 路径？

DeepSeek 的 13s prefill 是服务端行为，我们无法控制：
- 无法启用服务端 KV Cache（API 不支持）
- 无法减少排队延迟（共享资源）
- 压缩 prompt 可降到 ~7s，但仍远慢于 gpt-4o 的 3s

**结论**：在 DeepSeek 提供 prompt caching API（类似 Anthropic 的 cache_control）之前，API 路径无法达到网页端的速度。

---

## 六、当前已完成的优化

| 优化项 | 改动前 | 改动后 |
|--------|--------|--------|
| Thinking 流模型 | deepseek-v4-pro (13s) | gpt-4o-mini (1.3s) |
| Thinking prompt | 完整 5 层 ~8K tokens | 轻量 ~100 tokens |
| Thinking max_tokens | 无限制 | 2000（足够 300-500 字） |
| Thinking 流式节流 | 无（瞬间完成） | 30ms/chunk（自然节奏） |
| Thinking 输出质量 | 80 字以内 | 300-500 字结构化分析 |
| SSE error handler | ResponseNotRead crash | 安全处理流式错误 |
| Provider 路由 | 默认混用 | thinking 明确走 aihubmix |

---

## 七、关键代码文件索引

| 文件 | 职责 |
|------|------|
| `app/crm_profile/services/ai_coach.py` | 主编排：prepare、stream、safety gate |
| `app/crm_profile/services/prompt_builder.py` | 5 层 prompt 组装 |
| `app/crm_profile/services/profile_loader.py` | 12 模块串行加载 |
| `app/crm_profile/services/profile_context_cache.py` | L1/L2 缓存管理 |
| `app/crm_profile/services/context_builder.py` | CRM 卡片 → 文本序列化 |
| `app/clients/ai_chat_client.py` | OpenAI 兼容客户端，双 provider failover |
| `app/config.py` | Provider/模型配置 |
| `frontend/src/views/CrmProfile/composables/useAiCoach.ts` | 前端 SSE 连接管理 |
| `frontend/src/views/CrmProfile/components/AiCoachThinkingPanel.vue` | 思考面板渲染 |
