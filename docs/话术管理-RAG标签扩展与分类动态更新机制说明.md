# 话术管理：RAG 标签扩展与分类动态更新机制说明

> 日期：2026-05-11  
> 文档性质：current truth + candidate recommendation  
> 范围：话术编辑抽屉中的 `客户目标 / 干预场景 / 问题类型`，话术三级分类树，CSV 导入归类与标签落地  
> 相关文件：`app/rag/vocabulary.py`、`app/rag/tag_service.py`、`app/rag/tag_cache.py`、`app/routers/api_rag.py`、`app/routers/api_speech_templates.py`、`app/services/speech_template_import.py`、`app/services/speech_template_service.py`、`app/schema_migrations.py`、`frontend/src/composables/useRagTags.ts`、`frontend/src/views/SpeechTemplates.vue`

---

## 一、先回答两个问题

### 1. 如果将来有一条话术不在现有“客户目标 / 干预场景 / 问题类型”里怎么办？

当前正确做法不是让运营随便输入一个新词并直接保存，而是先把新词纳入 RAG 标签词表，再让话术引用这个 code。

当前系统已经具备“动态扩标签”的底座：

- 标签正式表是 `rag_tags`
- 前端下拉来自 `GET /api/v1/rag/tags`
- 管理端接口支持 admin 新增标签：`POST /api/v1/rag/tags`
- 新增或更新标签后，`tag_service` 会 `tag_cache.reload_from_db(db)`，运行时解析会跟着更新

也就是说，未来出现新类型时，应该走“新增词表项 → 再标注话术”的流程。例如新增一个客户目标：

```json
{
  "dimension": "customer_goal",
  "code": "postpartum_weight",
  "name": "产后体重管理",
  "description": "产后恢复阶段的体重管理目标",
  "sort_order": 20,
  "aliases": ["产后减重", "产后管理"]
}
```

新增后，前端重新加载标签，下拉列表就能出现这个新项；CSV 导入也能通过 `postpartum_weight`、中文名或 aliases 解析到这个 code。

### 2. 话术层级目前是怎么动态更新的，尤其是 CSV 导入？

话术分类树不是前端写死的，正式数据在 `speech_categories` 表里。页面加载时调用：

- `GET /api/v1/speech-templates/categories`：读取 L1/L2/L3 分类树
- `GET /api/v1/speech-templates/scenes`：读取话术场景，并返回 `category_id/category_code/category_l1/category_l2/category_l3`

CSV 导入时有两条归类路径：

1. CSV 显式填 `category_code`：优先按 `speech_categories.code` 找分类，这是稳定路径
2. CSV 不填 `category_code`：根据 `intervention_scene/question_type` 推导 `scene_key`，再用 `SCENE_CATEGORY_MAP[scene_key]` 找中文 L3 名称，这是兼容 fallback

因此，CSV 要稳定归到某个 L3，最好显式填 `category_code`。如果新分类没有 code，CSV 就无法用 `category_code` 精确指向它。

---

## 二、RAG 标签的当前实现真值

### 2.1 标签来源

当前 `客户目标 / 干预场景 / 问题类型` 三个下拉来自同一套 RAG 标签体系。

基础种子在 `app/rag/vocabulary.py`：

- `customer_goal`
- `intervention_scene`
- `question_type`
- `visibility`
- `safety_level`
- `content_kind`
- `status`
- `source_type`

运行时正式读取 `rag_tags` 表。系统启动时 `app/main.py` 会加载 `tag_cache.load_from_db(db)`；初始化种子时 `app/services/seed.py` 会调用 `refresh_tags_from_vocabulary(db)`，把 `vocabulary.py` 中的默认词表 upsert 到 `rag_tags`。

### 2.2 前端下拉如何出现

前端 `frontend/src/composables/useRagTags.ts` 调用：

```text
GET /api/v1/rag/tags
```

然后按 `dimension` 分组，供 `SpeechTemplates.vue` 使用：

```text
tagOptions('customer_goal')
tagOptions('intervention_scene')
tagOptions('question_type')
```

所以这几个下拉不是必须改前端代码才能扩，只要后端 `rag_tags` 有新项，前端重新加载后就可以显示。

### 2.3 当前“允许输入新标签”的真实行为

前端 `el-select` 目前配置了 `allow-create`，用户可以手动输入下拉里没有的值。但这不等于这个值会正式进入系统。

单条编辑保存时，后端 `PATCH /api/v1/speech-templates/{id}/rag-meta` 会：

1. 构造 `SpeechMetadata`
2. 调用 `validate_metadata_vocabulary(meta)`
3. 对 `customer_goal / intervention_scene / question_type` 走 `resolve_tag_values`
4. 不在词表里的值会进入 `dropped_values`
5. 前端收到 `dropped_values` 后弹 warning

这说明当前系统已经开始防止“自由输入直接污染正式标签”。但 UI 上仍然给了用户“可以输入”的感觉，容易造成误解。

---

## 三、如果标签不在下拉里，推荐流程是什么

### 3.1 临时处理

