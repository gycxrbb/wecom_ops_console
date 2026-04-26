# 健康摘要 7/14/30 天升级 — 多轮任务档

- **来源真值**：`docs/CRM_HEALTH_SUMMARY_7D_14D_30D_ENHANCEMENT_REPORT.md`
- **当前阶段**：Round 1 进行中（P0 全量）
- **后续阶段**：Round 2 = P1（场景化 + selected_expansions 真接入），Round 3 = P2（洞察规则库）

## 真值规则

- `MODULE_KEY="health_summary_7d"` 暂时**保留**作为 official module key（前端 `getCard('health_summary_7d')`、AI prompt 标签都依赖）。本字符串只是历史命名，**真实窗口从 payload.window_days 读**，不再从 key 推断。
- 模块输出 payload 必须**向后兼容**：原有字段 `days/weight/weight_trend/blood_pressure/glucose/sleep/activity/diet/symptoms` 保留语义不变，新字段以 `window_days/water_*/meal_*/glucose_*/trend_flags/data_quality` 等独立 key 增量添加。
- AI 默认窗口 = 7d（不变），仅 `/profile?window=` 接受 14/30。这是 Round 1 的**有意约束**，避免 AI prompt token 暴涨。
- `customer_glucose.points` 是**正式血糖曲线真值**；`customer_health.glucose_data` 不再读。

## Round 1（本轮）：P0 后端 + 前端窗口切换

### Round 1 子任务

1. 后端模块拆文件：`_health_summary_const.py / _loaders.py / _glucose.py / _meals.py / _summarize.py`，主入口 `health_summary.py` 收敛 ≤ 200 行
2. 主入口签名：`load(conn, customer_id, *, window_days: int = 7)`，仅接受 7/14/30，否则回落 7
3. `profile_loader.load_profile(customer_id, *, health_window_days: int = 7)` 把窗口透传给 health_summary
4. 路由 `GET /v1/crm-customers/{id}/profile?window=7|14|30`，缓存 key `profile:{id}:hw{window}`
5. `context_builder.FIELD_LABELS["health_summary_7d"]` 补齐新字段中文标签
6. 前端 `useCrmProfile.loadProfile(customerId, windowDays?)` + 健康摘要卡片右上角 `<el-radio-group>` 7/14/30 切换器
7. 前端渲染：trend_flags 列表、meal_highlights 卡片（最近 3 天）、glucose_highlights（峰值天）、data_quality 缺失提示
8. 沉淀 `progress.md / memory.md`，发现 bug 写 `bug.md`

### Round 1 不在范围内（明确放到下一轮）

- `selected_expansions = [meal_detail_window, glucose_curve_window]` 真接入
- AI 上下文按场景切窗口（周期复盘场景 → 30d）
- 自动洞察规则（餐后波动 / 平台期联动）
- `EXPANSION_MODULE_OPTIONS` 新增 `meal_detail_window / glucose_curve_window`

## Round 2：P1（下一轮）

- AI flow 接受 `health_window_days` 参数，按 `scene_key` 决定默认值（qa_support=7, weekly_review=14, monthly_review=30）
- `selected_expansions` 中 `meal_detail_window / glucose_curve_window` 在 `context_builder.build_context_text` 真正展开为 N 天明细
- 前端把当前窗口随 AI 抽屉一起带过去（`AiCoachPanel` 读 `useCrmProfile` 的 `currentWindowDays`）

## Round 3：P2（下一轮）

- 服务层洞察规则库：`insights/post_meal_swing.py`、`insights/weight_plateau.py` 等
- 规则输出统一进 `trend_flags` + `meal_highlights[i].insights[]`
- 规则可配置阈值，落 `_health_summary_const.py`

## 验收口径（Round 1 official）

1. `/profile?window=14` 与 `/profile?window=30` 能返回不同 days、不同 trend_flags、不同 highlights
2. `customer_glucose` 表无数据时 `glucose_*` 字段为 None / [] / 0，**不抛异常**
3. 餐食 JSON 字段缺失或反序列化失败不影响其他指标计算
4. 前端切换 7/14/30 后只刷新健康摘要卡片，URL 上 `cid` 不丢
5. 现有 `getCard('health_summary_7d')` 保持可用，旧字段仍然显示
6. AI 流入口 `/ai/chat-stream` 行为不变（默认 7d，token 用量不增）

## 风险

- `customer_health.breakfast_data` JSON 结构是历史业务字段，可能存在多种 schema variants（数组/对象、键名差异）。Round 1 用宽松解析 + 失败回退到"已记录"标志位，不强结构化，避免反序列化报错搞挂整个摘要。
- `customer_glucose.points` 为大 JSON，14/30 天窗口下单客户最多 30 行。建议只拉关键聚合，不把原始 points 透传给前端 / AI。
