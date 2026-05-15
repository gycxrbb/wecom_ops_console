# AI 提示词加载架构调研报告

- **日期**: 2026-05-15
- **范围**: 提示词存储、加载、组装、管理全链路
- **目的**: 梳理提示词架构设计，明确灵活性边界

---

## 一、架构概览

提示词系统采用**六层组装**架构，最终发送给 LLM 的内容由多个层次拼接而成：

```
assemble_prompt() 组装结果
├── system #1:  L1/L2 base 层模板（所有已启用的基础模板拼接）
├── system #2:  L4 客户档案上下文（context_builder 自动聚合）
├── system #3:  L5 客户备注 + RAG 检索结果 + 场景提示（动态部分，分离以优化 prompt cache）
└── user:       L6 用户消息 + L3 style 层模板（输出风格提示）
```

| 层 | 来源 | 示例 |
|----|------|------|
| L1/L2 | base 层模板（DB 或 .md） | 平台护栏、健康教练核心角色 |
| L3 scene | scene 层模板（DB 或 .md） | 餐食审核、数据监测、QA 支持 |
| L3 style | style 层模板（DB 或 .md） | 教练简报、客户回复、交接备注 |
| L4 | context_builder.py 自动聚合 | 基本信息、健康档案、饮食记录 |
| L5 | CustomerAiProfileNote（DB） | 教练手写的客户补充信息 |
| L6 | 运行时用户消息 | 用户问题 + 附件描述 |

---

## 二、存储机制：数据库优先 + .md 文件兜底

### 三级解析链

```
内存缓存（60s TTL）
    ↓ 未命中
DB prompt_templates 表
    ↓ 不存在该 key
.md 文件兜底（app/crm_profile/prompts/*.md）
```

**核心代码**: `app/crm_profile/prompts/registry.py:114-137`

```python
def _load_prompt(layer: str, key: str, version: str | None = None) -> str:
    # 1. 查缓存
    # 2. 查 DB
    if row and row.is_active:
        return row.content
    if row and not row.is_active:
        return ""   # ← 关键：DB 中存在但已禁用 → 返回空，不兜底
    # 3. 兜底到 .md 文件
```

### 关键行为

- **DB 中存在且 `is_active=True`** → 使用 DB 内容
- **DB 中存在但 `is_active=False`** → 返回空字符串，**不回退到 .md**
- **DB 中不存在该 key** → 回退到 `app/crm_profile/prompts/{key}.md` 文件

这意味着提示词管理界面关闭一个模板后，它完全消失，不会被 .md 文件"复活"。

### 缓存策略

- 60 秒 TTL 内存缓存（`threading.Lock` 保护）
- 后台保存操作调用 `reload_prompt(key)` 或 `reload_all()` 主动失效
- 管理员编辑提示词后，最多 60 秒后生效（保存时主动失效则为即时生效）

---

## 三、数据库表结构

**文件**: `app/models_prompt.py`

### `prompt_templates` — 主表

| 字段 | 说明 |
|------|------|
| `layer` | 模板层级：`base` / `scene` / `style` |
| `key` | 唯一标识，如 `platform_guardrails`、`qa_support` |
| `label` | 显示名称，如"平台护栏"、"QA 支持" |
| `content` | 提示词正文（Markdown） |
| `version` | 当前版本号 |
| `is_active` | 是否启用 |

### `prompt_template_versions` — 版本历史

每次保存自动创建一条记录，含 `content`、`version`、`change_note`、`created_by`。

### `prompt_snapshots` + `prompt_snapshot_items` — 全局快照

类似 git tag，记录某一时刻所有模板的状态。支持一键回滚到任意快照版本。

---

## 四、提示词组装流程

### 4.1 主回答（`assemble_prompt`）

**文件**: `app/crm_profile/services/prompt_builder.py:75-151`

```
1. get_all_base_prompts()           → 拼接所有启用的 base 层模板 → system msg #1
2. get_context_header() + 上下文    → 客户档案数据               → system msg #2
3. get_rag_header() + RAG 检索结果  → 知识库内容                 → system msg #3
   + 客户备注 + 场景提示
4. 用户消息 + get_style_prompt()    → 风格提示                   → user msg
```

`scene` 层模板的使用方式：不是作为独立的 system message，而是根据 `scene_key` 选择对应的场景提示文本，拼入 system msg #3 中。

### 4.2 思考流（`assemble_visible_thinking_prompt`）

结构与主回答相同，额外注入一条思考提示指令："你正在为健康教练生成一个可显示的思维总结"。

### 4.3 轻量思考（`assemble_lightweight_thinking_prompt`）

