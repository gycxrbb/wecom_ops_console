# RAG 生产化架构与标注标准优化报告

> 日期: 2026-04-28  
> 范围: 当前 RAG 代码架构、话术/素材 CSV 标注、生产化检索质量、未来规模风险  
> 审阅文件: `docs/shujubiaozhu/素材库字段.md`、`docs/shujubiaozhu/test_huashu.csv`、`docs/shujubiaozhu/test_material_rag.csv`、`app/rag/*`、`app/services/*rag*`、`app/crm_profile/services/prompt_builder.py`  
> 结论口径: RAG 是 `support knowledge / support index`，不能晋升为客户档案 `official/formal truth`。

## 1. 结论摘要

当前 RAG 已经具备 P0 技术闭环：话术和素材能被导入、切片、embedding、写入 Qdrant，并在 CRM AI 对话里以参考资料形式返回。

但从资深 RAG 工程角度看，它还不是成熟生产级 RAG。当前主要是:

```text
人工标注 CSV
-> semantic_text 拼接
-> dense embedding
-> Qdrant cosine topK
-> 少量 payload filter
-> 分数阈值截断
-> 注入 prompt / 返回推荐素材
```

这套方案能做小样本验证，但语料一多会出现明显问题:

1. 高相似但不适用的内容排在前面。
2. 表情包、运营话术、医学敏感内容污染专业问答。
3. 视频、文件、图片都用 `file/image` 粗分类，后续展示和召回会混。
4. 标签有中文、有英文、有业务口语，检索过滤会失效。
5. 没有 rerank 和评估集，无法证明“召回变好了”。
6. 没有索引版本和数据质量门禁，线上索引会慢慢漂移。

因此下一步不应该急着全量上线，而应该先把它升级成“可控小规模生产版”。

第一版成熟生产标准建议定义为:

```text
精选语料 + 受控标签 + 强过滤 + dense/sparse 混合召回 + rerank + 质量门禁 + 评估集验收 + 可回滚索引
```

## 2. 当前系统判断

### 已经做对的部分

1. `rag_resources` 作为索引层，没有直接替代话术库和素材库，这是正确方向。
2. `rag_chunks` 保存 chunk 与 point id，便于追踪 Qdrant point。
3. `rag_retrieval_logs` 已能记录 query、filter、hit、latency、intent，是后续评估基础。
4. `prompt_builder.py` 明确写了 RAG 是“公司话术与知识库参考”，不是客户事实。
5. `retriever.py` 已经把话术/知识和素材推荐分成两路检索。
6. 话术导入已经能把 `customer_goal / intervention_scene / question_type / safety_level / visibility / summary` 写入 `metadata_json`，并在索引时进入 Qdrant payload。

### 当前还不成熟的部分

1. 检索只依赖 dense vector，没有 BM25/关键词召回，精确术语、素材名、设备名会不稳。
2. `rag_rerank_enabled` 有配置，但没有 rerank client 和实际精排链路。
3. query 只拼 `scene_key + message`，没有系统化引入客户目标、客户阶段、安全边界、输出意图。
4. 标签没有统一到受控词表，素材 CSV 仍有 `血糖管理/饮食管理/情绪支持` 等中文自由值。
5. `visibility` 口径不统一: 话术样本用 `customer_sendable`，素材字段规范用 `customer_visible`。
6. `content_kind=file` 被用来表示视频素材，未来视频、PDF、课件、普通文件会混在一起。
7. 素材 UI 保存 RAG 元数据后会直接索引，缺少审核状态、版权、公网地址、安全等级硬门禁。
8. `RagSource.tags` schema 有字段，但当前返回没有真正填充标签。
9. 素材推荐理由现在基本取 `semantic_text[:100]`，不是针对用户问题生成的可解释推荐理由。
10. 没有离线评估集和指标，无法判断参数调优是否有效。

## 3. 当前 CSV 与字段标准审阅

