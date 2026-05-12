# RAG 检索召回失败调研报告 — "用户要出差，推荐一下餐食"无法召回出差餐食话术

- **日期**: 2026-05-12
- **问题**: 同一条话术（出差餐食推荐），不同提问方式召回结果不同
- **涉及模块**: `app/rag/query_compiler.py`, `app/rag/intent_rules.py`, `app/rag/tag_cache.py`, `app/rag/retriever.py`

---

## 一、现象

| 提问 | 能否召回 |
|------|---------|
| "用户出差推荐餐食" | ✅ 能 |
| "给我出差外食外卖场景点餐指导话术" | ✅ 能 |
| "用户要出差，推荐一下餐食" | ❌ 不能 |

用户认为这不合理——三个问题的语义完全相同，但自然语言变体无法召回。

---

## 二、检索链路完整梳理

用户消息进入 RAG 检索后，经过以下步骤：

```
用户消息
  → ① intent_rules.py: 关键字匹配识别领域 (nutrition / points_operation)
  → ② query_compiler.py: 从消息中提取 tag 关键字，组装 query_text
  → ③ embedding_client.py: 对 query_text 做 embedding
  → ④ vector_store.py: Qdrant 向量相似度搜索（带 filter）
  → ⑤ retriever.py: tag boost + profile boost 加分
  → ⑥ reranker.py: 可选重排
  → ⑦ score gate: 绝对阈值 0.42 + 相对阈值 (top × 0.65)
  → 最终结果
```

---

## 三、逐步分析三个查询的差异

### 查询 A："用户出差推荐餐食"（成功）

**① 意图识别**（`intent_rules.py`）：
- 检查消息中是否包含 `_NUTRITION_KEYWORDS` 中的关键字
- "出差" ✅ 命中（在 `_NUTRITION_KEYWORDS` 中）
- "餐食" ✅ 命中（在 `_NUTRITION_KEYWORDS` 中）
- `nutrition_hits=2, points_hits=0` → domain = "nutrition"

**② 关键字提取**（`query_compiler.py` → `_extract_keywords()`）：
- 扫描 `tag_cache.get_keywords("question_type")` 返回的 name + aliases
- "外食/外卖" 是 `dining_out` 的 name，别名字段由 DB 中 `rag_tags` 表的 `aliases` JSON 决定
- 本消息不含 "外食"、"外卖" 等精确关键字 → question_type 未匹配
- 扫描 `intervention_scene` 关键字 → "出差" 如果被配置为某个 scene tag 的别名，则匹配
- 实际上 "餐食" 可能不是任何 tag 的 name 或 alias → 无 tag 匹配

**③ query_text 构建**：
- 如果有 tag 匹配：`"标签名1 标签名2 用户出差推荐餐食"`
- 如果无 tag 匹配：`"用户出差推荐餐食"`（原始消息）
- 这个短句本身语义明确，embedding 质量好 → 向量搜索命中率高

**④ 向量搜索**：
- query_text 紧凑，embedding 集中在"出差"+"餐食"语义上
- 与目标话术的 embedding 距离近 → score 高
- 通过 score gate（≥ 0.42 且 ≥ top × 0.65）✅

### 查询 B："给我出差外食外卖场景点餐指导话术"（成功）

**① 意图识别**：
- "出差" ✅、"外卖" ✅、"外食" ✅、"点餐" ✅ → nutrition_hits=4
- domain = "nutrition"

**② 关键字提取**：
- "外食" 命中 `dining_out` tag（name="外食/外卖"，substring 匹配）
- "外卖" 命中 `dining_out` tag
- "点餐" 可能命中某 tag 的别名
- 多个 tag 匹配 → query_text 丰富：`"外食/外卖 [其他标签] 给我出差外食外卖场景点餐指导话术"`

**③ 向量搜索**：
- query_text 包含大量命中关键字 + 原始消息 → embedding 语义非常精确
- 而且可能有 `intervention_scene` filter 缩小搜索范围
- score 很高 ✅

