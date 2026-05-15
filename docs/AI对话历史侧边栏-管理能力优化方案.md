# AI 对话历史侧边栏 — 管理能力优化方案

> 调研日期：2026-05-13  
> 调研范围：客户档案页 AI 教练助手 → 历史对话侧边栏  
> 出发点：教练反馈"右键不能重命名"，但实际问题更深 — 当前侧边栏完全是只读列表，缺少教练管理需要的所有交互能力

---

## 1. 问题描述（用户视角）

> "侧边栏历史对话框，点击右键，不能修改名称【重命名】，不方便客户管理"

教练把这个问题描述为"重命名缺失"，但深入排查后发现，**这只是水面上的一个症状，水下还有一整套缺失的管理能力**。

---

## 2. 现状真值（代码视角）

### 2.1 后端真值

**模型**（文件：`app/crm_profile/models.py`）：
```python
class CrmAiSession(Base):
    __tablename__ = "crm_ai_sessions"
    session_id        # 主键
    local_user_id     # 教练ID
    crm_admin_id      # 关联管理员
    crm_customer_id   # 客户ID
    entry_scene       # 进入场景：customer_profile / quick_prompt / customer_list
    scene_key         # 场景策略
    output_style      # 输出风格
    prompt_version    # Prompt 版本
    prompt_hash       # Prompt 哈希
    created_at
```

**关键缺字段**：
- ❌ `title` / `display_name` — 无自定义标题
- ❌ `is_pinned` — 无置顶
- ❌ `is_archived` / `is_deleted` — 无归档/软删
- ❌ `tags` — 无标签
- ❌ `folder_id` / `group_id` — 无分组
- ❌ `last_active_at` — 没有"最后活动时间"独立字段（当前借 `created_at` + 关联消息）
- ❌ `summary` — 无 AI 自动总结的摘要

**API 端点现状**（文件：`app/crm_profile/routers/ai_config.py`）：

| 已有端点 | 能力 |
|---------|------|
| `GET /{customer_id}/ai/sessions` | 列出会话（最多 20 条） |
| `GET /{customer_id}/ai/sessions/{session_id}` | 获取单个会话详情 |

**完全缺失的端点**：
- ❌ `PATCH .../sessions/{session_id}` — 编辑标题/标签
- ❌ `DELETE .../sessions/{session_id}` — 删除会话
- ❌ `POST .../sessions/{session_id}/pin` — 置顶
- ❌ `POST .../sessions/{session_id}/archive` — 归档
- ❌ `GET .../sessions?search=xxx` — 搜索

### 2.2 前端真值

**侧边栏组件**（文件：`frontend/src/views/CrmProfile/components/AiSessionHistoryList.vue`）：

```vue
<button
  v-for="session in sessions"
  @click="$emit('select', session.session_id)"
>
  <!-- 时间 + 消息数 -->
  <!-- 末条预览（取最后一条消息内容前 N 字） -->
  <!-- 场景标签 + 会话ID短码 -->
</button>
```

**前端真值检查**：
- ❌ 没有 `@contextmenu` 监听 — 右键根本没接事件，所以不可能弹出菜单
- ❌ 没有 hover 时的快捷操作图标（编辑/删除/置顶）
- ❌ 没有搜索框
- ❌ 没有分组/筛选
- ❌ 没有"显示更多/分页/无限滚动"（硬编码 limit=20）
- ❌ 没有 loading skeleton（只有"正在加载历史对话..."文本）
- ✅ 有"开始新对话"按钮
- ✅ 当前会话高亮（is-active）

### 2.3 数据展示真值

当前每条会话展示的内容：
- **时间**：`MM-DD HH:mm` 格式
- **消息数**：`N 条消息`
- **预览**：最后一条消息内容截取（前 50 字左右）
- **场景**：`客户档案进入` / `快捷提问`
- **会话ID**：`会话 abc12345`（前 8 位 hash）

**问题**：
- 没有"标题"字段，教练只能靠"末条预览"+"时间"猜出这个会话是聊什么的
- 一个客户聊了 20 次，每次都问类似问题，列表里末条预览全是相似的，根本分不清
- 同一天聊多次，时间 `05-13 14:30`/`05-13 14:55` 也分不清主题

---

## 3. 教练真实使用场景诊断

### 3.1 教练每天怎么用历史对话

通过对话流和数据推测教练的真实场景：