### 3.1 `test_huashu.csv`

当前样本共 5 条:

1. 4 条 `customer_sendable + nutrition_education`
2. 1 条 `coach_internal + medical_sensitive`
3. 都是 `content_kind=script`
4. `source_type=speech_template`

优点:

1. 字段比早期版本完整，已经有 `source_id/source_location/owner/reviewer/review_note`。
2. 话术内容本身有较明确业务场景。
3. 医疗敏感话术被标为 `coach_internal + medical_sensitive`，方向正确。

问题:

1. `visibility=customer_sendable` 与素材侧 `customer_visible` 不一致。
2. `tone` 使用中文，如 `专业温和/温柔安抚/实用落地`，当前代码会映射为英文 style，但不是所有值都有稳定映射。
3. `question_type` 是自由 code，如 `carb_choose/low_calorie/food_safety`，目前没有字典约束。
4. CSV 导入到 `speech_templates` 后，`source_id/source_location/owner/reviewer/review_note` 没有作为正式审计字段落库，只能部分进入导入结果。
5. 话术安全等级有 `nutrition_education/medical_sensitive`，但素材字段文档里只写了 `general/medical_review`，安全等级体系不统一。

### 3.2 `test_material_rag.csv`

当前样本共 4 条:

1. 2 条 `content_kind=file`
2. 2 条 `content_kind=image`
3. 全部 `visibility=coach_internal`
4. 1 条 `customer_sendable=yes` 但仍是 `coach_internal`
5. 多个 `customer_goal` 使用中文自由值

优点:

1. 已要求 `material_ref/file_name/file_hash` 匹配素材库资产。
2. 已要求 `summary/alt_text/usage_note/tags`，对图片/视频语义化是正确方向。
3. 已区分 `copyright_status`，能避免未知版权素材入库。

问题:

1. 视频素材被标为 `content_kind=file`，未来会导致视频召回、封面展示、播放操作、转写质量评估全部混乱。
2. `customer_goal` 用中文值，如 `血糖管理/设备使用/饮食管理/情绪支持`，不能直接作为生产 payload filter。
3. `customer_sendable=yes` 但 `visibility=coach_internal`，这两个字段冲突。生产标准里应以 `visibility` 为正式口径，`customer_sendable` 只做导入辅助。
4. 表情包 `content_kind=image`，但实际应为 `meme`，否则会污染知识图片召回。
5. `question_type` 有时为空，有时误填 `meal_review` 这种场景值，维度混用。
6. 缺少 `reviewer/reviewed_at/review_note/quality_score/effective_from/effective_to` 等生产治理字段。

## 4. 第一版生产标注标准

### 4.1 通用原则

第一版上线必须统一这几个概念:

```text
source_type: 内容来源
content_kind: 内容形态
customer_goal: 客户目标
intervention_scene: 干预场景
question_type: 用户问题类型
visibility: 谁能看、能否发客户
safety_level: 安全风险等级
status: 内容审核与生命周期
semantic_quality: 语义标注质量
```

所有用于 payload filter 的字段必须用英文 code，不用中文自由文本。中文只作为 label 展示。

### 4.2 受控词表 v1

#### source_type

| code | 含义 | official truth |
| --- | --- | --- |
| `speech_template` | 话术 | `speech_templates` |
| `material` | 素材 | `materials` |
| `manual_card` | 人工知识卡片 | 未来知识卡片表 |
| `external_doc` | 外部文档 | `external_doc_resources` |

第一版只正式启用 `speech_template` 和 `material`。

#### content_kind

| code | 说明 | 是否注入 prompt | 是否作为素材卡 |
| --- | --- | --- | --- |
| `script` | 可参考/可改写话术 | 是 | 可选 |
| `knowledge_card` | 稳定知识卡片 | 是 | 可选 |
| `image` | 图片素材 | 否，最多注入摘要 | 是 |
| `video` | 视频素材 | 否，最多注入摘要 | 是 |
| `meme` | 表情包 | 否 | 只在情绪场景推荐 |
| `file` | PDF/表格/文档类附件 | 否，最多注入摘要 | 是 |

