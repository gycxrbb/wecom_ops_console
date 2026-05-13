# AI 健康摘要上下文预加载与睡眠问答异常审查报告

> 审查日期：2026-05-13  
> 问题客户：CRM 用户 ID 2740，王法生  
> 触发问题：教练询问“用户最近的睡眠数据怎么样”  
> 异常现象：AI 回复称“过去 7 天日均睡眠 0 小时”，同时在“数据来源”里写成“近14天健康摘要”。

---

## 1. 结论先行

这次不是前端把 7 天窗口错传成 14 天。审计记录显示，本次 AI 请求参数是：

```json
{
  "health_window_days": 7,
  "scene_key": "qa_support",
  "model": "deepseek-v4-pro"
}
```

上下文快照中健康摘要也明确写着：

```text
### 健康摘要
记录天数: 8
统计窗口(天): 7
睡眠摘要: 均值 0.0h
日均睡眠(分钟): 0
```

所以两个异常的根因不同：

1. **“睡眠 0 小时”是上下文污染，不是模型凭空编的。**  
   顶层健康摘要读取 `customer_health.sleep_min`，2740 在窗口内只有一条 `sleep_min = 0`，因此后端生成 `sleep = 均值 0.0h`、`sleep_avg_min = 0`。

2. **真实睡眠数据其实已经查到了，但没有进入 AI 可见上下文。**  
   `customer_sleep` 中有 3 天有效数据，平均睡眠约 456 分钟，已进入 payload 的 `sleep_detail`，但 `build_context_text()` 默认跳过 dict/list 字段，导致 AI prompt 只看到错误的顶层 0，看不到真实 `sleep_detail`。

3. **“近14天健康摘要”不是实际数据源名称，而是模型写错来源。**  
   本次上下文里没有“近14天健康摘要”这个模块；但紧随健康摘要后有多个模块名是“近14天积分与活跃 / 近14天习惯执行 / 近14天计划推进”，模型很可能把相邻模块标签和健康摘要混淆了。

4. **健康摘要已经作为 profile cache 的 card 被预加载，但不等于所有健康摘要字段都进了 AI prompt。**  
   当前缓存层保存的是完整 `CustomerProfileContextV1.cards`；AI prompt 使用的是 `build_context_text()` 渲染后的扁平文本。嵌套字段在缓存里存在，但在 prompt 里不可见。

---

## 2. 现场证据

### 2.1 审计记录

本次会话：

| 项目 | 值 |
|---|---|
| session_id | `071ad16d-8066-441f-8c09-717675281925` |
| 用户问题 | `用户最近的睡眠数据怎么样` |
| 请求窗口 | `health_window_days = 7` |
| 使用模块 | `basic_profile,safety_profile,goals_preferences,health_summary_7d,body_comp_latest_30d,points_engagement_14d,service_scope,habit_adherence_14d,plan_progress_14d,learning_engagement_30d` |

上下文快照中的健康摘要片段：

```text
### 健康摘要
记录天数: 8
统计窗口(天): 7
最新体重(kg): 56.25
体重变化: 82.35 → 56.25
血压摘要: 收缩压 108.0 mmHg / 舒张压 73.5 mmHg
睡眠摘要: 均值 0.0h
运动摘要: 日均 7216 步
饮食摘要: 日均 963.9 kcal
日均睡眠(分钟): 0
```

### 2.2 运行时 health summary payload

直接加载 `load_profile(2740, health_window_days=7)` 后，`health_summary_7d` payload 中与睡眠相关的字段为：

```text
window_days = 7
days = 8
sleep = 均值 0.0h
sleep_avg_min = 0
sleep_detail = {
  sleep_record_days: 3,
  sleep_avg_min: 456,
  sleep_avg_deep_min: 81,
  sleep_avg_rem_min: 102,
  sleep_avg_score: 80,
  sleep_avg_rhr: 63,
  source: customer_sleep
}
```

说明：真实睡眠明细已经在后端 payload 里，但 prompt 渲染阶段被丢掉。

### 2.3 原始数据对比

`customer_health` 在 7 天窗口内的睡眠字段：

| 日期 | sleep_min | 说明 |
|---|---:|---|
| 2026-05-06 | NULL | 无睡眠宽表值 |
| 2026-05-07 | NULL | 无睡眠宽表值 |
| 2026-05-08 | NULL | 无睡眠宽表值 |
| 2026-05-09 | NULL | 无睡眠宽表值 |
| 2026-05-10 | NULL | 无睡眠宽表值 |
| 2026-05-11 | 0 | 被当前顶层摘要当作有效睡眠 |
| 2026-05-12 | NULL | 无睡眠宽表值 |
| 2026-05-13 | NULL | 无睡眠宽表值 |

