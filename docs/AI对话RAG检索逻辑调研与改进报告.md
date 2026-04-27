# AI 对话 RAG 检索逻辑调研与改进报告

> 日期: 2026-04-27  
> 范围: CRM 客户档案 AI 对话、RAG 检索、话术索引、前端参考语料展示与发送中心衔接  
> 结论口径: RAG 召回内容是 `support knowledge`，不是客户档案 `official/formal truth`

---

## 1. 结论摘要

当前 AI 对话的 RAG 已经接入了基础闭环：话术入库、embedding、Qdrant 向量召回、注入 prompt、通过 SSE 返回前端参考语料。

但目前检索判断还停留在“向量相似度 topK 截取”阶段，缺少标签过滤、意图识别、分数门槛、精排和污染过滤。因此会出现“目标话术排第一，但低相关的积分运营话术也被一起返回”的问题。

针对用户测试问题 `客户要出差，推荐一下餐食`，最新数据库召回日志显示：

| 排名 | 资源标题 | 分数 | 判断 |
| --- | --- | ---: | --- |
| 1 | 出差外食外卖场景点餐指导话术 | 0.5908 | 正确命中 |
| 2 | 低卡放心食材参考指导话术 | 0.3573 | 弱相关 |
| 3 | 潜水提醒 | 0.3336 | 污染，积分/活跃运营语料 |
| 4 | 社群 PK | 0.3329 | 污染，积分/社群运营语料 |
| 5 | 每日氛围 | 0.3326 | 污染，积分运营语料 |
| 6 | 减脂控糖主食分级选择指导话术 | 0.3219 | 饮食相关但弱相关 |

所以严格说，当前第一名是对的；问题在于后续结果没有做“低置信度截断”和“业务域过滤”，导致参考语料区混入不该展示的内容。

---

## 2. 当前 RAG 逻辑是什么

### 2.1 语料来源

当前 RAG 主要索引两类资源：

1. `speech_templates`: 话术模板。
2. `materials`: 素材库资源。

相关文件：

1. `app/routers/api_speech_templates.py`
   - CSV 导入话术。
   - 如果导入时传 `index_rag=true`，会调用 RAG 重新索引。
2. `app/rag/resource_indexer.py`
   - `index_speech_templates()` 索引话术。
   - `index_materials()` 索引素材。

### 2.2 话术如何变成向量

话术入库时会构造 `semantic_text`：

```text
标题 label
正文 content
场景: scene_key
风格: style
```

然后执行：

1. `chunk_text()` 按字符切片，默认 `chunk_size=600`、`overlap=80`。
2. `embed_texts_batch()` 调用 aihubmix OpenAI 兼容 `/v1/embeddings`。
3. 默认模型配置是 `text-embedding-3-large`，维度 `1024`。
4. 写入 Qdrant，collection 是 `wecom_health_rag`，距离算法是 `Cosine`。

当前向量 payload 只包含：

```json
{
  "resource_id": 39,
  "source_type": "speech_template",
  "source_id": 39,
  "status": "active",
  "content_kind": "script",
  "safety_level": "general",
  "visibility": "coach_internal"
}
```

关键问题是：CSV 中的 `customer_goal / intervention_scene / question_type / tone / visibility / safety_level` 等标注字段没有完整进入 `rag_resource_tags` 或 Qdrant payload。也就是说，系统知道这是一条脚本，但不知道它是“出差/外卖/外食/餐食”这个强标签。

### 2.3 对话时如何检索

CRM AI 对话 prepare 阶段会调用：

```python
retrieve_rag_context(
    customer_id=customer_id,
    message=message,
    scene_key=scene_key,
    output_style=output_style,
)
```

当前检索流程：

1. 拼接查询文本: `query_text = f"{scene_key} {message}"`。
2. 对 query_text 做 embedding。
3. 调 Qdrant 向量搜索。
4. 固定过滤:

```python
filters = {"content_kind": ["script", "text", "knowledge_card"]}
```

5. Qdrant 侧再默认加 `status=active`。
6. 召回 `rag_top_k=30`。
7. 不做 rerank，直接截取前 `rag_rerank_top_n=6`。
8. 把前 6 条组装为 `RagSource`。
9. 生成 `context_text` 注入 AI prompt。
10. 通过 SSE `event: rag` 返回前端。

### 2.4 使用的算法

当前实际算法是：