生产要求: mp4/mov/视频类素材必须标 `video`，表情包必须标 `meme`，不要再用 `file/image` 兜底。

#### customer_goal

| code | 中文 |
| --- | --- |
| `weight_loss` | 减重 |
| `glucose_control` | 控糖 |
| `habit_building` | 习惯养成 |
| `nutrition_education` | 饮食营养教育 |
| `exercise_adherence` | 运动坚持 |
| `emotion_support` | 情绪支持 |
| `device_usage` | 设备使用 |
| `maintenance` | 长期维护 |

CSV 中的中文应导入时映射，例如 `血糖管理 -> glucose_control`，`饮食管理 -> nutrition_education`。

#### intervention_scene

| code | 中文 |
| --- | --- |
| `meal_checkin` | 晒餐/餐盘打卡 |
| `meal_review` | 餐评 |
| `obstacle_breaking` | 破阻力 |
| `habit_education` | 习惯教育 |
| `emotional_support` | 情绪支持 |
| `qa_support` | 问题答疑 |
| `period_review` | 周期复盘 |
| `maintenance` | 长期维护 |
| `abnormal_intervention` | 异常干预 |
| `data_monitoring` | 数据监测 |
| `device_guidance` | 设备指导 |
| `points_operation` | 积分/社群运营 |

注意: 当前代码 `_SCENE_MAP` 把 `abnormal_intervention` 映射为 `obstacle_breaking`，这在健康异常场景里不够准确。建议保留 `abnormal_intervention` 本身，不要默认降到破阻力。

#### question_type

第一版不要无限扩张，先固定高频问题:

| code | 中文 |
| --- | --- |
| `dining_out` | 外食/外卖 |
| `carb_choose` | 主食选择 |
| `low_calorie` | 低卡食材 |
| `late_night_snack` | 晚间零食 |
| `craving` | 嘴馋/食欲 |
| `hunger` | 饥饿感 |
| `food_safety` | 食材安全 |
| `high_glucose` | 血糖偏高 |
| `blood_fluctuation` | 血糖波动 |
| `data_monitoring` | 数据解读 |
| `no_checkin` | 不打卡 |
| `low_motivation` | 动力不足 |
| `device_usage` | 设备使用 |
| `plateau` | 平台期 |

#### visibility

生产只保留两个正式值:

| code | 含义 |
| --- | --- |
| `coach_internal` | 仅教练内部参考，不允许一键发送客户 |
| `customer_visible` | 可展示给客户/可进入发送中心，但仍需教练复核 |

`customer_sendable` 不再作为正式 visibility 值。CSV 可以保留 `customer_sendable=yes/no` 作为导入辅助，但最终必须映射到 `visibility=customer_visible/coach_internal`。

#### safety_level

| code | 含义 | 生产动作 |
| --- | --- | --- |
| `general` | 通用安全 | 可正常召回 |
| `nutrition_education` | 饮食营养科普 | 可召回，输出不得承诺疗效 |
| `medical_sensitive` | 医疗敏感 | 仅内部参考，不直接发客户 |
| `doctor_review` | 需医生确认 | 不进客户可见推荐 |
| `contraindicated` | 禁用/高风险 | 不进入 active 索引 |

`medical_review` 建议作为兼容别名，导入时映射到 `doctor_review`。

#### status

| code | 含义 | 是否进入 active 检索 |
| --- | --- | --- |
| `candidate` | 候选 | 否 |
| `approved` | 已审核 | 可索引 |
| `active` | 已上线 | 可召回 |
| `disabled` | 停用 | 否 |
| `archived` | 归档 | 否 |

