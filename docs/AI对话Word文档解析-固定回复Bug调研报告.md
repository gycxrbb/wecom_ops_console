# AI 对话 Word 文档解析 — "当前客户52岁"固定回复 Bug 调研报告

> 调研日期：2026-05-15
> 调研范围：AI 教练对话中上传 docx 附件后被"固定回复 + 召回 RAG 素材"的根因排查、与 Word 文档解析全链路闭环复核
> 问题来源：用户反馈上传 `赵雯静健康档案（5.12）.docx` 后 AI 固定回复"当前客户52岁"，并把 RAG 素材/话术全召回；切换客户重复测试仍是同样结果
> 报告位置：`docs/`（按 AGENTS.md 第 12 节"Bug 与工程经验沉淀"沉淀，未对生产代码做任何改动）

---

## 一、问题现象复述

1. 用户在 CRM 客户档案 → AI 对话页，上传 `赵雯静健康档案（5.12）.docx`。
2. AI 助手没有真正"阅读"该 docx 并按照客户问题作答，而是：
   - 在前端先把若干 RAG 召回的素材/话术列出来；
   - 紧接着固定输出"当前客户52岁。"作为回答正文。
3. 切换到另一名客户（非赵雯静），再次让 AI 处理这份附件或继续追问，回复依然落到"当前客户52岁。"。

用户提出的疑问：

- 这句话是不是被写死了？
- AI 对 Word 文档的解析是否做闭环了？

下面分别回答。

---

## 二、AI 处理 docx 的端到端调用链（先回答"闭环情况"）

按"输入接入层 → 清洗与理解层 → 决策与执行层 → 交付与运营层"的视角梳理：

| 阶段 | 责任文件 | 现状 |
|---|---|---|
| ① 附件上传（直传 / 服务器中转） | [app/crm_profile/routers/ai_attachment.py](app/crm_profile/routers/ai_attachment.py) `prepare-upload / confirm-upload / upload-attachment` | 已支持 docx（MIME `application/vnd.openxmlformats-officedocument.wordprocessingml.document` 在白名单内，[ai_attachment.py:36-41](app/crm_profile/services/ai_attachment.py:36)） |
| ② 落库 + 后台分析触发 | [ai_attachment.py:130-190](app/crm_profile/services/ai_attachment.py:130) `_create_attachment_record` + `_start_background_analysis` | 上传成功后 sleep 3s 触发 `analyze_attachment` |
| ③ 文档抽取 | [vision_analyzer.py:100-109](app/crm_profile/services/vision_analyzer.py:100) `_analyze_document` → [document_extractor.py:39-58](app/crm_profile/services/document_extractor.py:39) `_extract_docx` | 用 `python-docx` 读 `paragraphs + tables`，前置 `[Word文档: <filename>]`，最大 15000 字符截断 |
| ④ 注入对话上下文 | [ai/_prepare.py:254-292](app/crm_profile/services/ai/_prepare.py:254) `_resolve_attachment_descriptions` → [vision_analyzer.py:281-297](app/crm_profile/services/vision_analyzer.py:281) `build_user_message_with_attachments` | 把抽取结果以"【附件分析结果】… [附件: filename] …\n【用户提问】<原始 message>"格式拼接到 user message 前 |
| ⑤ Prompt 装配 + LLM 调用 | [ai/_prepare.py:32-128](app/crm_profile/services/ai/_prepare.py:32) `_prepare_ai_turn` → [ai/__init__.py:332-406](app/crm_profile/services/ai/__init__.py:332) `stream_ai_coach_answer` | DeepSeek 流式调用，正常情况下会拿到拼好的 prompt |
| ⑥ 审计落库 | `audit.write_message / write_context_snapshot` | docx 附件随 `bind_attachments_to_message` 绑定到本条 user message |

**结论 1（闭环情况）**：从"上传 → docx 抽文本 → 拼到 user message → 送 LLM"这一条主链路在代码层是接通的，docx 不会卡在上传阶段，也不会被忽略。**真正的问题不在解析本身，而在解析后那段拼接好的 user message 被一个本不该触发的"快捷直答"分支拦截了。**

