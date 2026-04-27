# RAG 集成到 wecom 项目手册

> 文档日期: 2026-04-26  
> 适用项目: `wecom_ops_console`  
> 目标场景: 健康教练 AI 助手接入公司内部“分场景话术库 + 知识库 + 图片/视频素材库”，提升 AI 回复准确性、可用性与可交付性。

---

## 1. 业务目标

公司内部健康教练每天需要围绕客户的减重、控糖、晒餐、餐评、习惯教育、阻力拆解、情绪陪伴等场景做陪伴式干预。现有 AI 教练已经能够读取客户档案，但还缺少公司沉淀的话术经验、知识卡片和可转发素材。

本次 RAG 的核心目标不是“新建一个独立聊天机器人”，而是把公司知识沉淀接入当前 AI 教练助手，让 AI 在回答时能够：

1. 按客户诉求、当前阶段、沟通场景检索内部话术。
2. 按问题语义检索知识库内容，减少泛化和编造。
3. 推荐图片、视频、图文卡片给前端，供教练复制、下载、转发或带到发送中心。
4. 保留来源、标签、审计记录，让每次 AI 参考了什么可回溯。

---

## 2. 当前系统适配结论

当前系统已经具备几个可以复用的 official 模块，不应重复造一套孤立的 RAG 产品。

| 当前模块 | 现状 | RAG 中的定位 |
| --- | --- | --- |
| `speech_templates` 话术模板 | 已有 `scene_key/style/content`，偏积分运营话术 | 可升级为“话术管理”的基础，但需要和模板中心区分 |
| 模板中心 `templates` | 用于企业微信发送内容模板、变量、消息类型 | 不作为话术库 truth，只负责发送格式 |
| 素材库 `materials / asset_folders` | 已支持本地/七牛存储、下载、预览，模型里已有 `tags` 字段 | 作为图片/视频/文件资产 truth，但需要补强标签、摘要、适用场景 |
| CRM AI 教练 | 已有客户档案上下文、SSE、历史会话、审计 | RAG 应接入此链路，而不是另起 `/rag/chat` 长期入口 |
| `ai_chat_client.py` | 当前通过 httpx 调 OpenAI 兼容 chat/completions | Embedding/Rerank 也建议复用 httpx 与 aihubmix base_url/key |
| `docker-compose.prod.yml` | 服务名为 `wecom-ops-console`，host 网络部署 | Qdrant 可作为新增 service，但文档必须匹配当前服务名 |

结论：

1. 固定干预话术应进入“话术管理”，不是模板中心。
2. 图片/视频/图文知识点应复用“素材库”，但素材库必须从“文件仓库”升级为“可检索知识资产库”。
3. RAG 后端应先做检索服务，再嵌入现有 CRM AI 教练回答流。
4. RAG 召回内容是 support knowledge，不等于客户档案 formal truth。
5. AI 会话中真正落库的上下文快照和来源快照，才是该轮回答的 formal 审计事实。

---

## 3. 产品边界

### 3.1 话术管理和模板中心的区别

话术管理负责“说什么”和“为什么这样说”。

示例：

1. 用户晚上总想吃零食时如何破阻力。
2. 用户血糖波动后如何安抚和建议复盘。
3. 用户晒餐后，教练如何做餐评和强化习惯。
4. 用户长期不打卡时如何温和唤回。

模板中心负责“怎么发出去”。

示例：

1. 企业微信 markdown 模板。
2. 图片、文件、语音、图文消息格式。
3. 发送中心变量替换。
4. 定时任务、审批、群发日志。

因此，RAG 应读取话术管理作为知识源；当教练要把内容发出去时，再进入模板中心或发送中心。

### 3.2 素材库升级方向

当前素材库已有文件、类型、文件夹和基础 `tags` 字段，但还不足以支撑 RAG。图片/视频要被 AI 正确推荐，必须有可检索的文字语义。

素材库需要补齐：