生产建议: CSV 导入时 `approved` 可以建索引，但 Qdrant payload 的 `status` 应使用 `active`；内容下线时必须同步把 payload 更新为非 active 或删除 point。

### 4.3 话术 CSV v1 标准

必填字段:

```csv
source_id,source_type,source_location,owner,title,clean_content,summary,status,customer_goal,intervention_scene,content_kind,visibility,safety_level,question_type,tone,reviewer,review_note
```

约束:

1. `source_type` 固定 `speech_template`。
2. `content_kind` 固定 `script`。
3. `clean_content` 必须是可复用话术，不要带客户隐私、活动临时信息、二维码。
4. `summary` 用 50-120 字解释适用场景，不重复整段话术。
5. `visibility=customer_visible` 的话术必须能直接给客户看，但仍是教练复核草稿。
6. `safety_level in (medical_sensitive, doctor_review)` 时，visibility 必须是 `coach_internal`。
7. `tone` 导入后统一映射为英文 code: `professional / encouraging / practical / gentle / firm / competitive`。

建议新增字段:

```csv
version,effective_from,effective_to,contraindications,source_confidence,duplicate_group
```

这些字段不是 P0 必须，但进入生产后很有用。

### 4.4 素材 CSV v1 标准

必填字段:

```csv
source_id,source_type,title,summary,content_kind,status,rag_enabled,visibility,safety_level,copyright_status,customer_goal,intervention_scene,question_type,tags,usage_note,material_ref,file_name,file_hash
```

按内容类型额外必填:

| content_kind | 额外必填 |
| --- | --- |
| `image` | `alt_text` |
| `video` | `transcript` 或 `video_summary`，至少一个 |
| `meme` | `alt_text` + `usage_note` + `intervention_scene=emotional_support` |
| `file` | `summary` + `usage_note` + 文件页/主题说明 |

客户可见素材额外必填:

```csv
public_url,reviewer,review_note
```

强规则:

1. `customer_sendable=yes` 但 `public_url` 为空，必须失败，不建议静默降级。
2. `copyright_status=unknown` 必须跳过。
3. `content_kind=meme` 不能进入 prompt，只能作为 attachment 推荐。
4. `semantic_quality=weak` 不允许进入正式生产推荐。
5. 素材必须先在 `materials` 中存在，RAG 只保存 `source_id=materials.id`，不维护第二份 URL truth。
6. 可发客户必须以后端回查 `materials.public_url/storage_status` 为准，不能相信前端或 CSV 回传 URL。

## 5. 检索算法成熟度评估

### 当前算法等级

当前是 P0 等级，不是成熟生产级。

| 能力 | 当前状态 | 判断 |
| --- | --- | --- |
| Dense 向量召回 | 已有 | 可用 |
| Payload filter | 部分已有 | 需增强 |
| Query 改写 | 没有 | 缺口 |
| 客户画像参与检索 | 没有系统化使用 | 缺口 |
| BM25/关键词召回 | 没有 | 缺口 |
| Rerank | 配置有，代码无 | 缺口 |
| 分数阈值 | 有基础阈值 | 需评估校准 |
| 多样性控制 | 没有 | 缺口 |
| 重复内容合并 | 没有 | 缺口 |
| 评估集 | 没有工程化 | 缺口 |

### 生产版检索流程 v1

建议改成:

```text
用户问题 + scene_key + output_style + 客户目标/阶段/风险摘要
  ↓
Query Compiler: 标准化查询意图、场景、目标、安全等级
  ↓
强过滤: source_type/content_kind/status/visibility/safety_level/customer_goal/intervention_scene
  ↓
Hybrid Recall:
  - Dense vector top 40
  - Keyword/BM25 top 20
  - 规则召回 top 10
  ↓
候选合并去重
  ↓
Rerank top 50 -> top 8
  ↓
质量门禁:
  - min_score
  - relative_score
  - semantic_quality
  - safety_level
  - visibility
  - recency/effective time
  ↓
分桶:
  - prompt_sources: script / knowledge_card
  - recommended_assets: image / video / meme / file
  ↓
审计:
  - query_intent
  - filters
  - raw_hits
  - rerank_scores
  - filtered_reason
  - final_sources
```

