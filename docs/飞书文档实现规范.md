# 飞书文档实现规格说明

> 日期：2026-04-24
>
> 关联文档：`docs/FEISHU_DOCS_INFORMATION_ARCHITECTURE_PLAN.md`
>
> 结论口径：本文档是“飞书文档”模块的详细实现规格，用于指导后续开发排期、接口定义、页面拆分和迁移落地，不代表功能已经正式完成。

---

## 1. 文档目标

这份文档解决两个问题：

1. 把方案文档里的“推荐方向”翻译成可以直接研发的结构。
2. 把后端、前端、迁移、验收统一成一套正式口径，减少后续反复对齐。

本文档默认坚持以下边界：

1. “飞书文档”只做外部文档入口、维护、归档、关系管理和使用引导。
2. 系统内不做飞书正文预览。
3. 系统内不做飞书正文编辑。
4. 用户点击后仍跳转飞书。

---

## 2. 当前正式真值与改造目标

### 2.1 当前正式真值

当前仓库中的正式实现主要有 3 个点：

1. `app/models.py` 中的 `SopDocument`
2. `app/routers/api_sop.py`
3. `frontend/src/views/SopDocuments.vue`

当前只支持：

1. 标题
2. 分类
3. 链接
4. 描述
5. 简单增删改查

### 2.2 目标状态

目标不是把现有列表页做复杂，而是把它升级成：

1. 以“工作台”作为主入口
2. 以“文档资源”作为本体真值
3. 以“绑定关系”表达阶段、角色、产物类型
4. 以“治理视图”收口待整理、待校验、重复与缺口

---

## 3. 研发范围

### 3.1 本期纳入研发范围

1. 新数据模型
2. 新接口组
3. 新首页
4. 工作台详情页
5. 快速登记文档弹窗
6. 基础治理页
7. 旧数据迁移

### 3.2 本期明确不纳入

1. 飞书正文同步
2. 系统内富文本阅读
3. 飞书评论/权限联动
4. 自动抓飞书全文做全文索引
5. 复杂审批链

---

## 4. 数据模型详细规格

### 4.1 枚举约定

#### `source_platform`

1. `feishu`
2. `unknown`

#### `doc_type`

1. `doc`
2. `sheet`
3. `bitable`
4. `wiki`
5. `folder`
6. `unknown`

#### `resource_status`

1. `active`
2. `archived`
3. `invalid`

#### `verification_status`

1. `verified`
2. `unverified`
3. `broken`
4. `need_check`

#### `workspace_type`

1. `project`
2. `campaign`
3. `customer`
4. `template_hub`
5. `inbox`

#### `workspace_status`

1. `planning`
2. `running`
3. `reviewing`
4. `archived`

#### `relation_role`

1. `official`
2. `support`
3. `candidate`
4. `archive`

#### `binding_status`

1. `active`
2. `inactive`
3. `archived`

#### `term_dimension`

1. `stage`
2. `deliverable_type`
3. `function_topic`
4. `audience_role`
5. `channel_or_scene`
6. `legacy_category`

#### `term_scope_type`

1. `global`
2. `biz_line`
3. `workspace`

---

### 4.2 表结构草案

#### 表：`external_doc_resources`

```sql
CREATE TABLE external_doc_resources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title VARCHAR(128) NOT NULL,
  canonical_url TEXT NOT NULL,
  canonical_url_hash CHAR(64) NOT NULL,
  open_url TEXT NOT NULL,
  source_platform VARCHAR(32) NOT NULL DEFAULT 'feishu',
  source_doc_token VARCHAR(128),
  doc_type VARCHAR(32) NOT NULL DEFAULT 'unknown',
  summary VARCHAR(255) NOT NULL DEFAULT '',
  access_scope VARCHAR(32) NOT NULL DEFAULT 'unknown',
  owner_user_id INTEGER NULL,
  maintainer_user_id INTEGER NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  verification_status VARCHAR(32) NOT NULL DEFAULT 'unverified',
  last_verified_at DATETIME NULL,
  last_opened_at DATETIME NULL,
  extra_meta_json TEXT NULL,
  created_by INTEGER NULL,
  updated_by INTEGER NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引与约束建议：

```sql
CREATE UNIQUE INDEX uq_external_doc_resource_source
ON external_doc_resources(source_platform, source_doc_token, doc_type);