| 场景 | 频率 | 当前痛点 |
|------|------|---------|
| 接到客户问题 → 找上次同类问题怎么回的 | 高频 | 只能往上翻，找不到关键词 |
| 阶段性复盘客户：跟进了哪些问题 | 中频 | 没有按主题归类 |
| 整理一份"客户经典案例"给同事参考 | 中频 | 不能把会话标记/导出 |
| 跨客户找同类问题：比如"血糖偏高时教练怎么应对" | 中频 | 不能跨客户搜索 |
| 删除测试/无意义的会话 | 中频 | 完全不能删 |
| 把重要问答置顶以便随时查看 | 中频 | 完全不能置顶 |

### 3.2 教练理想中的侧边栏（用户语言）

教练表达的是"重命名"，但他实际想要的能力栈大概是：

> "这个客户最近问了 30 次，我想：
> - 给重要的几次起个名字（比如'血糖飙升应对方案'）
> - 把它们置顶在最上面
> - 测试用的、聊废了的能删掉
> - 按'血糖''饮食''心理'这种主题分组
> - 输入'血糖'能搜出所有相关会话
> - 每次新建对话能选'继续上次的'还是'开新主题'"

---

## 4. 优化方案设计

### 4.1 设计原则

1. **数据无损**：所有"删除"先做软删，可恢复（教练操作时容错）
2. **零迁移成本**：新增字段都给默认值，老会话能继续用
3. **AI 辅助**：标题不要求教练手动起，由 AI 自动生成首句话作为兜底
4. **渐进交互**：MVP 只做最高频功能（重命名+删除+置顶+搜索），后续再加分组
5. **遵循 AGENTS.md 工程规范**：后端按 `app/crm_profile/{routers,services}/` 分层，前端按 `views/CrmProfile/{components,composables}/` 分层

---

### 4.2 数据模型扩展

`CrmAiSession` 新增字段（迁移用 `schema_migrations.py` 的现有惯例添加列）：

| 字段 | 类型 | 默认值 | 用途 |
|------|------|-------|------|
| `title` | `String(120)` | NULL | 教练自定义标题 |
| `auto_title` | `String(120)` | NULL | AI 自动生成的标题（由首条用户消息提炼） |
| `is_pinned` | `Boolean` | FALSE | 是否置顶 |
| `pinned_at` | `DateTime` | NULL | 置顶时间，决定置顶组排序 |
| `is_deleted` | `Boolean` | FALSE | 软删标记 |
| `deleted_at` | `DateTime` | NULL | 软删时间 |
| `last_active_at` | `DateTime` | NULL | 最后一条消息时间（写消息时同步更新） |
| `tags_json` | `Text` | NULL | JSON 数组，未来扩展（MVP 不暴露） |

**展示标题的取数优先级**：
```
session.title > session.auto_title > "末条预览前 20 字" > 时间戳
```

---

### 4.3 后端 API 设计

按 AGENTS.md 的"按资源拆分路由文件"规范，新建 `app/crm_profile/routers/ai_session.py`，从现有 `ai_config.py` 中把 sessions 相关迁过去（保持 ai_config.py 只管配置类）。

```python
# app/crm_profile/routers/ai_session.py
GET    /v1/crm-customers/{customer_id}/ai/sessions
       ?keyword=&pinned=&include_deleted=false&limit=&offset=
PATCH  /v1/crm-customers/{customer_id}/ai/sessions/{session_id}
       body: { title?: str, is_pinned?: bool }
DELETE /v1/crm-customers/{customer_id}/ai/sessions/{session_id}
       (soft delete by default; ?hard=true for permanent — admin only)
POST   /v1/crm-customers/{customer_id}/ai/sessions/{session_id}/restore
       (撤销软删，30 天内可恢复)
POST   /v1/crm-customers/{customer_id}/ai/sessions/{session_id}/auto-title
       (强制重新生成 AI 自动标题)
```

服务层（按规范拆 `services/ai/_session_admin.py` 等子模块，避免 audit.py 膨胀）：

```
app/crm_profile/services/
└── ai/
    ├── __init__.py            # 现有 chat/stream
    ├── _prepare.py            # 现有
    ├── _session_admin.py      # 新增：标题/置顶/删除
    └── _auto_title.py         # 新增：调小模型生成标题
```

权限：
- 教练自己的会话才能改/删（`session.local_user_id == current_user.id`）
- 管理员可以管理任意会话（`require_permission(user, 'crm_profile_admin')`）
- 软删 30 天后做硬清理（用现有 `app/celery_app.py` 加定时任务）

---

### 4.4 前端交互设计

#### 4.4.1 列表项交互改造（`AiSessionHistoryList.vue`）

