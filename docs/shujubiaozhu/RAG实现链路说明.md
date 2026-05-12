# RAG 实现链路说明

## 这份文档解决什么问题？

`docs/shujubiaozhu` 目录里有两类标注规范：

- `话术标注规范.md`：告诉业务同学怎么整理可推荐的话术。
- `素材标准规范.md`：告诉业务同学怎么整理可推荐的图片、视频、文件素材。

这份文档把两份规范和当前系统实现串起来，说明一条语料从 CSV 到 AI 对话推荐，中间经过哪些表、哪些代码、哪些门禁。

先定一个总口径：RAG 是 **support index / support knowledge**。它用于帮助教练和 AI 助手找到参考资料，但不替代话术库、素材库、客户档案里的 official truth。

---

## 一句话链路

话术或素材先进入业务表，再被整理成 RAG 资源，切成 chunk，写入 Qdrant；AI 对话时根据客户问题检索 Qdrant，再回查数据库，把可用的话术和素材返回给前端。

```text
CSV 标注
  -> 业务表 speech_templates / materials
  -> RAG 表 rag_resources / rag_chunks
  -> Qdrant collection wecom_health_rag
  -> AI 对话检索
  -> 话术参考 sources + 素材 recommended_assets
```

---

## 当前真值在哪里？

当前服务使用 `.env` 里的 MySQL 业务库：

```text
DATABASE_URL=mysql+pymysql://.../wecom_ops
```

默认的 `data/app.db` 不是当前服务真值。它可能存在，但不能用它判断 RAG 是否入库。

RAG 相关真值分三层：

| 层级 | 位置 | 用途 |
|------|------|------|
| 业务 official truth | `speech_templates`、`materials` | 正式话术、正式素材、素材存储状态 |
| RAG support index | `rag_resources`、`rag_chunks`、`rag_retrieval_logs` | 检索资源、切片、审计日志 |
| 向量索引 | Qdrant `wecom_health_rag` | 向量召回和 payload 过滤 |

`rag_tags` 是受控词表。`rag_resource_tags` 当前不是主链路，不能只看它是否有数据来判断标签是否生效。

---

## 话术怎么进入 RAG？

### 1. CSV 入口

对应文档：`话术标注规范.md`

关键字段：

```text
title,clean_content,category_code,summary,status,customer_goal,intervention_scene,content_kind,visibility,safety_level,question_type,tags,usage_note,tone,reviewer,review_note
```

当前导入逻辑：

- `title` 必须有。
- `clean_content` 或 `content` 必须有。
- `status` 只接受 `approved` 或 `active`。
- 标签必须使用当前词表 code。不在词表中的值会被丢弃并报告 warning。
- `visibility` 只应使用 `coach_internal` 或 `customer_visible`。
- `category_code` 推荐填写，用于精确定位三级分类（如 `health.diet.food_choice`）。
- 安全级别硬规则：`contraindicated` 禁止入库；`medical_sensitive` / `doctor_review` 不可设为 `customer_visible`。
- 导入结果会区分 error（阻断）和 warning（非阻断，如未知标签被忽略），应逐一排查。

### 2. 落业务表

代码入口：

```text
app/services/speech_template_import.py
scripts/import_speech_templates_csv.py
```

落库关系：

| CSV 字段 | 业务表落点 |
|----------|------------|
| title | `speech_templates.label` |
| clean_content | `speech_templates.content` |
| category_code | 解析为 `speech_templates.category_id`（通过 `speech_categories.code` 匹配） |
| tone | `speech_templates.style` |
| intervention_scene / question_type | 参与推导 `speech_templates.scene_key`（场景列表从 `rag_tags` 动态加载） |
| summary / customer_goal / intervention_scene / question_type / visibility / safety_level / tags / usage_note | `speech_templates.metadata_json`（未知标签被丢弃并报告 warning） |

### 3. RAG 索引

代码入口：

```text
app/rag/resource_indexer.py
```

索引时会把这些信息拼成 `semantic_text`：

- 话术标题
- 话术正文
- 摘要
- 目标、场景、问题类型
- 使用场景
- 自由标签
- 话术分类 L1/L2/L3
- 分类 code（如 `health.diet.food_choice`）

