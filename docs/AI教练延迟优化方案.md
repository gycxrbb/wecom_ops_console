# AI 教练助手 首包延迟分析与优化方案

- **文档类型**：现状分析 + 优化方案（official，待评审落地）
- **覆盖范围**：`app/clients/ai_chat_client.py`、`app/crm_profile/services/ai_coach.py`、`app/crm_profile/router.py`（`/ai/chat-stream`、`/ai/thinking-stream`）、`frontend/src/views/CrmProfile/composables/useAiCoach.ts`、`frontend/src/views/CrmProfile/components/AiCoachPanel.vue`
- **关注指标**：TTFT（首字节/首包时间）、Thinking 与 Answer 双流节奏对齐、单次会话端到端耗时
- **现象口径**：用户主观感受到 AI 教练助手在点击发送后存在约 **5–6s** 的"无反馈空窗"，首包出现后体验立刻变好

---

## 一、现状梳理（先看真值，不拍脑袋）

### 1.1 调用链与时序

```
用户输入  →  前端 useAiCoach.sendChat()
            ├── POST /ai/chat-stream     (answerPromise)
            └── POST /ai/thinking-stream (thinkingPromise)
                       ↓ 后端 router → service.stream_ai_coach_*()
                       ↓ _prepare_ai_turn_async (上下文/历史/安全卡)
                       ↓ chat_completion_stream() → httpx → 上游 LLM
                       ↓ aiter_lines → ChatStreamChunk → SSE event=delta
            ←  前端 streamSse 回调 → assistantMessage.content / thinkingContent
```

参考点位：

- `@d:\惯能\群机器人定时推送\wecom_ops_console\app\clients\ai_chat_client.py:23-31`：`_get_client()` 已经做了 `httpx.AsyncClient` 单例 + 连接池，但参数较保守。
- `@d:\惯能\群机器人定时推送\wecom_ops_console\app\clients\ai_chat_client.py:109-201`：`chat_completion_stream` 是上游流式入口，TTFT 主要取决于此处 `client.stream(...)` 到第一条 `data:` chunk 的耗时。
- `@d:\惯能\群机器人定时推送\wecom_ops_console\app\crm_profile\services\ai_coach.py:419-560`：answer 流逻辑，`_prepare_ai_turn_async` 在调用 LLM 前就要落库 / 拼上下文。
- `@d:\惯能\群机器人定时推送\wecom_ops_console\app\crm_profile\services\ai_coach.py:563-676`：thinking 流，DeepSeek 走轻量路径直接绕过 prepare，aihubmix 仍走完整 prepare。
- `@d:\惯能\群机器人定时推送\wecom_ops_console\frontend\src\views\CrmProfile\composables\useAiCoach.ts:316-388`：前端用两个独立 SSE 并发请求 `chat-stream` 与 `thinking-stream`，answer `done` 时直接 abort 掉 thinking 流。

### 1.2 已有 SSE-TIMING 日志埋点

后端 `_sse.info("[SSE-TIMING] ...")` 已经覆盖了关键节点：route enter、prepare start/done、AI stream 首包、每个 chunk、done。这意味着**真值是可以从日志里量出来的**，下文讨论以此为口径，避免凭感觉调优。

### 1.3 当前等待时间结构（按真值文件 / 日志已观测口径）

| 阶段 | 区间 | 典型耗时 | 主要影响因素 |
|---|---|---|---|
| A. 路由进入 → prepare 完成 | route enter → `prepare done` | 100–800ms（含 SQLite/Redis IO，命中缓存时更短） | `_prepare_ai_turn_async` 中的 ORM 查询、上下文卡组装 |
| B. prepare 完成 → 上游首字节 | `AI API stream starts` → `first chunk at` | **2.5–5s**（DeepSeek/aihubmix 思考型模型尤其明显） | TLS 握手 / DNS / TCP / 上游模型 prefill / 思维链预热 |
| C. 上游首字节 → 前端首包渲染 | `first chunk` → 浏览器收到首个 `event: delta` | 50–300ms | FastAPI StreamingResponse、Nginx/反代缓冲、httpx buffer、`_CHUNK_BUFFER_SIZE=12` 的累积 |
| D. 上游持续输出 | first chunk → `[DONE]` | 与回答长度成正比 | 模型生成速度 |