**hover 时显示快捷操作图标**（避免完全依赖右键，移动端友好）：
```
┌─────────────────────────────────────┐
│ 📌 标题 / 末条预览                    │
│ 05-13 14:30  ·  12 条消息  · 客户档案 │ ⋯  ← hover 时显示
└─────────────────────────────────────┘
```

点击 `⋯` 弹下拉菜单 + 长按/右键也触发同一菜单：
- ✏️ 重命名
- 📌 置顶 / 取消置顶
- 🗑️ 删除（带二次确认）
- 📋 复制会话 ID（开发期间调试用）

#### 4.4.2 重命名交互

**优先用 inline edit 而不是弹窗**：
- 点击"重命名" → 当前标题变成 `<el-input>` → Enter 保存 / Esc 取消 / 失焦保存
- 留给 AI 自动生成的标题用浅色字（`auto_title` 兜底），用户输入后用深色字（`title` 优先）

#### 4.4.3 排序与分组

```
[置顶组]                ← is_pinned=true 的，按 pinned_at 倒序
  📌 重要主题 1
  📌 重要主题 2

[今天]                  ← 按 last_active_at 倒序
  对话 A
  对话 B

[本周]
[更早]
```

#### 4.4.4 搜索

顶部加搜索框：
```
┌─────────────────────┐
│ 🔍 搜索历史对话      │
└─────────────────────┘
```

后端搜索逻辑（`load_customer_sessions` 扩展）：
- LIKE 匹配 `title` / `auto_title`
- LIKE 匹配 `CrmAiMessage.content`（前 N 条消息内容里命中）
- 命中后高亮关键词

#### 4.4.5 状态机和确认弹窗

| 操作 | 确认方式 |
|------|---------|
| 重命名 | 无 — 静默保存 + 顶部 toast 提示 |
| 置顶 | 无 — 立即生效 + toast |
| 删除（软删） | 简单弹窗"确认删除？删除后 30 天内可恢复" |
| 还原 | 无 |
| 硬删 | 强弹窗"将永久删除该对话及全部消息记录，此操作不可逆" |

---

### 4.5 AI 自动生成标题（auto_title）

**触发时机**：
1. 第一次有用户消息写入时，异步触发
2. 用户也可手动"重新生成 AI 标题"

**实现方式**（`services/ai/_auto_title.py`）：

```python
async def generate_auto_title(session_id: str) -> str | None:
    # 1. 取该会话最早的 1-3 条用户消息
    msgs = audit.load_first_user_messages(session_id, limit=3)
    if not msgs:
        return None
    
    # 2. 用便宜的小模型（DeepSeek / GPT-4o-mini）做摘要
    prompt = "请为以下对话生成不超过 15 字的简短标题，直接输出标题，不要任何前缀。"
    content, _ = await chat_completion(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "\n".join(m["content"] for m in msgs)},
        ],
        temperature=0.3,
        max_tokens=40,
        model="gpt-4o-mini",  # 或便宜的国产小模型
    )
    
    # 3. 持久化到 session.auto_title
    audit.update_session_auto_title(session_id, _truncate(content, 60))
    return content
```

**调用时机**：
- 在 `stream_ai_coach_answer` 写完 user message 后用 `asyncio.create_task` 后台触发
- 不阻塞主流程

---

### 4.6 文件拆分计划（按 AGENTS.md 红线）

#### 4.6.1 后端

```
app/crm_profile/
├── routers/
│   ├── ai_config.py          # 瘦身：只留 config/profile-note/context-preview
│   └── ai_session.py         # 新增：sessions 相关全部端点
├── services/
│   └── ai/
│       ├── _session_admin.py # 新增：rename/pin/delete/restore
│       └── _auto_title.py    # 新增：AI 自动标题
├── schemas/api.py            # 扩 AiSessionUpdateRequest / AiSessionListItem
└── schema_migrations.py      # 新增 ensure_crm_ai_session_columns()
```

预计变化行数：
- `models.py` +8 行
- `routers/ai_session.py` 新文件 ~150 行
- `services/ai/_session_admin.py` 新文件 ~120 行
- `services/ai/_auto_title.py` 新文件 ~60 行
- `schema_migrations.py` +30 行（按现有 `ensure_crm_ai_attachment_indexes` 模式）

每个文件都在 300 行红线下，符合规范。

#### 4.6.2 前端

```
frontend/src/views/CrmProfile/
├── components/
│   ├── AiSessionHistoryList.vue       # 改：hover 操作 + inline edit + 分组渲染
│   ├── AiSessionItemMenu.vue          # 新：单条右键/⋯ 下拉菜单
│   └── AiSessionSearchBar.vue         # 新：搜索框
├── composables/
│   ├── useAiCoach.ts                  # 改：扩 rename/pin/delete actions
│   └── useAiSessionAdmin.ts           # 新：拆出会话管理逻辑（避免 useAiCoach 超 400 行）
```

