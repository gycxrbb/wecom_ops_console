# Findings

## CRM 真值
- `customers` 是客户主实体，`customer_groups` 是客户-群桥表，`groups` 是 CRM 社群维表。
- `point_logs` 是积分流水真值，`created_at` 可用于周/月积分统计；`num` 为积分变动值，`type` 区分获得/消费。

## 当前群管理实现
- `app/services/crm_group_directory.py` 当前只读查询 `groups/customer_groups/customers`，个人榜、群榜、成员页均展示 `points` 和 `total_points`。
- 现有实现没有接入 `point_logs`，也没有时间窗口统计、趋势分析或榜单快照能力。

## 当前运营编排实现
- 当前模型为 `Plan -> PlanDay -> PlanNode`，节点核心字段只有 `node_type / msg_type / content_json / variables_json`。
- `score_publish` 只是一个普通节点类型，没有专用 payload、规则引擎或动态数据绑定。
- 导入/导出服务对节点类型、列结构、标题映射都有硬编码，说明当前体系偏“固定日程型 SOP”。

## 积分运营参考资料
- Excel 第 1 个 sheet 是“话术库”，按场景类型提供三套风格文案，如头部激励、连续活跃、异常增长、回归用户等。
- Excel 第 2 个 sheet 是“投送阶段节点”，按每日发榜、每周复盘、结营冲刺、结营当天拆了阶段动作与配套 1v1 动作。
- 这说明积分运营不是单一模板，而是“榜单数据 + 人群识别 + 固定风格话术”的组合生成。

## 当前前端导航与侧边栏真值
- 路由主导航位于 `frontend/src/router/index.ts`，当前正式页面包括：`看板 / 发送中心 / 群管理 / 模板中心 / 话术管理 / 素材库 / 定时任务 / 飞书文档 / 发送记录 / 审批中心 / 用户管理 / 权限管理 / 个人中心`。
- 其中 `话术管理 / 用户管理 / 权限管理` 仅 `admin` 可见；`发送中心 / 群管理 / 模板中心 / 素材库 / 定时任务 / 发送记录 / 审批中心` 受模块权限控制。
- 侧边栏分组位于 `frontend/src/layout/SidebarContent.vue`，当前分为：`核心业务 / 数据管理 / 运营配置 / 系统设置`。
- 如果后续新增“系统教学/帮助中心”，最自然的落点是：
  - 作为独立一级菜单插入 `运营配置` 或 `系统设置`
  - 或作为 `飞书文档` 的并列文档入口，形成“外部文档 / 系统教学”双入口

## 当前主要页面层级与已确认按钮
- `群管理`
  - 顶部视图切换按钮：`内部群 / 外部群视图`
  - 内部群：`新增群 / 编辑 / 删除 / 保存 / 取消`
  - 外部群：`刷新 / 积分榜单 / 搜索 / 切换到用户搜索`
- `发送中心`
  - 页面由 `MessageForm / PreviewCard / ScheduleCard` 三块组成。
  - 已确认存在：`预览此条 / 单独发送此条 / 队列定时发送`
  - 消息类型至少包括：`文本 / Markdown / 图片 / 表情包 / 图文 / 文件 / 语音 / 模板卡片`
- `侧边栏用户区`
  - 下拉动作包含：`个人中心 / 退出登录`

## 文档中心与存储复用判断
- 现有 `SopDocuments.vue` 已经提供了一套“文档列表 -> 分类筛选 -> 搜索 -> 管理员新增/编辑/删除 -> 点击打开文档”的文档中心交互骨架，可作为“系统教学中心”的入口形态参考。
- 现有素材上传/七牛链路已经完整支持：
  - 服务端直传与客户端直传
  - `Material` 资产记录
  - 文件夹归档
  - 七牛前缀 `QINIU_PREFIX`
- 如果教学文档中的图片走七牛，最稳的方案不是新造上传体系，而是：
  - 复用当前素材上传 API
  - 为文档图片单独约定目录或 key 前缀，例如 `qiwei/docs/...`
  - 教学文档正文里直接引用生成后的公共 URL

## 系统教学中心方案判断
- 当前最推荐的落地方式是“文件系统增强方案”：
  - 正式真值放在 `docs/system_teaching/*.md`
  - 系统内新增只读教学中心页面
  - `admin` 通过系统内编辑页修改 Markdown 文件
  - 图片不入库到本地 docs，而是上传到七牛 `qiwei/docs/...`
- 这样既满足“docs 路径下看到 MD 文档”的诉求，也能兼顾管理员在线维护效率。

## CRM 健康摘要升级研究
- 当前 `app/crm_profile/services/modules/health_summary.py` 只做了固定 7 天、单表 `customer_health`、轻量聚合摘要，未接 `breakfast_data/lunch_data/dinner_data/snack_data`，也未接 `customer_glucose.points`。
- `docs/CRM/mfgcrmdb_database_explanation.md` 已明确：
  - 看“业务端每日综合记录”优先 `customer_health`
  - 看“某项生理指标的日汇总/点位”优先 `customer_glucose` 等专项表
  - `customer_health.glucose_data` 存在弃用痕迹，不应再当正式血糖真值