CREATE UNIQUE INDEX uq_external_doc_resource_canonical_hash
ON external_doc_resources(canonical_url_hash);

CREATE INDEX idx_external_doc_resources_status
ON external_doc_resources(status);

CREATE INDEX idx_external_doc_resources_owner
ON external_doc_resources(owner_user_id);

CREATE INDEX idx_external_doc_resources_maintainer
ON external_doc_resources(maintainer_user_id);
```

说明：

1. `canonical_url` 用于资源识别和去重。
2. `open_url` 用于用户点击跳转。
3. `canonical_url_hash` 是 `canonical_url` 的标准化哈希，用于兜底防重。
4. 如果短期拿不到稳定 `source_doc_token`，允许为空，但解析器应尽量提取。
5. 后端写入前仍应做一次显式 `canonical_url` 查重，不能只依赖数据库唯一约束。

#### 表：`external_doc_workspaces`

```sql
CREATE TABLE external_doc_workspaces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name VARCHAR(128) NOT NULL,
  workspace_type VARCHAR(32) NOT NULL DEFAULT 'project',
  biz_line VARCHAR(64) NULL,
  client_name VARCHAR(64) NULL,
  owner_user_id INTEGER NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'planning',
  current_stage_term_id INTEGER NULL,
  description VARCHAR(255) NOT NULL DEFAULT '',
  start_date DATE NULL,
  end_date DATE NULL,
  created_by INTEGER NULL,
  updated_by INTEGER NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

说明：

1. 必须初始化一个系统工作台：`inbox`
2. 历史迁移数据默认先进入 `inbox`

#### 表：`external_doc_terms`

```sql
CREATE TABLE external_doc_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dimension VARCHAR(32) NOT NULL,
  code VARCHAR(64) NOT NULL,
  label VARCHAR(64) NOT NULL,
  scope_type VARCHAR(32) NOT NULL DEFAULT 'global',
  scope_id INTEGER NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引与约束建议：

```sql
CREATE UNIQUE INDEX uq_external_doc_terms
ON external_doc_terms(dimension, code, scope_type, scope_id);
```

#### 表：`external_doc_bindings`

```sql
CREATE TABLE external_doc_bindings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  resource_id INTEGER NOT NULL,
  workspace_id INTEGER NULL,
  primary_stage_term_id INTEGER NULL,
  deliverable_term_id INTEGER NULL,
  relation_role VARCHAR(32) NOT NULL DEFAULT 'support',
  is_primary INTEGER NOT NULL DEFAULT 0,
  due_at DATETIME NULL,
  remark VARCHAR(255) NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_by INTEGER NULL,
  updated_by INTEGER NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引建议：

```sql
CREATE INDEX idx_external_doc_bindings_workspace_role
ON external_doc_bindings(workspace_id, relation_role);

CREATE INDEX idx_external_doc_bindings_workspace_stage
ON external_doc_bindings(workspace_id, primary_stage_term_id);

CREATE INDEX idx_external_doc_bindings_resource
ON external_doc_bindings(resource_id);
```

业务约束说明：

1. 同一工作台 + 同一阶段 + 同一产物类型下，`official + is_primary=1` 只能有一条
2. 模板语义由 `workspace_type = template_hub` 表达，不再通过 `relation_role=template` 表达

#### 表：`external_doc_term_bindings`

```sql
CREATE TABLE external_doc_term_bindings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  resource_id INTEGER NOT NULL,
  term_id INTEGER NOT NULL,
  binding_type VARCHAR(32) NOT NULL DEFAULT 'secondary',
  created_at DATETIME NOT NULL
);
```