---

## 三、根因定位："当前客户52岁"是怎么被写死的

### 3.1 真凶：`_try_answer_profile_fact_question` 命中了附件正文

文件：[app/crm_profile/services/ai/_helpers.py:55-91](app/crm_profile/services/ai/_helpers.py:55)

```python
def _try_answer_profile_fact_question(message: str, ctx) -> str | None:
    q = _normalize_text(message)
    ...
    if any(k in q for k in ("几岁", "年龄")) and age not in (None, ""):
        return f"当前客户{age}岁。"
```

`_normalize_text` 只是 `lower + 去空白`，对中文不做任何 token 化，**等于在整段 user message 上做"年龄/几岁"子串匹配**。

而第二章中的 ④ 步会把 user message 改写成：

```
【附件分析结果】
[附件: 赵雯静健康档案（5.12）.docx]
[Word文档: 赵雯静健康档案（5.12）.docx]
…基本信息…年龄: 52 …
【用户提问】
<用户在输入框里真正输入的内容>
```

只要 docx 内容里出现"年龄"二字（健康档案几乎一定有），就会命中 shortcut；shortcut 不再走 LLM，直接拼出 `f"当前客户{age}岁。"` 返回。

这就是"被写死的那句话"的来源——它不是写死的字面量，而是**模板字符串 + 客户档案里的 age 字段拼出来的**。

### 3.2 RAG 素材为什么还会"全部召回"

文件：[app/crm_profile/services/ai/__init__.py:251-330](app/crm_profile/services/ai/__init__.py:251)

```python
# RAG sources event (optional)
if prepared.rag_sources or prepared.rag_recommended_assets:
    yield AiStreamEvent(event="rag", data={...})          # ← 先 emit RAG
yield AiStreamEvent(event="loading", data={"stage": "model_call"})
...
if prepared.shortcut_answer:
    ...
    async for chunk in _emit_text_chunks(prepared.shortcut_answer, ...):
        yield AiStreamEvent(event="delta", data={"delta": chunk})
    ...
    return
```

`_prepare_ai_turn_async` 里 RAG 检索是**先于** shortcut 判定执行的（[_prepare.py:131-181](app/crm_profile/services/ai/_prepare.py:131)）。所以即使 shortcut 命中、根本不会用 RAG 上下文，召回的 sources 仍然通过 `event: rag` 推给前端，前端就把它当作"已经使用的素材"展示出来。

**结果**：用户视觉上看到"RAG 召回 + 一句生硬回答"，但其实那句话和 RAG 没关系，LLM 也没真正消费 docx。

### 3.3 "切换客户还是 52 岁"的两种可能解释

shortcut 用的是**当前客户**的 `basic_profile.age`，理论上切客户后该值会变。但用户看到的依然是 52，最可能的两种解释（按概率排序）：

1. **shortcut 在新客户身上未命中，LLM 被 docx 内容带偏**：
   - 新客户的 `basic_profile.age` 为空或不含"年龄"关键字命中条件失效；
   - 但 docx 的抽取结果（`年龄: 52`）已经被前缀写入 user message；
   - LLM 在"系统说 current customer 是 X，user 又附了一份说 52 岁的档案"的冲突里，倾向于以更具体的文本（docx）为准 → 复述"当前客户52岁"。
   - 这条路径下，shortcut bug 与"档案主体错位"两个问题叠加。

2. **赵雯静档案被多个客户复用（content_hash 去重跨客户不生效，但客户实际年龄恰巧接近）**：[ai_attachment.py:60-77](app/crm_profile/services/ai_attachment.py:60) `find_existing_attachment` 是按 `(customer_id, content_hash)` 联合去重的，不同客户互不共用记录，所以**不是数据库去重问题**。但如果用户测试的两个客户档案里年龄都是 52（巧合），shortcut 路径同样命中。

无论是哪一条，**根因都是同一个：附件文本被当作"用户问题"参与了关键词命中 / 被 LLM 当作客户事实**。

### 3.4 附带问题：thinking 流也同样会被拦截

