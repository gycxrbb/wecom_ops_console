# AI 教练 RAG 检索优化方案

> 调研日期：2026-04-30
> 状态：待实施

---

## 一、问题概述

当前 RAG 检索链路存在三个层面的严重问题：

1. **数据漏传**：非流式路径完全跳过 RAG，AI 根本看不到任何话术/素材
2. **数据截断**：即使 RAG 命中，AI 只看到每个话术的前 200 字，无法理解完整内容
3. **字段浪费**：`customer_goal`、`question_type`、`visibility` 等标注字段在检索中未发挥作用

直接后果：AI 教练的回复中几乎体现不出 RAG 入库的话术和素材内容。

---

## 二、已发现的 Bug 和问题

### Bug 1：`hashlib` 未导入（HIGH）

**文件**：`app/crm_profile/services/ai_coach.py:297`

`_prepare_ai_turn_cached()` 第 297 行使用了 `hashlib.sha256()`，但文件头部没有 `import hashlib`。
当用户使用"追问"功能（`quoted_content` 非空）时，会直接抛出 `NameError`，导致整个流式对话崩溃。

**修复**：在文件头部添加 `import hashlib`。

---

### Bug 2：非流式路径 `ask_ai_coach()` 完全跳过 RAG（HIGH）

**文件**：`app/crm_profile/services/ai_coach.py:525`

`ask_ai_coach()` 调用同步的 `_prepare_ai_turn()`，没有传 `rag_context_text`、`rag_sources`、`rag_recommended_assets` 参数。
这些参数默认为空字符串和空列表，导致非流式路径下 AI 完全看不到任何 RAG 内容。

**修复**：将 `ask_ai_coach()` 改为调用 `_prepare_ai_turn_async()`（内部执行 RAG 异步检索），或在调用前单独执行 RAG 检索并传入结果。

---

### Bug 3：RAG 上下文截断到 200 字（HIGH）

**文件**：`app/rag/retriever.py:247`

```python
snippet = resource.semantic_text[:200]
```

`semantic_text` 存储了话术的完整内容（标题 + 正文 + 标签 + 使用说明），但注入 AI prompt 时只截取了前 200 字符。
一条典型话术约 500-1500 字，200 字只够覆盖标题和前两句话，AI 无法理解话术的完整内容。

**同时**：`enriched_hits` 中已加载了 `semantic_text[:500]`（第 201 行），但这个更完整的版本从未用于 `context_text`。

**修复**：将注入 prompt 的截取长度从 200 提升到 800（或使用 `rag_max_source_chars` 配置项）。

---

### 问题 4：`max_visible_sources=3` + 截断 = AI 几乎用不上 RAG（MEDIUM）

**文件**：`app/rag/retriever.py:236`，`app/config.py:93`

当前限制最多 3 条话术 × 200 字 = 600 字 RAG 上下文。对于动辄上千字的话术模板，600 字远远不够。
`rag_relative_score_ratio=0.72` 的相对阈值也可能过滤掉很多相关结果。

**优化方向**：
- 提升 `rag_max_visible_sources` 到 5
- 增加配置项 `rag_max_source_chars: int = 800` 控制每条话术的截取长度
- 放宽 `rag_relative_score_ratio` 到 0.65

---

### 问题 5：RAG 提示词太消极（MEDIUM）

**文件**：`app/crm_profile/prompts/base/rag_header.md`

当前内容：
```
- 可借鉴话术风格，但不要机械照抄。
```

这告诉 AI "不要照抄"，实际上应该是：当找到高度匹配的话术时，AI 应该**参考话术的核心表达和用词**组织回复。

**优化方向**：重写 RAG header，明确指导 AI 如何使用话术参考：
- 高匹配度话术可以参考其表达方式和结构
- 注明话术来源的场景类型，帮助 AI 判断适用性
- 区分"参考风格"和"参考内容"两种使用方式

---

### 问题 6：历史会话丢失 RAG 引用卡片（MEDIUM）

**文件**：`frontend/src/views/CrmProfile/composables/useAiCoach.ts:329-340`

`openHistorySession()` 从审计记录恢复消息时，只恢复 `user` 和 `assistant` 消息。
RAG 引用卡片（`rag_reference` 和 `rag_attachment`）在页面刷新或切换回来后消失。

**优化方向**：在 `crm_ai_messages` 审计表中记录 RAG source 信息，恢复会话时重建引用卡片。

---

### 问题 7：意图识别只覆盖营养/积分两个域（LOW）

