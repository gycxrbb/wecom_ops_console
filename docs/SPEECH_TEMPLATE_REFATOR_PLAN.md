# 话术管理三入口一致性重构 — 分阶段开发 Plan

> 日期：2026-05-11
> 文档状态：plan / candidate design
> 前置文档：`docs/话术管理-三入口一致性与可扩展方案.md`（本文是其可执行落地计划）
> 开发规范：遵循 `AGENTS.md`、`CLAUDE.md`

---

## 当前代码真值（2026-05-11 审查结果）

### 已确认的 Bug / 缺陷

| # | 问题 | 等级 | 文件 | 行号 |
|---|------|:----:|------|------|
| B1 | `import_speech_templates_csv` 签名缺 `owner_id`，前端 CSV 导入必然 TypeError | **P0** | `speech_template_import.py:275` | 275 |
| B2 | RAG 全量索引 `index_speech_templates` 只认 L2 category，L3 分类下模板全部缺失 `category_l1/category_l2` | **P0** | `resource_indexer.py:108-127` | 108 |
| B3 | RAG 增量索引 `index_single_speech_template` 只认 L2，L3 同上 | **P0** | `resource_indexer.py:231-239` | 231 |
| B4 | `_build_semantic_text_speech` 不含 L3 名称，L3 信息未被向量化 | **P1** | `resource_indexer.py:38-76` | 38 |
| B5 | Qdrant payload 不含 `category_l3`，检索无法按 L3 过滤 | **P1** | `resource_indexer.py:79-99` | 79 |
| B6 | 前端 RAG 配置 safety_level 选项 `caution/risk` 与词表不一致，词表为 `nutrition_education/medical_sensitive/doctor_review/contraindicated` | **P1** | `SpeechTemplates.vue:257-263` | 257 |
| B7 | `PATCH /rag-meta` 不走词表校验，任意字符串直接写入 `metadata_json` | **P1** | `api_speech_templates.py:278-279` | 278 |
| B8 | `PUT /{id}` 和 `PATCH /{id}/rag-meta` 不拦内置模板，可被覆盖 | **P2** | `api_speech_templates.py:161,257` | 161 |
| B9 | 前端 `isPointsScene` 用中文名 `'积分管理'` 判定，运营改名即失效 | **P2** | `useSpeechTemplates.ts:78-81` | 78 |

### 已完成的基建（本次 plan 之前）

- 3 级分类已上线：4 L1 × 18 L2 × 72 L3，模板 `category_id` 已全部指向 L3
- `SCENE_CATEGORY_MAP` 已改为 `(L2名, L3名)` 元组
- CSV 导入已按 L3 解析 `category_id`
- 前端侧边栏已渲染 3 级分类树

---

## Phase 0 · 修 P0 Blocker（半天）

> 目标：让 CSV 导入能跑通、RAG 索引正确处理 L3

### 0.1 修 `import_speech_templates_csv` 签名

**文件**: `app/services/speech_template_import.py:275`

```python
# Before
def import_speech_templates_csv(db, csv_text, *, dry_run=False):
    return import_speech_template_rows(db, parse_csv_text(csv_text), dry_run=dry_run)

# After
def import_speech_templates_csv(db, csv_text, *, dry_run=False, owner_id=None):
    return import_speech_template_rows(db, parse_csv_text(csv_text), dry_run=dry_run, owner_id=owner_id)
```

同步修 `import_speech_templates_csv_file`:

```python
def import_speech_templates_csv_file(db, csv_path, *, dry_run=False, owner_id=None):
    return import_speech_templates_csv(db, decode_csv_bytes(csv_path.read_bytes()), dry_run=dry_run, owner_id=owner_id)
```

### 0.2 修 RAG 全量索引 `index_speech_templates` — 支持 L3

**文件**: `app/rag/resource_indexer.py`

将 category 预加载改为 3 级：