1. 业务标题: 给教练看的清晰标题，不只用文件名。
2. 内容摘要: 50-200 字，说明素材讲什么。
3. 适用场景: 晒餐、餐评、控糖科普、减重动机、习惯教育等。
4. 适用人群: 减重、控糖、平台期、外食多、情绪性进食等。
5. 禁忌/谨慎: 不适合孕期、肾病、未成年人、严重低血糖等。
6. 可发状态: 内部参考、可发客户、需主管审核、废弃。
7. 视频转写: 视频需要转写文本，才能进入向量检索。
8. 图片说明: 图片需要人工或 AI 生成 alt text/讲解文本。

---

## 4. 标签体系设计

RAG 效果的关键不是只把内容丢进向量库，而是先把语料治理好。标签必须是受控词表，不能只依赖自由输入。

### 4.1 核心标签维度

| 维度 | 字段建议 | 示例 |
| --- | --- | --- |
| 客户目标 | `customer_goal` | `weight_loss`, `glucose_control`, `habit_building` |
| 干预场景 | `intervention_scene` | `meal_checkin`, `meal_review`, `obstacle_breaking`, `habit_education`, `emotional_support`, `qa_support` |
| 客户阶段 | `customer_stage` | `onboarding`, `first_week`, `adaptation`, `plateau`, `relapse_recovery`, `maintenance` |
| 问题类型 | `question_type` | `craving`, `dining_out`, `late_night_snack`, `high_glucose`, `low_motivation` |
| 内容类型 | `content_kind` | `script`, `knowledge_card`, `image`, `video`, `mixed` |
| 话术语气 | `tone` | `professional`, `encouraging`, `gentle`, `firm`, `competitive` |
| 可见范围 | `visibility` | `coach_internal`, `customer_sendable` |
| 安全级别 | `safety_level` | `general`, `nutrition_education`, `medical_sensitive`, `doctor_review` |
| 交付渠道 | `delivery_channel` | `private_chat`, `group_chat`, `send_center`, `offline_followup` |
| 内容状态 | `status` | `draft`, `active`, `archived`, `disabled` |

### 4.2 标签治理规则

1. 系统内维护 `rag_tags` 作为标签字典，业务人员只能从字典选择。
2. 允许 AI 自动给新内容生成候选标签，但必须人工确认后才进入 active。
3. 每条语料至少需要 `customer_goal / intervention_scene / content_kind / visibility / safety_level`。
4. 医疗敏感内容必须带 `medical_sensitive` 或 `doctor_review`，AI 只能作为内部提醒，不应直接生成诊断式话术。
5. 标签变更应记录 `updated_by / updated_at`，避免知识库漂移后无法追责。

---

## 5. 数据模型方案

不要直接把 `rag_script` 和 `rag_knowledge_card` 做成新的内容孤岛。推荐建立一层 RAG 资源索引，把现有话术、素材、外部文档、未来知识卡片统一纳入检索。

### 5.1 新增表建议

#### `rag_tags`

标签字典。

```sql
CREATE TABLE IF NOT EXISTS rag_tags (
    id INTEGER PRIMARY KEY,
    dimension VARCHAR(64) NOT NULL,
    code VARCHAR(96) NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE (dimension, code)
);
```

#### `rag_resources`

统一资源索引，不替代原始内容表。

```sql
CREATE TABLE IF NOT EXISTS rag_resources (
    id INTEGER PRIMARY KEY,
    source_type VARCHAR(32) NOT NULL,
    source_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    semantic_text TEXT,
    content_kind VARCHAR(32) DEFAULT 'text',
    visibility VARCHAR(32) DEFAULT 'coach_internal',
    safety_level VARCHAR(32) DEFAULT 'general',
    status VARCHAR(32) DEFAULT 'draft',
    reviewed_by INTEGER NULL,
    reviewed_at DATETIME NULL,
    source_hash VARCHAR(64) DEFAULT '',
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE (source_type, source_id)
);
```