约束建议：

```sql
CREATE UNIQUE INDEX uq_external_doc_term_binding
ON external_doc_term_bindings(resource_id, term_id, binding_type);
```

#### 表：`external_doc_open_logs`

```sql
CREATE TABLE external_doc_open_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  resource_id INTEGER NOT NULL,
  workspace_id INTEGER NULL,
  opened_by INTEGER NULL,
  opened_at DATETIME NOT NULL,
  client_type VARCHAR(32) NULL
);
```

---

### 4.3 SQLAlchemy 模型拆分建议

建议落到：

1. `ExternalDocResource`
2. `ExternalDocWorkspace`
3. `ExternalDocTerm`
4. `ExternalDocBinding`
5. `ExternalDocTermBinding`
6. `ExternalDocOpenLog`

不建议继续把这条线写回 `SopDocument`。

### 4.4 模板语义正式口径

模板不再作为通用 `relation_role` 枚举值存在。

正式定义改为：

1. `template_hub` 是模板工作台
2. 某篇资源如果被沉淀为模板，本质上是新增一条指向模板工作台的 `binding`
3. 在模板工作台内部，这篇资源仍使用 `official / support / candidate / archive`
4. 原项目工作台里的绑定角色不应因为“沉淀为模板”被改写

这样做的好处是：

1. 模板和项目仍共用一套数据结构
2. 不会出现 `workspace_type=template_hub` 和 `relation_role=template` 双重真值
3. 后续模板复制、模板推荐、模板治理会更顺

### 4.5 软删除与级联策略

正式约束：

1. `workspace` 删除或撤销时，优先做软删除或归档，不做物理删除
2. `workspace` 归档时，其下 `binding.status` 应级联更新为 `archived` 或 `inactive`
3. `resource` 不允许因 `workspace` 被删除而级联物理删除
4. 只有当 `resource` 没有任何有效 `binding` 时，才允许进入单独的清理流程
5. `open_logs` 作为行为留痕，可保留，不要求级联清理

---

## 5. 初始化与种子数据规格

### 5.1 系统初始化必须创建

1. `inbox` 工作台
2. 默认阶段字典
3. 默认产物类型字典
4. 默认 `legacy_category` 字典

### 5.2 默认阶段建议

1. `lead_intake`
   - 线索接入
2. `solution_design`
   - 方案设计
3. `launch_preparation`
   - 启动准备
4. `delivery_running`
   - 执行中
5. `mid_review`
   - 中期复盘
6. `final_delivery`
   - 结项交付

### 5.3 默认产物类型建议

1. `positioning_sheet`
2. `schedule_sheet`
3. `daily_report`
4. `weekly_review`
5. `material_list`
6. `script_sheet`
7. `replay_sheet`
8. `delivery_checklist`

### 5.4 旧分类映射

当前旧分类：

1. `运营流程`
2. `话术库`
3. `经验库`
4. `营养知识`
5. `培训手册`
6. `其他`

在迁移中应进入 `legacy_category` 维度，不直接当成新正式分类真值。

---

## 6. API 详细规格

### 6.1 `POST /api/v1/external-docs/resources/resolve-link`

用途：粘贴飞书链接后，尝试解析基础信息。

请求：

```json
{
  "url": "https://example.feishu.cn/docx/abc123"
}
```

响应：

```json
{
  "ok": true,
  "platform": "feishu",
  "doc_type": "doc",
  "source_doc_token": "abc123",
  "canonical_url": "https://example.feishu.cn/docx/abc123",
  "open_url": "https://example.feishu.cn/docx/abc123",
  "title_hint": "",
  "needs_manual_title": true,
  "warnings": []
}
```

规则：

1. 第一阶段允许只解析 URL 结构，不强依赖飞书开放平台
2. 如果拿不到标题，则前端要求用户手填标题
3. 如果解析失败，返回 `ok=false` 并允许用户手动录入

