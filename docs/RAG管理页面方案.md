# RAG 知识库管理页面设计与现状审查

> 更新时间：2026-05-08  
> 结论口径：RAG 管理页管理的是 `support index / support knowledge`，不是话术库、素材库、客户档案的 official truth。

## 1. 当前阶段判断

原始蓝图方向没有跑偏。当前系统已经从“完全没有 RAG 管理页”推进到 **第一版管理闭环已落地**：

- 前端已有 `/rag-manage` 知识库管理页。
- 后端已有 RAG 状态、重建、标签、资源列表/详情/删除、检索日志接口。
- `vector_store.py` 已补充 Qdrant 集合信息、删除点、scroll 调试函数。
- 侧边栏、路由、面包屑均已接入，且前端菜单仅 admin 可见。

但当前实现还不是“生产治理完成态”。它更接近 **可用的 RAG 管理 MVP**，剩余重点是：权限收紧、统计兼容性、单条/批量治理动作、检索日志可读性和删除一致性。

---

## 2. 原计划与当前实现对照

### 2.1 前端页面

| 原计划 | 当前实现 | 判断 |
|--------|----------|------|
| `/rag-manage` 路由 | `frontend/src/router/index.ts` 已接入 `RagManage/index.vue` | 已完成 |
| 侧边栏 admin 可见 | `SidebarContent.vue` 已加“知识库管理”，仅 admin 可见 | 已完成 |
| 面包屑映射 | `layout/index.vue` 已加 `/rag-manage` | 已完成 |
| Tab 布局 | `RagManage/index.vue` 包含概览/资源/标签/日志 | 已完成 |
| 概览仪表盘 | `OverviewTab.vue` 已有 Qdrant 状态、向量、磁盘、维度、重建按钮 | 部分完成 |
| 资源列表 | `ResourceTable.vue` 已有列表、筛选、详情、删除 | 部分完成 |
| 资源详情独立组件 | 当前详情弹窗内联在 `ResourceTable.vue` | 可接受，后续可拆 |
| 标签管理 | `TagManager.vue` 已有列表、新建、编辑、刷新、启停 | 已完成 |
| 检索日志 | `RetrievalLogTable.vue` 已有列表、客户筛选、详情 JSON | 部分完成 |

当前前端文件：

```text
frontend/src/views/RagManage/
├── index.vue
└── components/
    ├── OverviewTab.vue
    ├── ResourceTable.vue
    ├── TagManager.vue
    └── RetrievalLogTable.vue
```

和原计划相比，少了独立的 `ResourceDetail.vue`，但功能已内联，不算偏离。

### 2.2 后端 API

当前 `app/routers/api_rag.py` 已实现：

| 能力 | 当前接口 | 判断 |
|------|----------|------|
| 状态查询 | `GET /api/v1/rag/status` | 已完成，并补充 collection/resource 统计 |
| 全量/按类型重建 | `POST /api/v1/rag/reindex?source=all/speech/material&force=true/false` | 已完成 |
| 素材 CSV 导入 | `POST /api/v1/rag/import-material-csv` | 已完成 |
| 标签列表 | `GET /api/v1/rag/tags` | 已完成 |
| 标签刷新 | `POST /api/v1/rag/tags/refresh` | 已完成 |
| 标签新建 | `POST /api/v1/rag/tags` | 已完成 |
| 标签编辑/启停 | `PUT /api/v1/rag/tags/{tag_id}` | 已完成 |
| 标签软删除 | `DELETE /api/v1/rag/tags/{tag_id}` | 已完成 |
| 资源列表 | `GET /api/v1/rag/resources` | 已完成 |
| 资源详情 | `GET /api/v1/rag/resources/{resource_id}` | 已完成 |
| 单条删除 | `DELETE /api/v1/rag/resources/{resource_id}` | 已完成 |
| 批量删除 | `POST /api/v1/rag/resources/batch-delete` | 后端已完成，前端未暴露 |
| 检索日志列表 | `GET /api/v1/rag/retrieval-logs` | 已完成 |
| 检索日志详情 | `GET /api/v1/rag/retrieval-logs/{log_id}` | 已完成 |