然后写入：

```text
rag_resources.source_type = speech_template
rag_resources.content_kind = script
rag_chunks
Qdrant payload
```

Qdrant payload 会保存 `customer_goal / intervention_scene / question_type / visibility / safety_level / content_kind / status / category_code / category_l3` 等字段，用于后续过滤和加权。

---

## 素材怎么进入 RAG？

### 1. 前提

素材必须先在素材库里存在。CSV 不负责新建素材文件，只负责给已有素材补 RAG 标注。

素材必须满足：

- `materials.enabled=1`
- `materials.deleted_at IS NULL`
- `materials.storage_status=ready`
- 如果要 `customer_visible`，必须已有可访问的 `materials.public_url`

### 2. CSV 入口

对应文档：`素材标准规范.md`

关键字段：

```text
source_type,title,summary,content_kind,status,rag_enabled,visibility,safety_level,copyright_status,customer_sendable,alt_text,usage_note,customer_goal,intervention_scene,question_type,tags,material_ref,file_name,file_hash,transcript,public_url
```

匹配素材优先级：

```text
material_ref > file_hash > file_name
```

推荐优先用：

```text
materials.id=具体素材ID
```

### 3. 导入门禁

代码入口：

```text
app/services/material_rag_import.py
```

当前 CSV 导入会检查：

- 必填字段是否完整。
- `status` 是否为 `approved/active`。
- `rag_enabled` 是否为 `yes/true/1`。
- `copyright_status` 是否不是 `unknown`。
- 图片/表情包是否有 `alt_text`。
- 视频是否有 `transcript` 或 `alt_text`。
- 素材是否能匹配到 `materials`。
- 素材存储是否 ready。
- `customer_visible` 是否有 public_url。
- 医疗敏感、医生审核、禁忌素材不能设为 `customer_visible`。

### 4. RAG 索引

素材通过门禁后，会写入：

```text
rag_resources.source_type = material
rag_resources.content_kind = image / video / meme / file
rag_chunks
Qdrant payload
```

素材的 `semantic_text` 主要来自：

- 标题
- 摘要
- 图片说明或视频转写
- 使用场景
- 目标、场景、问题类型
- 自由标签

---

## AI 对话时怎么检索？

代码入口：

```text
app/rag/retriever.py
app/rag/query_compiler.py
app/rag/vector_store.py
```

检索分两路：

### 第一路：话术/知识参考

系统先检索：

```text
content_kind in script, text, knowledge_card
```

这些结果会进入 `sources`，并被拼进 AI prompt 作为参考资料。

过滤规则包括：

- 只取 `status=active`。
- 排除 `semantic_quality=weak/stale`。
- 根据 `intervention_scene` 做场景过滤。
- 根据问题风险限制 `safety_level`。
- 根据 `customer_goal / question_type / intervention_scene` 做标签加权。

如果场景过滤太严导致 0 命中，系统会放宽场景过滤再试一次。

### 第二路：素材推荐

系统再检索：

```text
content_kind in image, video, meme, file
```

这些结果不会直接拼进 AI 正文，而是形成 `recommended_assets`。

返回前还会回查 `materials`，确认素材仍然：

- 启用
- 存储 ready
- 未删除

---

## 审计日志怎么查？

每次 RAG 检索会写入：

```text
rag_retrieval_logs
```

重点字段：

| 字段 | 说明 |
|------|------|
| query_text | 实际用于检索的查询文本 |
| filter_json | 本次检索使用的过滤条件 |
| hit_json | 命中的资源、分数、过滤原因 |
| intent_json | 轻量意图识别结果 |
| query_intent_json | 结构化标签意图 |
| rerank_scores_json | 开启 rerank 后的分数记录 |

排查“为什么没召回”时，先看 `filter_json` 和 `hit_json`。

---

## 当前目录里的文件怎么配合？

| 文件 | 作用 |
|------|------|
| `话术标注规范.md` | 给话术 CSV 标注人员使用 |
| `素材标准规范.md` | 给素材 CSV 标注人员使用 |
| `test_huashu.csv` | 话术导入样例 |
| `test_material_rag.csv` | 素材导入样例 |
| `question-category.xlsx` | 问题分类参考表，目前主要作为分类参考，不是 RAG 强过滤词表 |
| `RAG实现链路说明.md` | 本文，串联标注、入库、索引、检索和治理 |