如果只是这条话术有一个补充关键词，但还不确定要不要成为正式维度，可以放在 `tags` 自定义标签里。`tags` 当前更像弱标签，不应该承担正式检索维度。

适合放 `tags` 的例子：

- `外卖`
- `出差`
- `低卡`
- `客户情绪低落`

不适合只放 `tags` 的例子：

- 一个未来要被检索过滤的客户目标
- 一个稳定业务场景
- 一个应该在 CSV 规范里反复出现的问题类型

### 3.2 正式处理

如果这是未来会反复出现、需要检索过滤或加权的类型，应新增到 `rag_tags`：

```text
POST /api/v1/rag/tags
role: admin
```

建议规则：

- `dimension` 必须是明确维度，比如 `customer_goal`
- `code` 使用英文小写蛇形，如 `postpartum_weight`
- `name` 给运营看的中文名
- `aliases` 放中文别名、历史叫法、CSV 可能写法

新增后要做三件事：

1. 刷新/重开话术页面，确认下拉出现
2. 用一条话术保存验证 `metadata_json` 正确写入 code
3. 如果已有 CSV 使用这个新值，先 dry-run，再正式导入

### 3.3 长期产品化建议

当前已有后端 CRUD，但话术页面里还没有“申请新词 / 管理词表”的运营入口。建议后续增加一个轻量流程：

1. 运营在话术编辑里输入未知值
2. 前端提示“该标签不在正式词表，是否申请新增”
3. 写入待审核表或直接调用 admin-only 管理入口
4. admin 审核后进入 `rag_tags`
5. 话术重新保存或批量回填

这样既保留扩展性，也避免随手输入造成检索污染。

---

## 四、CSV 导入时标签如何落地

CSV 当前在 `app/services/speech_template_import.py` 中解析。关键行为：

### 4.1 RAG 标签字段

这些字段会进入 `metadata_json`：

```text
customer_goal
intervention_scene
question_type
safety_level
visibility
summary
tags
usage_note
```

其中：

- `customer_goal / intervention_scene / question_type` 通过 `resolve_tag_values(...)` 解析
- `safety_level / visibility` 通过 `resolve_code(...)` 解析
- `tags` 只是 split 后保存，不走正式词表

### 4.2 CSV 中遇到未知标签会怎样

当前 CSV 导入对未知 `customer_goal / intervention_scene / question_type` 的处理偏“宽松”：

- 能解析到正式 code 的值会写入 `metadata_json`
- 解析不到的值不会写入对应字段
- 当前导入结果没有像单条编辑那样返回 `dropped_values`

所以，如果 CSV 里写了一个还没进 `rag_tags` 的新客户目标，它大概率不会进入正式 RAG 标签。运营可能以为填了，系统实际上没有用上。

这是当前需要补的闭环：CSV dry-run 应该报告未知标签，例如：

```json
{
  "warnings": [
    "第 8 行 customer_goal=产后减重 未命中词表，已忽略"
  ]
}
```

### 4.3 `intervention_scene/question_type` 还会影响 `scene_key`

CSV 归一时还有一条独立逻辑：`normalize_scene_key(row)` 会从 `intervention_scene` 和 `question_type` 里猜 `scene_key`。

当前只认 `KNOWN_SCENES` 中的 8 个场景：

```text
meal_checkin
meal_review
obstacle_breaking
habit_education
emotional_support
qa_support
period_review
maintenance
```

如果命中这些 code，就用它作为 `scene_key`。如果没有命中，会 fallback：

1. 用 `question_type` 归一后的前 64 字符
2. 再没有则用 `rag_import`

这意味着：新增一个 RAG 标签，不等于新增一个业务 `scene_key`。  
`scene_key` 是话术业务身份，`customer_goal/intervention_scene/question_type` 是 RAG 标注，两者不能混为一谈。

---

## 五、分类树的当前动态更新机制

### 5.1 分类数据在哪里

话术三级分类存在 `speech_categories` 表：

```text
id
name
code
parent_id
level
sort_order
deleted_at
```

`code` 是稳定标识，例如：

```text
health.diet.food_choice
community.points.earning
service.user.problem
```

种子分类来自 `app/services/crm_speech_templates.py::CATEGORY_SEED`，迁移和回填在 `app/schema_migrations.py`。

### 5.2 页面如何动态展示分类

话术页面通过以下接口动态读取分类：

```text
GET /api/v1/speech-templates/categories
```

返回 L1/L2/L3 树，每个节点含：

```text
id, name, code, level, parent_id, sort_order, children
```

前端在 `useSpeechTemplates.ts` 中把 `scenes` 按 `category_id` 挂到 L3 节点下。因此：

- 新增分类后，只要重新 `loadCategories()` 就能看到
- 重命名分类后，页面节点名会更新
- 移动分类后，树结构会更新

### 5.3 当前分类 CRUD 的边界

当前页面和接口支持：

- 新建 L1/L2/L3
- 重命名
- 删除
- 移动 L2/L3
- 给 scene 批量指定 `category_id`