原计划中仍未落地：

| 能力 | 原计划路径 | 当前状态 |
|------|------------|----------|
| 单条资源重建 | `POST /rag/resources/{id}/reindex` | 未实现 |
| 按筛选条件重建 | 资源列表批量操作 | 未实现 |
| 前端批量删除 | 资源表格批量选择 | 未实现 |
| 日志时间范围筛选 | `start_date/end_date` | 未实现 |
| Qdrant 点位 scroll 页面 | 仅 `vector_store.scroll_points()` 函数存在 | 未暴露前端/接口 |

### 2.3 vector_store

当前 `app/rag/vector_store.py` 已新增：

```text
get_collection_info()
delete_points(point_ids)
scroll_points(limit, offset, filters)
```

这与原计划一致。需要注意的是，当前 `get_collection_info()` 读取 `vectors_count / disk_data_size / ram_data_size` 等字段时，可能受 qdrant-client 版本影响；如果字段不存在，会返回 `None`，导致概览页部分统计显示为空。

---

## 3. 是否偏离蓝图？

没有发生方向性偏离。

### 已对齐的地方

1. 页面定位正确：它是中文 RAG 管理台，不依赖 Qdrant 自带 Dashboard。
2. 架构边界正确：local/remote 都通过 SQL 表管理资源，Qdrant 只承担向量索引和搜索。
3. 管理对象正确：资源、标签、检索日志、索引操作都覆盖到了。
4. 前端入口正确：放在管理后台侧边栏，admin 可见。
5. RAG 口径正确：页面展示的是 support index，不应替代话术/素材 official truth。

### 有轻微偏差但可接受的地方

1. 原计划拆 `ResourceDetail.vue`，当前内联在 `ResourceTable.vue`。MVP 可接受，后续再拆。
2. 原计划强调“资源管理核心”，当前资源列表可看可删，但治理操作还少。
3. 原计划有“存储卡片”，当前实现依赖 Qdrant collection info；local 模式/客户端字段不兼容时会空。
4. 原计划有“检索日志调试”，当前能看 JSON，但业务可读性还弱。

---

## 4. 当前实现风险

### P0：后端权限需要收紧

前端菜单仅 admin 可见，但部分后端资源和日志接口当前只调用 `get_current_user()`，没有统一 `require_role(user, "admin")`。

建议收紧这些接口：

```text
GET    /api/v1/rag/resources
GET    /api/v1/rag/resources/{id}
DELETE /api/v1/rag/resources/{id}
POST   /api/v1/rag/resources/batch-delete
GET    /api/v1/rag/retrieval-logs
GET    /api/v1/rag/retrieval-logs/{id}
```

理由：RAG 资源可能包含内部话术、医疗敏感说明、素材链接、客户检索日志，不应让普通 coach 直接浏览或删除。

### P0：删除一致性风险

当前删除资源流程是：

```text
删除 DB resource/chunks
提交 DB
再 delete Qdrant points
```

如果 Qdrant 删除失败，DB 已经没有 chunk point id，后续很难补删，可能留下向量孤点。

建议改为：

1. 先收集 point_ids。
2. 先尝试删除 Qdrant points。
3. Qdrant 删除成功后再提交 DB 删除。
4. 如果 Qdrant 不可用，至少把资源标记为 `disabled`，不要直接物理删除 DB。

### P1：概览统计兼容性不足

当前 `get_collection_info()` 可能读取了当前 qdrant-client 版本没有的属性，例如 `vectors_count / disk_data_size / ram_data_size`。一旦抛异常，接口会吞掉并返回 `collection=None`，前端统计就变成空。

建议使用兼容写法：

```python
points_count = getattr(info, "points_count", None)
vectors_count = getattr(info, "vectors_count", None) or points_count
disk_data_size = getattr(info, "disk_data_size", None)
ram_data_size = getattr(info, "ram_data_size", None)
```

前端也应明确展示“当前 Qdrant 客户端不支持该指标”，而不是只显示 `-`。

