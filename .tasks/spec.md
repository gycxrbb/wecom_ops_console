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

## 2026-05-20: AI 视觉生图任务失败但审计显示 success 排查

### Goal
定位并修复 AI 对话视觉生图链路中，用户提问“用户要出差，推荐下餐食”后后端报错
`Visual job ... failed: api_error (Connection error: Server disconnected without sending a response.)`，
但 AI 调用审计界面 `visual_safety_check` 和 `visual_generation` 均显示 `success` 的状态不一致问题。

### Scope
- 后端 AI 对话流中的视觉决策、视觉任务创建、图像 API 调用、审计步骤状态写入。
- 只把真实失败写成失败，不把 candidate/job_created 误写成 official generation success。
- 如涉及 bug 修复，必须同步更新 `bug.md`。

### Success
- 找到审计 success 与 visual job failed 的真实分叉点。
- 失败的生图任务能在 AI 审计中体现为 failure/error，而不是 success。
- focused validation 覆盖失败路径。
- 后端启动验证通过；如无前端改动，前端启动验证说明为未涉及或抽查。

## 2026-05-20: AI 视觉生图上游断连稳定性优化

### Goal
在不改变视觉决策和审计真值规则的前提下，优化 `gpt-image-2` 直出生图调用稳定性，减少
`Server disconnected without sending a response`、连接读写异常、临时 5xx 网关异常导致的单次失败。

### Scope
- `app/ai_visual/services/image_client.py` 的连接池、HTTP/2 降级、有限重试和错误归类。
- 配置项默认值，允许后续通过 `.env` 调整重试次数和退避时间。
- focused validation 覆盖断连后重试成功、重试耗尽失败。

### Success
- 上游首包前断连时会重置连接池并有限重试。
- 临时 502/503/504 会有限重试，4xx 不重试。
- 重试耗尽仍返回真实 `ImageGenerationError`，由后台 job/审计记录为 failed。
- 全量测试和项目启动验证通过。

## 2026-05-20: AI 视觉生图连接错误根因诊断脚本

### Goal
为持续出现的 `Server disconnected without sending a response` 提供分层诊断脚本，区分：
- 本机 DNS/TCP/TLS 网络问题
- HTTP/2 协议兼容问题
- base_url / endpoint / 鉴权 / 模型支持问题
- 图片生成接口真实上游断连或网关限制

### Scope
- 新增 `scripts/diagnose_ai_visual_image_api.py`
- 默认只做低成本连接与 `/models` 探测，不默认真实生图
- 使用 `--generate` 时才调用 `/images/generations`
- 输出必须脱敏 API key，不写入密钥

### Success
- 脚本可在 PowerShell 下运行
- 能分别测试 HTTP/2 与 HTTP/1.1
- 能显示异常类型、阶段、协议、状态码、响应体摘要
- 可选测试当前 payload 与兼容 payload，帮助判断是否是参数/模型兼容造成的断连
