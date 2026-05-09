# 话术管理 CSV 导入对齐调研报告

日期：2026-05-09  
范围：话术管理页面、CSV 导入接口、3 级分类、话术 RAG 标注字段、RAG 索引链路  
结论：当前架构方向基本对齐，但不建议立刻全量入库。必须先修复导入接口运行时报错，并补齐全量导入前的字段与安全门禁。

## 1. 给项目负责人的结论

### 已经能做什么

- 话术管理页面已经具备 3 级分层展示：大类、二级类、三级类、场景、话术。
- 页面已经有“导入 CSV”入口，上传后会调用后端导入接口，并可选择同步 RAG 索引。
- 后端已经把话术导入放在独立 service：路由层负责权限和文件检查，导入 service 负责解析与落库，RAG indexer 负责向量索引。
- 标注规范里的核心字段大部分已有落点：`title / clean_content / summary / customer_goal / intervention_scene / question_type / safety_level / visibility / tags / usage_note / tone`。
- 当前数据库已存在 3 级分类结构：一级 4 个、二级 18 个、三级 72 个；`speech_templates=41`，`rag_resources(source_type=speech_template)=41`。

### 半能做什么

- CSV 解析服务本身可以读 `docs/shujubiaozhu/test_huashu.csv`，dry-run 结果为 `updated=5, skipped=0`。
- RAG 索引可以把 `metadata_json` 里的标签写入 Qdrant payload，检索层也会使用 `customer_goal / intervention_scene / question_type / safety_level` 做过滤和加权。
- 3 级分类可以把导入话术自动归到 L3 分类，但 RAG indexer 对 L3 分类的 `category_l1/category_l2` payload 解析还没完全对齐。

### 还不能做什么

- 当前不能直接从页面执行全量导入。实际点击“导入 CSV”会触发后端 `TypeError`。
- 不能把“CSV 能解析”理解为“全量入库安全”。当前导入门禁还没有严格校验标注规范要求的全部质量字段。
- 不能保证旧数据完全符合新标注词表。当前 RAG 话术资源里仍有 4 条 `visibility=customer_sendable`，这是历史旧值，不是当前规范允许值。

### 当前 blocker

1. `app/routers/api_speech_templates.py` 第 235 行调用：

```python
import_speech_templates_csv(db, decode_csv_bytes(raw), dry_run=dry_run, owner_id=user.id)
```

但 `app/services/speech_template_import.py` 第 275 行的 `import_speech_templates_csv` 不接收 `owner_id` 参数。focused validation 已确认会报：

```text
import_speech_templates_csv() got an unexpected keyword argument 'owner_id'
```

2. 全量入库前缺少严格门禁：`summary/customer_goal/intervention_scene/safety_level/visibility/tags/usage_note/tone` 目前不是强校验字段。

3. 安全规则未强制阻断：`medical_sensitive/doctor_review` 必须 `coach_internal`，`contraindicated` 不应进入正式推荐语料，但当前导入 service 还没有实现这些硬规则。

### 是否偏离蓝图

没有明显偏离蓝图。当前路线仍是：

```text
CSV 标注
  -> speech_templates official 话术表
  -> metadata_json 保存话术标注
  -> rag_resources / rag_chunks support 索引
  -> Qdrant support 向量检索
```

风险不是架构方向错，而是“导入可用性”和“全量入库门禁”还没收口。

## 2. 当前链路核对

### 前端入口

文件：`frontend/src/views/SpeechTemplates.vue`

- 第 14-16 行：页面右上角有“导入 CSV”按钮。
- 第 288-292 行：使用 `el-upload`，限制 `.csv,text/csv`。
- 第 295 行：默认支持“导入后同步 RAG 索引”。
- 第 388-389 行：提交 `index_rag` 并调用 `/v1/speech-templates/import-csv`。
- 当前 UI 提示字段只列到 `source_id/source_type/title/clean_content/summary/intervention_scene/question_type/tone/status`，没有完整提示 `customer_goal/content_kind/visibility/safety_level/tags/usage_note/reviewer/review_note`。