### P1：检索日志 hit_count 统计不准

当前 `hit_json` 实际可能是：

```json
{
  "phase1": [...],
  "material": [...],
  "material_ids": [...]
}
```

但列表接口按 `len(hit_json)` 统计时，dict 只会得到 key 数，不等于命中条数。

建议改为：

```text
phase1_hit_count = len(hit_json.phase1)
material_hit_count = len(hit_json.material)
visible_hit_count = phase1 中 filter_reason 为空的数量
```

前端列表可展示：

```text
参考命中 / 素材命中 / 可见命中
```

### P1：资源列表筛选不完整

后端支持：

```text
source_type, content_kind, quality, rag_status, safety_level, q
```

前端当前只暴露：

```text
q, source_type, quality, safety_level
```

建议补：

- content_kind
- status
- visibility
- source_id
- 仅显示 weak/stale

这样才能真正支撑 RAG 数据治理。

### P1：缺少单条重建能力

当前可以全量或按类型重建，但不能只重建一个资源。

建议补：

```text
POST /api/v1/rag/resources/{resource_id}/reindex
```

重建逻辑：

- `speech_template`：按 `source_id` 找话术，只重建该话术。
- `material`：按 `source_id` 找素材，只重建该素材。
- 重建前不要把 candidate/support 误升为 official。

### P1：缺少“禁用”而非“删除”

RAG 资源更适合支持：

```text
active / disabled / stale
```

删除适合测试数据或确认误入库数据；生产治理更常用“禁用”，因为 official truth 仍在源表。

建议新增：

```text
POST /api/v1/rag/resources/{id}/disable
POST /api/v1/rag/resources/{id}/enable
```

### P2：资源详情标签为空会误导

当前详情会查 `rag_resource_tags`，但当前标签主链路在：

```text
metadata_json
semantic_text
Qdrant payload
```

`rag_resource_tags` 为空不代表资源没有标签。前端详情如果只展示 `tags`，会让用户误以为标签没入库。

建议详情接口补充：

- `metadata_json` 解析结果
- Qdrant payload 中的 `customer_goal/intervention_scene/question_type`
- 如果 `rag_resource_tags` 为空，显示“当前标签来自 payload/metadata”

### P2：缺少治理视图

基于最近 RAG 审查，当前库里存在历史数据问题：

- 旧 visibility：`customer_sendable`
- active weak 素材
- deleted/no-meta 素材仍在 RAG resource
- 中文/旧 code 标签残留

管理页应增加“治理视图”或“问题资源筛选”：

| 问题类型 | 判断条件 |
|----------|----------|
| 旧 visibility | `visibility NOT IN ('coach_internal','customer_visible')` |
| weak active | `semantic_quality='weak' AND status='active'` |
| stale active | `semantic_quality='stale' AND status='active'` |
| 源素材已删除 | `source_type='material'` 且源 `materials.storage_status='deleted'` |
| 素材无 meta | `materials.rag_meta_json IS NULL OR ''` |
| 标签不在词表 | metadata/payload 中出现非 `rag_tags` code |

---

## 5. 建议的下一轮开发计划

### Phase 1：权限与一致性收口

- [ ] RAG 资源/日志接口统一要求 admin。
- [ ] 删除操作改为先删 Qdrant，再删 DB；失败时降级为 disabled。
- [ ] 后端删除接口返回 `qdrant_deleted / db_deleted / fallback_disabled`。
- [ ] 前端删除确认文案明确“删除的是 RAG 索引，不删除原始话术/素材”。

### Phase 2：概览和日志修正

- [ ] `get_collection_info()` 兼容当前 qdrant-client 字段。
- [ ] 概览页补资源质量分布：ok / medium / weak / stale。
- [ ] 概览页补来源分布：speech_template / material。
- [ ] 日志列表修正 hit_count，区分参考命中和素材命中。
- [ ] 日志筛选补时间范围。

### Phase 3：资源治理能力