### 6.2 `POST /api/v1/external-docs/resources`

用途：创建文档资源。

请求：

```json
{
  "title": "CCM 减脂营项目定位表",
  "canonical_url": "https://example.feishu.cn/docx/abc123",
  "canonical_url_hash": "sha256:xxxxx",
  "open_url": "https://example.feishu.cn/docx/abc123",
  "source_platform": "feishu",
  "source_doc_token": "abc123",
  "doc_type": "doc",
  "summary": "项目定位与目标约束",
  "owner_user_id": 1,
  "maintainer_user_id": 1
}
```

响应：

```json
{
  "id": 101,
  "title": "CCM 减脂营项目定位表",
  "source_platform": "feishu",
  "doc_type": "doc",
  "status": "active",
  "verification_status": "unverified",
  "created_at": "2026-04-24T10:00:00+08:00",
  "updated_at": "2026-04-24T10:00:00+08:00"
}
```

说明：

1. 这是底层资源接口，适合后台治理、脚本导入、后续批量能力复用
2. 前台“快速登记文档”主链路不建议直接串行调用它和绑定接口，而应走事务型组合接口

### 6.3 `POST /api/v1/external-docs/quick-add`

用途：在一个事务内完成“资源查重复用或创建” + “创建绑定”，避免孤儿资源。

请求：

```json
{
  "resource": {
    "title": "CCM 减脂营项目定位表",
    "canonical_url": "https://example.feishu.cn/docx/abc123",
    "open_url": "https://example.feishu.cn/docx/abc123",
    "source_platform": "feishu",
    "source_doc_token": "abc123",
    "doc_type": "doc",
    "summary": "项目定位与目标约束",
    "owner_user_id": 1,
    "maintainer_user_id": 1
  },
  "binding": {
    "workspace_id": 12,
    "primary_stage_term_id": 3,
    "deliverable_term_id": 10,
    "relation_role": "official",
    "is_primary": true,
    "remark": "开营前统一使用这一版"
  },
  "open_after_save": false
}
```

响应：

```json
{
  "resource": {
    "id": 101,
    "title": "CCM 减脂营项目定位表",
    "dedupe_mode": "matched_by_source_token"
  },
  "binding": {
    "id": 501,
    "workspace_id": 12,
    "relation_role": "official",
    "is_primary": true
  },
  "open_url": null
}
```

事务规则：

1. 先按 `source_platform + source_doc_token + doc_type` 查重
2. 如果 `source_doc_token` 缺失，则按标准化后的 `canonical_url` 查重
3. 找到资源则复用，找不到则创建
4. 创建绑定失败则整笔事务回滚，不留下孤儿资源
5. 这个接口是前台“快速登记文档”的正式主入口

### 6.4 `POST /api/v1/external-docs/bindings`

用途：把资源挂到某个工作台和阶段中。

请求：

```json
{
  "resource_id": 101,
  "workspace_id": 12,
  "primary_stage_term_id": 3,
  "deliverable_term_id": 10,
  "relation_role": "official",
  "is_primary": true,
  "remark": "开营前统一使用这一版"
}
```

响应：

```json
{
  "id": 501,
  "resource_id": 101,
  "workspace_id": 12,
  "relation_role": "official",
  "is_primary": true,
  "status": "active"
}
```

说明：

1. 这是底层绑定接口，适合资源已存在时单独补挂载
2. 对普通前台新增链路，不建议优先暴露这条接口

### 6.5 `GET /api/v1/external-docs/workspaces/{id}/overview`

用途：返回工作台概览。

响应建议：

```json
{
  "workspace": {
    "id": 12,
    "name": "2026Q2 减脂营专项",
    "workspace_type": "project",
    "status": "running",
    "current_stage": {
      "id": 4,
      "code": "delivery_running",
      "label": "执行中"
    },
    "owner": {
      "id": 1,
      "name": "张三"
    }
  },
  "stages": [
    {
      "term": {
        "id": 3,
        "code": "launch_preparation",
        "label": "启动准备"
      },
      "official_docs": [],
      "support_docs": [],
      "candidate_docs": []
    }
  ],
  "recent_updates": [],
  "governance_flags": [
    {
      "type": "missing_official_doc",
      "label": "当前阶段缺少正式文档"
    }
  ]
}
```