### Rerank 建议

第一版生产建议接入 rerank，但可以灰度开关:

```env
RAG_RERANK_ENABLED=true
RAG_RERANK_MODEL=jina-reranker-v3
RAG_RERANK_TOP_N=8
```

精排输入不要只给 chunk，要给:

```text
title
summary
chunk_text
customer_goal
intervention_scene
question_type
content_kind
```

否则 rerank 也会丢失业务标签上下文。

## 6. 素材变多后的主要风险

### 6.1 召回噪音指数上升

当素材从几十个变成几百/几千个时，仅靠 dense similarity 会召回大量“语义接近但业务不可用”的素材。例如用户问血糖波动，可能同时召回血糖仪教程、血糖标准图、饥饿感视频、医学敏感图表。如果没有 safety 和 content_kind 门禁，前端会显得“推荐了一堆东西，但不能直接用”。

### 6.2 表情包污染专业问答

表情包如果标成 `image`，会和科普图竞争推荐位。生产必须要求:

```text
content_kind=meme
intervention_scene=emotional_support
safety_level=general
不进入 prompt
只在低动力/鼓励/打卡完成场景出现
```

### 6.3 视频与文件混用

当前样本中视频使用 `content_kind=file`。未来视频多了之后，无法做视频封面、播放、转写质量、时长、章节摘要、客户可发校验。生产必须单独使用 `video`。

### 6.4 标签漂移

如果运营持续新增中文自由标签，Qdrant payload filter 会越来越失效。必须有导入映射表和未知标签拒绝策略:

```text
unknown tag -> candidate / skipped
不能自动进入 active
```

### 6.5 索引和 MySQL truth 漂移

素材在 MySQL 被禁用、删除、换 URL 后，Qdrant point 如果没有同步下线，会继续被召回。生产需要:

1. 保存素材时写 pending index job。
2. 删除/停用素材时同步 disable RAG resource。
3. 每日巡检 `rag_resources.source_id` 与原始表状态。
4. 支持一键重建索引。

### 6.6 性能与成本

语料变多后:

1. 每次 `is_available()` 都访问 Qdrant，会增加链路耗时。
2. 大批量 reindex 会消耗 embedding 费用。
3. 没有后台任务队列时，用户保存素材会被 embedding 阻塞。
4. Qdrant 需要 payload index，否则过滤字段多了性能会下降。

建议给 Qdrant 创建 payload index:

```text
status
source_type
content_kind
customer_goal
intervention_scene
question_type
visibility
safety_level
semantic_quality
```

## 7. 推荐优化路线

### Phase 0: 上线前必须完成

1. `requirements.txt` 加 `qdrant-client==1.17.1`。
2. 生产使用 `QDRANT_MODE=remote`。
3. 修正 healthcheck，避免 `/api/v1/bootstrap` 未登录 401。
4. 统一 `visibility`: 正式只用 `coach_internal/customer_visible`。
5. 统一 `safety_level`: 正式使用 `general/nutrition_education/medical_sensitive/doctor_review/contraindicated`。
6. 修改素材 CSV 标准: 视频用 `video`，表情包用 `meme`。
7. 建 30-50 条评估问题集，覆盖外食、血糖、晚间零食、打卡、设备使用、情绪支持。

### Phase 1: 第一版生产 RAG

1. 新增 Query Compiler，把用户问题解析成:

```json
{
  "domain": "nutrition",
  "customer_goal": ["weight_loss", "glucose_control"],
  "intervention_scene": ["qa_support"],
  "question_type": ["dining_out"],
  "max_safety_level": "nutrition_education"
}
```