- [ ] 前端资源列表补 content_kind/status/visibility 筛选。
- [ ] 补单条重建接口和按钮。
- [ ] 补禁用/启用接口和按钮。
- [ ] 补批量选择、批量禁用、批量删除。
- [ ] 增加“问题资源”快捷筛选。

### Phase 4：详情页增强

- [ ] 把资源详情拆成 `ResourceDetail.vue`。
- [ ] 详情展示 metadata_json 解析结果。
- [ ] 详情展示 Qdrant payload。
- [ ] 详情展示源对象链接：跳转到话术管理或素材库。
- [ ] 详情展示“这条资源是否可被检索召回”的判断结果。

### Phase 5：RAG 调试工具

- [ ] 增加“模拟检索”输入框，输入 query/scene 后查看命中。
- [ ] 展示 raw score、tag_boost、filter_reason。
- [ ] 支持按某条资源测试是否能命中。
- [ ] 支持导出检索日志 JSON，用于复盘。

---

## 6. 当前文件变更清单

已落地：

| 文件 | 当前状态 |
|------|----------|
| `app/rag/vector_store.py` | 已有 `get_collection_info/delete_points/scroll_points` |
| `app/routers/api_rag.py` | 已有状态、重建、标签、资源、日志接口 |
| `frontend/src/views/RagManage/index.vue` | 已有 Tab 主页面 |
| `frontend/src/views/RagManage/components/OverviewTab.vue` | 已有概览和重建 |
| `frontend/src/views/RagManage/components/ResourceTable.vue` | 已有资源列表、详情、删除 |
| `frontend/src/views/RagManage/components/TagManager.vue` | 已有标签 CRUD |
| `frontend/src/views/RagManage/components/RetrievalLogTable.vue` | 已有日志列表和详情 |
| `frontend/src/router/index.ts` | 已接入 `/rag-manage` |
| `frontend/src/layout/SidebarContent.vue` | 已接入侧边栏 |
| `frontend/src/layout/index.vue` | 已接入页面标题映射 |

建议新增或调整：

| 文件 | 建议 |
|------|------|
| `app/routers/api_rag.py` | 收紧权限、补单条重建、禁用/启用、日志时间筛选 |
| `app/rag/vector_store.py` | 修正 collection info 字段兼容性 |
| `frontend/src/views/RagManage/components/ResourceTable.vue` | 补筛选、批量操作、禁用/重建按钮 |
| `frontend/src/views/RagManage/components/RetrievalLogTable.vue` | 修正命中展示，补时间筛选 |
| `frontend/src/views/RagManage/components/OverviewTab.vue` | 补质量/来源分布，处理指标不可用状态 |
| `frontend/src/views/RagManage/components/ResourceDetail.vue` | 可从 ResourceTable 内联详情中拆出 |

---

## 7. 面向项目负责人的解释

### 已经能做什么

- 能看到 RAG 是否启用、Qdrant 是否连接。
- 能一键重建全部、话术或素材索引。
- 能浏览已入库的 RAG 资源。
- 能查看资源详情、语义文本和 chunk。
- 能删除 RAG 索引资源。
- 能管理 RAG 词表。
- 能查看检索日志和命中 JSON。

### 半能做什么

- 能做基础排查，但日志还偏技术 JSON，不够业务可读。
- 能删除资源，但删除一致性和生产安全性还要加强。
- 能看资源质量，但缺少问题资源治理入口。
- 能重建索引，但还不能单条重建或按筛选条件重建。

### 还不能做什么

- 不能把 RAG 管理页当成话术/素材 official truth 管理后台。
- 不能保证删除 RAG 资源后 Qdrant 一定无孤点。
- 不能直接完成历史脏数据治理。
- 不能做完整检索评测和召回质量分析。

### 当前 blocker

当前 blocker 不是页面有没有，而是 **管理页还缺生产治理闭环**：权限、删除一致性、单条重建、问题资源筛选和日志可读性需要补齐。

### 下一步最值得做什么

先做 Phase 1 + Phase 2：收紧权限、修正 Qdrant 统计兼容性、修正日志命中统计、改删除一致性。这些是把 MVP 变成可放心使用的管理工具的最低门槛。