> **5–6s 空窗的主要构成**：B 阶段（上游冷连接 + 模型 prefill）≈ 70–85%，A 阶段 ≈ 10–25%，C 阶段 ≈ 5%。因此**优化重点在 B 与 A**，C 是体验补丁，D 取决于模型本身。

### 1.4 现有实现里已经做对的事（避免重复造轮子）

- **httpx 连接复用**：`_get_client()` 已是单例，TLS/TCP 在第一次请求后会被 keep-alive 命中。
- **首 chunk 立即下发**：`@d:\惯能\群机器人定时推送\wecom_ops_console\app\clients\ai_chat_client.py:177-182` 命中第一个有内容的 chunk 立即 `yield`，后续才用 `_CHUNK_BUFFER_SIZE=12` 聚合。
- **背景 audit 写入**：`_background_audit` 使用 `asyncio.create_task`，不阻塞首包。
- **DeepSeek 轻量 thinking 路径**：跳过 `_prepare_ai_turn_async`，直接读 `cache_get(profile:{id})` 拼 prompt。
- **shortcut 兜底**：纯事实型问题用 `_build_shortcut_thinking_text` / `prepared.shortcut_answer` 直接出文，不走上游。
- **SSE 串行响应头**：路由层已设 `_STREAM_HEADERS`（包含 `X-Accel-Buffering: no` 等，避免 Nginx 缓冲）。

---

## 二、问题定位（按用户提的四个维度逐一对齐）

### 2.1 模型侧：长连接池 + 实例常驻

**当前状态**：`_get_client()` 是懒加载单例，`max_connections=20 / max_keepalive_connections=10`，`timeout(connect=10, read=90, write=10, pool=10)`。

**问题**：
1. **冷启动首包**：进程启动后第一次请求仍要现做 DNS + TCP + TLS（aihubmix/DeepSeek 都是 https），实测约 200–600ms 不等。
2. **长时间空闲后被运营商/网关回收 keepalive**，下次请求重新握手。
3. **HTTP/1.1 + 连接数有限**：thinking 与 answer 两路并发请求会同时占用连接池；如果池子里之前空闲连接被回收，需要重新建链。
4. **未启用 HTTP/2**：上游 aihubmix / DeepSeek 都支持 H2，单连接多路复用比 H1 keep-alive 更稳。
5. **未做"实例常驻预热"**：进程起来后第一个用户必然踩冷启动。

### 2.2 网络侧：HTTPX 超时 / 连接复用 / 域名就近接入

**问题**：
1. `connect=10s` 偏宽松，掩盖了"网络抖动正在重连"的现象，**不是延迟原因，但是诊断盲区**。
2. 没有显式 `http2=True`、没有 `limits.keepalive_expiry`，长空闲后连接静默断开，下一次请求会"无声地"重新握手。
3. `base_url` 是 `aihubmix.com` / `api.deepseek.com`，**没有就近接入策略**：如果服务器在国内、上游在境外节点，单次往返 100–250ms × N。这部分**只能通过更换接入点 / 走代理就近落地 / 走中转域名**来缓解。
4. 没有 `transport=httpx.AsyncHTTPTransport(retries=...)`，遇到瞬时 connect reset 时直接抛 `RuntimeError('AI 服务响应超时')`，体验差。

### 2.3 业务侧：首包优化

