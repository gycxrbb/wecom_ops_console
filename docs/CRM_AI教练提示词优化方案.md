# CRM AI 教练提示词体系优化方案

> 日期：2026-04-28
> 文档状态：approved
> 适用范围：CRM AI 教练助手提示词体系

---

## 1. 背景

当前 AI 教练助手已具备 5 层分层架构（L1 平台底线 → L2 核心角色 → L3 场景策略 → L4 客户上下文 → L5 教练补充 → L6 用户提问），框架设计合理，但**提示词内容质量不足**：

| 层级 | 当前行数 | 主要问题 |
|------|----------|----------|
| L1 平台底线 | 9 行 | 医疗安全、角色身份、输出质量混在一起，缺乏结构 |
| L2 核心角色 | 19 行 | 缺少推理流程、输出格式模板、术语规范、边界处理指引 |
| L3 场景策略 | ~12 行/场景 | 缺少 Few-shot 示例和常见错误提醒 |
| 风格提示 | 1 行/风格 | 仅一句话 Python dict，无结构、无示例 |

工程侧问题：
- `preferred_scene_hint` 存而未用（仅前端默认值，不注入 prompt）
- 上下文 header / RAG header 硬编码在 Python 字符串中
- `lru_cache` 需重启才能更新提示词
- 无 DB 存储、无版本管理、无管理后台

---

## 2. 优化目标

1. **内容质量**：每层提示词从「规则罗列」升级为「结构化指令 + Few-shot 示例 + 术语规范 + 边界处理」
2. **可维护性**：所有提示词外部化为 .md 文件，硬编码字符串迁移出 Python
3. **可迭代性**：为后续 DB 存储、版本管理、A/B 测试奠定基础

---

## 3. 三阶段推进计划

### P0：提示词内容质量（本次实施）

改 .md 文件和少量 Python，不改架构。6 项改进：

#### 3.1 重构 L1 平台底线

**文件**：`app/crm_profile/prompts/base/platform_guardrails.md`

从 9 条平铺规则改为三节分组结构：

```
## 医疗安全红线
- 不诊断、不开处方、不建议停减换改药
- 药物/异常指标/医疗风险 → 必须转医生
- 优先尊重过敏、禁忌、运动损伤、风险信息

## 角色与身份边界
- 服务教练，不是客户
- 代词默认指当前客户
- 信息不足必须明示，不允许编造
- 只有被问才介绍 AI 自己

## 输出质量底线
- 输出是草稿不是结论
- 用真实值不用字段名或占位词
- 不反复提醒缺失字段
```

#### 3.2 充实 L2 核心角色

**文件**：`app/crm_profile/prompts/base/health_coach_core.md`

从 19 行扩展到 ~60 行，新增四块内容：

**a) 分析推理流程**（显式 CoT 引导）：
```markdown
## 分析推理流程
收到提问后，按以下步骤内部推理：
1. 信息确认 → 2. 安全扫描 → 3. 目标匹配 → 4. 数据评估 → 5. 结论形成 → 6. 建议生成
```

**b) 标准输出格式模板**：
```markdown
## 输出结构模板
- 【结论/判断】一句话核心发现
- 【关键依据】2-3 条支撑数据
- 【建议/下一步】可执行操作
- 【话术草稿】（可选）可转述文本
```

**c) 术语规范表**：
统一「升糖负担」「体重趋势」「调整建议」「运动方案」「客户」等术语使用。

**d) 边界情况处理**：
数据缺失、客户焦虑、矛盾数据、医疗边界、情绪化问题的处理策略。

#### 3.3 为 L3 场景增加 Few-shot 示例

**文件**：`app/crm_profile/prompts/scenes/*.md`（6 个文件）

每个场景从 ~12 行扩展到 ~60 行，新增：
- 核心分析维度详述
- 正向示例（Good）+ 反面示例（Bad）
- 常见错误提醒

以餐评为例：

```markdown
## ✅ 正向示例
教练问：帮我评一下这顿晚餐，白米饭 + 红烧排骨 + 炒白菜

【总评】这餐主要问题是碳水占比偏高且为高 GI 白米饭...
【关键问题】白米饭 GI 约 83，红烧含糖调味，蔬菜占比不足...
【替代建议】白米饭→杂粮饭，红烧排骨→清蒸排骨...
【话术草稿】"今天排骨很好吃！有个小调整：下次饭量减半..."

## ❌ 反面示例
"这顿饭不好，白米饭 GI 太高，排骨太油腻，要控制饮食。"
问题：空泛判断、无替代方案、语气负面
```