`source_type` 建议值：

1. `speech_template`: 来自话术管理。
2. `material`: 来自素材库。
3. `external_doc`: 来自外部文档资源。
4. `manual_card`: 未来新增的结构化知识卡片。

#### `rag_resource_tags`

资源与标签多对多。

```sql
CREATE TABLE IF NOT EXISTS rag_resource_tags (
    resource_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (resource_id, tag_id)
);
```

#### `rag_chunks`

向量切片索引。

```sql
CREATE TABLE IF NOT EXISTS rag_chunks (
    id INTEGER PRIMARY KEY,
    resource_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_hash VARCHAR(64) NOT NULL,
    vector_point_id VARCHAR(64) NOT NULL,
    embedding_model VARCHAR(128) NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    status VARCHAR(32) DEFAULT 'active',
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE (resource_id, chunk_index, embedding_model)
);
```

#### `rag_retrieval_logs`

记录每次 AI 召回证据。

```sql
CREATE TABLE IF NOT EXISTS rag_retrieval_logs (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(64),
    message_id VARCHAR(64),
    customer_id INTEGER NULL,
    query_text TEXT,
    filter_json TEXT,
    hit_json TEXT,
    latency_ms INTEGER DEFAULT 0,
    created_at DATETIME
);
```

### 5.2 素材库补强字段

优先不大改 `materials` 表，新增 `rag_resources` 作为知识索引层即可。如果素材库 UI 需要更好的编辑体验，可以追加或映射以下字段：

1. `display_title`: 业务标题。
2. `summary`: 内容摘要。
3. `transcript`: 视频转写/图片说明。
4. `usage_note`: 教练使用说明。
5. `customer_sendable`: 是否可直接发客户。
6. `review_status`: 审核状态。

这些字段可以先落在 `rag_resources.semantic_text/summary` 中，等素材库产品形态稳定后再反向沉淀到素材专属表。

---

## 6. 向量数据库与模型选型

### 6.1 向量数据库

推荐第一版使用 Qdrant。

理由：

1. 单机 Docker 部署简单，适合当前 `docker-compose.prod.yml`。
2. 支持 payload filter，可按 `customer_goal / intervention_scene / safety_level / status` 做预过滤。
3. 后续迁移到独立服务器或云服务成本低。

生产 compose 需要匹配当前服务名：

```yaml
services:
  wecom-ops-console:
    # 现有配置保持不变

  qdrant:
    image: qdrant/qdrant:latest
    container_name: wecom-qdrant
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./data/qdrant_storage:/qdrant/storage
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "1.0"
```

### 6.2 Embedding 模型推荐

Embedding 直接走 aihubmix，不再引入额外供应商 SDK。aihubmix 文档显示其 embedding 接口兼容 OpenAI `/v1/embeddings`，可用模型包含 `text-embedding-3-large`、`text-embedding-3-small`、`gemini-embedding-001`、`jina-embeddings-v4`、`Qwen/Qwen3-Embedding-0.6B` 等。

推荐配置：

```env
RAG_EMBEDDING_PROVIDER=aihubmix
RAG_EMBEDDING_BASE_URL=https://aihubmix.com/v1
RAG_EMBEDDING_MODEL=text-embedding-3-large
RAG_EMBEDDING_DIMENSION=1024
```

推荐理由：

1. `text-embedding-3-large` 稳定、通用、多语言表现好，适合第一版正式落地。
2. 1024 维能在质量、存储、检索速度之间取得较好平衡。
3. 当前项目已有 `AI_API_KEY / AI_BASE_URL` 口径，可复用同一套 aihubmix key 和 httpx 调用方式。

候选评测：

| 模型 | 用途 | 建议 |
| --- | --- | --- |
| `text-embedding-3-large` | 默认生产模型 | P0 默认 |
| `text-embedding-3-small` | 低成本/大批量冷启动 | 作为降级模型 |
| `jina-embeddings-v4` | 中文语义与多模态描述候选 | P1 用评估集 A/B |
| `Qwen/Qwen3-Embedding-0.6B` | 中文知识库候选 | P1 用评估集 A/B |
| `gemini-embedding-001` | 长文本候选 | 暂不作为第一版默认 |