`useAiCoach.ts` 当前已经 600+ 行，拆 `useAiSessionAdmin.ts` 是必要的。

---

### 4.7 迁移与兼容

**字段迁移**（按现有 `ensure_*_columns` 模式）：

```python
# schema_migrations.py
def ensure_crm_ai_session_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "crm_ai_sessions" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("crm_ai_sessions")}
    with engine.begin() as conn:
        if "title" not in cols:
            conn.execute(text("ALTER TABLE crm_ai_sessions ADD COLUMN title VARCHAR(120)"))
        if "auto_title" not in cols:
            conn.execute(text("ALTER TABLE crm_ai_sessions ADD COLUMN auto_title VARCHAR(120)"))
        if "is_pinned" not in cols:
            conn.execute(text("ALTER TABLE crm_ai_sessions ADD COLUMN is_pinned TINYINT(1) DEFAULT 0"))
        if "pinned_at" not in cols:
            conn.execute(text("ALTER TABLE crm_ai_sessions ADD COLUMN pinned_at DATETIME NULL"))
        if "is_deleted" not in cols:
            conn.execute(text("ALTER TABLE crm_ai_sessions ADD COLUMN is_deleted TINYINT(1) DEFAULT 0"))
        if "deleted_at" not in cols:
            conn.execute(text("ALTER TABLE crm_ai_sessions ADD COLUMN deleted_at DATETIME NULL"))
        if "last_active_at" not in cols:
            conn.execute(text("ALTER TABLE crm_ai_sessions ADD COLUMN last_active_at DATETIME NULL"))
```

**老数据兼容**：
- `last_active_at` 的回填用 SQL：`UPDATE crm_ai_sessions SET last_active_at = (SELECT MAX(created_at) FROM crm_ai_messages WHERE session_id = crm_ai_sessions.session_id)`
- `auto_title` 默认 NULL，前端兜底用现有的"末条预览"逻辑
- `is_deleted=0`、`is_pinned=0` 默认值保证老数据照常显示

---

## 5. 优先级与分期建议

按 AGENTS.md 的"先看现状、再拆任务、能并行时并行"思路：

### Phase 1（MVP，1.5 天）
**目标**：解决教练最高频的 3 个痛点：重命名 / 置顶 / 删除

- [ ] 后端：`title / is_pinned / is_deleted / last_active_at` 字段 + 迁移
- [ ] 后端：`PATCH /sessions/{id}`、`DELETE /sessions/{id}` 端点
- [ ] 后端：`load_customer_sessions` 改为按 `is_pinned DESC, last_active_at DESC` 排序，过滤 `is_deleted=0`
- [ ] 前端：列表项 hover 显示 ⋯ 菜单（重命名/置顶/删除）
- [ ] 前端：inline rename 交互
- [ ] 前端：删除前二次确认弹窗
- [ ] 前端：置顶分组渲染

### Phase 2（增强，2 天）
**目标**：搜索 + AI 自动标题

- [ ] 后端：search 参数 + LIKE 查询 + content 联合搜索
- [ ] 后端：`auto_title` 字段 + `_auto_title.py` 服务 + 后台任务
- [ ] 后端：在 `stream_ai_coach_answer` 写消息后触发 auto_title 生成
- [ ] 前端：搜索框 + 关键词高亮
- [ ] 前端：标题展示优先级（title > auto_title > 末条预览）

### Phase 3（管理增强，2-3 天）
**目标**：还原 / 硬删 / 时间分组

- [ ] 后端：`POST /sessions/{id}/restore` 端点
- [ ] 后端：硬删定时任务（30 天后清理 is_deleted 数据）
- [ ] 前端：回收站视图（管理员可见）
- [ ] 前端：列表按"今天/本周/更早"分组

### Phase 4（远期，按需）
- [ ] 标签 / 自定义分组
- [ ] 跨客户搜索（管理员视角）
- [ ] 会话导出（PDF / Markdown）
- [ ] 收藏夹

---

## 6. 验证清单（AGENTS.md 硬要求）

### 6.1 后端启动验证
```powershell
cd wecom_ops_console
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8099
```
关注：
- 数据库迁移正常（schema_migrations 添加列不报错）
- `ensure_crm_ai_session_columns` 在已有列上是幂等的（重启不重复 ALTER）
- 老会话能正常 list（默认值生效）

