# 上线前 RAG 向量库生产更新审阅报告

> 日期: 2026-04-28  
> 范围: 本地当前代码、RAG 向量库、话术/素材入库链路、Docker 生产部署、上线前验证  
> 结论口径: RAG 是 `support index / support knowledge`，不是素材、话术、客户档案的 `official/formal truth`。

## 1. 总控结论

这次代码可以继续推进到服务器，但不建议“直接 git pull 后立刻当作 RAG 正式全量能力启用”。当前系统主应用可以启动，RAG 技术链路也已基本接上；本轮已把原先几个上线 blocker 收口为“已补齐/仍需服务器配置确认”的状态：

1. `requirements.txt` 已补 `qdrant-client==1.17.1`，生产 Docker 镜像不再漏装 Qdrant 客户端。
2. `docker-compose.prod.yml` 已使用无需登录的 `/api/v1/health` 做 healthcheck，原 `/api/v1/bootstrap` 401 风险已解除。
3. `.dockerignore` 已排除 `data/qdrant/` 与 `data/qdrant_storage/`，避免把开发机向量库打进镜像上下文。
4. 素材 RAG 保存和 CSV 入库已收紧字段口径：`customer_sendable` 会归一为 `customer_visible`，但可发客户素材必须有 `materials.public_url`，且医疗敏感/需医生审核/禁忌内容不能标记为可发客户。

仍需服务器侧确认：生产 `.env` 必须使用 `QDRANT_MODE=remote` 并确认 `AI_API_KEY` 或 `RAG_EMBEDDING_API_KEY` 可用于 embedding。

当前阶段判断: RAG 处于 P0 技术闭环和小样本验证阶段，方向没有偏离蓝图；依赖、healthcheck 和素材入库门禁已补齐，但仍不是“全量素材/全量话术可放心生产召回”的阶段。

## 2. 项目负责人视角

### 已经能做什么

1. 系统已有 RAG 表: `rag_tags / rag_resources / rag_resource_tags / rag_chunks / rag_retrieval_logs`。
2. 话术、素材都已有索引入口，可以生成 semantic text、embedding，并写入 Qdrant。
3. CRM AI 教练回答流已经能调用 RAG，并通过 SSE 返回 `rag` 事件。
4. 前端 AI 对话已经能把 RAG 参考话术和推荐素材作为独立 reference 消息展示。
5. 素材库已有 RAG 标注弹窗和 `PATCH /api/v1/assets/{asset_id}/rag-meta` 保存入口。

### 半能做什么

1. 话术入 RAG 已可用，但依赖 CSV/metadata 标签质量。
2. 素材可入 RAG，当前 UI 保存路径已经有版权、公网地址、说明文本、安全等级硬门禁；但素材业务审核流仍是轻量门禁，还不是完整的主管审批流程。
3. RAG 检索已支持 `intervention_scene` 强过滤，但标签字典还没有完全 official 化。
4. Qdrant 可用性是降级设计，不会拖垮 AI 主回答，但如果生产依赖缺失，会表现为 RAG 不可用。

### 还不能做什么

1. 不能把全量素材自动丢进 RAG。
2. 不能把本地 `data/qdrant` 当作生产正式向量库直接搬过去。
3. 不能把 RAG 命中的内容当作客户档案事实。
4. 不能默认所有 `customer_sendable` 素材都能安全发客户。
5. 不能只靠 `docker compose up -d` 判断 RAG 已正式可用。

## 3. 服务器需要做的调整

### P0 必做

1. 在 `requirements.txt` 加入并锁定:

```txt
qdrant-client==1.17.1
```

`requirements.txt` 已声明 `qdrant-client 1.17.1`。生产 Dockerfile 只安装 `requirements.txt`，因此后续镜像构建会带上 Qdrant 客户端。

2. 生产 `.env` 建议使用独立 Qdrant 服务:

```env
RAG_ENABLED=true
QDRANT_MODE=remote
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
QDRANT_COLLECTION=wecom_health_rag
RAG_EMBEDDING_BASE_URL=https://aihubmix.com/v1
RAG_EMBEDDING_MODEL=text-embedding-3-large
RAG_EMBEDDING_DIMENSION=1024
```

`RAG_EMBEDDING_API_KEY` 可以留空复用 `AI_API_KEY`，但服务器 `.env` 必须确认 `AI_API_KEY` 可用于 embedding。

