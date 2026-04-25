② AI Prompt 架构 P0 — 5 层分层提示词
层	文件	作用
L1 平台底线	prompts/base/platform_guardrails.md	医疗边界、安全红线
L2 健康教练核心	prompts/base/health_coach_core.md	角色定位、输出风格
L3 场景策略	prompts/scenes/*.md (6 个)	餐评/数据监测/异常干预/问答/复盘/长期维护
L4 客户上下文	context_builder.py (已有)	自动聚合的 CRM 数据
L5 教练补充	CustomerAiProfileNote 模型 + API	教练手填的长期背景信息