- `customer_health` 更适合作为“每日健康概览”真值，承载体重、饮水、营养摄入、三餐与睡眠/步数。
- `customer_glucose` 更适合作为“血糖波动与峰值分析”真值，承载全天曲线与餐后冲高判断。
- `breakfast_data` 等餐食 JSON 里，适合进入正式摘要/AI 上下文的是：
  - `name/des/time`
  - `kcal/cho/fat/protein`
  - 三餐是否完整、哪餐缺失、哪餐更像异常来源
- `diet_assessment` 不应默认作为 AI 正式上下文真值，更适合作为 support；它本身是长文本点评，容易污染当前 AI 生成。
- 健康摘要建议从固定 `health_summary_7d` 升级成参数化 `health_summary(window_days=7|14|30)`，但兼容层可暂保留 `health_summary_7d`。
- 档案页推荐把“近7天健康摘要”改名为统一“健康摘要”，右上角提供 `近7天 / 近14天 / 近30天` 切换。

## CRM AI 用户 Profile 缓存 L2 快照收口
- 代码中已新增 `app/crm_profile/services/profile_context_cache.py`，当前实现为 L1 进程内缓存 + L2 应用数据库表 `crm_ai_profile_cache`，符合“当前阶段不引 Redis”的方向。
- `profile_context_cache.py` 已提供 `get_cached_profile_context / ensure_profile_context / schedule_profile_preload`，并有同进程 single-flight；L2 快照是 support cache，不是 CRM 用户档案 official truth。
- `docs/CRM_AI用户Profile缓存机制调研与优化报告.md` 当前仍大量推荐 Redis L2，与用户 2026-04-27 最新诉求“不先引 Redis，先用本地数据库做 L2 快照”不一致，需要更新口径。
- `router.py` 已把 `/profile`、`/ai/preload`、`/ai/context-preview` 改到统一缓存服务，并且 `AiChatRequest` 已包含 `health_window_days`。
- `ai_coach.py` 尚未收口：`ask_ai_coach / stream_ai_coach_answer / stream_ai_coach_thinking` 函数签名没有接 `health_window_days`，但路由已经传参，运行时会触发 unexpected keyword argument。
- `ai_coach.py` 的 DeepSeek thinking 轻量路径仍使用旧的 `profile_cache_key/cache_get/cache_get_stale/load_profile/get_connection` 逻辑，这些符号当前没有导入；并且它绕过了新的本地 DB L2 快照。
- `useAiCoach.ts` 发送 `chat-stream/thinking-stream` 时还没有把当前健康窗口写入请求体；`AiCoachPanel.vue` 也没有接收 `currentWindowDays`。
- `useCrmProfile.ts` 初次 `loadProfile()` 后会 fire-and-forget 调 `/ai/preload`，但 `switchHealthWindow()` 后没有同步预热新窗口，`context-preview` 前端也未携带 `health_window_days`。
## 2026-05-08 Findings: `docs/shujubiaozhu` 标注规范初读

- `话术标注规范.md` 定义话术 CSV 字段：`title, clean_content, summary, status, customer_goal, intervention_scene, content_kind, visibility, safety_level, question_type, tags, usage_note, tone, reviewer, review_note`。
- 话术规范要求 `status` 为 `approved` 或 `active`，`content_kind=script`，`customer_goal/intervention_scene/safety_level/visibility/tags/usage_note/tone` 作为推荐质量关键字段；`medical_sensitive/doctor_review` 必须 `coach_internal`。
- `素材标准规范.md` 定义素材 CSV 字段：`source_type,title,summary,content_kind,status,rag_enabled,visibility,safety_level,copyright_status,customer_sendable,alt_text,usage_note,customer_goal,intervention_scene,question_type,tags,material_ref,file_name,file_hash,transcript,public_url`。
- 素材规范要求素材先能匹配系统素材库；匹配优先级为 `material_ref > file_hash > file_name`；`copyright_status=unknown` 应跳过；`visibility=customer_visible` 需 `public_url`，否则降回 `coach_internal`。
- 文档口径把 RAG 定位为教练/AI 助手的检索推荐 support layer，不是素材/话术 official truth。

## 2026-05-08 Findings: 当前 RAG 代码实现初读