```python
# 原来：只 load L2 + L1
# 改为：load L3 + 通过 parent_id 反查 L2 + L1

cats = db.query(SpeechCategory).filter(...).all()
cat_l3_map = {}  # L3 id -> L3 obj
cat_l2_map = {}  # L2 id -> L2 obj
cat_l1_map = {}  # L1 id -> L1 obj
for c in cats:
    if c.level == 3: cat_l3_map[c.id] = c
    elif c.level == 2: cat_l2_map[c.id] = c
    elif c.level == 1: cat_l1_map[c.id] = c

# 解析时：tpl.category_id -> L3 -> L2.parent_id -> L1
cat_l1, cat_l2, cat_l3 = '', '', ''
if tpl.category_id and tpl.category_id in cat_l3_map:
    l3 = cat_l3_map[tpl.category_id]
    cat_l3 = l3.name
    l2 = cat_l2_map.get(l3.parent_id)
    if l2:
        cat_l2 = l2.name
        l1 = cat_l1_map.get(l2.parent_id)
        if l1: cat_l1 = l1.name
# 向后兼容：如果 category_id 还指向 L2（老数据）
elif tpl.category_id and tpl.category_id in cat_l2_map:
    l2 = cat_l2_map[tpl.category_id]
    cat_l2 = l2.name
    l1 = cat_l1_map.get(l2.parent_id)
    if l1: cat_l1 = l1.name
```

### 0.3 修 RAG 增量索引 `index_single_speech_template` — 支持 L3

同样的 L3 → L2 → L1 解析逻辑，替换 `if cat.level == 2` 判定。

### 0.4 修 `_build_semantic_text_speech` — 加入 L3

增加 `category_l3` 参数，拼入 semantic text：

```python
if category_l3:
    parts.append(f"三级分类: {category_l3}")
```

### 0.5 修 `_build_payload_from_metadata` — 加入 L3

增加 `category_l3` 参数，写入 payload：

```python
if category_l3:
    payload["category_l3"] = category_l3
```

### 0.6 修前端 safety_level 选项

**文件**: `frontend/src/views/SpeechTemplates.vue`

```html
<!-- Before -->
<el-radio value="caution">caution</el-radio>
<el-radio value="risk">risk</el-radio>

<!-- After -->
<el-radio value="nutrition_education">nutrition_education</el-radio>
<el-radio value="medical_sensitive">medical_sensitive</el-radio>
<el-radio value="doctor_review">doctor_review</el-radio>
<el-radio value="contraindicated">contraindicated</el-radio>
```

### Phase 0 验证

1. `python -c "from app.services.speech_template_import import import_speech_templates_csv; import inspect; print(inspect.signature(import_speech_templates_csv))"` — 确认有 `owner_id` 参数
2. 后端启动，手动触发一次 RAG 全量索引，抽查 Qdrant payload 含 `category_l3`
3. 前端 RAG 配置对话框打开，safety_level 选项与词表一致
4. CSV 导入不再报 TypeError

---

## Phase 1 · 统一字段 schema + 服务层（1.5 天）

> 目标：三个路由入口全部走同一个 service 函数，消除逻辑漂移

### 1.1 新增 `app/schemas/speech_template.py`

```python
from pydantic import BaseModel
from typing import Literal

class SpeechMetadata(BaseModel):
    summary: str | None = None
    customer_goal: list[str] = []
    intervention_scene: list[str] = []
    question_type: list[str] = []
    safety_level: Literal['general','nutrition_education','medical_sensitive',
                          'doctor_review','contraindicated'] | None = None
    visibility: Literal['coach_internal','customer_visible'] | None = None
    tags: list[str] = []
    usage_note: str | None = None
    reviewer: str | None = None
    review_note: str | None = None
    content_kind: Literal['script'] = 'script'
```

### 1.2 新增 `app/services/speech_template_service.py`

核心函数：