`customer_sleep` 在同一窗口内的有效睡眠字段：

| 日期 | total_min | deep_time | rem | score | rhr |
|---|---:|---:|---:|---:|---:|
| 2026-05-10 | 462 | 79 | 88 | 78 | 63 |
| 2026-05-11 | 489 | 90 | 90 | 90 | 62 |
| 2026-05-12 | 416 | 73 | 127 | 72 | 64 |

结论：`customer_health.sleep_min = 0` 与 `customer_sleep.total_min` 冲突时，当前代码没有数据源优先级规则，导致低质量宽表值覆盖了更可信的专项睡眠表。

---

## 3. 当前实现链路审查

### 3.1 前端窗口传参

前端 `AiCoachPanel.vue` 调用 `sendChat()` 时传入：

```ts
healthWindowDays: props.healthWindowDays
```

`useAiCoach.ts` 再写入请求体：

```ts
health_window_days: normalizeHealthWindowDays(options?.healthWindowDays)
```

本次审计记录证明前端实际传了 `7`。因此“14 天”不是前端传参问题。

### 3.2 后端 AI prepare

AI 对话入口会归一化窗口：

```python
window_days = normalize_window_days(health_window_days)
profile_result = get_ai_ready_profile_context(customer_id, window_days=window_days)
```

缓存 key 按窗口隔离：

```text
profile:{customer_id}:hw{window_days}
```

当前 2740 的缓存状态：

| 窗口 | cache key | 状态 | health payload |
|---|---|---|---|
| 7 | `profile:2740:hw7` | ready | `window_days = 7` |
| 14 | `profile:2740:hw14` | ready | `window_days = 14` |
| 30 | `profile:2740:hw30` | missing | 未预加载 |

说明：健康摘要会按窗口进入 profile cache；但当前只会预加载用户实际打开或请求过的窗口，不会自动为每个客户预加载 7/14/30 全部窗口。

### 3.3 健康摘要加载

当前 `health_summary.load()` 已经扩展到读取：

```text
customer_health
customer_glucose
customer_sleep
customer_sport
customer_heartrate
customer_stress
```

但顶层 `sleep` 仍来自 `customer_health.sleep_min`：

```python
sleep_mins = [rec["sleep_min"] for rec in records if rec.get("sleep_min") is not None]
sleep_summary = f"均值 {avg_h}h"
sleep_avg_min = int(round(sum(sleep_mins) / len(sleep_mins)))
```

专项睡眠表只进入嵌套字段：

```python
payload["sleep_detail"] = build_sleep_highlights(sleep_rows)
```

这造成同一 payload 内出现两个睡眠真值：

| 字段 | 来源 | 值 | AI 是否默认可见 |
|---|---|---:|---|
| `sleep` | `customer_health.sleep_min` | `均值 0.0h` | 可见 |
| `sleep_avg_min` | `customer_health.sleep_min` | `0` | 可见 |
| `sleep_detail.sleep_avg_min` | `customer_sleep.total_min` | `456` | 不可见 |

### 3.4 AI 上下文渲染

`build_context_text()` 目前只序列化标量字段：

```python
if isinstance(v, (list, dict)):
    if is_expanded and isinstance(v, list):
        ...
    continue
```

影响：

- `sleep_detail` 是 dict，默认跳过。
- 即使前端勾选 `sleep_detail`，当前逻辑也只展开 list，不展开 dict。
- `meal_highlights`、`glucose_highlights` 等 list 也只有在扩展命中时才会部分进入 prompt。

这就是“数据在 payload 里，但 AI 看不见”的直接原因。

---

## 4. 为什么会说“近14天健康摘要”

本次上下文快照中没有“近14天健康摘要”这个标题，健康摘要标题是：

```text
### 健康摘要
统计窗口(天): 7
```

但健康摘要后面紧跟多个 14 天模块：

```text
### 近14天积分与活跃
### 近14天习惯执行
### 近14天计划推进
```

模型在回答“数据来源”时把相邻模块标签误拼成“近14天健康摘要”。这属于 prompt 可读性问题：多个模块标题混在同一段上下文中，模型没有强约束必须引用“模块标题 + 统计窗口字段”，因此会把模块名称和窗口口径混淆。

建议把健康摘要标题直接渲染成：

```text
### 健康摘要（统计窗口：近7天）
```