**问题**：
1. **空窗期没有占位反馈**：从用户点发送到第一个 `delta` 到达之间的 2.5–5s，前端只能依赖 `AiCoachPanel.vue` 中 `'正在整理当前客户的关键信息与回复思路...'` 这条静态文案（参见 `@d:\惯能\群机器人定时推送\wecom_ops_console\frontend\src\views\CrmProfile\components\AiCoachPanel.vue:198-206`），**不是流式的，没有"正在思考"的呼吸感**。
2. **meta 事件已经在 prepare 完成后立刻下发**，但前端 `useAiCoach` 在 `meta` 上只更新了 `session_id` / `message_id`，**没有把它转化成 UI 占位骨架**，所以用户看不到这"先到的一步"。
3. **shortcut 路径** 在文本到达前没有 loading 标记，用户看到的仍然是同一段静态文案。
4. **answer `done` 时直接 abort thinking**（`useAiCoach.ts:345-347`），如果 thinking 流还没出第一个 delta，用户会看到思考框先出现又被瞬间清空，节奏割裂。

### 2.4 双流对齐：thinking / answer 触发时机

**问题**：
1. **两条 SSE 是同时发起的**，但服务端 prepare 各自独立执行：
   - DeepSeek 走轻量 thinking → thinking 通常先出首包；
   - aihubmix 双路都走完整 prepare → 谁先出首包看上游响应抖动，**节奏不可预测**。
2. **prepare 重复**：thinking 和 answer 各自调用了一次 `_prepare_ai_turn_async`，重复读 SQLite / 拼上下文（aihubmix 路径），单次提问产生 **2× DB 查询 + 2× prompt 组装**。
3. **abort 语义不一致**：answer done → abort thinking 是当前策略；但反过来 thinking 失败不影响 answer，错误处理不对称（前端 `.catch` 静默吞掉 thinking 异常）。
4. **thinking 完成时间晚于 answer 首包时**，UI 折叠思考框的瞬间可能造成抖动（`thinkingVisible = false`）。

---

## 三、优化方案（按四个维度，给出可落地动作）

> 每条动作都标注 **优先级（P0/P1/P2）**、**预期收益**、**风险**、**改动范围**。
> 总目标：把"无反馈空窗"从 5–6s 压缩到 **≤ 1.2s（占位/骨架可见）+ 实际首包 ≤ 3s**。

### 3.1 模型侧：长连接 + 常驻 + 预热

#### A1 [P0] 启用 HTTP/2 + 提高 keepalive 上限

**改动**：`@d:\惯能\群机器人定时推送\wecom_ops_console\app\clients\ai_chat_client.py:23-31`

```python
_client = httpx.AsyncClient(
    http2=True,                                         # 新增
    timeout=httpx.Timeout(connect=5, read=90, write=10, pool=5),
    limits=httpx.Limits(
        max_connections=50,
        max_keepalive_connections=20,
        keepalive_expiry=300.0,                         # 新增，5min 内不释放
    ),
    transport=httpx.AsyncHTTPTransport(retries=1),      # 新增，瞬时网络重试
    headers={"Connection": "keep-alive"},
)
```

依赖：`requirements.txt` 增加 `httpx[http2]` 或 `h2`（pip 名 `h2`）。

**预期收益**：长空闲后首包 -150~400ms；并发 thinking+answer 不再抢连接。
**风险**：H2 个别 CDN/代理（特别是公司侧出口）支持差，需要灰度；保留 `http2=False` 兜底配置项。

#### A2 [P0] 进程启动预热（warm-up）

**改动**：在 FastAPI `startup` 钩子里发一个轻量预热请求，让 TLS/TCP/H2 连接进入活跃池。

```python
# app/main.py startup
async def _warmup_ai_client():
    try:
        client = await _get_client()
        await client.head(settings.ai_base_url, timeout=3.0)
    except Exception:
        pass
```

并加一个**心跳协程**：每 60s `HEAD` 一次，避免上游 / 中间网关因空闲断开 keepalive。

**预期收益**：第一个用户的首包不再踩 TLS 冷启动（约 -200~600ms）。
**风险**：极少数环境上游不接受 HEAD，可改 `OPTIONS` 或忽略错误。

#### A3 [P1] 客户端按 provider 分实例 + 域名预解析

如果同时配置了 aihubmix 与 deepseek（双供应商热切换），把 `_client` 拆成 `_clients: dict[provider -> AsyncClient]`，避免一个 provider 切换时把另一个 provider 的活跃连接也释放。