```text
Dense embedding 向量召回
+ Qdrant Cosine 相似度
+ status/content_kind payload 过滤
+ topN 直接截断
```

当前没有实际启用：

1. 关键词检索 / BM25。
2. 意图分类。
3. 标签强过滤。
4. Rerank 精排。
5. 分数阈值。
6. 相对分差截断。
7. 业务域黑白名单过滤。

虽然配置里有 `rag_rerank_enabled / rag_rerank_model`，但当前代码没有 rerank client 和 rerank 调用。

---

## 3. 为什么会混入积分运营语料

### 3.1 topN 无门槛截取

最新日志中，第一名分数是 `0.5908`，第 3-5 名已经降到 `0.333` 左右。

当前代码仍然直接取前 6 条，导致只要 Qdrant 返回了结果，就会展示出来。这里缺少：

1. 最低分数阈值。
2. 相对分差阈值。
3. 每个业务域的污染过滤。
4. 至少命中一个强标签的判断。

### 3.2 CSV 语料标注没有真正参与检索

`docs/shujubiaozhu/test.csv` 中“出差外食外卖场景点餐指导话术”的标注是比较完整的：

```text
customer_goal=weight_loss|glucose_control
intervention_scene=meal_review|qa_support
content_kind=script
visibility=customer_sendable
safety_level=nutrition_education
question_type=dining_out
tone=实用落地
```

但导入到 `speech_templates` 后，只保留了 `scene_key/style/label/content`。RAG 索引时也只把 `content_kind/safety_level/visibility/status` 放进 payload，没有把 `dining_out / meal_review / glucose_control` 等标签带入检索。

结果是系统无法用 “出差/外卖/餐食” 这种强业务标签把目标语料和积分运营语料拉开。

### 3.3 积分运营种子话术也处于 active 状态

当前 `speech_templates` 里有大量积分运营种子话术，例如：

1. 头部领先。
2. 前六冲刺。
3. 积分暴涨。
4. 潜水提醒。
5. 每日氛围。
6. 社群 PK。

这些内容也被索引为 `content_kind=script` 且 `status=active`，和饮食话术在同一个召回池里。向量模型看到“健康、减重、习惯、打卡、客户”等词时，会给它们一定相似度；如果没有标签过滤，就会混入。

### 3.4 查询改写太薄

当前 query 只是：

```text
qa_support 用户出差了，推荐下餐食
```

它没有显式补充：

1. `question_type=dining_out`
2. `intervention_scene=meal_review`
3. `domain=nutrition`
4. `exclude=points_operation`

因此向量召回只能靠自然语言相似度，无法稳定执行“出差外卖饮食语料优先”。

### 3.5 `_SCENE_MAP` 定义了但未真正用于过滤

`app/rag/retriever.py` 里存在 `_SCENE_MAP`，但当前 `_do_retrieve()` 没有用它构造 payload filter。也就是说，`scene_key` 只进入了 query 文本，没有进入强过滤条件。

### 3.6 素材推荐链路存在结构性缺口

`retriever.py` 里会从命中的 `source_type == "material"` 构造 `recommended_assets`。

但当前搜索过滤固定为：

```python
{"content_kind": ["script", "text", "knowledge_card"]}
```

而素材索引的 `content_kind` 是 `image` 或 `file`。这会导致素材通常不会被召回，`recommended_assets` 很难真正生效。

---

## 4. 当前前端返回结构问题

### 4.1 RAG 资料目前挂在 assistant 消息内部

当前 SSE 会返回：

```text
event: rag
data: {
  "rag_status": "ok",
  "sources": [...],
  "recommended_assets": [...]
}
```

前端 `useAiCoach.ts` 收到后，把它写到同一条 assistant message：

```ts
assistantMessage.ragSources = payload.sources || []
assistantMessage.ragAssets = payload.recommended_assets || []
```

`AiCoachAssistantMessage.vue` 再在 AI 回复气泡内部渲染“参考话术 / 推荐素材”卡片。

### 4.2 对复制和发送中心的影响

当前复制按钮复制的是：

```ts
msg.content
```

也就是只复制 AI 正文，不复制参考卡片。这个行为对“只复制 AI 回复”是对的，但产品语义不清晰：前端视觉上参考语料仍在同一个 assistant 气泡里，用户容易以为它属于 AI 回复本体。

发送中心打通也有同样问题。`sendToCenter()` 只会把选中的 `chatHistory` 消息按 `msg.content` 送到发送中心。RAG 参考话术不是独立消息，因此无法被单独选择、单独复制、单独发送。

