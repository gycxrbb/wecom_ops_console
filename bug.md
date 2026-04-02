## Bug #1: 定时任务与日志模型真值漂移导致调度链路不稳定

- **日期**: 2026-03-31
- **现象**: `Schedule`、`MessageLog`、`scheduler_service` 与 `api.py` 之间字段口径不一致，出现旧模型名 `MessageJob`、旧字段 `content_snapshot` 与新字段 `content_json` / `group_ids_json` 并存，导致定时任务、日志列表、日志重试和素材下载链路不稳定。
- **根因**: 后端代码从旧单群任务模型向当前前端消费口径迁移过程中，路由层先演进，ORM、调度服务、种子数据和日志链路没有同步收口。
- **复现条件**: 创建或查询定时任务、触发调度服务、查看日志列表、重试日志、下载素材时，命中旧字段引用或旧模型名引用。
- **解决方案**: 第一批最小收口不做 refresh、REST 重构或额外功能扩展，保留当前数据库真值，改为在 `api.py`、`scheduler_service.py`、`tasks.py`、`seed.py` 和 `models.py` 中补兼容桥接与旧字段适配，统一围绕当前前端口径稳定工作。
- **关联文件**: app/models.py, app/routers/api.py, app/services/scheduler_service.py, app/services/seed.py, app/tasks.py

## Bug #2: 第二轮正式迁移在 MySQL 上被 TEXT 默认值规则阻断

- **日期**: 2026-03-31
- **现象**: 第二轮将 `Schedule` 新列正式落库时，应用启动失败，报错 `TEXT column ... can't have a default value`。
- **根因**: 当前环境实际连接的是 MySQL，不是本地 SQLite；迁移 SQL 中为 `TEXT` 列声明了默认值，触发 MySQL 限制。
- **复现条件**: 启动应用执行 `ALTER TABLE schedules ADD COLUMN group_ids_json TEXT DEFAULT '[]'` 等语句。
- **解决方案**: 迁移脚本改为不给 `TEXT` 列设置数据库默认值，改用幂等回填逻辑补齐初始值；随后重新启动验证通过。
- **关联文件**: app/schema_migrations.py, app/main.py

## Bug #3: 测试群占位 webhook 被误判为已配置，导致发送按钮必失败

- **日期**: 2026-03-31
- **现象**: 发送中心点击“发送到测试群”后失败，但群列表仍显示 webhook 已配置，排查成本高。
- **根因**: 种子数据默认写入 `replace-test-key` / `replace-prod-key` 占位 webhook；接口序列化仅按 `webhook_cipher` 是否有值判断 `webhook_configured`，把占位值误当成真实配置；同时现有数据库里的“测试群”记录还可能漂移成 `formal` 类型，导致 `test_group_only` 查询不到目标群。
- **复现条件**: 使用默认 seed 初始化数据库后，未在群管理中改成真实企业微信群机器人地址，直接点击发送到测试群。
- **解决方案**: 前端补上正式“发送到测试群”按钮和 `test_group_only` 参数；后端测试发送改为同步直发并在队列不可用时回退直发；同时把占位 webhook 识别为“未配置”，发送时返回明确错误，新环境 seed 不再写入假 webhook，并在启动时自动修正默认测试群类型漂移。
- **关联文件**: frontend/src/views/SendCenter/composables/useSendLogic.ts, frontend/src/views/SendCenter/components/MessageForm.vue, frontend/src/views/SendCenter/index.vue, app/routers/api.py, app/services/seed.py

## Bug #4: 图文预览把普通文本当 Jinja 模板编译，导致预览直接 500

- **日期**: 2026-03-31
- **现象**: 发送中心选择图文消息后，点击预览时后端抛出 `jinja2.exceptions.TemplateSyntaxError: expected token 'end of print statement', got ':'`。
- **根因**: `render_value` 对所有字符串都执行 `env.from_string(...).render(...)`；图文内容中的某些普通文本或用户输入若包含不完整的 `{{ ... }}` 片段，会被 Jinja 当模板解析并直接报错。
- **复现条件**: 图文消息的标题、描述、链接等任意字符串字段中出现 Jinja 风格花括号但语法不合法，然后调用 `/api/v1/preview`。
- **解决方案**: 模板渲染器改为仅在字符串看起来像模板时才走 Jinja 编译，并在 `TemplateSyntaxError` 时降级返回原文，避免预览和发送链路被单个非法文本击穿。
- **关联文件**: app/services/template_engine.py, app/routers/api.py

## Bug #5: 图文消息把相对素材地址当公网 URL 发送，导致企业微信返回 40039

- **日期**: 2026-03-31
- **现象**: 图文消息预览通过，但真正发送时企业微信返回 `{"errcode": 40039, "errmsg": "invalid url size"}`。
- **根因**: 图文消息的 `url` / `picurl` 需要公网可访问的 `http(s)` 地址；当前编辑器曾允许把素材库返回的相对下载地址 `/api/v1/assets/{id}/download` 填进 `picurl`，或提交空/非法链接，直到发送时才被企业微信拒绝。
- **复现条件**: 在图文编辑器中使用素材库/本地上传生成的相对地址，或填写非公网 `url` / `picurl`，然后调用发送接口。
- **解决方案**: 后端在预览和发送前统一校验图文链接必须是公网可访问的 `http(s)` 地址；前端图文编辑器去掉误导性的本地上传/素材库封面入口，改为明确要求填写公网图片地址。
- **关联文件**: app/routers/api.py, frontend/src/components/message-editor/NewsEditor.vue

## Bug #6: 群管理与发送记录页继续使用旧字段名，导致配置保存和结果展示失真