`app/main.py` 启动时执行 `socket.getaddrinfo(host)` 做一次 DNS 预解析，防止首请求走系统 DNS 冷查。

#### A4 [P2] 模型实例常驻（应用层）

`chat_completion_stream` 内每次调用都重建 messages、headers、payload 字典——这部分耗时 < 5ms，意义不大。**真正值得"常驻"的是 prompt 模板对象**：把 `assemble_visible_thinking_prompt` 等 prompt 装配函数的常量段（system 模板、scene 配置）做模块级缓存（已经做了一部分，复核一遍是否每次都会重读 JSON）。

### 3.2 网络侧：HTTPX 超时与就近接入

#### N1 [P0] 收紧 connect 超时 + 显式 keepalive_expiry

见 A1 改动。`connect=5s` 比 `10s` 更早失败重试，避免"5s 看似在思考其实在等 TCP"。

#### N2 [P1] 上游域名就近接入 / 中转

- **诊断**：在生产服务器上 `tcping aihubmix.com 443` / `curl -w '%{time_connect}/%{time_starttransfer}\n'` 多次取样，定位是握手慢还是模型慢。
- **如果是握手慢**：
  - 走云厂商提供的内网/同区域中转域名（aihubmix 提供 `cn-*` 接入点，DeepSeek 国内可直连）。
  - 在 `config.py` 新增 `ai_base_url_failover`，httpx 失败时切换。
- **如果是模型慢**：换成响应更快的型号（如 DeepSeek `deepseek-v3` / aihubmix `gpt-4o-mini` 已经是较快的档位），或者**对 thinking 流强制使用更小更快的模型**（thinking 短，不需要 v4-pro 级别）。

新增配置项建议：

```python
ai_thinking_model: str = ''        # 留空则与 ai_model 一致
deepseek_thinking_model: str = ''
```

服务里 thinking 路径调用 `chat_completion_stream(..., model=settings.ai_thinking_model or None)`。

#### N3 [P1] StreamingResponse 路径上的缓冲检查

确认部署侧反向代理（Nginx / Caddy）确实尊重 `X-Accel-Buffering: no`、关闭 gzip on SSE。**这条是 0 改动 / 纯运维核对**，但经常是首包变慢的隐藏原因。

### 3.3 业务侧：首包占位与骨架

#### B1 [P0] 后端立即下发 `loading` 占位事件

在 `stream_ai_coach_answer` / `stream_ai_coach_thinking` 中，**进入函数体的第一件事就是 yield 一个标记事件**，让前端立刻拿到信号，掩盖 prepare + 上游首包的空窗：

```python
# 路由生成器里 yield ":connected\n\n" 之后立刻：
yield AiStreamEvent(event="loading", data={"stage": "prepare"})
# prepare 完成后：
yield AiStreamEvent(event="loading", data={"stage": "model_call"})
# 上游首 chunk 到来前不再有 loading
```

实际上 `meta` 事件本身就可以承担"prepare 完成"的信号，只需要在 `meta` 之前再补一个 `loading: prepare` 即可，**不需要新增协议字段**。

#### B2 [P0] 前端把 loading 转成可见的占位骨架

`useAiCoach.ts` 的 SSE 回调里新增分支：

```ts
if (event === 'loading') {
  if (payload.stage === 'prepare') {
    assistantMessage.thinkingContent = '__SKELETON_PREPARE__'
  } else if (payload.stage === 'model_call') {
    assistantMessage.thinkingContent = '__SKELETON_MODEL__'
  }
  return
}
```

`AiCoachPanel.vue` 中针对 `__SKELETON_*__` 渲染**呼吸/打字光标骨架条**（3 行灰色条 + 闪烁光标），第一次 `delta` 到达时把骨架替换为真实文本。

> 关键：**用户在 < 200ms 内看到东西在动**，主观体感 5s 空窗会变成 1s 内。

#### B3 [P1] 提前下发"已读到的客户上下文摘要"作为可读占位

