## 2026-05-18

- 已恢复 `docs/AI对话多模态Agent化总体开发文档.md` 当前状态，确认文档已有 Agent 化、Visual Lane、图片生成和阶段计划章节。
- 已完成第一批修改：总体链路、Agent 化路径、职责拆分已改为“从本文档开始按 Agent 工作流落地，图片生成直接调用 `gpt-image-2` 直出”。
- 已完成置信度分流修改：高置信自动异步生成；低置信进入 `manual_confirm_required`，由前端询问教练是否需要绘制图片。
- 已完成文档一致性复核：去除了模板渲染器/混合渲染作为主路径的口径，补齐了配置、事件、阶段计划和验收标准的一致性。

## 2026-05-20

- 开始排查 AI 视觉生图任务失败但 AI 调用审计显示 success 的状态不一致问题。
- 初始判断：需要对照 AI 对话流中的视觉任务创建审计写入点、后台图像生成执行点、任务失败状态回写点。
- 已定位根因：`visual_generation` 在 job 创建后立即写 `success`，后台图片 API 失败只更新 `ai_visual_jobs`，未更新 `crm_ai_trace_steps`。
- 已完成修复：job 创建时审计 step 写为 `pending`；后台 `ready/failed` 后通过 `audit_call_id + step_index` 更新同一条 step。
- 已补 focused validation：`tests/test_ai_visual_audit.py` 模拟上游断连，验证 job 与审计 step 均变为 failed。
- 已沉淀 `bug.md` Bug #78 与 `memory.md` 经验 #131。
- 后端启动验证通过：临时端口 8017，`GET /api/v1/health` 返回 `{"status":"ok","db":true}`。
- 前端启动抽查通过：临时端口 5177，Vite ready，首页返回 HTTP 200；临时进程已停止。
- 全量测试通过：`python -m pytest tests -q`，59 passed（仅保留既有 utcnow / Query regex deprecation warnings）。

## 2026-05-20 生图稳定性优化

- 开始优化 `image_client.py`，目标是减少上游图片 API 首包前断连导致的单次失败。
- 已对照 `ai_chat_client.py` 的协议降级/连接池重置模式，决定在图片生成客户端内实现有限重试，并继续保留上一轮“失败必须如实进审计”的 official 真值规则。
- 已完成客户端优化：连接级异常会关闭当前连接池并重试，HTTP/2 开启时降级 HTTP/1.1；502/503/504 做有限重试；返回 URL 的图片下载也做安全重试。
- 新增配置：`ai_visual_generation_max_retries` 默认 2，`ai_visual_generation_retry_delay_seconds` 默认 1.5。
- focused validation 已通过：`tests/test_ai_visual_image_client.py` 覆盖断连后重试成功、持续断连后失败；连同上一轮审计失败路径共 3 passed。
- 已沉淀 `bug.md` Bug #79 与 `memory.md` 经验 #132。
- 代码编译通过：`py_compile` 覆盖 `image_client.py`、`job_executor.py`、`job_service.py`、`config.py` 和新增测试。
- 全量测试通过：`python -m pytest tests -q`，61 passed（仅既有 deprecation warnings）。
- 后端启动验证通过：临时端口 8018，`GET /api/v1/health` 返回 `{"status":"ok","db":true}`，临时进程已停止。
- 前端启动抽查通过：临时端口 5178，Vite ready，首页 HTTP 200，临时进程已停止。

## 2026-05-20 生图连接错误根因诊断

- 用户反馈重试后仍出现 HTTP/2 与 HTTP/1.1 均断连：说明客户端重试已触发，但上游/链路仍在响应头前断开。
- 本轮目标调整为新增分层诊断脚本，先确认 DNS/TCP/TLS、`/models`、HTTP 协议和 `/images/generations` payload 兼容性，不把 support 探测结果误写成 official 生图成功。
- 已新增 `scripts/diagnose_ai_visual_image_api.py`：默认只做 DNS/TCP/TLS、`/models`、无额度图片端点探针；`--generate` 才真实调用 `/images/generations`。
- 低成本诊断结果：DNS/TCP/TLS 正常；`/models` 在 HTTP/2 和 HTTP/1.1 均 200，且模型列表包含 `gpt-image-2`；`/images/generations` 无效模型探针在 HTTP/2 和 HTTP/1.1 均返回预期 400 JSON，证明图片端点路径、鉴权和基础协议可达。
- 当前最可能原因收敛：不是本机基础网络/证书/鉴权/endpoint 路径问题；更可能是 `gpt-image-2` 真实生图上游、账号对该模型的实际生成权限/额度、或当前有效 payload（`size=auto`、`quality=auto`）在 aihubmix 图片生成转发链路上的兼容问题。
- 验证完成：脚本 `py_compile` 通过；视觉相关 focused tests 3 passed；后端临时端口 8019 启动并健康检查通过；前端临时端口 5179 Vite ready 且首页 HTTP 200。
- 真实生图诊断继续收敛：`gpt-image-2` 的 current payload、compat payload、甚至极短 prompt `red apple` 都在 HTTP/1.1 下约 62 秒后 `RemoteProtocolError: Server disconnected without sending a response`；`gpt-image-2-free` 返回明确 400 无权限；`gemini-2.5-flash-image` 返回明确 400 schema 不兼容。
- 当前 official 判断：本项目客户端、DNS/TCP/TLS、鉴权、`/models` 和 `/images/generations` 路径均可达；失败集中在 aihubmix 对 `gpt-image-2` 的真实生成上游链路，疑似 provider 网关 60s 超时/账号实际生成权限或服务端生成超时。
- 已调整客户端失败策略：短连接抖动继续重试；若真实生图请求已等待超过 `ai_visual_generation_gateway_timeout_hint_seconds`（默认 55s）后才断开，则归类为 `api_timeout` 并停止重复请求，避免一次失败拖成多轮 60s 等待。
- 已沉淀 `bug.md` Bug #80 与 `memory.md` 经验 #133。
- 全量验证通过：`py_compile` 覆盖 image client/config/诊断脚本/测试；`python -m pytest tests -q` 为 62 passed；后端临时端口 8020 健康检查通过；前端临时端口 5180 Vite ready 且首页 HTTP 200。
