# 积分运营升级任务计划

## 目标
- 基于 CRM 的 `customers / customer_groups / groups / point_logs`，为群管理-外部群、发送中心、运营编排设计一套可实现的积分展示与积分运营升级方案。
- 当前阶段先完成现状恢复、方案设计和落盘计划，不进入代码实现。

## 阶段
- [x] Phase 1: 读取 CRM 表说明、Schema 知识与积分运营参考 Excel
- [x] Phase 2: 梳理当前外部群积分榜、发送中心、运营编排实现现状
- [x] Phase 3: 输出积分展示、排行推送、积分运营编排升级方案
- [x] Phase 4: 将正式计划写入 `docs/`

## 当前判断
- 当前群管理积分视图只基于 `customers.points/total_points` 做静态聚合，没有周/月积分口径。
- 当前发送中心支持模板/运营编排节点引用，但没有“按 CRM 外部群积分排行生成动态内容”的发送逻辑。
- 当前运营编排是标准 `Plan -> Day -> Node` 固定节奏模型，适合周期内容运营，不适合积分榜驱动的事件型运营。

## 风险与待确认
- `customers.points` 与 `customers.total_points` 的业务含义存在历史口径，需要在升级中明确 UI 保留哪个列。
- 积分运营文案不是纯模板替换，涉及 `point_logs` 趋势分析与人群识别，需要单独的数据分析层。
- 现有导入/导出链路对节点类型和 Excel 列结构有硬编码，改编排模型时要避免直接破坏旧流程。

---

## 2026-04-26 临时任务锚点：CRM 健康摘要 7/14/30 天升级研究

### 目标
- 基于 `customer_health` 与 `customer_glucose` 的真实字段，评估如何把“近7天健康摘要”升级为支持 7/14/30 天的正式健康摘要，并明确 UI 展示口径与 AI 上下文接法。

### 阶段
- [x] Phase 1: 读取 `mfgcrmdb_database_explanation.md`、`mfgcrmdb_schema_knowledge.json`、当前 `health_summary.py`
- [x] Phase 2: 梳理 `customer_health` 与 `customer_glucose` 的字段角色、表关系与当前缺口
- [x] Phase 3: 输出健康摘要升级开发报告到 `docs/`
- [ ] Phase 4: 后续如进入实现，再拆后端模块重构、前端窗口切换、AI 上下文升级

### 当前判断
- 当前 `health_summary.py` 只用了 `customer_health` 的少量标量字段，还没有正式接入三餐 JSON 与 `customer_glucose.points`。
- `customer_health` 应作为每日业务概览真值，`customer_glucose` 应作为血糖曲线与波动分析真值，两者通过 `customer_id + 日期` 在服务层轻量对齐。
- `diet_assessment`、餐食图片 URL、全量血糖 `points` 原始数组不适合作为 AI 默认正式上下文，更适合作为 support 或按需展开。

### 风险与待确认
- 高血糖/低血糖阈值不宜在第一版硬编码到多处，建议统一配置。
- 现有主报告 `CRM_USER_PROFILE_AI_INTEGRATION_REPORT.md` 仍以 `health_summary_7d` 为主，后续需要和本次报告同步口径，避免真值漂移。

---

## 2026-04-26 临时任务锚点：客户档案详情导航缓存修复

### 目标
- 修复客户在详情页切到发送中心后，再回客户档案时丢失原客户详情、退回客户列表的问题。

### 阶段
- [x] Phase 1: 恢复客户档案路由、页面和 composable 状态现状
- [x] Phase 2: 定位详情恢复只依赖 URL query，侧边栏导航会丢 query 的根因
- [x] Phase 3: 在客户档案 composable 中补充会话级恢复锚点
- [x] Phase 4: 运行 focused validation 与项目启动验证

### 当前判断
- `official` 的显式恢复入口仍是 `/crm-profile?cid=...`。
- `sessionStorage` 只作为同一浏览器会话内的辅助恢复锚点，不写成长期 truth。
- 点击“返回客户列表”是用户显式退出详情，应清理恢复锚点。

---

## 2026-04-26 临时任务锚点：CRM AI 上下文缓存与预加载优化计划

### 目标
- 梳理当前 AI 对话缓存架构、缓存未命中原因，并输出一份符合工程规范的后台预热优化计划到 `docs/`。

### 阶段
- [x] Phase 1: 恢复 `cache.py / profile_loader.py / context_builder.py / ai_coach.py / useAiCoach.ts` 现状
- [x] Phase 2: 定位 profile cache key 不一致、首次对话未预热、DeepSeek thinking 轻量路径绕行等问题
- [x] Phase 3: 设计 P0/P1/P2 分阶段工程方案
- [x] Phase 4: 输出正式计划文档到 `docs/CRM_AI_CONTEXT_CACHE_PRELOAD_OPTIMIZATION_PLAN.md`