```python
def upsert_speech_template(db, *, scene_key, style, label='', content='',
                            category_id=None, category_code=None,
                            metadata: SpeechMetadata | None = None,
                            owner_id=None, template_id=None,
                            index_rag=True) -> SpeechTemplate:
    """三个入口的唯一写入通道。"""
    ...

def validate_safety_rules(metadata: SpeechMetadata) -> list[str]:
    """medical_sensitive/doctor_review 必须 coach_internal；contraindicated 禁止入库。"""
    ...

def resolve_category_id(db, *, category_id=None, category_code=None,
                         scene_key=None) -> int | None:
    """优先级：显式 category_id > category_code > SCENE_CATEGORY_MAP fallback。"""
    ...
```

### 1.3 路由层改造

**`POST /`** — 手动创建调 `upsert_speech_template(template_id=None)`

**`PUT /{id}`** — 更新内容调 `upsert_speech_template(template_id=id)`

**`PATCH /{id}/rag-meta`** — 更新 RAG 标注调 `upsert_speech_template(template_id=id, metadata=...)`，且走词表校验

**`/import-csv`** — 内层循环调 `upsert_speech_template(template_id=None)`

### 1.4 PATCH /rag-meta 走词表校验

```python
from ..rag.vocabulary import resolve_code, resolve_tag_values

# 对 customer_goal / intervention_scene / question_type 走 resolve_tag_values
# 对 safety_level / visibility 走 resolve_code
# 非法值返回 dropped_values 给前端
```

### 1.5 Builtin 保护

在 `upsert_speech_template` 内加：

```python
if row and row.is_builtin == 1 and not allow_builtin_override:
    raise BizError('内置模板不可修改')
```

`allow_builtin_override` 默认 False，管理员显式传 True。

### Phase 1 验证

1. `python -m py_compile app/services/speech_template_service.py app/schemas/speech_template.py`
2. 后端启动，三个入口各跑一次冒烟
3. `PATCH /rag-meta` 传 `safety_level=caution`（非法）→ 应返回 dropped_values 或报错
4. `PUT /{id}` 对 builtin 模板 → 应拒绝

---

## Phase 2 · 分类稳定标识 category_code（1 天）

> 目标：让分类有一个不受中文名变更影响的稳定 key

### 2.1 DDL 迁移

```sql
ALTER TABLE speech_categories ADD COLUMN code VARCHAR(128);
```

`schema_migrations.py` 中幂等执行。

### 2.2 Seed code

为 4 L1 × 18 L2 × 72 L3 一次性生成 code：

```
health / health.weight / health.weight.loss_speed
health / health.diet / health.diet.food_choice
system / system.func / system.func.checkin
community / community.points / community.points.earning
service / service.user / service.user.problem_solve
...
```

### 2.3 API 返回 code

`GET /categories` 和 `GET /scenes` 响应增加 `code` 字段。

### 2.4 RAG semantic_text + payload 加 category_code

`_build_semantic_text_speech` 加 `分类编码: {code}`
`_build_payload_from_metadata` 加 `category_code: code`

### 2.5 修 `isPointsScene` 地雷

```typescript
// Before
return scene?.category_l2 === '积分管理'

// After
return scene?.category_code?.startsWith('community.points')
```

### Phase 2 验证

1. `speech_categories.code` 全部非空且唯一
2. 改一个 L3 中文名 → `GET /categories` 的 `code` 不变
3. RAG 全量索引后，Qdrant payload 含 `category_code`
4. 前端积分话术的占位符提示不受 L3 改名影响

**注意**：Phase 2 是**单向门**——DDL 落盘后回滚需重建分类表。执行前必须 DB 备份。

---

## Phase 3 · CSV 新增 category_code 列（0.5 天）

### 3.1 import 逻辑

`speech_template_import.py` 解析新列 `category_code`：
- 非空 → 查 `speech_categories.code` → 得 L3 id
- 空 → 老逻辑（SCENE_CATEGORY_MAP fallback）

### 3.2 词表补充

`vocabulary.py` 或 `speech_template_import.py` 中增加 `category_code` 的合法性校验。

### Phase 3 验证

1. 带 `category_code` 列的 CSV 按 L3 精确归类
2. 不带该列的老 CSV 走老路径，向后兼容
3. 非法 `category_code` 在 dry-run 时报行级错误