### 4.3 历史会话也无法恢复参考语料

当前历史会话只加载 `role/content/message_id/token_usage`。RAG 资料没有作为独立消息或附件持久化，重新打开历史会话时参考卡片会丢失。

---

## 5. 改进目标

### 5.1 检索目标

对问题 `客户要出差，推荐一下餐食`，期望行为：

1. Top 1 必须是 `出差外食外卖场景点餐指导话术`。
2. 参考语料不应出现 `潜水提醒 / 社群 PK / 每日氛围 / 积分暴涨` 等积分运营内容。
3. 如果只有 1-2 条高置信语料，就只返回 1-2 条，不强行凑满 6 条。
4. 每条参考语料必须带推荐原因和置信依据。

### 5.2 产品目标

AI 回复和参考语料要分开：

1. AI 回复是一条正式 assistant message。
2. 每条参考话术是一条独立 reference message。
3. 每个素材是独立 attachment/reference message。
4. 复制 AI 回复时只复制 AI 正文。
5. 复制参考话术时只复制该条话术。
6. 发送到发送中心时，用户可以勾选 AI 正文，也可以勾选单条参考话术或素材。

---

## 6. 建议的检索算法改造

### 6.1 P0 快速止血

先不大改表结构，也可以先做一轮止血：

1. 增加最低分数阈值，例如 `min_score=0.42`。
2. 增加相对分差阈值，例如低于 `top_score * 0.72` 的结果默认不展示。
3. 如果 query 命中饮食/外食意图，过滤明显积分运营场景:
   - `top_leader`
   - `top_six`
   - `top_ten`
   - `surge`
   - `daily_remind`
   - `group_pk`
   - `lurker_remind`
4. 参考话术最多展示 3 条，不强行展示 6 条。
5. `hit_json` 记录完整 `resource_id/title/score/filter_reason`，便于复盘。

这能立刻减少“低分污染结果被展示”的问题。

### 6.2 P1 增加意图识别和标签过滤

增加轻量规则识别：

| 用户词 | 识别意图 |
| --- | --- |
| 出差、外卖、外食、点餐、便利店、酒店早餐 | `question_type=dining_out` |
| 餐食、吃什么、主食、低卡、控糖 | `domain=nutrition` |
| 积分、排名、榜单、打卡、活跃、PK | `domain=points_operation` |

检索时先把 query 转成结构化条件：

```json
{
  "domain": "nutrition",
  "question_type": "dining_out",
  "intervention_scene": ["meal_review", "qa_support"],
  "customer_goal": ["weight_loss", "glucose_control"],
  "negative_scene": ["top_leader", "daily_remind", "group_pk"]
}
```

然后把这些条件加入 payload filter 或后置过滤。

### 6.3 P2 恢复并使用 CSV 标签真值

需要解决“标注做了但没参与检索”的问题。

建议二选一：

1. 在 `speech_templates` 增加 `metadata_json`，保存 CSV 中的 `customer_goal / intervention_scene / question_type / tone / visibility / safety_level`。
2. 或在 CSV 导入后直接写入 `rag_tags / rag_resource_tags`，让 RAG 索引层保存标签。

推荐方案是两者结合：

1. `speech_templates` 保留原始业务元信息，作为话术管理可编辑字段。
2. `rag_resource_tags` 做检索索引层。
3. Qdrant payload 写入扁平化标签，支持强过滤。

推荐 payload：

```json
{
  "resource_id": 39,
  "source_type": "speech_template",
  "source_id": 39,
  "status": "active",
  "content_kind": "script",
  "customer_goal": ["weight_loss", "glucose_control"],
  "intervention_scene": ["meal_review", "qa_support"],
  "question_type": ["dining_out"],
  "domain": ["nutrition"],
  "visibility": "customer_sendable",
  "safety_level": "nutrition_education"
}
```

### 6.4 P3 增加 rerank 精排

当前配置已有：

```env
RAG_RERANK_ENABLED=false
RAG_RERANK_MODEL=jina-reranker-v3
```

建议补齐 `app/rag/rerank_client.py`，使用 aihubmix `/v1/rerank`。

流程改为：

```text
query 意图识别
  ↓
payload 强过滤
  ↓
Qdrant dense top_k=30
  ↓
关键词补召回 top_k=10
  ↓
rerank top_n=6
  ↓
阈值/分桶/污染过滤
  ↓
返回 reference messages
```