独立的约 1K token 提示词，硬编码系统指令，不走六层组装。用于快速生成思维摘要。

---

## 五、场景与风格的动态发现

### 后端

**文件**: `app/crm_profile/prompts/registry.py:154-161`

```python
def list_scenes() -> list[tuple[str, str]]:
    return [(k, l) for k, l, _ in _db_query_layer("scene")]

def list_styles() -> list[tuple[str, str]]:
    return [(k, l) for k, l, _ in _db_query_layer("style")]
```

从 `prompt_templates` 表动态查询所有 `is_active=True` 的 scene/style 模板。

### 前端 API

**文件**: `app/crm_profile/routers/ai_config.py:36-61`

`GET /{customer_id}/ai/config` 返回：

```json
{
  "scenes": [{"key": "qa_support", "label": "QA 支持"}, ...],
  "styles": [{"key": "coach_brief", "label": "教练简报"}, ...]
}
```

### 前端 UI

**文件**: `frontend/src/views/CrmProfile/composables/useAiCoach.ts:55-86`

`loadAiConfig()` 加载后填充两个响应式变量，驱动 AI 教练面板中的两个下拉菜单：
- "工作场景"（`currentScene`）— 默认 `qa_support`
- "输出模式"（`outputStyle`）— 默认 `coach_brief`

选中的值作为 `scene_key` 和 `output_style` 随每次请求发送。

---

## 六、初始种子

**文件**: `app/services/prompt_seed.py`

16 个默认模板，首次启动时从 .md 文件写入 DB：

| 层 | 数量 | 模板 key |
|----|------|----------|
| base | 6 | `platform_guardrails`, `health_coach_core`, `visible_thinking_core`, `context_header`, `rag_header`, `scene_hint_header` |
| scene | 6 | `meal_review`, `data_monitoring`, `abnormal_intervention`, `qa_support`, `period_review`, `long_term_maintenance` |
| style | 5 | `coach_brief`, `customer_reply`, `handoff_note`, `bullet_list`, `detailed_report` |

种子函数同时创建 `v1.0` 和 `v2.1` 两个初始快照。

---

## 七、提示词管理界面

**路由**: `/prompt-manage`（仅 admin 可见）

**文件**: `frontend/src/views/PromptManage/index.vue`

### 功能

| 功能 | 说明 |
|------|------|
| 树状浏览 | 按 base/scene/style 分组展示所有模板，显示启用状态 |
| 在线编辑 | Markdown 文本编辑器，保存后自动创建版本记录 |
| 启用/禁用 | 切换 `is_active`，禁用后该模板从 AI 教练中消失 |
| 新建模板 | 可在任意层创建新模板（key 限小写字母数字+下划线） |
| 版本历史 | 查看每个模板的历史版本，支持一键回滚 |
| 全局快照 | 创建命名快照（如 `v3.0`），查看快照时间线和差异对比 |
| 快照回滚 | 一键恢复到任意快照版本 |
| 重新导入 | 从 .md 文件重新播种（清空 DB，从头初始化） |

### 启用/禁用的实际效果

| 操作 | 效果 |
|------|------|
| 禁用 base 模板 | 该模板内容不再出现在 system 消息中 |
| 禁用 scene 模板 | 该场景从"工作场景"下拉菜单消失，已选中的不受影响 |
| 禁用 style 模板 | 该风格从"输出模式"下拉菜单消失 |
| 新建 scene 模板 | 立即出现在"工作场景"下拉菜单 |
| 新建 style 模板 | 立即出现在"输出模式"下拉菜单 |

---

## 八、灵活性边界

### 灵活的部分

- 提示词内容完全在线编辑，无需改代码或重启服务
- 可自由新建 scene 和 style 模板，自动出现在教练面板
- 版本管理 + 快照回滚，支持安全的迭代试验
- 场景和风格的 key/label 完全自定义

### 固定的部分

- **三层结构固定**：只有 `base`、`scene`、`style` 三层，不能新增层级
- **组装顺序固定**：六层拼接的顺序和 system/user 消息的分配方式硬编码在 `prompt_builder.py` 中
- **轻量思考提示硬编码**：`assemble_lightweight_thinking_prompt` 的系统指令不在 DB 中管理
- **L4 上下文结构固定**：客户档案的字段白名单和聚合方式由 `context_builder.py` 控制

### 灵活性总结

```
              完全固定 ◄──────────────────────────► 完全灵活
                │                                      │
  六层组装顺序    base/scene/style 三层      提示词文本内容
  L4 字段白名单   层级不可新增               场景/风格的增删
  轻量思考提示    消息分配方式               版本/快照管理
```