---

## 当前已知历史数据风险

这些是审查当前库时发现的历史问题，不代表新规范应该照着填。

1. ~~历史话术里仍有 `visibility=customer_sendable`，应统一迁移为 `customer_visible`。~~ **已修复**：系统迁移脚本已自动将 `customer_sendable` / `internal` / `public` 统一替换为 `customer_visible` / `coach_internal`。
2. 历史素材 RAG 里仍有 active weak 资源，其中部分素材已删除或没有 `rag_meta_json`。
3. 个别素材 RAG meta 里仍有中文标签或旧 code，例如 `血糖管理`、`lifestyle_change`、`exercise_guidance`。
4. ~~`question-category.xlsx` 的三级、细分分类尚未进入 RAG payload，当前只落了话术分类 L1/L2。~~ **已修复**：RAG payload 现在包含 L3 分类名称和 `category_code`（如 `health.diet.food_choice`）。
5. `rag_resource_tags` 当前为空，这是实现现状；标签主要在 `metadata_json`、`semantic_text` 和 Qdrant payload 中生效。
6. CSV 导入时不在词表中的标签值会被静默丢弃——**已改善**：导入结果现在会报告 warning 列出被丢弃的标签值，标注同学可据此补充词表后重新导入。

---

## 标准上线前检查清单

上线或批量导入前，建议按这个顺序检查：

- [ ] CSV 表头与规范一致。
- [ ] 话术 CSV 中 `category_code` 列填写了正确的分类标识（如 `health.diet.food_choice`）。
- [ ] 所有受控字段都使用英文 code，且在词表中存在。
- [ ] `contraindicated` 话术不会出现在 CSV 中（会被导入拦截）。
- [ ] `medical_sensitive / doctor_review` 没有标成 `customer_visible`。
- [ ] 素材都能匹配到 `materials`。
- [ ] 素材 `storage_status=ready`。
- [ ] `customer_visible` 素材有 public_url。
- [ ] 图片有 alt_text，视频有 transcript 或 alt_text。
- [ ] 导入后检查结果中的 errors（阻断）和 warnings（非阻断），逐一处理。
- [ ] 导入后 `rag_resources` 和 `rag_chunks` 数量符合预期。
- [ ] Qdrant `wecom_health_rag` points 数量与 `rag_chunks` 基本对齐。
- [ ] 用固定问题做检索回放，检查 `rag_retrieval_logs.hit_json`。

---

## 面向项目负责人的当前状态

### 已经能做什么

- 能把审核后的话术导入系统，并索引进 RAG。
- 能通过 `category_code` 精确指定话术的三级分类（L1/L2/L3 均在 RAG payload 中）。
- 能在话术管理页面直接管理标签（新增/编辑），无需联系后端。
- 能把已有素材补充 RAG 标注，并作为推荐素材返回。
- 能按场景、安全等级、语义相似度和标签加权做检索。
- 能在 CSV 导入时自动校验安全级别硬规则，并报告未知标签 warning。
- 能记录检索日志，支持复盘为什么召回或没召回。

### 半能做什么

- 能过滤 weak/stale，但历史 weak 素材还需要一次治理。
- 能用 Qdrant payload 做过滤，但 `rag_resource_tags` 关系表还不是正式主链路。

### 还不能做什么

- 不能把 RAG 命中结果当成素材或话术 official truth。
- 不能保证历史旧数据都符合新规范。
- 不能只靠上传 CSV 就让不存在或已删除的素材变成可推荐素材。

### 当前 blocker

最大 blocker 不是文档，而是历史 RAG 数据治理：旧标签 code、weak/deleted 素材 active 状态需要统一清理并重建索引。（旧 `visibility` 值已由迁移脚本自动修复。）

### 下一步最值得做什么

先做一轮 RAG 数据治理脚本和重建索引（重点是 weak 素材清理和旧标签 code 修正），再扩大语料导入范围。否则新规范写得再清楚，旧索引仍会干扰检索质量和验收判断。
