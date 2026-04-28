# 企微群机器人 20 条/分钟限流适配调查报告

> **调查日期**: 2026-04-28
> **调查背景**: 发送中心在批量发送场景下，仍会出现因触达企微 20 条/分钟限制导致部分消息发送失败的情况。日志显示消息间隔仅约 2 秒。

---

## 一、现状概述

系统已在 `WeComService._check_rate_limit` 中实现了基于滑动窗口的本地限流保护，核心参数：

- **RATE_LIMIT** = 20 条
- **RATE_WINDOW_SECONDS** = 60 秒
- **粒度**: 按 `group_key`（即 `str(group.id)`）独立计数

该机制的意图是：在消息真正发送到企微 API 之前，先做本地计数拦截，避免触达企微的 45009 错误。

---

## 二、调用链路全景

系统中所有调用 `WeComService.send()` 的路径共 **5 条**，全部传入了 `group_key` 参数：

| # | 调用位置 | 场景 | group_key 取值 |
|---|---------|------|---------------|
| 1 | `api.py → _send_to_single_group` | 手动发送 / 定时任务的实际逐群发送 | `str(group.id)` |
| 2 | `api.py → retry_log` | 日志重试 | `str(log.message.group_id)` |
| 3 | `tasks.py → send_message_task` | Celery 异步任务 | `str(group.id)` |
| 4 | `batch_summary.py → send_ranking_summary` | 积分排行摘要推送 | `f'summary-{name}'` |
| 5 | 前端手动「立即发送」→ `send_message` → `do_send_to_groups` | 同路径 1 | `str(group.id)` |

**结论**: 所有发送路径均经过 `_check_rate_limit`，覆盖完整。

---

## 三、发现的缺陷

### 缺陷 1（严重）：限流器采用"立即失败"策略而非"等待重试"

**文件**: `app/services/wecom.py:109-118`

```python
@staticmethod
async def _check_rate_limit(group_key: str):
    lock = _locks[group_key]
    async with lock:
        bucket = _timestamps[group_key]
        now = asyncio.get_running_loop().time()
        while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT:
            raise RuntimeError('该群机器人触发了 20 条/分钟 的保护限制，请稍后重试。')
        bucket.append(now)
```

当桶内已满 20 条时，直接 `raise RuntimeError` 使调用方失败。**不会等待窗口滑动后重试**。

这意味着第 21 条消息不会"排队等一会儿再发"，而是直接报错。

---

### 缺陷 2（严重）：上层重试无法识别本地限流错误

**文件**: `app/routers/api.py:443-452`

```python
except Exception as exc:
    last_error = exc
    error_str = str(exc).lower()
    # 检测到限流错误时，长等待让滑动窗口释放
    if '45009' in error_str or 'freq out of limit' in error_str or 'api freq' in error_str:
        wait = 30 if attempt == 1 else 15
        logger.warning('触发限流(45009)，等待 %ds 后重试 ...')
        await asyncio.sleep(wait)
    elif attempt < max_retries:
        await asyncio.sleep(retry_delay)  # retry_delay = 1.0~3.0 秒
```

`_check_rate_limit` 抛出的 RuntimeError 消息是 `"该群机器人触发了 20 条/分钟 的保护限制，请稍后重试。"`，其中 **不包含** `45009`、`freq out of limit`、`api freq` 任何一个关键词。

因此本地限流错误走的是 `elif` 分支，仅等待 **1~3 秒** 就重试。但此时窗口远未滑过，重试仍然失败。默认最多重试 3 次（`send_max_retries=3`），3 次都打在限流上 → **消息永久失败**。

**这是用户反馈的根本原因**：消息以 ~2s 间隔发送了 20 条后，后续消息全部在本地限流 → 短间隔重试 → 再次限流 → 最终失败。

---

### 缺陷 3（中等）：`do_send_to_groups` 对所有群采用全并发无节流

**文件**: `app/routers/api.py:481-486`

```python
# 多群并发发送，不同群之间互不影响可并行
tasks = [
    _send_to_single_group(group, ...)
    for group in groups
]
results = await asyncio.gather(*tasks)
```

假设一个定时任务需要向 30 个群发送，`asyncio.gather` 会同时发起 30 个并发请求。虽然每个群有独立的 `group_key` 限流桶（每个群最多 20 条/分钟），但如果短时间内大量 HTTP 请求涌向企微 API，仍可能触发企微侧全局级别的限流或网络拥塞。

此处注释声称"不同群之间互不影响可并行"，这在群各自拥有独立 webhook 时**逻辑上成立**，但无任何并发上限控制（如 `asyncio.Semaphore`），对系统资源和外部 API 不友好。

---

### 缺陷 4（中等）：batch_items 循环间隔仅 1 秒