### 查询 C："用户要出差，推荐一下餐食"（失败）—— 根因分析

**① 意图识别**：
- "出差" ✅ 命中（`"出差" in "用户要出差，推荐一下餐食"` → True）
- "餐食" ✅ 命中（`"餐食" in "用户要出差，推荐一下餐食"` → True）
- nutrition_hits=2 → domain = "nutrition" ✅ 这一步没问题

**② 关键字提取**：
- `_extract_keywords()` 做的是 **substring 匹配**：`keyword in text`
- 扫描 question_type 关键字：检查"用户要出差，推荐一下餐食"中是否包含"外食/外卖"、"出差餐食"等 tag name 或 alias
- **问题 1：关键字库可能不包含"出差"对应任何 question_type**
  - "出差"不是 `question_type` 维度的关键字（它是 `intervention_scene` 或 `customer_goal` 维度的）
  - 如果 DB 中没有 tag 将"出差"设为 alias，就不会匹配
- **问题 2："推荐一下"不匹配任何 tag 关键字**
  - 系统只做精确 substring 匹配，没有语义理解
  - "推荐"不等于"点餐指导"，不会触发 `dining_out` 匹配

**③ query_text 构建**：
- 如果没有匹配到任何 tag 关键字：`query_text = "用户要出差，推荐一下餐食"`（原始消息）
- 或者只匹配到很少 tag：`"出差 用户要出差，推荐一下餐食"`

**④ embedding 差异**——这是核心：

| query_text | 特征 |
|------------|------|
| A: "用户出差推荐餐食" | 6 个字，高度浓缩，语义集中 |
| B: "外食/外卖 出差 给我出差外食外卖场景点餐指导话术" | 有关键字标签前缀 + 长 query，语义丰富 |
| C: "用户要出差，推荐一下餐食" | 11 个字，含填充词"要"、"，"、"推荐一下"，语义被稀释 |

**text-embedding-3-large** 对中文自然语言句子的 embedding：
- 查询 A 和 B 的 embedding 向量与目标话术的语义空间更近
- 查询 C 的 embedding 因为填充词和不同句式，向量被拉偏

**⑤ 向量搜索结果**：
- 查询 C 的向量与目标话术的余弦相似度低于 0.42（绝对阈值）
- 或者虽然 > 0.42，但远低于 top score，被相对阈值（top × 0.65）过滤掉
- **结果：目标话术未被召回** ❌

---

## 四、根因总结

系统存在 **3 个结构性问题**：

### 问题 1：关键字提取只有精确 substring 匹配，没有语义扩展

`query_compiler.py` 的 `_extract_keywords()`（第 71-76 行）：

```python
def _extract_keywords(text: str, mapping: dict[str, str]) -> list[str]:
    found: list[str] = []
    for keyword, code in mapping.items():
        if keyword in text and code not in found:
            found.append(code)
    return found
```

这是纯粹的 Python `in` 操作符（substring 匹配）。"推荐一下餐食"中的"推荐"和"餐食"如果不在 tag 关键字库中，就完全无法匹配。

"出差餐食推荐" → "餐食" 可能直接作为 tag alias 存在 → 匹配成功。
"推荐一下餐食" → "推荐" 不在关键字库 → 匹配失败。

### 问题 2：query_text 构建依赖关键字命中，无法补偿自然语言变体

```python
if label_parts:
    query_text = f"{' '.join(label_parts)} {message}"
else:
    query_text = f"{scene_key} {message}" if scene_key else message
```

当关键字命中少时，query_text 缺少标签前缀的语义补充，完全依赖原始消息的 embedding 质量。而自然语言填充词（"要"、"一下"、"，"）会稀释 embedding 的语义集中度。

### 问题 3：score gate 可能过于严格

- 绝对阈值 `rag_min_score = 0.42`
- 相对阈值 `rag_relative_score_ratio = 0.65`