并在 prompt 规则中要求：

```text
引用健康摘要时，必须以“健康摘要（统计窗口：X天）”为准，不得根据相邻模块标题改写窗口。
```

---

## 5. 是否已经完整预加载健康摘要

结论：**缓存层已经预加载了健康摘要 card，但 AI prompt 层没有完整使用健康摘要字段。**

当前链路分两层：

| 层级 | 当前状态 | 问题 |
|---|---|---|
| Profile cache | 保存完整 `CustomerProfileContextV1.cards`，其中包含 `health_summary_7d.payload.sleep_detail` | 基本已预加载 |
| Prompt context | `build_context_text()` 把 cards 渲染成文本，只保留标量，跳过 dict/list | 健康摘要明细字段没有进入 AI |

因此，不能只用“cache ready”判断 AI 已经拿到完整上下文。还需要验证：

1. health summary card 是否在 `ctx.cards` 中。
2. health summary payload 是否有字段。
3. 渲染后的 `context_text` 是否包含这些字段。
4. audit snapshot 是否保存了最终 prompt 可见内容。

---

## 6. 其他类似漏洞

### 6.1 窗口天数存在 8 天记录

当前 SQL：

```sql
date_col >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
```

在 2026-05-13 查询 7 天时，会包含 2026-05-06 到 2026-05-13，共 8 个自然日期。2740 的 `days = 8` 正是这个原因。

风险：

- “近7天”文案与实际统计天数不一致。
- 7/14/30 都会多包含 1 天。

建议改为：

```sql
date_col >= DATE_SUB(CURDATE(), INTERVAL %s - 1 DAY)
```

或在 Python 侧明确计算 start_date。

### 6.2 `customer_health` 与专项表没有 source priority

当前顶层字段优先使用 `customer_health`，专项表只放到 detail。对于睡眠，这会让 `sleep_min = 0` 这种宽表占位值压过 `customer_sleep.total_min`。

建议建立 source priority：

| 指标 | 优先源 | 备用源 |
|---|---|---|
| 睡眠总时长 | `customer_sleep.total_min` | `customer_health.sleep_min` |
| 睡眠评分/结构 | `customer_sleep` | 无 |
| 步数 | `customer_sport.total_steps` | `customer_health.step_count` |
| 心率 | `customer_heartrate.points` / `customer_sleep.rhr` | `body_comp.heart_rate` |

### 6.3 同名字段语义冲突

当前存在：

```text
payload.sleep_avg_min = 0
payload.sleep_detail.sleep_avg_min = 456
```

同名字段在不同层级表达不同来源，容易在前端、AI、审计排查时误读。

建议改名：

```text
sleep_avg_min -> sleep_avg_min_from_health
sleep_detail.sleep_avg_min -> sleep_avg_min
```

或者把顶层统一改为最终 official 指标：

```text
sleep_avg_min = 456
sleep_source = customer_sleep
sleep_fallback = customer_health.sleep_min ignored because lower priority
```

### 6.4 扩展模块选中后仍可能不可见

`EXPANSION_MODULE_OPTIONS` 中有 `sleep_detail`，但 `build_context_text()` 对 dict 不展开，所以勾选睡眠明细也不会把 `sleep_detail` 写入 prompt。

建议补充 dict 渲染：

```text
睡眠结构详情:
- 睡眠记录天数: 3
- 日均睡眠: 456 分钟
- 日均深睡: 81 分钟
- 日均 REM: 102 分钟
- 睡眠评分: 80
- 数据源: customer_sleep
```

### 6.5 缓存 schema 缺少健康摘要版本校验

`_read_l2()` 当前只校验 `service_issues.issue_detail_summary`，没有校验健康摘要 schema 版本或关键字段。

风险：

- 代码升级后，L2 旧缓存可能继续被 AI 使用。
- 新增字段如 `sleep_detail` 即使代码已支持，旧 cache 仍可能没有。

建议在 cache 中加入：

```text
schema_version
health_summary_schema_version
context_builder_version
```

并在 `_read_l2()` 中发现版本不匹配时丢弃缓存重建。

### 6.6 P0 预加载不等于轻量

`health_summary_7d` 已纳入 P0，这是对 AI 可用性有利的。但当前 health summary 自身会查询多个专项表，P0 预加载已经不再只是轻量模块。

建议：

- P0 保留 health summary，但内部允许“summary-only”模式。
- P1 full preload 再补全 `sleep_detail/exercise_detail/heart_rate/stress_detail`。
- 或者保留当前全量加载，但明确性能预算和失败告警。