判断：入口形态可用，但全量入库前建议补“dry-run 预检”按钮和完整字段提示。

### 后端路由

文件：`app/routers/api_speech_templates.py`

- 第 217 行：`POST /api/v1/speech-templates/import-csv`。
- 第 226 行：要求 `speech_template` 权限。
- 第 228-233 行：校验 CSV 后缀和空文件。
- 第 235 行：调用导入 service。
- 第 237-238 行：导入后可同步 RAG 索引。

判断：路由层边界基本符合当前架构模式，但第 235 行参数不匹配是 P0 blocker。

### 导入服务

文件：`app/services/speech_template_import.py`

- 第 114 行：`_build_metadata_json` 会写入 `customer_goal/intervention_scene/question_type/safety_level/visibility/summary/tags/usage_note`。
- 第 144 行：`validate_row` 只强校验 `title`、`clean_content/content`、`source_type`。
- 第 164 行：`import_speech_template_rows` 支持 `owner_id`，并能写入 `owner_id`。
- 第 275 行：`import_speech_templates_csv` 未透传 `owner_id`。
- 第 284 行：`import_speech_templates_csv_file` 也未透传 `owner_id`。

判断：service 内部主函数已经有 owner_id 能力，但外层 facade 漏了参数，是小改动但高影响。

### 3 级分类

文件：`app/services/crm_speech_templates.py`、`app/schema_migrations.py`

- `CATEGORY_SEED` 已按 L1 > L2 > L3 定义。
- `SCENE_CATEGORY_MAP` 已将 `scene_key` 映射到 L2/L3。
- schema migration 会把模板 `category_id` 回填到 L3。
- 当前数据库验证：`{1: 4, 2: 18, 3: 72}`。

判断：话术管理页面的 3 级分层与导入归类方向一致。

### RAG 索引

文件：`app/rag/resource_indexer.py`、`app/rag/retriever.py`

- indexer 会把 `metadata_json` 拼入 `semantic_text`。
- indexer 会把 `customer_goal/intervention_scene/question_type/safety_level/visibility` 写入 Qdrant payload。
- retriever 会用这些字段做场景过滤、安全等级过滤和标签加权。
- 但 indexer 当前只按 `cat.level == 2` 解析分类名；现在模板 `category_id` 指向 L3，因此分类 payload 不完整。

判断：RAG support 链路可用，但分类增强字段需要补齐 L3 -> L2 -> L1 解析。

## 3. 标注字段对齐表

| CSV 字段 | 当前落点 | 状态 | 备注 |
|---|---|---|---|
| `title` | `speech_templates.label`、`rag_resources.title` | 已对齐 | 强校验 |
| `clean_content` | `speech_templates.content`、`semantic_text` | 已对齐 | 强校验 |
| `summary` | `metadata_json.summary`、`semantic_text` | 半对齐 | 不强校验 |
| `status` | 导入门禁 | 半对齐 | 只接受 `approved/active`，不单独落业务字段 |
| `customer_goal` | `metadata_json.customer_goal`、Qdrant payload | 已对齐 | 不强校验 |
| `intervention_scene` | `metadata_json.intervention_scene`、scene 推导、Qdrant payload | 已对齐 | 不强校验 |
| `content_kind` | 默认 `script` | 半对齐 | 当前不校验 CSV 是否为 `script` |
| `visibility` | `metadata_json.visibility`、`rag_resources.visibility` | 半对齐 | 不强校验，历史旧值仍残留 |
| `safety_level` | `metadata_json.safety_level`、`rag_resources.safety_level` | 半对齐 | 未强制安全组合规则 |
| `question_type` | `metadata_json.question_type`、scene 推导、Qdrant payload | 已对齐 | 不强校验 |
| `tags` | `metadata_json.tags`、`semantic_text` | 半对齐 | 不强校验 |
| `usage_note` | `metadata_json.usage_note`、`semantic_text` | 半对齐 | 不强校验 |
| `tone` | `speech_templates.style` | 已对齐 | 中文 tone 会映射到 `professional/encouraging/competitive` |
| `reviewer` | 无 | 未对齐 | 当前丢弃 |
| `review_note` | 无 | 未对齐 | 当前丢弃 |