当查询 C 的 embedding 偏移后，目标话术的 score 可能降到 0.38-0.41 之间，被绝对阈值拦截；或者 score 约 0.43 但 top score 是 0.70+，被相对阈值拦截（0.70 × 0.65 = 0.455 > 0.43）。

---

## 五、修复建议

### 建议 1：添加查询归一化/扩展层（P0，推荐）

在 `compile_query()` 之后、embedding 之前，添加一步查询归一化：

- 去除填充词（"一下"、"的"、"了"、"要"、"帮我"、"给我" 等）
- 将同义词扩展到 query_text 中（如 "出差" → "外食/外卖"，"餐食推荐" → "点餐指导 外食外卖"）
- 可基于静态映射表或 LLM 提取核心意图

```python
# 伪代码
_FILLER_WORDS = {"一下", "帮我", "给我", "请问", "推荐一下", "想要", "需要"}
def normalize_query(message: str) -> str:
    text = message
    for filler in sorted(_FILLER_WORDS, key=len, reverse=True):
        text = text.replace(filler, "")
    return text.strip()
```

### 建议 2：增加 tag alias 的同义词覆盖（P1，最快见效）

在 `rag_tags` 表中，为关键字 tag 增加更多别名：

- `question_type = dining_out` 的 aliases 增加：`["出差", "出差餐食", "出差推荐", "餐食推荐", "推荐餐食"]`
- `intervention_scene` 维度增加出差相关 alias

这不需要改代码，只改数据，效果立竿见影。

### 建议 3：双重 embedding 查询（P1）

对每个用户消息生成两条 query_text 同时搜索：

1. 原始消息（保留自然语言语义）
2. 去填充词 + 关键字富化后的消息

取两者搜索结果的并集。这样可以兼顾语义匹配和关键字匹配。

### 建议 4：放宽 score gate 并引入 fallback（P2）

当前配置：`rag_min_score=0.42`，`rag_relative_score_ratio=0.65`

建议：
- 主搜索保持当前阈值
- 如果主搜索返回结果为空或太少（< 2 条），自动用**去掉所有 filter**的宽泛搜索做 fallback
- fallback 的阈值降到 0.35

### 建议 5：用 embedding 相似度做关键字扩展（P2）

当前 `_extract_keywords()` 完全依赖 tag name/alias 的精确匹配。可以额外做一步：

- 预计算所有 tag name 和 alias 的 embedding
- 用户消息 embedding 与 tag embedding 做相似度匹配
- 相似度超过阈值的 tag 自动加入 query_intent

这相当于"语义关键字提取"，不依赖精确匹配。

---

## 六、优先级

| 优先级 | 建议 | 效果 | 工作量 |
|-------|------|------|-------|
| P0 | 查询归一化（去填充词） | 直接解决本次问题 | 小（加一个函数） |
| P1 | 增加 tag alias 同义词 | 最快见效，不改代码 | 小（改数据） |
| P1 | 双重 embedding 查询 | 兼顾语义和关键字 | 中 |
| P2 | 放宽 score gate + fallback | 减少漏召回 | 小 |
| P2 | embedding 相似度做关键字扩展 | 根本性提升匹配质量 | 大 |

---

## 七、结论

"用户要出差，推荐一下餐食"无法召回的根本原因是：

1. **关键字提取只有精确 substring 匹配**——"推荐一下餐食"中的"推荐"、"餐食"不在 tag 关键字库中，无法触发标签富化
2. **query_text 缺少标签前缀补充**——完全依赖原始消息 embedding，而填充词"要"、"一下"稀释了语义集中度
3. **embedding 偏移**——自然语言句式与关键字式查询的 embedding 向量距离不同，导致 score 低于阈值

最推荐的短期修复是 **建议 1（查询归一化）+ 建议 2（增加 tag alias）**，组合使用可以解决绝大多数自然语言变体的召回问题。