### 6.7 子表查询失败被静默降级

`_safe_fetch()` 捕获异常后返回空列表，只写日志，不进入 `ModulePayload.warnings`。

风险：

- `customer_sleep` 查询失败时，AI 不知道“睡眠明细加载失败”。
- 前端也不会显示数据缺口。

建议把扩展源失败写入：

```text
payload.data_quality.source_errors
warnings
```

### 6.8 审计快照只保存渲染文本

审计表 `crm_ai_context_snapshots.compact_json` 保存的是 prompt 可见文本，不保存完整 card payload 和 cache key。

优点是能复盘模型实际看见了什么。缺点是无法直接复盘“哪些字段在 payload 里但被渲染器丢掉”。

建议额外保存：

```text
cache_key
health_window_days
context_renderer_version
cards_payload_hash
rendered_context_hash
```

---

## 7. 修复建议

### 7.1 必须先修

1. **睡眠指标 source priority**  
   当 `customer_sleep.total_min` 有有效值时，顶层 `sleep` 和 `sleep_avg_min` 应使用 `customer_sleep`，不要使用 `customer_health.sleep_min = 0`。

2. **上下文渲染支持 dict**  
   `build_context_text()` 必须能把 `sleep_detail` 这类 dict 渲染进 prompt，至少对健康摘要关键 detail 字段做白名单展开。

3. **健康摘要标题带窗口**  
   将渲染标题改为 `健康摘要（统计窗口：近7天）`，降低模型把相邻 14 天模块误当健康摘要来源的概率。

4. **修正 7 天窗口多取一天**  
   当前 `>= DATE_SUB(CURDATE(), INTERVAL 7 DAY)` 会取 8 天，应统一改成精确窗口。

### 7.2 紧随其后

1. `sleep_min = 0` 是否为有效值需要业务定义。若 0 表示“缺失/占位”，应在 loader 层转成 `None`。
2. 给 `health_summary` 增加 `source_priority` 和 `metric_source` 字段。
3. `selected_expansions=['sleep_detail']` 必须有可见效果。
4. L2 cache 加 schema version，不匹配时自动重建。
5. source table 查询失败要写入 warnings 和 data quality。

### 7.3 验收用例

以 2740 王法生为回归用例：

| 验收项 | 预期 |
|---|---|
| AI 请求参数 | `health_window_days = 7` |
| context 标题 | `健康摘要（统计窗口：近7天）` |
| 顶层睡眠 | 日均约 456 分钟，约 7.6 小时 |
| 睡眠来源 | `customer_sleep` |
| 睡眠记录天数 | 3 天 |
| 不应出现 | “日均睡眠 0 小时” |
| 不应出现 | “近14天健康摘要” |
| audit snapshot | 能看到睡眠 detail 或最终 official 睡眠字段 |

---

## 8. 建议的开发闭环

1. **补单元测试**
   - `customer_health.sleep_min = 0` 且 `customer_sleep.total_min` 有值时，顶层 sleep 使用 `customer_sleep`。
   - `build_context_text()` 能渲染 `sleep_detail` dict。
   - 7 天窗口只返回 7 个自然日期。

2. **补集成测试**
   - 构造 2740 的最小 fixture。
   - 调用 `load_profile(2740, health_window_days=7)`。
   - 调用 `build_context_text(ctx.cards)`。
   - 断言 context 中出现 `睡眠记录天数: 3`、`日均睡眠(分钟): 456`，且不出现 `日均睡眠(分钟): 0`。

3. **补运行审计**
   - 每次 AI 对话记录 `health_window_days`、`cache_key`、`context_renderer_version`。
   - 在 context preview 中显示“payload 字段数 / prompt 可见字段数”。

4. **补前端提示**
   - 已加载信息面板里显示健康摘要当前窗口。
   - 如果用户切换 7/14/30 后缓存还没 ready，禁止发送或明确提示“当前窗口上下文准备中”。

---

## 9. 最终判断

这次 bug 的本质是 **profile payload 与 AI prompt 之间存在字段丢失和数据源优先级错误**。

健康摘要确实进入了用户上下文预加载体系，但当前预加载只保证“card 存在”，不保证“关键字段以正确口径进入 prompt”。对睡眠这类已经有专项表的指标，必须把 `customer_sleep` 提升为 official 指标来源，并让最终 AI 可见上下文只保留一个明确、带来源的睡眠结论。

如果只修 prompt 文案，不修指标优先级，AI 仍可能继续基于 `customer_health.sleep_min = 0` 给出错误结论。