Rerank 输入不能只用标题，应该使用命中的 chunk 文本、标题、标签和摘要组合。

### 6.5 P4 建立评估集和回归门禁

用 `docs/shujubiaozhu/test.csv` 作为第一批 gold set，补充真实问法：

| query | expected_top1 | forbidden_titles |
| --- | --- | --- |
| 客户要出差，推荐一下餐食 | 出差外食外卖场景点餐指导话术 | 潜水提醒, 社群 PK, 每日氛围 |
| 出差只能点外卖怎么吃 | 出差外食外卖场景点餐指导话术 | 积分暴涨, 前六冲刺 |
| 外面吃饭怎么选主食 | 出差外食外卖场景点餐指导话术 或 主食分级选择指导话术 | 社群 PK |
| 想吃低卡食材怎么推荐 | 低卡放心食材参考指导话术 | 每日氛围 |
| 积分榜怎么激励前三名 | 头部领先 (TOP3) | 出差外食外卖场景点餐指导话术 |

指标：

1. Top1 命中率。
2. Top3 命中率。
3. MRR。
4. 污染率。
5. `no_hit` 合理率。

---

## 7. 参考语料作为附件/独立消息的方案

### 7.1 后端返回结构建议

新增 RAG reference message schema，不把参考语料伪装成 assistant 正文：

```json
{
  "event": "rag",
  "data": {
    "rag_status": "ok",
    "messages": [
      {
        "message_type": "rag_reference",
        "reference_type": "script",
        "resource_id": 39,
        "source_type": "speech_template",
        "source_id": 39,
        "title": "出差外食外卖场景点餐指导话术",
        "content": "出差和在外用餐，可以参考这套简单好执行的选择方式...",
        "score": 0.5908,
        "reason": "命中出差、外食、外卖、餐食意图",
        "copyable": true,
        "sendable": true,
        "support_level": "support"
      }
    ],
    "attachments": [
      {
        "message_type": "rag_attachment",
        "reference_type": "asset",
        "material_id": 12,
        "title": "外卖点餐示例图",
        "material_type": "image",
        "preview_url": "...",
        "download_url": "...",
        "sendable": true
      }
    ]
  }
}
```

注意：

1. `message_type` 必须区分 `assistant_answer / rag_reference / rag_attachment`。
2. `support_level=support`，不要写成 `official`。
3. 参考语料可以持久化，但不应进入下一轮 LLM 历史消息。
4. 如果写入历史表，需要 `audit.load_session_messages()` 过滤掉 reference message，避免污染下一轮 prompt。

### 7.2 前端消息模型建议

把 `AiChatMessage` 扩展为：

```ts
type AiChatMessage =
  | { role: 'user'; messageType: 'user'; content: string }
  | { role: 'assistant'; messageType: 'assistant_answer'; content: string }
  | { role: 'reference'; messageType: 'rag_reference'; content: string; title: string; sendable: boolean }
  | { role: 'reference'; messageType: 'rag_attachment'; title: string; asset: RagRecommendedAsset; sendable: boolean }
```

SSE 收到 `rag` 事件后，不再挂到 `assistantMessage.ragSources`，而是插入独立消息：

```ts
chatHistory.value.push(...payload.messages.map(toReferenceMessage))
chatHistory.value.push(...payload.attachments.map(toAttachmentMessage))
```

展示顺序建议：

```text
用户问题
参考话术 1
参考话术 2
AI 正式回复
推荐素材 1
```

也可以把参考话术放在 AI 回复之后，但必须是独立消息。

### 7.3 复制与发送中心规则

复制规则：

1. assistant 正文复制 `assistant.content`。
2. rag_reference 复制 `reference.content`。
3. rag_attachment 复制素材链接或插入素材卡，不复制 AI 正文。

发送中心规则：

1. `assistant_answer` 进入发送中心时生成一条 markdown 消息。
2. `rag_reference` 进入发送中心时生成一条 markdown 消息，标题用 reference title。
3. `rag_attachment` 进入发送中心时生成 image/file 消息，带 material id 或 public url。
4. `sendable=false` 的 reference 只能复制为内部参考，不允许一键发送。

---

## 8. 推荐实施顺序

### 第一轮: 检索止血

改动目标：

1. 给 RAG visible sources 加 score gate。
2. 饮食/出差意图下过滤积分运营场景。
3. 不强行凑满 6 条参考语料。
4. 日志记录 resource title 和过滤原因。

