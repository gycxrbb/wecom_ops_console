# Specification
Based on the PRD, API_SPEC, and SYSTEM_DESIGN documents.

## Current State:
- Basic `Vue` + `FastAPI` + `SQLite/SQLAlchemy` skeleton is in place.
- Models like `User`, `Group`, `Template`, `Asset`, `MessageJob`, `SendLog` exist.
- API is mostly under `/api` instead of `/api/v1`.
- Authentication uses session/cookies for basic web pages, but API requires token-based `Authorization: Bearer <token>` in `API_SPEC.md`. (Currently it seems to rely on session).
- Some core modules like `approval_requests`, `audit_logs` are missing from the schema.
- Standardization of the JSON response wrappers (code, message, data, request_id) is likely missing in some routes.

## Target State:
- Align database tables with `SYSTEM_DESIGN.md` (add `approval_requests`, `audit_logs`).
- Implement the standard structure `{ "code", "message", "data", "request_id" }`.
- Migrate `/api` to `/api/v1` and implement missing JWT standard (or align with API_SPEC).
- Implement Dashboard API & Approvals API.

## Constraints & Rules:
- Apply `taskmaster` multi-thread rules.
- Do not randomly refactor running code without checking.
- Output focused metrics.

## 2026-05-18: AI 对话多模态 Agent 化文档口径更新

### Goal
更新 `docs/AI对话多模态Agent化总体开发文档.md`，将图片生成正式口径收敛为：
- 默认直接调用 `gpt-image-2` 直出
- 高置信自动异步生成
- 低置信进入人工干预节点，前端询问教练是否需要绘制图片
- 从这份文档开始，AI 对话新增能力按 Agent 工作流落地

### Scope
- 只改总体开发文档与 `.tasks` 恢复锚点
- 不改业务代码
- 不做运行时验证

### Success
- 文档中不再以模板/混合渲染作为本轮主路径
- 文档中的阶段计划、SSE 事件、服务职责、配置、验收标准与新口径一致
- `.tasks/todo.md`、`.tasks/progress.md`、`.tasks/subtasks.md` 有对应记录