### 6.3 Rerank 模型推荐

aihubmix 也提供 `/v1/rerank`，可用模型包含 `jina-reranker-v3`、`qwen3-reranker-0.6b/4b/8b`、`gte-rerank-v2` 等。

推荐配置：

```env
RAG_RERANK_ENABLED=true
RAG_RERANK_MODEL=jina-reranker-v3
RAG_RERANK_TOP_N=6
```

第一版策略：

1. P0 可以先上线向量召回 + 标签过滤，不强依赖 rerank。
2. P1 开启 rerank，用 `jina-reranker-v3` 做默认精排。
3. 中文健康场景再评测 `qwen3-reranker-4b`，如果命中率更高再切换。

---

## 7. 检索工程设计

### 7.1 检索输入

每次 AI 提问时，RAG 查询不应只使用用户原始问题，而要组合客户上下文。

推荐构造：

```text
客户目标: 减重 / 控糖
客户阶段: 第几周 / 平台期 / 复盘期
干预场景: 晒餐 / 餐评 / 破阻力 / 情绪陪伴
用户问题: 最近总想吃零食怎么办
输出模式: 教练简报 / 客户话术 / 详细报告
安全约束: 过敏、疾病、孕期、低血糖等
```

### 7.2 检索流程

```text
用户问题 + 客户档案摘要
        ↓
场景识别与标签过滤
        ↓
向量召回 top_k=30
        ↓
关键词/BM25 补召回 top_k=10
        ↓
Rerank 精排 top_n=6
        ↓
按类型分桶: 话术 / 知识 / 素材
        ↓
注入 AI prompt + 前端推荐卡片
```

### 7.3 分桶策略

每轮建议最多提供：

1. 话术片段: 2-4 条。
2. 知识片段: 2-3 条。
3. 推荐素材: 0-3 个。

素材推荐不能只靠相似度，还必须满足：

1. `status = active`
2. `visibility = customer_sendable`
3. `safety_level` 不高于当前场景允许级别
4. 文件 `storage_status = ready`
5. 有可用 `public_url / preview_url / download_url`

### 7.4 召回失败策略

如果没有高质量召回：

1. AI 可以继续基于客户档案回答，但必须标记 `rag_status=no_hit`。
2. 不展示素材推荐。
3. 记录查询日志，用于后续补充话术或知识卡片。

---

## 8. AI 教练接入方案

### 8.1 不新增长期独立 RAG 对话入口

旧方案中的 `/api/v1/rag/chat` 可以作为调试接口，但不应成为正式用户入口。正式入口应继续走：

1. `POST /api/v1/crm-customers/{customer_id}/ai/chat-stream`
2. `POST /api/v1/crm-customers/{customer_id}/ai/thinking-stream`

新增 RAG 服务模块：

```text
app/rag/
├── __init__.py
├── embedding_client.py     # aihubmix embeddings
├── rerank_client.py        # aihubmix rerank
├── vector_store.py         # Qdrant 访问
├── resource_indexer.py     # 话术/素材/文档入库
├── retriever.py            # 检索编排
├── schemas.py              # Pydantic schema
└── audit.py                # 召回日志
```

AI 教练中只调用：

```python
rag_bundle = retrieve_rag_context(
    customer_id=customer_id,
    message=message,
    scene_key=scene_key,
    output_style=output_style,
    profile_context=prepared.ctx,
)
```

### 8.2 Prompt 注入规则

RAG 内容应作为单独区域进入 prompt：

```text
【公司话术与知识库参考】
- 以下内容来自内部话术库/知识库，是辅助参考，不等于客户档案事实。
- 回答时优先结合客户档案和安全档案。
- 可借鉴话术风格，但不要机械照抄。
- 医疗敏感内容只做风险提醒，不做诊断。

【召回片段】
...
```