## 4. 全量入库前建议门禁

### P0：必须先修

1. 修复 `owner_id` 参数透传：
   - `import_speech_templates_csv(..., owner_id=None)`
   - `import_speech_templates_csv_file(..., owner_id=None)`
   - 透传给 `import_speech_template_rows`。

2. 增加 strict dry-run：
   - 页面先执行 dry-run，只展示新增/更新/跳过/错误。
   - 错误为 0 后，再允许正式导入。

3. 强校验安全规则：
   - `content_kind` 必须为空或 `script`。
   - `visibility` 必须是 `coach_internal/customer_visible`。
   - `safety_level` 必须是词表 code。
   - `medical_sensitive/doctor_review` 必须 `coach_internal`。
   - `contraindicated` 默认跳过，不进入 active RAG。

### P1：建议全量入库前完成

1. 对 `summary/customer_goal/intervention_scene/tags/usage_note/tone` 增加缺失预警。
2. 将 `reviewer/review_note/content_kind` 纳入 `metadata_json`，避免标注文件信息丢失。
3. 修复 RAG indexer 的 L3 分类解析，把 L3 所属 L2/L1 写入 `semantic_text` 和 payload。
4. 清理或迁移历史 `customer_sendable` 为 `customer_visible`。

### P2：入库后治理

1. 生成导入批次审计记录，保留文件名、操作人、created/updated/skipped/errors。
2. 对 RAG 命中做 gold set 回归测试，确认饮食问法不会混入积分运营话术。
3. 后台增加“只预检不入库”的可下载错误报告。

## 5. 本轮验证结果

### Focused validation

- `python -m py_compile app\routers\api_speech_templates.py app\services\speech_template_import.py app\rag\resource_indexer.py app\rag\retriever.py`：通过。
- `cd frontend && .\node_modules\.bin\vue-tsc.cmd --noEmit`：通过。
- `python scripts\import_speech_templates_csv.py docs\shujubiaozhu\test_huashu.csv --dry-run`：通过，结果 `created=0 updated=5 skipped=0`。
- 参数错配复现：通过，确认 `import_speech_templates_csv() got an unexpected keyword argument 'owner_id'`。
- 当前 DB 抽查：`speech_templates=41`，`with_metadata=41`，`rag_speech_resources=41`，`rag_speech_chunks=41`。
- 旧值抽查：`rag_resources.visibility` 中存在 `customer_sendable=4`。

### 项目启动验证

- 后端：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8011` 启动成功，日志到 `Application startup complete`。
- 前端：`npm run dev -- --host 0.0.0.0 --port 5181` 启动成功，Vite ready。
- 前端构建：`npm run build` 通过；存在 chunk size warning，不影响本次导入结论。

## 6. 最终建议

当前不建议直接全量入库。最稳的下一步是先做一个小的 P0 修复包：修 `owner_id` 参数、加 strict dry-run、补安全门禁，然后用 `test_huashu.csv` 和一份真实小批量 CSV 做预检，再进入全量导入。

从业务视角看：

- “看见”：3 级话术管理界面已经能看见分类、场景和话术。
- “理解”：CSV 标注字段大部分能进入 `metadata_json` 并参与 RAG 理解。
- “决策”：全量入库前的质量门禁不足，当前不能放心批量放行。
- “闭环”：启动验证通过，但导入接口本身存在运行时 blocker，修复后才能进入正式导入闭环。