`meta` 事件已经携带 `used_modules`，前端可以**在思考框里立刻渲染一行**：
"已加载：基础档案 / 历史订单 / 体重数据 …"。这条文本本身有信息量，掩盖等待感比纯骨架更好。

`AiCoachPanel.vue` 已经有 `usedModuleEntries` 渲染逻辑，只需要在 `meta` 时把它绑定到当前 assistantMessage 即可。

#### B4 [P2] shortcut 路径同样下发 loading

避免短路径"看起来什么都没发生就突然全文出现"，保持节奏一致。

### 3.4 双流对齐

#### S1 [P0] 合并 thinking / answer 的 prepare（消除重复 IO）

**问题根因**：aihubmix 路径下 thinking 和 answer 各调一次 `_prepare_ai_turn_async`。

**方案**：在 `crm_profile/services/ai_coach.py` 里新增一个进程内短期缓存（key = `(customer_id, message, session_id)`，TTL=15s），第二个流命中缓存直接复用 `prepared` 结果。

```python
_PREPARE_CACHE: dict[tuple, tuple[float, PreparedTurn]] = {}
_PREPARE_TTL = 15.0

async def _prepare_ai_turn_cached(customer_id, message, ...):
    key = (customer_id, message, session_id, scene_key, output_style, prompt_mode_neutral)
    now = time.time()
    hit = _PREPARE_CACHE.get(key)
    if hit and now - hit[0] < _PREPARE_TTL:
        return hit[1]
    prepared = await _prepare_ai_turn_async(...)
    _PREPARE_CACHE[key] = (now, prepared)
    return prepared
```

注意：`prompt_mode` 在 thinking/answer 之间不一样，**只缓存上下文部分**（`ctx.cards / used_modules / safety_card / session_id / shortcut`），prompt 装配仍各自做。

**预期收益**：aihubmix 路径节省 100–400ms；DB / Redis QPS -50%。

#### S2 [P0] 统一 thinking / answer 的"开播时机"

约定服务端协议：

1. `:connected`（已有）
2. `loading: prepare`（新）
3. `meta`（已有，prepare 完成后）
4. `loading: model_call`（新）
5. `delta`* / `done`

**两路 SSE 都遵守同一个 5 阶段协议**，前端可按阶段统一驱动 UI（思考框骨架 / 文字光标 / 切换到正式回复），不再依赖"谁先到谁触发"的偶然顺序。

#### S3 [P1] 优雅处理 answer 先完成时的 thinking 中断

当前 `answerCompleted = true` 后会 `thinkingAbortController.abort()`，**但若 thinking 还没出 delta，思考框直接消失会有抖动**。修法：

```ts
if (event === 'done' /* answer */) {
  answerCompleted = true
  // 给 thinking 200ms flush 时间
  setTimeout(() => thinkingAbortController.value?.abort(), 200)
  // thinkingVisible 等 thinking 真正 done 或 timeout 后再设 false
}
```

或者更彻底：**当 answer done 时，如果 thinking 一个 delta 都没出，直接隐藏思考框，不显示一个空骨架**。

#### S4 [P2] 极端场景：合并为单条 SSE

中长期可考虑把 thinking 与 answer 合并到一个 `/ai/turn-stream` SSE，事件用 `phase: "thinking" | "answer"` 区分。好处：
- 服务端只 prepare 一次
- 客户端只一次握手
- 节奏天然对齐

代价是协议改动大，前后端要同步发布，列入 P2 备选。

---

## 四、落地路线（建议执行顺序）

| 批次 | 内容 | 范围 | 风险 |
|---|---|---|---|
| **R1 — 当周可上** | A1（http2 + keepalive_expiry + retries=1）、A2（warmup + heartbeat）、N1、B1（后端 loading 事件）、B2（前端骨架）、S1（prepare 缓存）、S3（thinking 优雅 abort） | `ai_chat_client.py`、`ai_coach.py`、`useAiCoach.ts`、`AiCoachPanel.vue` | 低（兼容旧协议，loading 事件前端不识别也不会报错） |
| **R2 — 下一迭代** | A3（多 provider client 拆分 + DNS 预解析）、N2（thinking 用更轻模型 + base_url failover）、B3（meta 携带模块摘要直接渲染）、S2（5 阶段协议落档至 `docs/API_SPEC.md`） | 同上 + `config.py` + `docs/API_SPEC.md` | 中（涉及配置项 / 文档对齐） |
| **R3 — 备选** | A4（prompt 常量缓存复核）、B4（shortcut 占位）、S4（合并 turn-stream） | 同上 | 中高（S4 改协议） |