### 6.6 `POST /api/v1/external-docs/resources/{id}/open`

用途：记录打开行为，并返回跳转地址。

请求：

```json
{
  "workspace_id": 12,
  "client_type": "web"
}
```

响应：

```json
{
  "open_url": "https://example.feishu.cn/docx/abc123",
  "opened_at": "2026-04-24T10:30:00+08:00"
}
```

规则：

1. 后端只做记录，不做代理转发
2. 前端拿到 `open_url` 后新标签页打开

### 6.7 `GET /api/v1/external-docs/governance/queue`

用途：返回治理队列。

响应建议：

```json
{
  "needs_sorting": [],
  "needs_verification": [],
  "duplicate_primary_docs": [],
  "missing_official_docs": []
}
```

---

## 7. 前端页面与线框规格

### 7.1 页面清单

1. 飞书文档首页
2. 工作台详情页
3. 治理页
4. 快速登记弹窗

### 7.2 首页线框

```text
+-----------------------------------------------------------+
| 飞书文档                                                  |
| 搜索框                         [快速登记] [治理队列]       |
+-----------------------------------------------------------+
| 我负责的工作台                                            |
| [工作台卡片] [工作台卡片] [工作台卡片]                    |
+-----------------------------------------------------------+
| 最近打开                                                  |
| [文档卡片] [文档卡片] [文档卡片]                          |
+-----------------------------------------------------------+
| 当前阶段必用文档                                          |
| [official 文档卡片] [official 文档卡片]                   |
+-----------------------------------------------------------+
| 模板中心入口                | 待整理 / 待校验提醒         |
+-----------------------------------------------------------+
```

设计原则：

1. 先展示任务入口
2. 再展示治理提醒
3. 不先把所有筛选器砸给用户

### 7.3 工作台详情页线框

```text
+-----------------------------------------------------------+
| 2026Q2 减脂营专项                                         |
| 负责人：张三   当前阶段：执行中   状态：进行中             |
| [快速登记文档] [编辑工作台]                               |
+-----------------------------------------------------------+
| 启动准备                                                  |
| official: [卡片]                                          |
| support : [卡片] [卡片]                                   |
| candidate: [卡片]                                         |
+-----------------------------------------------------------+
| 执行中                                                    |
| official: [卡片] [卡片]                                   |
| support : [卡片]                                          |
+-----------------------------------------------------------+
| 最近更新                  | 推荐模板                      |
+-----------------------------------------------------------+
| 历史归档                                                  |
+-----------------------------------------------------------+
```

### 7.4 快速登记弹窗线框

```text
+-----------------------------------------------+
| 快速登记飞书文档                              |
+-----------------------------------------------+
| 飞书链接 [______________________________]     |
| [解析链接]                                   |
| 标题     [______________________________]     |
| 工作台   [下拉选择]                           |
| 阶段     [下拉选择]                           |
| 角色     [official/support/candidate/archive] |
| 负责人   [下拉选择]                           |
| 摘要     [______________________________]     |
| 备注     [______________________________]     |
|                         [取消] [保存并打开]   |
+-----------------------------------------------+
```

交互规则：

1. 解析成功后自动填充标题建议和资源信息
2. 解析失败也允许继续手工填写
3. 默认角色建议为 `support`
4. `official` 被选中时要做更显眼提示
5. 如果当前选择的是模板工作台，界面文案应明确提示“你正在把这篇资源沉淀到模板中心”

### 7.5 治理页线框