### 当前判断
- 当前缓存未命中最直接 blocker 是客户档案页使用 `profile:{id}:hw{window}`，AI prepare 使用 `profile:{id}`。
- 用户提出的“进入客户档案后后台预加载 AI 上下文”方向成立，但必须先统一 key、加 single-flight、区分 preload candidate 与正式审计 snapshot。
- 当前任务仅为方案文档，未改业务代码。

---

## 2026-04-26 临时任务锚点：CRM AI 用户信息字段扩充报告校准

### 目标
- 审核 `docs/CRM_AI加载用户信息字段优化扩充开发报告.md`，对齐当前代码仓库真实链路，删除模型额度限制类表述，修正不合理结论。

### 阶段
- [x] Phase 1: 恢复报告、AI coach、router、cache、前端预热调用现状
- [x] Phase 2: 对齐 `/profile -> /ai/preload -> profile_cache_key -> _prepare_ai_turn` 缓存链路
- [x] Phase 3: 修正 `selected_expansions` 未闭环问题描述
- [x] Phase 4: 删除相关限制章节并完成 focused validation

### 当前判断
- 当前 `/ai/preload` 只属于 support cache 预热，不是 formal 会话上下文快照。
- 当前 AI prepare 默认读取 `profile:{customer_id}:hw7`，非 7 天健康窗口仍可能出现预热成功但首问未命中的情况。
- 当前报告已调整为“当前代码真实口径 + 后续修复建议”，未改业务代码。

---

## 2026-04-26 临时任务锚点：RAG 接入方案重写

### 目标
- 将 `docs/RAG集成到wecom项目手册.md` 从独立 RAG demo 调整为适配当前系统的正式开发手册，覆盖话术管理、素材库标签治理、aihubmix embedding、Qdrant、AI 教练接入与前端推荐资料闭环。

### 阶段
- [x] Phase 1: 恢复当前 `speech_templates / materials / crm_profile ai_coach / ai_chat_client / docker-compose.prod.yml` 真值
- [x] Phase 2: 核对 aihubmix embedding/rerank 接口与候选模型
- [x] Phase 3: 重写 RAG 手册，明确复用当前模块、不新建长期独立 RAG 对话入口
- [x] Phase 4: 补充开发交接说明、P0 最小闭环拆分与硬性叮嘱
- [x] Phase 5: 聚焦校验关键漂移点与核心章节

### 当前判断
- 固定干预话术应进入“话术管理”，模板中心只负责企业微信发送格式与变量。
- 素材库已有 `materials.tags` 基础字段，但要支撑 RAG，还需要摘要、适用场景、安全级别、可发状态、图片说明和视频转写。
- 第一版 embedding 推荐通过 aihubmix 使用 `text-embedding-3-large`，Qdrant 负责向量存储，RAG 作为 support knowledge 接入现有 CRM AI 教练链路。
- 当前文档已能作为开发蓝图交接，但要求开发先做 P0 最小闭环，不允许把全量知识库平台一次性混进首轮。

---

## 2026-05-09 临时任务锚点：话术管理 CSV 导入全量入库前调研

### 目标
- 核对当前“话术管理”页面的 CSV 导入功能是否与 3 级分层架构、话术 RAG 标注规范和全量入库前质量门禁对齐，并输出调研报告到 `docs/`。

### 阶段
- [x] Phase 1: 恢复话术管理、RAG 标注规范、当前进度真值
- [x] Phase 2: 追踪前端导入入口、后端 API、导入服务、RAG 索引链路
- [x] Phase 3: 执行 focused validation 与项目启动验证
- [x] Phase 4: 输出正式调研报告并收口

### 当前判断
- 架构方向基本成立：前端页面、后端资源路由、导入 service、RAG indexer 是分层的。
- 当前不建议全量入库：`owner_id` 参数签名不匹配会让导入接口运行时报错，且 CSV 字段质量/安全门禁不足。
- 3 级分层 UI 已落地，但 RAG indexer 对 L3 分类的 category payload 解析还没完全对齐。
- 正式调研报告已输出到 `docs/SPEECH_TEMPLATE_CSV_IMPORT_ALIGNMENT_RESEARCH_REPORT.md`。

### 风险与待确认
- 全量导入前需要先修复接口运行时报错，并增加 dry-run/严格校验报告。
- 标注规范中的 reviewer/review_note/content_kind 当前不是 official 落库字段，需要明确是丢弃、补入 metadata_json，还是独立审核字段。

---

## 2026-04-27 临时任务锚点：CRM AI 用户 Profile 缓存 L2 快照收口

### 目标
- 审查并补齐 AI 对话用户 profile 缓存机制：当前阶段先不引入 Redis，使用本地数据库做 L2 缓存快照，避免用户在 AI 对话首问时等待 CRM 业务表聚合查询。

