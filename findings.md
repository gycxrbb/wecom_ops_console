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