其他 5 个场景同理扩展。

#### 3.4 外部化硬编码提示词

将 `prompt_builder.py` 中的 Python 字符串迁移到 .md 文件：

| 新文件 | 内容 |
|--------|------|
| `prompts/base/context_header.md` | L4 上下文注入 header |
| `prompts/base/rag_header.md` | L4.5 RAG 参考 header |
| `prompts/base/scene_hint_header.md` | 场景偏好提示模板 |

#### 3.5 丰富风格提示

新建 `prompts/styles/` 目录，每个风格一个 .md 文件：

| 文件 | 风格 |
|------|------|
| `coach_brief.md` | 教练简报（默认） |
| `customer_reply.md` | 客户话术草稿 |
| `handoff_note.md` | 交接备注 |
| `bullet_list.md` | 要点列表 |
| `detailed_report.md` | 详细分析报告 |

每个文件包含：输出目标、结构要求、长度约束、语气指引、示例。

#### 3.6 启用 preferred_scene_hint

在 L5 profile note 后追加场景偏好提示：
```
教练已标注该客户的首选工作场景为「{scene_label}」。
如果教练没有显式指定场景，建议按此场景的策略进行分析。
```

### P1：架构改进（中期）

| 项目 | 说明 |
|------|------|
| DB 存储提示词 | `prompt_templates` 表，.md 作为部署源，DB 作为运行时源 |
| 管理后台 UI | Vue 页面：树形目录 + Markdown 编辑器 + 预览 |
| 版本历史 | `prompt_template_versions` 表，每次保存产生新版本 |
| 热更新 | 替换 lru_cache 为 TTL 缓存，管理后台保存后即时生效 |
| 模板变量 | 复用 Jinja2 引擎支持 `{{ customer_name }}` 等变量 |

### P2：管理与评估（远期）

| 项目 | 说明 |
|------|------|
| 评估框架 | 测试集 + LLM-as-judge 评分（安全性/专业性/可执行性/话术质量） |
| A/B 测试 | 同一场景多版本并行，按 session 随机分配 |
| 指标看板 | 基于审计数据：场景使用频率、token 用量、安全触发率 |

---

## 4. 涉及文件清单

### 重写

| 文件 | 改动 |
|------|------|
| `app/crm_profile/prompts/base/platform_guardrails.md` | L1 三节重组 |
| `app/crm_profile/prompts/base/health_coach_core.md` | L2 扩展 4 块内容 |
| `app/crm_profile/prompts/scenes/meal_review.md` | 餐评 +Few-shot |
| `app/crm_profile/prompts/scenes/data_monitoring.md` | 数据监测 +Few-shot |
| `app/crm_profile/prompts/scenes/abnormal_intervention.md` | 异常干预 +Few-shot |
| `app/crm_profile/prompts/scenes/qa_support.md` | 问题答疑 +Few-shot |
| `app/crm_profile/prompts/scenes/period_review.md` | 周月复盘 +Few-shot |
| `app/crm_profile/prompts/scenes/long_term_maintenance.md` | 长期维护 +Few-shot |

### 新建

| 文件 | 内容 |
|------|------|
| `app/crm_profile/prompts/base/context_header.md` | 上下文注入 header |
| `app/crm_profile/prompts/base/rag_header.md` | RAG 参考 header |
| `app/crm_profile/prompts/base/scene_hint_header.md` | 场景偏好提示 |
| `app/crm_profile/prompts/styles/coach_brief.md` | 教练简报模板 |
| `app/crm_profile/prompts/styles/customer_reply.md` | 客户话术模板 |
| `app/crm_profile/prompts/styles/handoff_note.md` | 交接备注模板 |
| `app/crm_profile/prompts/styles/bullet_list.md` | 要点列表模板 |
| `app/crm_profile/prompts/styles/detailed_report.md` | 详细报告模板 |

### 修改

| 文件 | 改动 |
|------|------|
| `app/crm_profile/prompts/registry.py` | 新增 style/header 加载函数 |
| `app/crm_profile/services/prompt_builder.py` | 使用外部化模板 + 注入 scene hint |

---

## 5. 验收标准

1. 所有提示词 .md 文件内容完成改写
2. Python 代码无硬编码提示词字符串
3. `preferred_scene_hint` 正确注入 prompt
4. `uvicorn` 启动无报错
5. AI 对话功能正常工作（提示词加载无异常）