### 阶段
- [x] Phase 1: 恢复报告、缓存服务、AI 对话 prepare、用户档案页预热链路现状
- [x] Phase 2: 判断本地 DB L2 快照模型、迁移、读写路径是否已闭环
- [x] Phase 3: 补齐后端 L1/L2/profile preload/AI prepare 的健壮缓存路径
- [x] Phase 4: 补齐用户档案页静默检查或预热触发，避免只在打开 AI 抽屉时才补缓存
- [x] Phase 5: 跑 focused validation、项目启动验证，并回写报告、bug/memory/进度

### 当前判断
- 用户诉求明确为“不先引 Redis”；Redis 只能作为未来扩展，不能作为当前 official 依赖。
- 本地 DB 快照只能作为 L2 support cache，不应覆盖 CRM 业务表 official truth。
- AI 对话链路应优先读已准备好的缓存上下文；缓存缺失时可以后台刷新，但不能把常规路径设计成首问同步重查大量 DB。
- 当前代码已存在 `crm_ai_profile_cache` 本地表和 `profile_context_cache.py`；本轮已把 AI 对话改为 cache-only 读取 L1/L2，true miss 仅后台 preload。
- focused validation 与项目启动验证已通过；前端沙箱内 dev server 仍有既有 `esbuild spawn EPERM`，提权验证已确认 Vite 正常启动。

### 风险与待确认
- 需要避免把过期 L2 快照写成正式用户档案 truth。
- 需要确认用户档案页加载、健康窗口切换、AI preload、thinking/answer 双流是否使用同一套 cache key。

---

## 2026-04-27 临时任务锚点：CRM AI Profile 缓存状态门禁续优化

### 目标
- 在本地 DB L2 快照方案基础上继续补齐可观测、前端门禁和过期快照治理，让“缓存准备中/已就绪/过期可用”成为系统可判断状态。

### 阶段
- [x] Phase 1: 恢复上一轮 L1/L2/profile preload/AI prepare 状态
- [x] Phase 2: 后端新增 cache-status 与 L2 过期快照清理能力
- [x] Phase 3: 前端保存 profile cache 状态，并在缓存未就绪时短暂禁用 AI 发送
- [x] Phase 4: 更新调研报告、进度和经验沉淀
- [x] Phase 5: 跑 focused validation、项目启动验证，并复测现场 AI 对话报错

### 当前判断
- cache-status 只读缓存状态，不触发 CRM profile 构建，避免把调试/门禁接口变成新的慢查询入口。
- 前端门禁只在 `checking / scheduled / already_running / building / missing` 状态下短暂生效；fresh/stale ready 仍允许提问。
- L2 清理只删除 `stale_expires_at` 已过期的 support snapshot，不影响 CRM official truth。
- 用户现场测试已确认后端能启动且 `/ai/preload` 能返回 200；新暴露的 blocker 是 RAG 审计表旧库缺少 `rag_retrieval_logs.intent_json`，不是 Profile L2 缓存本身。
- 已补 `ensure_rag_schema()` 的幂等补列，并已对当前库执行一次迁移；下一步需要复测 AI 对话不再刷该 traceback。
- focused validation 已通过：`py_compile`、`ensure_rag_schema` 字段检查、`write_retrieval_log(intent_json=...)` 写入测试、`git diff --check`。
- 项目启动验证已通过：后端备用端口 8010 启动到 `Application startup complete`；前端沙箱内仍复现既有 `esbuild spawn EPERM`，提权后 5178 启动到 Vite ready 并已回收监听进程。

---

## 2026-04-26 临时任务锚点：RAG 语料准备与标注计划

### 目标
- 为业务侧整理散落在飞书文档、微信聊天、图片、视频和教练经验中的语料提供一份可执行计划，保障后续 RAG 链路能顺畅接入话术管理、素材库和 AI 教练助手。

### 阶段
- [x] Phase 1: 恢复 RAG 接入方案、外部文档资源模型和素材库模型现状
- [x] Phase 2: 设计语料来源盘点、清洗、脱敏、标注、审核、交付链路
- [x] Phase 3: 输出 `docs/RAG语料准备与标注工作计划.md`
- [x] Phase 4: 聚焦校验关键章节与交付物

### 当前判断
- 业务侧应先做高质量 P0 试点集，而不是全量搬运散落文档。
- P0 目标建议为 100 条话术、50 条知识卡片、30 个图片素材、10 个视频素材、50 条评估问题。
- 图片/视频必须补摘要、图片说明或转写文本，否则无法形成可检索语义。

---

## 2026-04-28 临时任务锚点：上线前 RAG 生产更新收口

### 目标
- 基于 `docs/上线前RAG向量库生产更新审阅报告.md` 和当前代码真值，补齐 RAG 上线前仍能直接落地的生产 blocker 与入库门禁。