- RAG 持久化模型包含 `rag_tags`、`rag_resources`、`rag_resource_tags`、`rag_chunks`、`rag_retrieval_logs`；实际索引主表是 `rag_resources` + `rag_chunks`，向量侧 payload 保留 source/type/status/kind/visibility/safety/tags。
- 话术 CSV 导入在 `app/services/speech_template_import.py`：只强校验 `title` 和 `clean_content/content`，`status` 仅允许 `approved/active` 入库；`customer_goal/intervention_scene/question_type/safety_level/visibility/summary/tags/usage_note` 写入 `SpeechTemplate.metadata_json`。
- 话术 RAG 索引在 `app/rag/resource_indexer.py`：从 `metadata_json` 读取标签，写入 semantic text 和 Qdrant payload；但不写 `rag_resource_tags` 关系表。
- 素材 CSV 导入在 `app/services/material_rag_import.py`：强校验必填、approved/active、rag_enabled、版权、素材匹配、存储 ready、customer_visible/public_url、安全等级；质量等级按 ok/medium/weak 计算。
- 素材 UI 保存链路在 `app/services/material_rag_service.py`：也做素材 ready、摘要、usage_note、图片/视频说明、版权、受控标签、public_url 和安全等级校验；但 schema 未包含 `content_kind/public_url` 字段，UI 链路可能无法完整表达文档 CSV 的全部字段。
- 检索链路在 `app/rag/retriever.py`：先检索 `script/text/knowledge_card` 注入 prompt，再单独检索 `image/video/meme/file` 作为 recommended_assets；使用 scene/safety/semantic_quality payload filter，0 命中时会放宽 scene filter，并做 tag boost。

## 2026-05-08 Findings: 当前 RAG 数据库/向量库真值

- 当前服务库来自 `.env` 的 MySQL `wecom_ops`；默认 `data/app.db` 没有业务/RAG 表，不是当前系统真值。
- MySQL RAG 表计数：`rag_tags=57`、`rag_resources=66`、`rag_chunks=66`、`rag_retrieval_logs=183`、`speech_templates=41`、`materials=51`，`rag_resource_tags=0`。
- `rag_tags` 当前词表与文档主词表基本一致：customer_goal 8 个、intervention_scene 12 个、question_type 14 个、safety_level 5 个、visibility 2 个。
- Qdrant 本地 collection `wecom_health_rag` 存在，状态 green，points_count=66，维度 1024，与 DB `rag_chunks=66` 对齐。
- 话术样例 37-41 已进入 `speech_templates` 和 `rag_resources`，semantic_text 包含正文、summary 和标签；但 37-40 的 visibility 为历史值 `customer_sendable`，不属于当前文档/词表的 `customer_visible`。
- 素材资源中仍有大量 `semantic_quality=weak` 且 `status=active`：17 个 image + 6 个 file；其中多条素材已 `storage_status=deleted` 或无 `rag_meta_json`，与“weak 不能推荐/缺字段跳过”的文档口径不一致。
- 文档样例中的 `materials.id=12` 当前存在且 ready/public_url 有值，但 `rag_meta_json=null`，其 RAG resource 仍是 weak 老索引；`materials.id=34` 当前存在且 ready/public_url 有值，但 `rag_meta_json=null`，与 `test_material_rag.csv` 的期望入库状态不一致。
- 当前素材 `id=53` 的 `rag_meta_json` 仍包含中文/旧 code：`customer_goal=["血糖管理"]`、`question_type=["lifestyle_change","exercise_guidance"]`，不在当前文档词表内。
- `question-category.xlsx` 是 102 行问题分类层级（L1-L4），当前 DB `speech_categories` 只落了 L1/L2 共 22 条；RAG 检索未直接使用三级/细分分类。

## 2026-05-09 Findings: 话术管理 CSV 导入调研

- 前端 `SpeechTemplates.vue` 已有“导入 CSV”入口，使用 `multipart/form-data` 调 `/v1/speech-templates/import-csv`，并默认勾选“导入后同步 RAG 索引”。
- 后端路由层 `app/routers/api_speech_templates.py` 已按资源拆分，导入接口只做权限、文件类型和空文件检查，再调用 `speech_template_import` 服务，整体符合 router/service 分层方向。
- 当前导入接口存在阻断问题：路由调用 `import_speech_templates_csv(..., owner_id=user.id)`，但 `app/services/speech_template_import.py` 中 `import_speech_templates_csv` 与 `import_speech_templates_csv_file` 不接收 `owner_id`，真实上传会触发 `TypeError`。
- CSV 标注字段中，`title/clean_content/status/customer_goal/intervention_scene/visibility/safety_level/question_type/tags/usage_note/summary/tone` 基本可进入 `speech_templates` 或 `metadata_json`；`content_kind/reviewer/review_note` 当前不会落库，也不会被校验。
- 导入服务只强校验 `title`、`clean_content/content`、`source_type`、`status in approved/active`；没有强校验标注规范要求的 `summary/customer_goal/intervention_scene/safety_level/visibility/tags/usage_note/tone`，也没有阻断 `medical_sensitive/doctor_review + customer_visible`、`contraindicated` 等安全规则。
- 三级分层已体现在 `SpeechCategory` 与前端侧栏，导入时通过 `scene_key -> SCENE_CATEGORY_MAP -> L3 category_id` 自动归类；但 `resource_indexer.py` 解析分类 payload 时只处理 level=2 category_id，当前 L3 category_id 不会正确写出 `category_l1/category_l2` 到 RAG payload/semantic_text。
- RAG 索引能把 `metadata_json` 中的目标、场景、问题类型、安全等级、可见范围写入 Qdrant payload；检索层也会使用这些字段做过滤和加权。因此字段一旦正确入库并重新索引，技术路径可用。