验收：

1. `客户要出差，推荐一下餐食` 只展示出差外卖相关和饮食相关语料。
2. 不展示 `潜水提醒 / 社群 PK / 每日氛围`。

### 第二轮: 参考语料消息拆分

改动目标：

1. 后端 `rag` 事件返回 `messages/attachments`。
2. 前端新增 reference message 类型。
3. 复制和发送中心按 messageType 分流。
4. 历史会话能恢复参考语料，但 LLM 历史不使用参考语料。

验收：

1. AI 回复和参考语料视觉上分开。
2. 每条参考话术可单独复制。
3. 每条参考话术可单独进入发送中心。
4. 复制 AI 回复不会带上参考语料。

### 第三轮: 标签恢复与 rerank

改动目标：

1. CSV 标签进入 `metadata_json / rag_resource_tags / Qdrant payload`。
2. 开启意图识别和 payload filter。
3. 接入 rerank。
4. 建立评估集脚本。

验收：

1. Top1 命中率稳定可量化。
2. 污染率可统计。
3. 每次错召回可从 retrieval log 复盘。

---

## 9. 当前阶段判断

从“看见、理解、决策、闭环”的负责人视角看：

### 已经能做什么

1. 已经能把话术入 RAG 索引。
2. 已经能在 AI 对话中召回内部话术。
3. 已经能把召回结果注入 AI prompt。
4. 已经能把参考语料通过 SSE 返回前端。
5. 已经能记录基础 retrieval log。

### 半能做什么

1. 能召回目标语料，但不能稳定过滤低相关污染语料。
2. 能展示参考语料，但它还是挂在 assistant 消息内部。
3. 能送 AI 回复到发送中心，但不能把参考话术/素材作为独立消息送过去。
4. 能记录命中 point id 和 score，但审计信息不够业务可读。

### 还不能做什么

1. 不能基于 `dining_out / meal_review / nutrition` 等标签做强过滤。
2. 不能用 rerank 做精排。
3. 不能用评估集自动判断一次改动是否改善召回。
4. 不能把素材稳定推荐为附件。
5. 不能在历史会话里完整恢复参考语料附件。

### 当前 blocker

1. CSV 标注字段没有沉淀为可检索标签。
2. 检索结果缺少阈值和意图门禁。
3. 前端消息模型只有 user/assistant 两类，缺少 reference/attachment 消息类型。
4. RAG 审计日志记录的是 point id 和 score，不够支持业务复盘。

### 是否偏离蓝图

方向没有偏：RAG 作为 support knowledge 接入 CRM AI 教练是正确的。

当前偏差在于 P0 落地过于简化：只完成了“能召回”，还没完成“可控召回”和“可交付参考语料”。

---

## 10. 下一步最值得推进

优先级建议：

1. 先做检索止血：score gate + 饮食/积分域过滤 + 不凑满 topN。
2. 再做前端消息拆分：reference message / attachment message 独立展示、复制、发送。
3. 然后补标签真值：CSV 标注进入 RAG payload。
4. 最后接 rerank 和评估集，把效果从“感觉更准”变成“指标可验收”。

这四步里，第一步和第二步最直接影响当前测试体验和发送中心闭环，应优先做。

---

## 11. 本次调研验证记录

本次只新增调研报告，没有改运行代码。

已完成验证：

1. 阅读 `app/rag/retriever.py`、`vector_store.py`、`resource_indexer.py`、`embedding_client.py`。
2. 阅读 CRM AI 接入链路 `app/crm_profile/services/ai_coach.py`、`prompt_builder.py`。
3. 阅读前端 AI 消息链路 `useAiCoach.ts`、`AiCoachAssistantMessage.vue`、`AiCoachPanel.vue`。
4. 读取当前应用数据库，确认：
   - `speech_templates`: 41 条。
   - `rag_resources`: 65 条。
   - `rag_chunks`: 65 条。
   - `rag_retrieval_logs`: 4 条。
5. 反查最新测试日志，确认 `出差外食外卖场景点餐指导话术` 为 Top 1，同时第 3-5 名混入积分运营语料。

未执行：

1. 后端启动验证：未执行，因为本次没有修改后端运行代码。
2. 前端启动验证：未执行，因为本次没有修改前端运行代码。
3. RAG 在线重建：未执行，避免在调研阶段改动现有索引状态。