### 6.2 前端启动验证
```powershell
cd wecom_ops_console/frontend
npm run dev -- --port 5179
```
关注：
- TypeScript 编译通过
- 旧会话列表能展示（兜底标题逻辑生效）

### 6.3 Focused Validation 场景

| 场景 | 预期 |
|------|------|
| 老会话刷新打开 | 标题位置显示"末条预览前 N 字" |
| 点击 ⋯ → 重命名 → Enter | 列表标题立即更新，刷新后保留 |
| 点击置顶 | 该条移到列表最上方，且加 📌 图标 |
| 删除 → 确认 | 该条从列表消失，DB 中 `is_deleted=1, deleted_at=now()` |
| 同会话再次发消息 | `last_active_at` 更新，回到列表上方（非置顶组） |
| 搜索 "血糖" | 标题或消息内容含此词的会话被列出 |
| 教练 A 试图改教练 B 的会话 | 返回 403 |

### 6.4 回归检查
- 现有会话进入流程不受影响（点击列表项仍然能恢复对话）
- 新对话创建后立即出现在列表顶部
- AI 流式回复完成后会话标题被自动生成（Phase 2 后）

---

## 7. 工程经验沉淀（memory.md 候选）

1. **"右键不能"≠"加个右键监听"**：用户用业务语言描述需求时，工程上应往后看一层 — 缺的是整套管理能力，不是单个 contextmenu
2. **软删 + 定时硬清是会话类数据的标配**：教练误删恢复的诉求很常见
3. **AI 辅助标题应该是"兜底+可覆盖"**：用户输入的优先级永远高于 AI 生成
4. **字段迁移用 `ensure_*_columns` 幂等模式**：项目已有惯例，避免引入 alembic 等重型方案
5. **前端 composable 拆分阈值**：当一个 composable 超过 400 行（如 `useAiCoach.ts` 已超 600 行），优先按"管理动作 / 状态读取"切分

---

## 8. 面向项目负责人的状态翻译

### 看见
教练用户档案页可以看到客户的 AI 对话历史侧边栏，能切回任意一次对话继续聊。

### 理解
当前侧边栏是只读列表，没有任何管理能力 — 教练不能给会话起名、不能删除、不能置顶、不能搜索。教练表达的"右键不能重命名"只是症状，本质问题是**整个会话管理体系缺失**。

### 决策
**Phase 1（1.5 天）就能解决 80% 痛点**：重命名 + 置顶 + 删除，加上 hover 操作 UI。这部分技术风险低、改动可控、立即对教练日常工作有帮助。  
**Phase 2（2 天）做 AI 自动标题 + 搜索**：把"列表里全是相似预览"这个根本观感问题彻底解决。

### 闭环
- 数据库字段加迁移（不动老数据）
- 后端按 routers/services 分层新增（不动现有 audit/chat 流程）
- 前端按 components/composables 分层新增（useAiCoach 拆分）
- 软删 + 30 天恢复期 → 误删可救

### 当前 Blocker
无 — 这是一个**纯增量功能**，不依赖其他模块，可以立刻开工。

### 下一步最值得做什么
今天就启动 Phase 1，预计 1.5 天交付教练可用版本。等 Phase 1 收口后再决策 Phase 2/3 的优先级。

---

## 9. 代码文件索引

### 当前涉及的文件
| 文件 | 当前职责 | Phase 1 改动 |
|------|---------|-------------|
| `app/crm_profile/models.py` | `CrmAiSession` 定义 | +6 字段 |
| `app/crm_profile/routers/ai_config.py` | sessions 路由 | 迁出到 ai_session.py |
| `app/crm_profile/services/audit.py` | `load_customer_sessions` | 改排序+过滤 |
| `app/crm_profile/schema_migrations.py` | 迁移惯例 | 加 ensure 函数 |
| `frontend/.../components/AiSessionHistoryList.vue` | 列表渲染 | 加 hover 菜单+inline edit |
| `frontend/.../composables/useAiCoach.ts` | 会话状态 | 拆出 useAiSessionAdmin |

### 新增文件
| 文件 | 职责 |
|------|------|
| `app/crm_profile/routers/ai_session.py` | 会话管理端点 |
| `app/crm_profile/services/ai/_session_admin.py` | rename / pin / delete 业务逻辑 |
| `app/crm_profile/services/ai/_auto_title.py` | AI 自动标题（Phase 2） |
| `frontend/.../components/AiSessionItemMenu.vue` | 单条菜单组件 |
| `frontend/.../components/AiSessionSearchBar.vue` | 搜索框（Phase 2） |
| `frontend/.../composables/useAiSessionAdmin.ts` | 会话管理状态/动作 |