### 阶段
- [x] Phase 1: 恢复审阅报告、RAG 代码、生产 compose、部署文档与素材标注入口现状
- [x] Phase 2: 确认原 healthcheck blocker 已由 `/api/v1/health` 解除，剩余重点转为依赖、镜像上下文、部署 env 与素材门禁
- [x] Phase 3: 补齐 `qdrant-client` 依赖、`.dockerignore` 向量库排除、部署文档 RAG env、素材 RAG 保存/CSV 入库硬门禁
- [x] Phase 4: 跑 focused validation 与后端/前端启动验证
- [x] Phase 5: 回写进度、bug/memory 与最终上线状态

### 当前判断
- RAG 仍是 support index / support knowledge，不是素材、话术、客户档案的 official truth。
- 当前不建议全量素材自动入 RAG；应先用 approved 小样本和固定评估问题做上线验收。
- 生产服务器 `.env` 必须使用 `QDRANT_MODE=remote`，否则会绕过 compose 中的 Qdrant 服务。

---

## 2026-05-08 临时任务锚点：shujubiaozhu 文档与当前 RAG 实现/数据库对齐审查

### 目标
- 阅读 `docs/shujubiaozhu` 下的话术、素材、样例与分类文件，对比当前 RAG 代码实现和本地 RAG 相关数据库，判断文档口径是否与系统真值存在出入。

### 阶段
- [x] Phase 1: 恢复已有 RAG/标注任务上下文和文档目录清单
- [x] Phase 2: 提炼话术/素材规范的字段、流程、门禁和“official/support/candidate”口径
- [x] Phase 3: 梳理当前 RAG 代码实现：入库、检索、分类、审计、素材/话术接入点
- [x] Phase 4: 检查当前 RAG 相关数据库表结构、样本数据和向量库状态
- [x] Phase 5: 输出差异结论、风险、focused validation、启动验证状态与下一步建议

### 当前判断
- 本轮是审查任务，优先产出差异判断；除非发现必须修复的阻断问题，否则不直接修改业务代码。
- RAG 仍应按 support index/support knowledge 理解，不能把向量库结果写成素材或话术的 official truth。
- 审查结论：文档的字段与主流程方向基本正确，但当前数据库存在历史脏数据/旧口径，且素材 weak 资源治理未和文档门禁完全一致。
- 当前 blocker：需要一次 RAG 数据治理/重建，把旧 visibility、旧标签 code、weak/deleted 素材 active 状态和素材样例入库状态收口。

---

## 2026-05-08 临时任务锚点：shujubiaozhu RAG 文档修订与链路总览

### 目标
- 基于刚完成的 RAG 实现/数据库审查，修订 `docs/shujubiaozhu` 下现有标注规范，并新增一份串联当前 RAG 实现的总览文档。

### 阶段
- [x] Phase 1: 复核现有话术/素材规范和样例 CSV
- [x] Phase 2: 修订话术规范，补充当前系统落点与旧值风险
- [x] Phase 3: 修订素材规范，修正 CSV 门禁和 customer_sendable 口径
- [x] Phase 4: 新增 `RAG实现链路说明.md`
- [x] Phase 5: 同步样例 CSV 并完成 focused validation

### 当前判断
- 文档已对齐当前实现：RAG 是 support index/support knowledge，业务 official truth 仍在 `speech_templates` 和 `materials`。
- 当前仍未处理数据库历史脏数据；这属于下一轮数据治理任务，不属于本轮文档修订。

---

## 2026-05-08 临时任务锚点：RAG 知识库管理页面计划审查

### 目标
- 审查 `docs/RAG_MANAGE_PAGE_PLAN.md` 是否仍符合当前“知识库管理”实现，并直接在原文档基础上修订，给出是否偏离蓝图和后续优化点。

### 阶段
- [x] Phase 1: 阅读原计划文档
- [x] Phase 2: 对照当前前端 `RagManage` 页面、路由、侧边栏和面包屑
- [x] Phase 3: 对照当前后端 `/api/v1/rag` 资源/标签/日志/重建接口和 Qdrant helper
- [x] Phase 4: 重写文档为“设计与现状审查”
- [x] Phase 5: 完成 focused validation 与启动验证

### 当前判断
- 方向未偏离：当前系统已实现第一版 RAG 管理 MVP。
- 原计划文档已过期：它把已实现的页面和接口仍写成待开发。
- 下一步重点不是“从零建页面”，而是补生产治理闭环：admin 权限、删除一致性、Qdrant 统计兼容、日志命中统计、单条重建、批量治理和问题资源筛选。
- 本轮验证已完成：RAG 后端模块语法检查通过，前端生产构建通过，后端 8031 健康检查返回 200，前端 5192 Vite ready 后已回收。
