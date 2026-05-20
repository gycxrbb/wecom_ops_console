## 2026-05-18 AI 对话多模态 Agent 化文档口径更新

1. 上下文恢复：读取目标文档、git 状态、现有 `.tasks` 锚点。
2. 口径定位：定位图片生成、Agent 化路径、配置、阶段计划和验收章节。
3. 文档修改：把生图改为直接调用 `gpt-image-2` 直出，并加入置信度分流。
4. 一致性复核：用检索确认 `hybrid`、`template_renderer`、fallback 模型等旧口径是否仍有冲突。
5. 收口同步：更新任务锚点并输出项目负责人可理解的状态。

## 2026-05-20 AI 视觉生图失败审计状态不一致

1. 上下文恢复：读取视觉模块、AI 对话流、调用审计服务、现有任务锚点。
2. 分叉定位：对照 `visual_generation` 审计 success 写入时机与 job 后台生成失败时机。
3. 修复实现：让失败路径把审计步骤更新为失败，或调整 success 语义为 job_created 并新增真实生成结果。
4. focused validation：构造/运行断连失败路径，确认审计不再误显示 success。
5. 收口沉淀：更新 `bug.md`、`.tasks/progress.md`，执行启动验证并输出负责人视角状态。

## 2026-05-20 AI 视觉生图上游断连稳定性优化

1. 上下文恢复：读取视觉生图客户端、通用 AI chat 客户端的协议降级/重试实现、上一轮审计修复点。
2. 客户端优化：为图片生成 POST 增加连接级重试、连接池重置、HTTP/2 -> HTTP/1.1 降级，以及 502/503/504 有限重试。
3. 下载优化：图片 API 返回 URL 时，对图片下载 GET 增加安全重试。
4. focused validation：模拟 RemoteProtocolError 后成功、持续 RemoteProtocolError 后失败。
5. 收口验证：全量测试、后端启动、前端启动抽查，并同步 bug/memory/tasks。