### 8.3 SSE 事件扩展

当前前端已经支持 `meta / loading / delta / done / error`。建议新增可选事件：

```text
event: rag
data: {
  "sources": [...],
  "recommended_assets": [...]
}
```

推荐时机：

1. `meta` 后、`model_call` 前先返回 `rag`，前端可以先展示“已参考资料”。
2. `done` 时再返回最终推荐素材列表，避免模型回答与推荐不一致。

第一版不依赖 function calling。素材推荐由后端根据召回结果和安全规则确定，AI 只负责生成解释文案。

---

## 9. 前端产品方案

### 9.1 AI 教练抽屉

在当前 AI 教练抽屉增加“推荐资料”区域。

每个推荐卡片展示：

1. 标题
2. 类型: 话术 / 图片 / 视频 / 图文 / 文件
3. 推荐原因
4. 标签
5. 来源
6. 操作: 复制话术、预览、下载、发送到发送中心

### 9.2 已加载信息侧栏

当前侧栏已有“已加载参考信息”。建议增加 RAG 区块：

1. 本轮召回了哪些话术。
2. 本轮召回了哪些知识点。
3. 本轮推荐了哪些素材。
4. 为什么没有推荐素材。

### 9.3 素材库管理页

素材库需要新增“知识属性”编辑面板：

1. 业务标题
2. 内容摘要
3. 使用说明
4. 标签选择
5. 是否可发客户
6. 安全级别
7. 视频转写文本
8. 图片说明文本
9. 是否进入 RAG
10. 同步状态

---

## 10. 同步与索引流程

### 10.1 内容入库

触发源：

1. 话术新增/修改/启用。
2. 素材新增/修改知识属性/启用。
3. 外部文档资源绑定为知识库资料。

入库流程：

```text
读取 source
  ↓
生成或读取 semantic_text
  ↓
计算 source_hash
  ↓
按语义块 chunk
  ↓
调用 aihubmix embedding
  ↓
写入 Qdrant
  ↓
写 rag_chunks / rag_resources 状态
```

### 10.2 增量同步

第一版推荐两种方式并存：

1. 内容保存后立即标记 `rag_sync_status=pending`。
2. 后台 job 每 1-5 分钟扫描 pending 或 updated_at 变更内容。

不要在用户保存素材时同步阻塞 embedding。保存应快速返回，索引异步完成。

### 10.3 删除与下线

内容下线时不建议物理删除向量，先更新 payload：

```json
{
  "status": "archived"
}
```

检索时过滤 `status=active`。需要重建索引时再批量清理。

---

## 11. 配置建议

### 11.1 `.env`

```env
RAG_ENABLED=true
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
QDRANT_COLLECTION=wecom_health_rag

RAG_EMBEDDING_PROVIDER=aihubmix
RAG_EMBEDDING_BASE_URL=https://aihubmix.com/v1
RAG_EMBEDDING_API_KEY=${AI_API_KEY}
RAG_EMBEDDING_MODEL=text-embedding-3-large
RAG_EMBEDDING_DIMENSION=1024

RAG_RERANK_ENABLED=true
RAG_RERANK_MODEL=jina-reranker-v3
RAG_TOP_K=30
RAG_RERANK_TOP_N=6
RAG_CHUNK_SIZE=600
RAG_CHUNK_OVERLAP=80
```

### 11.2 `app/config.py`

```python
rag_enabled: bool = False
qdrant_host: str = "127.0.0.1"
qdrant_port: int = 6333
qdrant_collection: str = "wecom_health_rag"
rag_embedding_provider: str = "aihubmix"
rag_embedding_base_url: str = "https://aihubmix.com/v1"
rag_embedding_api_key: str = ""
rag_embedding_model: str = "text-embedding-3-large"
rag_embedding_dimension: int = 1024
rag_rerank_enabled: bool = True
rag_rerank_model: str = "jina-reranker-v3"
rag_top_k: int = 30
rag_rerank_top_n: int = 6
rag_chunk_size: int = 600
rag_chunk_overlap: int = 80
```