**文件**：`app/rag/intent_rules.py`

`recognize_intent()` 只区分 `nutrition`（营养）、`points_operation`（积分运营）和 `unknown`。
运动指导、情绪支持、设备使用等域完全没有覆盖。

**优化方向**：后续迭代扩展意图域，当前优先级低。

---

## 三、已标注字段利用情况

| 字段 | 索引时写入 Qdrant | 检索时使用 | 状态 |
|------|:-:|:-:|------|
| `content_kind` | ✅ | ✅ 按类型过滤 | 已利用 |
| `status` | ✅ | ✅ active 过滤 | 已利用 |
| `safety_level` | ✅ | ✅ 安全上限过滤 | 已利用 |
| `semantic_quality` | ✅ | ✅ 排除 weak/stale | 已利用 |
| `intervention_scene` | ✅ | ✅ 场景过滤 + 加分（刚优化） | 已利用 |
| `customer_goal` | ✅ | ✅ 命中加分（刚优化） | 已利用 |
| `question_type` | ✅ | ✅ 命中加分（刚优化） | 已利用 |
| `visibility` | ✅ | ✅ 按 output_style 排序（刚优化） | 已利用 |
| `category_l1/l2` | ✅ | ❌ 未使用 | 未利用 |

**注**：标签加分机制已在本轮优化中实现。但加分只在有标注数据时生效，当前 37 条数据中仅 1 条有完整标签，覆盖率极低。

---

## 四、实施计划

### Phase 1：修复关键 Bug（立即）

**T1. 修复 `hashlib` 未导入**
- 文件：`app/crm_profile/services/ai_coach.py`
- 操作：头部添加 `import hashlib`
- 影响范围：1 行

**T2. 修复非流式路径跳过 RAG**
- 文件：`app/crm_profile/services/ai_coach.py`
- 操作：将 `ask_ai_coach()` 改为调用 `_prepare_ai_turn_async()`（异步路径含 RAG 检索）
- 注意：`ask_ai_coach()` 本身是 `async` 函数，可以直接 `await` 异步版本
- 影响范围：~5 行

**T3. 提升 RAG 上下文截取长度**
- 文件：`app/rag/retriever.py`
- 操作：将 `semantic_text[:200]` 改为 `semantic_text[:800]`
- 影响范围：1 行

### Phase 2：检索参数优化（与 Phase 1 同步）

**T4. 配置项调整**
- 文件：`app/config.py`
- 新增：`rag_max_source_chars: int = 800`（每条话术注入 prompt 的最大字符数）
- 调整：`rag_max_visible_sources` 默认值 3 → 5
- 调整：`rag_relative_score_ratio` 默认值 0.72 → 0.65
- 文件：`app/rag/retriever.py` — 使用 `settings.rag_max_source_chars` 替代硬编码 `200`

### Phase 3：RAG 提示词优化（Phase 1 完成后）

**T5. 重写 RAG header**
- 文件：`app/crm_profile/prompts/base/rag_header.md`
- 新内容应包含：
  - 话术参考的使用指导（什么情况下参考风格，什么情况下参考内容）
  - 话术来源说明（场景类型、安全级别）
  - 明确告诉 AI 可以参考匹配度高的话术的用词和结构

### Phase 4：历史会话 RAG 卡片恢复（后续迭代）

**T6. 审计表记录 RAG 信息**
- 在 `crm_ai_context_snapshots` 或独立表中记录每条消息关联的 RAG sources
- 前端 `openHistorySession()` 恢复时重建 RAG 引用卡片
- 改动量：后端 ~30 行，前端 ~20 行

---

## 五、预期效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| RAG 上下文注入 AI | 仅流式路径，200 字/条 × 3 条 ≈ 600 字 | 全路径可用，800 字/条 × 5 条 ≈ 4000 字 |
| AI 回复体现话术内容 | 几乎无法体现 | 能参考话术表达和结构 |
| `hashlib` 追问崩溃 | 使用追问即崩溃 | 修复 |
| 标签字段利用 | 3 个字段未使用 | 全部利用（加分 + 排序） |

---

## 六、关键文件清单

| 操作 | 文件 |
|------|------|
| 修复 | `app/crm_profile/services/ai_coach.py` — import hashlib + ask_ai_coach RAG |
| 修改 | `app/rag/retriever.py` — 截取长度改用配置项 |
| 修改 | `app/config.py` — 新增 rag_max_source_chars，调整默认值 |
| 修改 | `app/crm_profile/prompts/base/rag_header.md` — 重写提示词 |