```text
+-----------------------------------------------------------+
| 治理页                                                    |
| [待整理] [待校验] [重复主文档] [缺少正式文档]            |
+-----------------------------------------------------------+
| 列表 / 表格                                               |
| 资源标题 | 工作台 | 阶段 | 问题类型 | 操作               |
+-----------------------------------------------------------+
```

---

## 8. 前端组件拆分规格

建议目录：

```text
frontend/src/views/SopDocs/
  index.vue
  WorkspaceDetail.vue
  Governance.vue
  components/
    WorkspaceCard.vue
    ResourceCard.vue
    StageSection.vue
    QuickAddDialog.vue
    FilterBar.vue
    GovernanceTable.vue
  composables/
    useSopDocsHome.ts
    useWorkspaceDetail.ts
    useGovernance.ts
    useQuickAdd.ts
  styles/
    sopDocs.css
```

组件职责：

1. `WorkspaceCard`
   - 首页工作台卡片
2. `ResourceCard`
   - 文档资源展示卡片
3. `StageSection`
   - 按阶段渲染 `official/support/candidate`
4. `QuickAddDialog`
   - 快速登记文档
5. `GovernanceTable`
   - 治理页表格

---

## 9. 迁移脚本规格

### 9.1 迁移输入

旧表：`sop_documents`

旧字段：

1. `id`
2. `title`
3. `category`
4. `url`
5. `description`
6. `sort_order`
7. `created_by`
8. `created_at`
9. `updated_at`

### 9.2 迁移输出

1. `external_doc_resources`
2. `external_doc_bindings`
3. `external_doc_terms`
4. `external_doc_workspaces`

### 9.3 迁移规则

每一条旧 `sop_documents` 记录：

1. 先生成一条 `external_doc_resources`
2. `title -> title`
3. `url -> canonical_url/open_url`
4. `description -> summary`
5. `created_by -> created_by/updated_by`
6. `category -> legacy_category term`
7. 绑定一条到 `inbox` 工作台的 `external_doc_bindings`
8. 默认 `relation_role = support`
9. 默认 `status = active`
10. 默认 `verification_status = unverified`

### 9.4 迁移脚本输出日志建议

迁移脚本应输出：

1. 总资源数
2. 成功迁移数
3. 解析失败数
4. 重复链接数
5. 迁入 `inbox` 数
6. 每个旧分类迁移数量

---

## 10. 开发分期建议

### Phase 1：数据层与后端骨架

目标：

1. 新表可用
2. 新接口可跑
3. 旧数据可迁

交付：

1. SQLAlchemy 模型
2. 路由与 schema
3. 迁移脚本
4. 基础种子数据

### Phase 2：前端首页与快速登记

目标：

1. 用户能通过新入口管理和打开文档
2. 用户能快速登记文档

交付：

1. 首页
2. 快速登记弹窗
3. 打开行为记录

### Phase 3：工作台详情与治理页

目标：

1. 用户能围绕工作台查看文档
2. 管理员能开始做基础治理

交付：

1. 工作台详情页
2. 治理页
3. 异常提示和治理接口

---

## 11. 验证清单

### 11.1 focused validation

1. 迁移后旧链接是否都能看到
2. `resolve-link` 对常见飞书链接解析是否稳定
3. 同一链接重复录入是否正确去重
4. 新标签页打开是否正常
5. 首页是否确实先服务高频入口而非复杂筛选
6. 工作台详情是否能按阶段和角色区分展示
7. 治理页是否能看到待整理与待校验

### 11.2 启动验证

代码开发完成后必须执行：

1. 后端启动
   - `uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. 前端启动
   - `cd frontend && npm run dev`
3. 前端构建
   - `cd frontend && npm run build`

---

## 12. 当前最值得继续推进的下一步

基于这份规格，最适合马上继续落地的是：

1. 先做数据库模型与迁移脚本
2. 再做 `resolve-link / create resource / create binding / open` 四个最小接口
3. 再做首页和快速登记弹窗

这样可以最快把“旧分类链接库”升级成可用的新入口中心，同时保持研发范围可控。