实现时如果 `rag_embedding_api_key` 为空，可 fallback 到 `settings.ai_api_key`。

---

## 12. 分阶段实施计划

### Phase 0: 语料治理和产品边界

1. 明确“话术管理”和“模板中心”的页面边界。
2. 定义标签字典。
3. 给现有素材库增加知识属性草稿设计。
4. 选 100 条真实话术、50 个真实素材做试点。

### Phase 1: RAG 索引底座

1. 新增 `rag_tags / rag_resources / rag_resource_tags / rag_chunks / rag_retrieval_logs`。
2. 新增 Qdrant service。
3. 新增 aihubmix embedding client。
4. 支持 speech_template 和 material 两类 source 入库。
5. 提供后台同步任务和健康检查。

### Phase 2: AI 教练接入

1. 在 AI answer stream 的 prepare 阶段检索 RAG。
2. 将 RAG 片段注入 prompt。
3. SSE 返回 `rag` 事件。
4. 审计记录本轮召回来源。
5. 前端 AI 抽屉展示推荐资料。

### Phase 3: 素材库升级

1. 素材库增加标签、摘要、适用场景、可发状态。
2. 图片支持 alt text。
3. 视频支持转写文本。
4. 素材支持“一键进入 RAG / 暂停 RAG”。

### Phase 4: 效果评估与优化

1. 建立 50-100 条健康管理评估集。
2. 对比不同 embedding/rerank 模型命中率。
3. 统计无召回、错召回、不可用推荐。
4. 调整标签、chunk、rerank、素材推荐规则。

---

## 13. 验收标准

### 13.1 功能验收

1. 话术和素材可以进入 RAG 索引。
2. 客户 AI 对话能返回 RAG 来源。
3. AI 回复能明显参考公司话术和知识库。
4. 前端能展示推荐素材卡片。
5. 推荐素材可以复制、预览、下载或进入发送中心。

### 13.2 质量验收

1. 评估集 Top 5 召回命中率达到 80% 以上。
2. 人工评估 AI 回复“贴合公司话术风格”明显提升。
3. 素材误推荐率低于 5%。
4. 医疗敏感内容不会直接输出诊断式建议。

### 13.3 工程验收

1. RAG 不阻塞 AI 主回答链路；RAG 异常时 AI 可降级为仅客户档案回答。
2. Qdrant 不可用时返回 `rag_status=unavailable`，不影响客户档案 AI。
3. 每轮召回来源可审计。
4. embedding 模型、维度、chunk 策略可配置。
5. 后续可替换 embedding/rerank 模型而不改业务表结构。

---

## 14. 风险与应对

1. 风险: 语料没标签或标签混乱，向量库召回质量差。
   - 应对: 先建受控标签字典，AI 只生成候选标签，人工确认后入库。
2. 风险: 图片/视频没有文本描述，无法被准确检索。
   - 应对: 强制补摘要、alt text、转写文本，URL 不参与向量化。
3. 风险: AI 把内部话术原样发给客户。
   - 应对: 用 `visibility` 区分内部参考和可发客户，prompt 和前端都做隔离。
4. 风险: 医疗敏感内容被误用。
   - 应对: `safety_level` 预过滤，高风险内容只做内部提醒或要求医生确认。
5. 风险: RAG 成为另一套内容真值。
   - 应对: `rag_resources` 只做索引层，原始内容仍以话术管理、素材库、外部文档为 official source。

---

## 15. 推荐结论

本项目的 RAG 最佳路径是：