---

## Phase 4 · 前端手动创建动线优化（1 天）

### 4.1 自动生成 scene_key

点击 L3 "新建话术"时：
- 已知 `category_id` 和 L1/L2/L3 路径
- `scene_key` 自动生成为 `{l2_code}_{l3_code}`（如 `diet_food_choice`）
- 不再要求用户手填英文
- 高级折叠区可改

### 4.2 合并创建+RAG表单

对话框基础区：标题 + 内容 + 风格
高级折叠区：scene_key（可改）+ RAG 标注字段
保存时一次写入。

### Phase 4 验证

不懂英文的运营能走通"点饮食管理→食物选择建议→新建→填标题正文→保存"。

---

## Phase 5 · 单条编辑收敛成抽屉（1 天）

把"编辑内容"和"RAG 配置"合并为一个右侧抽屉：
- 顶部：label / content / style
- 中部：RAG 标注（走词表校验的 el-select）
- 底部：分类 cascader
- 保存调 `upsert_speech_template(template_id=id, ...)`

### Phase 5 验证

编辑后 RAG 增量索引自动触发。两个入口看到的字段一致。

---

## Phase 6 · 门禁与治理（按需）

1. CSV strict dry-run + 安全硬规则拦截
2. 历史 `customer_sendable` → `customer_visible` 迁移 SQL + RAG 重建
3. 导入批次审计表 `speech_import_batches`（可选）

---

## 涉及文件清单

| Phase | 文件 | 改动类型 |
|:------|------|:--------:|
| 0 | `app/services/speech_template_import.py` | 修签名 |
| 0 | `app/rag/resource_indexer.py` | 修 L3 解析 |
| 0 | `frontend/src/views/SpeechTemplates.vue` | 改 safety_level |
| 1 | `app/schemas/speech_template.py`（新） | 新增 |
| 1 | `app/services/speech_template_service.py`（新） | 新增 |
| 1 | `app/routers/api_speech_templates.py` | 改路由走 service |
| 2 | `app/models.py` | 加 code 列 |
| 2 | `app/schema_migrations.py` | seed code |
| 2 | `app/routers/api_speech_templates.py` | API 返回 code |
| 2 | `app/rag/resource_indexer.py` | payload 加 code |
| 2 | `frontend/src/views/SpeechTemplates/composables/useSpeechTemplates.ts` | 修 isPointsScene |
| 3 | `app/services/speech_template_import.py` | 解析 category_code |
| 4 | `frontend/src/views/SpeechTemplates.vue` | 创建对话框重构 |
| 4 | `frontend/src/views/SpeechTemplates/composables/useSpeechTemplates.ts` | 自动 scene_key |
| 5 | `frontend/src/views/SpeechTemplates.vue` | 编辑抽屉 |

---

## 开发纪律（AGENTS.md 对齐）

1. 每个 Phase 结束后必须**后端 + 前端启动验证**
2. Phase 0 修 blocker 后立即验证 CSV 导入能用
3. Phase 2 落盘前**DB 全量备份**
4. 遇到 bug 写进 `docs/bug.md`，工程经验写进 `docs/memory.md`
5. 单文件不超过 300 行（Python）/ 400 行（JS/TS），超了主动拆分
6. 路由层不写业务逻辑，全部 route 到 service

---

## 优先级建议

| 顺序 | Phase | 工期 | 收益 |
|:----:|:------|:----:|------|
| 1 | Phase 0 | 半天 | CSV 导入能用 + RAG L3 修好 |
| 2 | Phase 1 | 1.5 天 | 三入口一致性基建 |
| 3 | Phase 2 | 1 天 | 分类抗漂移 |
| 4 | Phase 3 | 半天 | CSV 精确归类 |
| 5 | Phase 4 | 1 天 | 运营体验 |
| 6 | Phase 5 | 1 天 | 编辑体验统一 |
| 7 | Phase 6 | 按需 | 历史数据治理 |