**文件**: `app/routers/api.py:497-520`

```python
for idx, item in enumerate(batch_items):
    ...
    results = await do_send_to_groups(db, groups, ...)
    ...
    await asyncio.sleep(1.0)  # 同一 webhook 限 20条/分钟
```

当 batch_items 中有超过 20 条目标为同一群时：
- 每条 batch_item 通过 `do_send_to_groups → _send_to_single_group → WeComService.send` 发送
- 间隔仅 1 秒
- 前 20 条正常记录进桶，第 21 条触发本地限流 → 立即失败（缺陷 1）
- 失败后短间隔重试无效（缺陷 2）

---

### 缺陷 5（低）：限流状态为进程内内存，多进程/重启不共享

**文件**: `app/services/wecom.py:21`

```python
_timestamps: dict[str, deque] = defaultdict(deque)
```

- 如果使用多 worker 进程（如 `uvicorn --workers N`），各进程独立计数，**合并后实际发送量可达 N × 20 条/分钟**
- 进程重启后桶清空，可能在短时间内再次打满限制
- Celery worker 与 Web 进程的桶也不共享

当前部署为单进程（`uvicorn --workers 1`），此问题影响较小，但属于架构级隐患。

---

### 缺陷 6（低）：Celery 路径每次 `asyncio.run()` 创建新事件循环

**文件**: `app/tasks.py:74`

```python
payload_data, resp_data = asyncio.run(
    WeComService.send(webhook_url, msg_type, rendered_content, group_key=str(group.id))
)
```

`asyncio.run()` 每次创建新的事件循环。虽然 `loop.time()` 底层使用 `time.monotonic()`（进程全局单调时钟），时间戳在同一进程内仍可比较。但 Celery worker 可能运行在独立进程中，与 Web 进程的 `_timestamps` 完全隔离。

---

## 四、问题复现路径

以下是最典型的复现场景：

```
用户操作: 创建一个定时任务，包含 25 条 batch_items，全部目标为同一个群

执行流程:
  perform_job_send
    → for item in batch_items (25 次循环):
        → do_send_to_groups(groups=[同一群])
            → _send_to_single_group(group, group_key="42")
                → WeComService.send(group_key="42")
                    → _check_rate_limit("42")
                        → 桶内 < 20: 通过，记录时间戳
                        → 桶内 >= 20: raise RuntimeError  ← 第 21 条开始失败
                → 重试 (1~3s 后)
                    → _check_rate_limit("42")
                        → 桶内仍 >= 20: raise RuntimeError  ← 重试也失败
                → 3 次重试耗尽 → 消息标记为 failed
        → await asyncio.sleep(1.0)

结果: 前 20 条成功，第 21~25 条全部失败
日志表现: 消息间隔约 1~2 秒，符合用户描述
```

---

## 五、建议修复方案

### 方案 A：将"立即失败"改为"等待后重试"（推荐，最小改动）

修改 `_check_rate_limit`，当桶满时计算最早可发送时间并 `await asyncio.sleep()` 等待，而非抛异常：

```python
@staticmethod
async def _check_rate_limit(group_key: str):
    lock = _locks[group_key]
    async with lock:
        bucket = _timestamps[group_key]
        now = asyncio.get_running_loop().time()
        # 清理过期时间戳
        while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT:
            # 计算需要等待的时间：最早的时间戳 + 窗口 - 当前时间
            wait_seconds = bucket[0] + RATE_WINDOW_SECONDS - now + 0.5  # +0.5s 安全余量
            logger.warning(
                '群 %s 触达 %d 条/分钟限制，等待 %.1fs 后继续',
                group_key, RATE_LIMIT, wait_seconds,
            )
    # 在锁外等待，避免阻塞其他 group_key
    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)
        # 等待后重新获取锁并记录
        async with lock:
            now = asyncio.get_running_loop().time()
            while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
                bucket.popleft()
            bucket.append(now)
    else:
        bucket.append(now)  # 已在锁内
```

**优点**: 消息不会因限流直接失败，而是自动排队等待
**注意**: 需要合理设置超时上限，避免请求无限挂起

### 方案 B：上层重试逻辑识别本地限流错误

在 `_send_to_single_group` 的 except 分支中增加对本地限流错误的识别：

```python
except Exception as exc:
    last_error = exc
    error_str = str(exc).lower()
    if '45009' in error_str or 'freq out of limit' in error_str or 'api freq' in error_str:
        wait = 30 if attempt == 1 else 15
        ...
    elif '20 条/分钟' in error_str or '保护限制' in error_str:
        # 本地限流：等待足够长的时间让窗口滑过
        wait = 35
        logger.warning('本地限流保护触发，等待 %ds 后重试 (attempt %d/%d)', wait, attempt, max_retries)
        await asyncio.sleep(wait)
    elif attempt < max_retries:
        await asyncio.sleep(retry_delay)
```