1. 先把“话术管理”和“素材库知识属性”建设好。
2. 用 `rag_resources` 作为统一索引层，不复制一套内容系统。
3. 用 aihubmix `text-embedding-3-large` 作为第一版默认 embedding。
4. 用 Qdrant 做向量库，payload filter 负责业务标签过滤。
5. RAG 作为 support knowledge 接入现有 CRM AI 教练，而不是新建长期独立对话入口。
6. 前端重点展示“推荐资料卡片”，让教练能复制、下载、转发，真正进入干预闭环。

---

## 16. 开发交接说明与硬性叮嘱

本章节用于交接给开发人员。开发时请按 P0 最小闭环推进，不要一次性把本文所有能力都做完。

### 16.1 当前是否可以开工

可以开工，但开工范围限定为 P0 最小闭环。

P0 的目标是证明“现有话术和素材可以被索引、检索、回传给 AI 教练前端”，不是一次性完成完整知识库平台。

P0 不要求：

1. 完成完整话术管理后台重构。
2. 完成视频自动转写。
3. 完成图片自动识别。
4. 完成多模型 A/B 评测。
5. 完成自动医学审核。
6. 完成独立 RAG 聊天机器人。

### 16.2 P0 开发任务拆分

#### P0-1: RAG 基础表与模型

负责人应新增：

1. `app/models_rag.py`
2. `rag_tags`
3. `rag_resources`
4. `rag_resource_tags`
5. `rag_chunks`
6. `rag_retrieval_logs`

接入方式：

1. 在 `app/models.py` 中汇入 `models_rag`。
2. 在 `schema_migrations.py` 中新增 `ensure_rag_schema(engine)`。
3. 在 `app/main.py` lifespan 中调用。

验收：

1. 后端启动后表能自动创建。
2. 反复启动不会重复建索引报错。
3. SQLite 开发环境和 MySQL 生产环境都能兼容。

#### P0-2: aihubmix embedding client

负责人应新增：

1. `app/rag/embedding_client.py`
2. `app/rag/schemas.py`

硬性要求：

1. 复用 OpenAI 兼容 `/v1/embeddings`。
2. 默认模型 `text-embedding-3-large`。
3. 默认维度 1024。
4. API key 优先读 `RAG_EMBEDDING_API_KEY`，为空时 fallback 到 `AI_API_KEY`。
5. 不引入额外供应商 SDK。

验收：

1. 单条文本可生成向量。
2. 批量文本可分批生成向量。
3. 接口异常时返回明确错误，不吞异常。

#### P0-3: Qdrant vector store

负责人应新增：

1. `app/rag/vector_store.py`
2. Qdrant collection 初始化逻辑

硬性要求：

1. point id 使用稳定 UUID，不使用 `script_1_0` 这类字符串拼接 ID。
2. payload 必须包含 `resource_id/source_type/source_id/status/tags/safety_level/visibility/content_kind`。
3. 检索时默认过滤 `status=active`。

验收：

1. collection 不存在时可初始化。
2. upsert 同一 chunk 不重复生成垃圾 point。
3. Qdrant 不可用时不影响主应用启动。

#### P0-4: 资源入库

负责人应新增：

1. `app/rag/resource_indexer.py`
2. `scripts/rag_rebuild_index.py`

P0 只接两类 source：

1. `speech_template`: 来自 `speech_templates`
2. `material`: 来自 `materials`

硬性要求：

1. RAG 只做索引层，不复制话术或素材原文作为新的 official truth。
2. 素材没有摘要时，可以临时用 `name + tags + material_type` 构造 semantic_text，但必须标记 `semantic_quality=weak`。
3. 图片/视频 URL 不参与向量化，只进入 payload。

验收：

1. 能将现有话术模板入库。
2. 能将现有素材以弱语义方式入库。
3. 修改内容后 source_hash 变化，重新生成 chunk。

#### P0-5: RAG 检索服务

负责人应新增：

1. `app/rag/retriever.py`
2. `app/rag/audit.py`

硬性要求：