3. 生产 healthcheck 已修正。当前:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"]
```

`/api/v1/health` 无需鉴权，会执行轻量 DB `SELECT 1`，适合 Docker healthcheck / 监控使用。

4. 首次上线前先备份 MySQL 和 `data/`:

```text
MySQL: wecom_ops
文件: ./data/uploads
向量库: ./data/qdrant_storage
```

向量库不在 MySQL 备份里，后续必须单独备份。若丢失，可用 `/api/v1/rag/reindex?force=true` 重建，但会消耗 embedding 成本和时间。

### P1 建议

1. `.dockerignore` 已排除本地向量库目录；后续仍要避免把向量库文件提交或打包进镜像。
2. `docker-compose.prod.yml` 里的 `deploy.resources` 在普通 Docker Compose 场景不一定生效，Qdrant 资源限制不要只依赖这里。
3. 上线部署文档已补 RAG 配置段；服务器实际 `.env` 仍需人工确认密钥和 `QDRANT_MODE=remote`。

## 4. RAG 与生产环境是否“排斥”

不会天然排斥，但当前存在“本地模式”和“生产模式”混用风险。

本地开发适合:

```env
QDRANT_MODE=local
QDRANT_LOCAL_PATH=data/qdrant
```

生产建议:

```env
QDRANT_MODE=remote
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
```

原因:

1. 当前 Dockerfile 用 `--workers 2` 启动 uvicorn。嵌入式 local Qdrant 更适合单进程开发，不适合生产多 worker 共享同一路径。
2. `docker-compose.prod.yml` 已经声明了 `qdrant` service，如果 app 仍是 `QDRANT_MODE=local`，这个 service 会变成摆设。
3. 生产向量库数据应落在 `./data/qdrant_storage:/qdrant/storage`，而不是 app 容器内部的 `data/qdrant`。

上线后验证顺序:

```bash
docker compose -f docker-compose.prod.yml up -d qdrant
curl http://127.0.0.1:6333/collections
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d wecom-ops-console
docker logs --tail 100 wecom-ops-console
```

然后用管理员登录后访问 RAG 状态接口:

```text
GET /api/v1/rag/status
```

预期:

```json
{
  "rag_enabled": true,
  "qdrant_mode": "remote",
  "qdrant_available": true
}
```

## 5. 话术入 RAG 审阅

话术链路总体方向正确。

当前路径:

```text
CSV -> speech_templates.metadata_json -> resource_indexer.index_speech_templates()
-> rag_resources / rag_chunks -> Qdrant payload
```

已做对的地方:

1. `metadata_json` 已保留 `customer_goal / intervention_scene / question_type / safety_level / visibility / summary`。
2. `resource_indexer.py` 会把这些标签写入 Qdrant payload。
3. 检索时会按场景构造 payload filter，减少错召回。

上线前注意:

1. 话术 CSV 不要只写自然语言标签，尽量用受控 code，例如 `dining_out / meal_review / qa_support`。
2. 导入后必须跑一次 `source=speech&force=true` 的重建，让线上 Qdrant 生成向量。
3. RAG 召回的话术仍是 support reference，不是 AI 必须照抄的 official answer。

## 6. 素材入 RAG 审阅

素材链路需要更谨慎。当前“技术上能入库”，但“不建议全量自动入库”。

推荐生产入库方式:

```text
素材先上传到 materials
-> 七牛 public_url / storage_status=ready 成为 asset truth
-> 运营补 title/summary/alt_text/transcript/usage_note
-> 主管审核 approved
-> 才写 rag_resources / Qdrant
```

当前风险点:

1. `RagAnnotationDialog.vue` 保存后会调用 `save_rag_meta_and_index()`，后端已强制检查版权状态、图片 alt text / 视频说明、使用场景、受控标签、可发客户公网地址和安全等级。
2. `material_rag_import.py` 对 `customer_sendable=yes` 且没有公网地址的素材已改为硬失败，不再静默降级。
3. `visibility` 口径已统一：
   - 正式 code 只保留 `coach_internal / customer_visible`
   - CSV 里的 `customer_sendable` 仅作为兼容别名映射到 `customer_visible`
   - `retriever.py` 只有 `visibility == "customer_visible"` 才返回 `customer_sendable=true`

上线前建议统一为:

```text
coach_internal
customer_visible
```

CSV 如果继续用 `customer_sendable`，需要导入时映射成 `customer_visible`。

P0 素材入库最低门槛:

1. `status=approved`
2. `rag_enabled=yes`
3. `storage_status=ready`
4. 图片必须有 `alt_text`
5. 视频至少有 `summary + usage_note`，最好有 `transcript`
6. `copyright_status` 不能是 unknown
7. 可发客户必须有 `materials.public_url`
8. RAG payload 必须包含 `resource_id/source_type/source_id/content_kind/status/visibility/safety_level/customer_goal/intervention_scene/question_type/semantic_quality`

## 7. 上线前操作清单

1. 先改依赖和生产 env:
   - `requirements.txt` 已加 `qdrant-client==1.17.1`
   - 服务器 `.env` 加 RAG/Qdrant 配置
   - 生产使用 `QDRANT_MODE=remote`

2. 健康检查:
   - 当前生产 healthcheck 已使用 `/api/v1/health`
   - 不再用需要登录的 `/api/v1/bootstrap`

3. 首次部署:
   - 备份 MySQL 和 `data/`
   - `docker compose -f docker-compose.prod.yml up -d qdrant`
   - 确认 `6333` 只对本机开放，不对公网暴露
   - 构建并启动 app 容器

4. 首次重建索引:
   - 先小样本话术
   - 再小样本素材
   - 使用 force 重建，避免本地 hash 已存在但线上 Qdrant 没点位

5. 验收:
   - RAG status 可用
   - 随机 5 条话术问题能召回正确来源
   - 随机 5 条素材问题能召回正确素材
   - `coach_internal` 不允许一键发送客户
   - `doctor_review/medical_sensitive/contraindicated` 不允许直接变成客户话术

## 8. 验证结果

本地 focused validation:

1. 后端语法检查: `python -m compileall -q app` 通过。
2. 本地依赖检查: `.venv` 有 `qdrant-client 1.17.1`，`requirements.txt` 已声明 `qdrant-client==1.17.1`。
3. RAG 入库门禁轻量验证: `RagMetaUpdate` 能把 `customer_sendable -> customer_visible`、`medical_review -> doctor_review`、中文目标/场景标签归一为受控 code；素材 CSV 行校验能识别图片缺少 `alt_text`。
4. 后端启动检查: `uvicorn app.main:app --host 127.0.0.1 --port 8018` 启动成功，禁用本机代理后 `/api/v1/health` 返回 `200`。
5. `/api/v1/bootstrap` 未登录返回 `401` 是鉴权预期；生产 healthcheck 已改用 `/api/v1/health`，不再受影响。
6. 前端 TypeScript 检查: `cd frontend; .\node_modules\.bin\vue-tsc.cmd --noEmit` 通过。
7. 前端生产构建: `cd frontend; npm.cmd run build` 通过。
8. 前端 dev 短启动: 沙箱内仍出现既有 `Error: spawn EPERM`；提权后 `npm.cmd run dev -- --host 127.0.0.1 --port 5181` 已确认 Vite ready，并已回收监听进程。
9. 前端构建有大 chunk 警告，属于性能优化项，不阻断本次上线。

## 9. 代码组织风险

上线不一定被这些问题阻断，但它们会增加后续维护成本:

1. `app/routers/api.py` 约 1348 行，超过项目 Python 文件 800 行红线，并且仍在承载资产等多资源接口。
2. 多个 Vue/TS 文件超过 600 行，例如 `frontend/src/views/Assets/index.vue`、`frontend/src/views/Templates/index.vue`、`frontend/src/views/SendCenter/composables/useSendLogic.ts`。
3. RAG 后续如果继续加接口，不应再往 `api.py` 堆，应拆到资源路由。

## 10. 最值得继续推进的线

1. 生产 RAG 环境线: 依赖、Qdrant remote、healthcheck、备份、重建索引。
2. 入库治理线: 统一标签字典和 visibility 口径，先跑 P0 小样本，不做全量。
3. 素材审核线: UI 保存前加必填校验、版权校验、公网地址校验和审核状态。
4. 验收评估线: 建 20-50 条固定评估问题，记录 Top3 命中和错召回。
5. 代码拆分线: 后续迭代再拆 `api.py` 和超大前端文件，避免 RAG 继续叠加到大文件里。

## 11. 最终建议

这次上线建议按“主系统更新 + RAG 小样本启用”的节奏走，不要按“RAG 全量正式上线”走。

最稳路径:

```text
先修依赖和生产 env
-> 独立 Qdrant remote 模式启动
-> 后端和前端构建启动验证
-> 小样本 force reindex
-> 管理员验证 /api/v1/rag/status
-> 评估问题验收
-> 再逐步扩大语料
```

只要按这个顺序走，RAG 不会和生产环境产生根本排斥；真正的风险不在向量库本身，而在依赖漏装、local/remote 模式混用、健康检查误判、以及未审核素材过早进入 active 索引。