文件：[ai/__init__.py:461-472](app/crm_profile/services/ai/__init__.py:461)

```python
shortcut_text = _build_shortcut_thinking_text(effective_message, None)
if shortcut_text:
    ...
    yield AiStreamEvent(event="done", data={"session_id": session_id})
    return
```

`_build_shortcut_thinking_text` 同样用 `"年龄" in q` 判断（[_helpers.py:94-111](app/crm_profile/services/ai/_helpers.py:94)），命中后跳过 LLM 输出固定的"这是年龄直读题…"。这导致 thinking 与 answer 两条 SSE 都被 shortcut 截胡，前端看到的"思考 + 回答"都是模板。

---

## 四、闭环度评估（按问题2"AI 解析 Word 是否做闭环了"回答）

| 维度 | 现状 | 是否闭环 |
|---|---|---|
| 上传 → 落库 | docx 走 `prepare-upload / confirm-upload` 或 `upload-attachment`，content_hash 去重，记录正常 | ✅ |
| 抽取 docx 文本 | `python-docx` 抽 paragraphs + tables，最大 15000 字 | ✅ 但**只抽段落与表格，跳过图片 / 嵌入对象 / 页眉页脚** |
| 后台分析触发 | 上传后 sleep 3s 起协程 `_analyze_document` | ⚠️ 仅依赖 `asyncio.get_running_loop()`，进程重启 + Celery 缺失场景下会丢任务（属另一议题） |
| 抽到的文本送入 LLM prompt | `build_user_message_with_attachments` 拼到 user message 前 | ✅ 拼接成功，但**没有区分"附件归属客户" vs "当前对话客户"** |
| Shortcut 是否对附件场景豁免 | 否，直接用整段 effective_message 做关键词命中 | ❌ **核心 bug 点** |
| RAG 是否区分 shortcut 命中 | 否，无论是否走 shortcut 都把 RAG sources 推给前端 | ❌ 误导用户 |
| 失败可观测性 | `processing_status / analysis_retry_count / vision_description` 字段齐备 | ✅ |

**一句话评价**：从"读得到 docx"角度看是闭环的；从"读懂 + 正确路由到 LLM"角度看**没有闭环**——存在 shortcut 误拦截、RAG 误推送、附件归属语义缺失三个断点。

---

## 五、复现条件

最小复现：

1. 登录一个 admin / coach 账号，进入任一已存在的 CRM 客户 AI 对话页。
2. 上传一份内容里出现"年龄"二字（或"几岁"/"性别"/"姓名"等任何 shortcut 关键字）的 docx 文件，例如本次提到的 `赵雯静健康档案（5.12）.docx`。
3. 在输入框里随便输入一句正常问题（"帮我分析下这份档案"），发送。
4. 观察：
   - SSE `event: rag` 会照常推送召回素材；
   - SSE `event: delta` 会输出 `"当前客户{当前客户的 age}岁。"` 然后 `done`。

无需改变客户、无需特殊网络条件，必现。

---

## 六、修复建议（**仅建议，未改代码**）

按"先止血、再治本"两层划分。

### 6.1 止血（小改动、低风险）

1. **Shortcut 只看用户原始问题，不看附件内容**
   - 在 [ai/__init__.py](app/crm_profile/services/ai/__init__.py) `stream_ai_coach_answer / ask_ai_coach / stream_ai_coach_thinking` 中保留原始 `message`，把"用于关键词命中的问句"和"用于 LLM 的 effective_message"拆成两个参数。
   - `_prepare_ai_turn` 新增 `original_message` 参数，shortcut 判定只用 `original_message`，prompt 装配仍用 `effective_message`。
   - 受影响：[_prepare.py:46-128](app/crm_profile/services/ai/_prepare.py:46) `_prepare_ai_turn`、`_prepare_ai_turn_async`、`_prepare_ai_turn_cached`、[_helpers.py:55-111](app/crm_profile/services/ai/_helpers.py:55) `_try_answer_profile_fact_question / _build_shortcut_thinking_text`。