1. 检索输入必须包含用户问题、客户目标、当前场景。
2. 先做标签/payload 过滤，再向量召回。
3. 第一版可以不开 rerank，但接口必须预留 rerank 位置。
4. 检索失败返回空 bundle，不抛到 AI 主链路。

验收：

1. 给定问题能返回 `sources` 和 `recommended_assets`。
2. 素材推荐必须只返回 `storage_status=ready` 的内容。
3. 每次召回写入 `rag_retrieval_logs`。

#### P0-6: 接入 CRM AI 教练

负责人修改：

1. `app/crm_profile/services/ai_coach.py`
2. 必要时拆出 `app/crm_profile/services/ai_turn_prepare.py`
3. `frontend/src/views/CrmProfile/composables/useAiCoach.ts`
4. `frontend/src/views/CrmProfile/components/AiCoachPanel.vue`

硬性要求：

1. 不新增长期独立 `/api/v1/rag/chat` 作为正式入口。
2. 继续使用现有 `/ai/chat-stream`。
3. 新增可选 SSE 事件 `rag`。
4. RAG 异常时主回答继续，只标记 `rag_status=unavailable`。
5. RAG 召回内容必须写入审计或日志，便于复盘。

验收：

1. AI 抽屉可以展示本轮推荐资料。
2. 推荐话术可以复制。
3. 推荐素材可以预览或下载。
4. 不影响原有 AI 对话、历史会话、客户档案上下文。

### 16.3 开发边界

必须做：

1. 复用现有 `speech_templates` 作为第一批话术来源。
2. 复用现有 `materials` 作为第一批素材来源。
3. RAG 表只做索引和审计，不替代内容管理。
4. RAG 结果作为 support knowledge 注入 AI。
5. 所有 RAG 召回来源可追踪。

禁止做：

1. 禁止把模板中心改成话术库。
2. 禁止新建一套与素材库并行的图片/视频文件管理系统。
3. 禁止让 AI 直接决定推送任意素材 ID，必须经过后端白名单校验。
4. 禁止 RAG 失败导致 AI 教练主回答失败。
5. 禁止把未审核、禁用、废弃素材推荐给教练。
6. 禁止把内部参考话术直接标记为可发客户。

### 16.4 开发人员需要先读的文件

后端：

1. `app/models.py`
2. `app/schema_migrations.py`
3. `app/clients/ai_chat_client.py`
4. `app/crm_profile/router.py`
5. `app/crm_profile/services/ai_coach.py`
6. `app/routers/api_speech_templates.py`
7. `app/routers/api.py` 中 assets 相关接口
8. `app/services/storage/`

前端：

1. `frontend/src/views/CrmProfile/components/AiCoachPanel.vue`
2. `frontend/src/views/CrmProfile/composables/useAiCoach.ts`
3. `frontend/src/views/Assets/index.vue`
4. `frontend/src/views/Assets/composables/useAssets.ts`
5. `frontend/src/views/Assets/components/AssetGrid.vue`

### 16.5 提交验收门槛

每个开发分支至少提供：

1. 改动文件清单。
2. 数据表或迁移说明。
3. focused validation。
4. 后端启动验证。
5. 前端改动涉及 UI 时，必须跑前端类型检查和构建。
6. 一个最小演示用例：输入一个客户问题，返回至少一条话术或素材推荐。

不能把“表建好了”写成 RAG 完成；不能把“向量能写入”写成 AI 教练已接入；不能把“推荐卡片能显示”写成素材库治理完成。

---

## 17. 参考资料

1. AiHubMix 向量嵌入文档: https://docs.aihubmix.com/cn/api/EBD
2. AiHubMix 重排序文档: https://docs.aihubmix.com/cn/api/Rerank
3. 当前素材模型: `app/models.py` 中 `Material / AssetFolder / MaterialStorageRecord`
4. 当前话术模型: `app/models.py` 中 `SpeechTemplate`
5. 当前 AI 教练链路: `app/crm_profile/router.py`、`app/crm_profile/services/ai_coach.py`
