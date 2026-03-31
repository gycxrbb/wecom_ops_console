# Task Plan

## Goal

在多线程模式下收口 WeCom Ops Console 的核心主链路，优先统一后端模型、API 契约和调度链路真值，并保证文档、代码、验证结果一致。

## Current Phase

- Phase 1: 上下文恢复与任务拆分 `complete`
- Phase 2: 后端模型真值统一 `complete`
- Phase 3: API 契约与前端对齐 `complete`
- Phase 4: 调度链路收口 `complete`
- Phase 5: 启动验证与文档回写 `complete`

## Parallel Workstreams

1. 后端模型与 ORM 真值盘点
2. API / 前端接口契约漂移盘点
3. 调度与发送链路可运行性盘点

## Decisions

- 先不横向扩功能，优先做工程收口
- 当前代码真值优先级高于历史文档口径
- 多线程阶段先做读与分析，再决定具体改动批次
- 第一批执行以“统一后端真值 + 最小前端契约修正”为范围，不在本轮引入 Redis / Celery / Next.js 新能力

## Risks

- `Schedule` / `Message` / `MessageLog` 字段漂移会导致多处联动修改
- 调度服务仍引用旧模型名，可能牵涉启动与运行验证
- 当前工作区已有未提交文档改动，需要避免覆盖
- `Schedule` 当前仍是旧表结构上的桥接实现，多群定时任务还没有成为正式数据库真值

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| PowerShell 沙箱偶发阻塞只读命令 | 1 | 对关键只读命令申请提权后继续 |