但有一个重要缺口：`POST /categories` 当前只接收 `name / parent_id / sort_order`，没有接收 `code`。因此页面新建出来的分类，`code` 可能为空。

这会导致两个后果：

1. 前端可以显示这个分类，但无法稳定用 `category_code` 引用它
2. CSV 导入无法通过 `category_code` 精确导入到这个新分类

所以“分类树能动态更新”是真的，但“分类 code 能动态维护”还没有完全闭环。

---

## 六、CSV 导入时分类如何动态归类

CSV 导入优先看 `category_code`：

```text
category_code → speech_categories.code → category_id
```

如果 `category_code` 不为空但找不到，会记录错误并跳过该行：

```text
第 N 行 category_code 'xxx' 未找到对应分类
```

如果 `category_code` 为空，则走老逻辑：

```text
intervention_scene/question_type → normalize_scene_key → SCENE_CATEGORY_MAP[scene_key] → L3 中文名 → category_id
```

这条 fallback 依赖中文 L3 名称，例如 `食物选择建议`。如果运营重命名了 L3，或者新增了一个完全不在 `SCENE_CATEGORY_MAP` 的分类，fallback 就不可靠。

因此，CSV 的推荐规则是：

1. 新分类先确保有稳定 `code`
2. CSV 显式填写 `category_code`
3. 不依赖 `SCENE_CATEGORY_MAP` 自动猜

---

## 七、当前风险清单

| 风险 | 当前表现 | 影响 | 建议 |
|---|---|---|---|
| 未知 RAG 标签 | 单条编辑会返回 `dropped_values`，CSV 目前可能静默忽略 | 运营以为填了，RAG 实际没用上 | CSV dry-run 增加 unknown tag warning |
| `allow-create` 误导 | 前端允许输入新值，但新值不一定保存为正式标签 | 用户心智混乱 | 改成“申请新增标签”或保存前明确提示 |
| 新分类无 code | 页面新建分类只填 name | CSV 无法用 `category_code` 指向新分类 | 分类创建接口和 UI 增加 `code` |
| `SCENE_CATEGORY_MAP` fallback 依赖中文名 | L3 重命名后 fallback 可能失效 | CSV 自动归类漂移 | fallback 逐步改成 code，CSV 强推 `category_code` |
| 标签扩展无业务审批 | admin 接口能直接新增 tag | 词表可能膨胀、重复 | 增加标签申请/审核/合并流程 |
| 新标签不等于新 scene_key | RAG 标签扩了，但业务触发 key 没扩 | 话术触发和分类混淆 | 文档和 UI 明确区分“RAG 标签”和“业务场景” |

---

## 八、建议落地顺序

### Phase A：先把运营心智讲清楚

1. 在话术编辑抽屉里把 `allow-create` 的 placeholder 改成“选择正式标签；新标签需先申请”
2. 后端返回 `dropped_values` 时，前端用中文解释：哪些值未进入正式词表
3. 在 `docs/shujubiaozhu/话术标注规范.md` 增加“未知标签处理规则”

### Phase B：补 CSV 预检闭环

1. CSV dry-run 输出 unknown tag warnings
2. warnings 不一定阻断导入，但要显示在导入结果里
3. 对 `category_code` 不存在继续保持 error + skip

### Phase C：补分类 code 管理

1. `CategoryCreateReq` 增加 `code`
2. `CategoryUpdateReq` 支持 admin 修改 code
3. 前端新建/编辑分类时显示 code
4. 校验 code 唯一、格式合法、层级前缀合理

### Phase D：标签管理产品化

1. 做一个 RAG 标签管理页，按 dimension 管理
2. 支持新增、禁用、别名维护
3. 支持查看某个 tag 被多少话术引用
4. 合并 tag 时批量迁移历史 `metadata_json`

---

## 九、项目负责人视角

**已经能做什么**

- 下拉列表可以从后端词表动态读取
- admin 可以通过接口新增正式 RAG 标签
- 种子分类已经有稳定 `category_code`
- CSV 已支持显式 `category_code` 精确归类
- 页面分类树可以动态读取、新建、重命名、移动

**半能做什么**

- 用户可以在下拉框输入新词，但系统不会自动把它变成正式标签
- 页面可以新建分类，但新分类的 `code` 还没有 UI 闭环
- CSV 能用 `category_code`，但前提是分类已经有 code

**还不能做什么**

- 不能让运营随便输入一个未知客户目标并立即成为正式检索维度
- 不能保证 CSV 中未知标签都被明确报告
- 不能仅靠新建分类中文名，就让 CSV 稳定导入到该分类

**当前 blocker**

- 标签扩展和分类 code 管理都有后端底座，但缺少面向运营的 UI 和审核流程
- CSV unknown tag warning 还不完整，容易造成“填了但没生效”的误解

**下一步最值得做什么**

先补 CSV dry-run 的 unknown tag warning，再补分类 code 的创建/编辑入口。这样运营既能扩词表，也能稳定导入新分类，不会继续依赖中文名和隐式猜测。