2. 接入 rerank。
3. 增加 keyword/BM25 召回。
4. 素材推荐只返回 `semantic_quality in (ok, medium)`。
5. RAG 事件返回 `filtered_reason`，方便调试。
6. 每次召回写完整审计: raw hits、rerank scores、过滤原因。

### Phase 2: 运营可持续治理

1. `rag_tags` 真正作为标签字典，不只是建表。
2. 素材标注 UI 改为“保存草稿 -> 审核 -> 索引”，不要保存即 active。
3. 增加索引任务表: `pending/indexing/indexed/failed`。
4. 建 RAG 后台看板:
   - 无召回问题
   - 错召回问题
   - 高风险素材命中
   - 低质量素材命中
   - Top query
5. 建内容去重和相似内容合并。

## 8. 验收标准

第一版成熟生产环境上线前，建议至少满足:

### 数据验收

1. 话术 100-150 条，素材 40-70 个，不做全量。
2. `unknown tag = 0`。
3. `semantic_quality=weak` 的素材不进入 active。
4. `medical_sensitive/doctor_review` 不进入客户可见推荐。
5. `customer_visible` 素材 100% 有 `public_url`。

### 检索验收

用 30-50 条评估问题做固定测试:

| 指标 | 目标 |
| --- | --- |
| Top1 命中率 | >= 60% |
| Top3 命中率 | >= 80% |
| 错误素材推荐率 | <= 5% |
| 医疗敏感误发推荐 | 0 |
| 表情包误入专业问答 | 0 |
| RAG 不可用时主回答可降级 | 100% |

### 工程验收

1. Qdrant remote 模式可用。
2. RAG status 接口显示 available。
3. 后端启动不依赖 Qdrant 必须成功，RAG 不可用只降级。
4. reindex 可重复执行，不生成重复 point。
5. 每条召回能追溯到 source table 和 source id。

## 9. 本轮对三个标注文档的结论

### `素材库字段.md`

可以作为 P0 草案，但需要升级:

1. 增加话术和素材共用的受控词表。
2. 把 `customer_sendable` 明确为导入辅助，不是正式 visibility。
3. 增加 `video/meme` content_kind。
4. 增加 `nutrition_education/medical_sensitive/doctor_review` 安全等级。
5. 增加“未知标签处理规则”和“弱语义不进生产推荐”。

### `test_huashu.csv`

样本质量不错，可以继续作为话术 P0 样本，但需要:

1. `customer_sendable` 改成或映射为 `customer_visible`。
2. `tone` 统一映射英文 code。
3. `question_type` 建字典。
4. 医疗敏感内容保持 `coach_internal`。

### `test_material_rag.csv`

只能作为素材 P0 草稿，不能直接代表生产标准。必须调整:

1. 视频 `content_kind=file` 改为 `video`。
2. 表情包 `content_kind=image` 改为 `meme`。
3. 中文 `customer_goal` 映射英文 code。
4. `customer_sendable=yes` 与 `visibility=coach_internal` 的冲突必须消除。
5. 可发客户素材必须提供 `public_url`。

## 10. 最终建议

下一步最值得做的不是继续堆更多语料，而是先让这套 RAG 变得可评估、可解释、可治理。

建议按这个顺序推进:

```text
统一字段标准
-> 改 CSV 样本
-> 建评估问题集
-> 强化导入校验
-> 接入 rerank
-> 做 hybrid recall
-> 小样本上线
-> 看召回日志迭代标签
```

只有当评估集稳定通过后，才扩大素材和话术规模。否则素材越多，系统越不像“知识增强”，越像“随机推荐一堆相似内容”。

第一版成熟版本的核心原则:

```text
宁可少召回，也不要错召回。
宁可先内部参考，也不要误发客户。
宁可字段严格，也不要向量库污染。
宁可小样本验收通过，也不要全量上线后靠人工救火。
```