2. **有附件时直接禁用 shortcut**
   - 简化版方案：`if attachment_ids: shortcut_answer = None`，规避所有边界。
   - 适用于"短期内来不及做参数拆分"的快速止血。

3. **Shortcut 命中时不推 RAG 事件**
   - [ai/__init__.py:251-256](app/crm_profile/services/ai/__init__.py:251) 把 RAG `yield` 放到"非 shortcut"分支里，避免给用户造成"我用了一堆素材但回答这么生硬"的错觉。

### 6.2 治本（结构性）

1. **附件归属的语义化标注**
   - 当前 `build_user_message_with_attachments` 只标了"【附件分析结果】"，没有声明这份附件是否属于当前对话客户。建议改成：
     ```
     【附件分析结果（教练自行上传，未必属于当前客户）】
     [附件: 赵雯静健康档案（5.12）.docx]
     …
     【当前对话客户档案以系统 profile 为准】
     【用户提问】…
     ```
   - 这样 LLM 不会把附件里的"52 岁"当作 current customer 的事实复读。

2. **shortcut 规则收敛**
   - 现有 shortcut 是"早期为了减 LLM 调用"的优化，但关键字命中粒度过粗（"年龄"二字在任何健康文档里都会出现）。建议改为：
     - 只在 message 长度 < 30 且不含附件的场景下尝试 shortcut；
     - 增加"句末问号 + 关键词"的同时命中条件；
     - 对命中的 shortcut 写埋点日志，便于后续评估是否还值得保留。

3. **附件抽取扩展**
   - 当前 `_extract_docx` 跳过图片、跳过页眉页脚、跳过 chart 对象。健康档案里常见的"体检指标"如果嵌在图片或图表里会直接丢失。属于另一条独立线，建议另立报告评估是否引入 Vision 兜底。

---

## 七、关联文件清单

| 文件 | 涉及内容 |
|---|---|
| [app/crm_profile/services/ai/_helpers.py:55-111](app/crm_profile/services/ai/_helpers.py:55) | shortcut 命中规则（核心 bug） |
| [app/crm_profile/services/ai/_prepare.py:32-181](app/crm_profile/services/ai/_prepare.py:32) | prepare 链 + shortcut 写入 PreparedAiTurn |
| [app/crm_profile/services/ai/__init__.py:171-413](app/crm_profile/services/ai/__init__.py:171) | answer / thinking SSE 主循环、RAG 事件顺序、shortcut 短路返回 |
| [app/crm_profile/services/ai_attachment.py:36-190](app/crm_profile/services/ai_attachment.py:36) | 上传白名单、后台分析触发、去重逻辑 |
| [app/crm_profile/services/vision_analyzer.py:100-109,281-297](app/crm_profile/services/vision_analyzer.py:100) | `_analyze_document` 与 `build_user_message_with_attachments` |
| [app/crm_profile/services/document_extractor.py:39-58](app/crm_profile/services/document_extractor.py:39) | docx 文本抽取实现 |
| [app/crm_profile/routers/ai_attachment.py](app/crm_profile/routers/ai_attachment.py) | 上传三件套路由 |

---

## 八、面向项目负责人的小结

- **被写死的不是字面量，是被一段"早期优化短路逻辑"误拦截**：shortcut 看到 docx 抽出来的文本里有"年龄"两字，就直接套用模板回 `"当前客户{age}岁"`，跳过 LLM，跳过 RAG，跳过附件本身。
- **docx 解析主链路是通的**：上传、抽文本、拼 prompt、写审计都正常；问题出在 shortcut 与 RAG 事件的执行顺序、以及附件归属语义不清。
- **可以做什么**：建议先做 6.1 的两条止血（shortcut 改为只看用户原句 + 有附件时禁用 shortcut），即可让"档案类附件"立刻恢复正常对话；治本层面再独立排期处理附件归属语义化与 docx 抽取增强。
- **本次产出**：本报告仅为调研，未改任何代码；同时建议在 `bug.md` / `memory.md` 中补一条"shortcut 关键字命中会被附件正文污染"的沉淀（按 AGENTS.md 第 12 节要求）。