- **日期**: 2026-04-01
- **现象**: 群管理页修改测试群/启用状态后可能不生效；发送记录页即使后端已有日志，也会把成功状态、请求体和响应体显示错位。
- **根因**: 前端继续向 `/v1/groups` 发送旧字段 `enabled` / `group_type`，而后端实际消费 `is_enabled` / `is_test_group`；日志页继续读取 `is_success`、`request_payload`、`response_payload`，而后端实际返回 `success`、`request_json`、`response_json`。
- **复现条件**: 在群管理页切换测试群或启用状态后刷新；或打开发送记录页查看最近日志。
- **解决方案**: 前端群管理页切回当前后端真值字段；发送记录页改为消费当前日志序列化结构并格式化 JSON 展示。
- **关联文件**: frontend/src/views/Groups.vue, frontend/src/views/Logs.vue, app/routers/api.py

## Bug #7: 图片/文件消息编辑器与素材库链路脱节，导致两类消息实际上难以发送

- **日期**: 2026-04-01
- **现象**: 图片消息要求手填服务器绝对路径，文件消息要求手填 `media_id`，普通运营用户几乎无法正确配置。
- **根因**: 前端编辑器没有复用现有素材库，而后端真实发送链路其实已经支持通过 `asset_id` 自动解析 `image_path` / `file_path` 并完成发送。
- **复现条件**: 在发送中心或模板中心选择 `image` / `file` 类型，尝试按界面提示完成配置。
- **解决方案**: 图片/文件编辑器改为直接接素材库，选择素材后写入 `asset_id`；发送时由后端统一补足真实文件路径或上传文件，不再要求用户手填底层字段。
- **关联文件**: frontend/src/components/message-editor/ImageEditor.vue, frontend/src/components/message-editor/FileEditor.vue, frontend/src/components/message-editor/AssetPicker.vue, app/routers/api.py

## Bug #8: 异步发送与日志重试未复用主发送校验，导致同一消息在不同入口报错口径不一致

- **日期**: 2026-04-01
- **现象**: 立即发送主链路已经能识别占位 webhook 和非法图文链接，但 Celery 异步发送与“日志重试”仍可能直接把问题请求发到下游，得到另一套错误表现。
- **根因**: 主发送链路里的 webhook 校验、图文链接校验没有同步复用到 `send_message_task` 和 `/logs/{id}/retry`。
- **复现条件**: 使用占位 webhook 或非法图文链接创建消息后，走异步队列发送，或在日志页点击“重试”。
- **解决方案**: 在异步任务与日志重试链路补入同一套 webhook 与图文 outbound 校验，统一错误行为和日志记录。
- **关联文件**: app/tasks.py, app/routers/api.py

## Bug #9: 图片消息把完整 base64 payload 写入数据库，导致发送时先被 MySQL 字段容量打爆

- **日期**: 2026-04-01
- **现象**: 图片消息预览正常，但真实发送到测试群时，后端在保存 `messages.request_payload` / `message_logs.request_payload` 时抛出 `Data too long for column 'request_payload'`，请求在本地数据库层失败。
- **根因**: 企业微信图片消息 payload 含完整 base64 内容，长度远超当前数据库字段可安全承载的范围；系统此前把完整 payload 原样写入日志。
- **复现条件**: 发送 `image` 类型消息，尤其是使用真实图片素材时。
- **解决方案**: 发送前保留完整 payload 参与请求，但写库时改为压缩存储版本，将超大的 `image.base64` 替换为长度占位文本；同时让主发送、异步任务和重试入口统一使用该压缩存储逻辑。
- **关联文件**: app/services/wecom.py, app/routers/api.py, app/tasks.py

## Bug #10: 素材下载地址被同时拿来做图片预览，导致缩略图失败且下载链路失效

- **日期**: 2026-04-02
- **现象**: 发送中心从素材库选择图片时缩略图显示 `FAILED`，但真实发送不受影响；素材库点击“下载”也无法真正下载文件。
- **根因**: 后端把素材 `url` 统一序列化成受鉴权保护的下载接口，前端又把它直接用于 `<el-image>` 预览和 `window.open()` 下载；浏览器这两种访问方式都不会自动带 SPA 里的 `Authorization` 请求头，而后端原先也不识别 query token。
- **复现条件**: 登录后在发送中心打开图片素材弹窗，或在素材库点击任一素材“下载”。
- **解决方案**: 后端为图片素材新增独立 `preview` 接口，并让鉴权兼容 `token` query；素材序列化拆出 `preview_url` / `download_url`；前端图片预览统一走带 token 的预览地址，下载改为 axios 带鉴权请求 blob 后再触发保存。
- **关联文件**: app/security.py, app/routers/api.py, frontend/src/utils/assets.ts, frontend/src/components/message-editor/AssetPicker.vue, frontend/src/components/message-editor/ImageEditor.vue, frontend/src/views/Assets.vue

## Bug #11: 素材库下载请求被前端 baseURL 二次拼接，导致接口稳定返回 404

- **日期**: 2026-04-02
- **现象**: 素材库页面点击“下载”后前端提示 `Request failed with status code 404`。
- **根因**: 素材数据里的 `download_url` 已经是完整的站内接口路径 `/api/v1/assets/{id}/download`，但前端继续使用带 `baseURL: /api` 的 axios 实例发起请求，最终实际访问成 `/api/api/v1/assets/...`。
- **复现条件**: 在素材库列表页点击任一素材“下载”。
- **解决方案**: 下载链路改为直接使用原始 axios 请求 `download_url`，只补 `Authorization` 请求头，不再经过带 `/api` 前缀的统一 request 实例；同时把素材库页升级为列表/平铺双模式，便于在同一页面完成预览和文件管理。
- **关联文件**: frontend/src/views/Assets.vue, frontend/src/utils/assets.ts