**优点**: 改动小，向后兼容
**缺点**: 等 35 秒会显著拖慢整体发送流程，且仍是"先失败再补偿"

### 方案 C：为 batch_items 增加基于 group_key 的自适应间隔

在 `perform_job_send` 的 batch_items 循环中，根据目标群的发送计数动态调整间隔：

```python
group_send_count: dict[int, int] = defaultdict(int)
for idx, item in enumerate(batch_items):
    ...
    for gid in item_group_ids:
        group_send_count[gid] += 1
    max_count = max(group_send_count.values(), default=0)
    if max_count > 0 and max_count % 18 == 0:  # 留 2 条安全余量
        await asyncio.sleep(62)  # 等一个完整窗口
    else:
        await asyncio.sleep(1.0)
```

### 方案 D（长期）：使用 Redis 作为分布式限流桶

将 `_timestamps` 迁移至 Redis sorted set，实现跨进程、跨重启的精确限流。适合未来多实例部署。

---

## 六、推荐实施优先级

| 优先级 | 方案 | 预计改动量 | 效果 |
|--------|------|-----------|------|
| **P0** | **方案 A**: `_check_rate_limit` 改为等待模式 | ~20 行 | 根治问题，消息自动排队 |
| P1 | **方案 B**: 上层重试识别本地限流 | ~5 行 | 兜底保护，防止静默失败 |
| P2 | **方案 C**: batch_items 自适应间隔 | ~10 行 | 减少不必要的等待 |
| P3 | **方案 D**: Redis 分布式限流 | 较大 | 多实例部署时必要 |

**建议**: 优先实施 **A + B** 组合。A 让绝大多数场景下消息自动排队发送；B 作为兜底，确保即使 A 出现边界情况，重试逻辑也能正确应对。

---

## 七、附录：相关文件清单

| 文件 | 关键函数/位置 | 作用 |
|------|-------------|------|
| `app/services/wecom.py` | `_check_rate_limit` (L109-118) | 本地滑动窗口限流 |
| `app/services/wecom.py` | `send` (L220-253) | 实际发送入口 |
| `app/routers/api.py` | `_send_to_single_group` (L380-472) | 单群发送+重试 |
| `app/routers/api.py` | `do_send_to_groups` (L475-487) | 多群并发调度 |
| `app/routers/api.py` | `perform_job_send` (L489-547) | 定时任务执行（含 batch_items） |
| `app/routers/api.py` | `send_message` (L942-959) | 手动/测试发送入口 |
| `app/routers/api.py` | `retry_log` (L1156-) | 日志重试 |
| `app/tasks.py` | `send_message_task` (L23-108) | Celery 异步任务 |
| `app/services/batch_summary.py` | `send_ranking_summary` (L33-81) | 排行摘要推送 |
| `app/config.py` | `send_max_retries` 等 (L57-62) | 重试参数配置 |

---

## 八、已实施的修复（2026-04-28）

以下修复已落地到代码：

### 修复 1: `_check_rate_limit` 改为等待模式（对应缺陷 1）

**文件**: `app/services/wecom.py`

- 桶满时不再 `raise RuntimeError`，改为计算 `wait_seconds = bucket[0] + RATE_WINDOW_SECONDS - now + 1.0`
- 在锁外执行 `await asyncio.sleep(wait_seconds)`，不阻塞其他 group_key
- 等待后重新进入循环获取锁、清理过期时间戳、尝试记录
- 增加 `MAX_RATE_WAIT_SECONDS = 120` 上限，超过则放弃发送（仅极端场景）

### 修复 2: 上层重试识别本地限流错误（对应缺陷 2）

**文件**: `app/routers/api.py` — `_send_to_single_group`

- 新增识别条件：`'限流等待超过' in error_str or '条/分钟' in error_str`
- 命中后等待 35 秒再重试，与 45009 处理策略对齐
- 作为兜底保护，防止修复 1 的超时异常被短间隔重试浪费

### 修复 3: `do_send_to_groups` 增加 Semaphore 并发控制（对应缺陷 3）

**文件**: `app/routers/api.py`

- 新增模块级 `_send_semaphore = asyncio.Semaphore(10)`
- 所有群的并发发送受限于最多 10 个同时进行
- 避免瞬间大量 HTTP 请求涌向企微 API

### 修复 4: batch_items 循环增加自适应间隔（对应缺陷 4）

**文件**: `app/routers/api.py` — `perform_job_send`

- 新增 `group_send_count` 字典跟踪每个群的累计发送次数
- 当同一群即将超过 18 条时（留 2 条安全余量），提前等待 62 秒（一个完整窗口）
- 等待后清空计数器，开始新的窗口周期
