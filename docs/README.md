# 企微群消息运营后台文档包

本文档包包含以下内容：

1. `PRD.md`：产品需求文档
2. `SYSTEM_DESIGN.md`：系统设计文档
3. `API_SPEC.md`：前后端统一接口文档
4. `CURRENT_STATUS.md`：基于当前代码仓库整理的实现现状、文档漂移和后续待办

## 技术栈约束说明

- 当前实现：Vue3 + Element Plus + TypeScript + FastAPI + SQLAlchemy + SQLite + APScheduler
- 规划演进：MySQL / PostgreSQL、Redis、Celery、Next.js 预览/SSR 扩展

## 输出说明

本套文档默认以“可直接进入评审与研发排期”的粒度编写，可作为：

- 需求评审底稿
- 架构评审底稿
- 前后端联调底稿
- 测试用例编写输入

## 阅读顺序建议

1. 先读 `CURRENT_STATUS.md`，确认当前仓库真实状态
2. 再读 `PRD.md`，理解业务目标、范围和里程碑
3. 再读 `SYSTEM_DESIGN.md`，区分当前实现架构和目标演进架构
4. 最后读 `API_SPEC.md`，区分已经实现的接口与规划接口

## 文档使用约定

- `README.md` 和 `docs/CURRENT_STATUS.md` 以“当前代码真值”为准
- `PRD.md` 以“目标能力、业务边界和验收口径”为主
- `SYSTEM_DESIGN.md` 同时包含 “当前实现态（as-is）” 和 “目标演进态（to-be）”
- `API_SPEC.md` 若出现“规划接口”和“当前已实现接口”不一致，联调和开发以代码现状为准，并优先补齐文档后再改代码