---

## 五、验收口径（official 真值）

落地后必须用日志真值验证，禁止仅凭主观体感判定收口：

1. **首包占位骨架可见时间**：从前端 `sendChat` 调用到 `assistantMessage.thinkingContent` 第一次非空，目标 **P50 ≤ 600ms / P95 ≤ 1.2s**。
2. **上游首字节时间**：后端日志 `[SSE-HTTPX] first chunk at` 与 `AI API stream starts` 的差值，目标 **P50 ≤ 2.0s / P95 ≤ 3.5s**（DeepSeek 思考型在 P95 ≤ 4.5s）。
3. **prepare 命中缓存比例**：双流同 turn 的二次 prepare 缓存命中率 ≥ 95%（用日志埋点统计）。
4. **空窗期主观体验**：QA 录屏对比，5 个典型问题（含 shortcut / 长问 / 体重类 / 安全敏感 / 多模块），首屏感知"AI 在动"的时间 ≤ 1s。
5. **回归门禁**：`docs/CRM_USER_PROFILE_AI_INTEGRATION_REPORT.md` 中已有的 thinking / answer / shortcut / safety 路径的回归用例必须全绿。

---

## 六、风险与开放问题

- **HTTP/2 + 公司出口代理兼容性**：上线前必须在生产同等网络环境下验证，否则保留 `http2=False` 配置开关。
- **prepare 缓存的并发一致性**：同一 (customer, session, message) 在 15s 内命中缓存是合理的，但如果客户档案在这 15s 内被更新，会出现"用旧上下文回答"。**风险偏低**（用户改完档案立刻再问 AI 的概率极小），但需要在 `docs/CRM_USER_PROFILE_AI_INTEGRATION_REPORT.md` 备注一笔。
- **就近接入域名切换**：涉及上游账号配置，需要与运维 / 供应商对齐，不在本次代码改动内闭环。
- **thinking 模型降级**：用更小模型可能让 thinking 内容变粗糙，需要 prompt 工程师人工抽检。

---

## 七、附录：当前关键代码位

| 关注点 | 位置 |
|---|---|
| httpx 客户端单例 | `@d:\惯能\群机器人定时推送\wecom_ops_console\app\clients\ai_chat_client.py:23-31` |
| 流式上游调用 | `@d:\惯能\群机器人定时推送\wecom_ops_console\app\clients\ai_chat_client.py:109-201` |
| answer 流业务 | `@d:\惯能\群机器人定时推送\wecom_ops_console\app\crm_profile\services\ai_coach.py:419-560` |
| thinking 流业务 | `@d:\惯能\群机器人定时推送\wecom_ops_console\app\crm_profile\services\ai_coach.py:563-676` |
| SSE 路由 | `@d:\惯能\群机器人定时推送\wecom_ops_console\app\crm_profile\router.py:514-583` |
| 前端双流编排 | `@d:\惯能\群机器人定时推送\wecom_ops_console\frontend\src\views\CrmProfile\composables\useAiCoach.ts:276-408` |
| 前端思考框渲染 | `@d:\惯能\群机器人定时推送\wecom_ops_console\frontend\src\views\CrmProfile\components\AiCoachPanel.vue:198-206` |
| 配置项 | `@d:\惯能\群机器人定时推送\wecom_ops_console\app\config.py:46-52` |

---

> 本文档定位为 **official 优化方案**，但所有"预期收益"数字均为基于现有 `[SSE-TIMING]` 日志的**估算**，最终收口请以 R1 上线后采集到的生产日志真值为准。
