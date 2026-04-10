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

## Bug #12: 发送中心把变量面板错误绑定到“是否选模板”，导致 Markdown 直编时看不到自定义变量

- **日期**: 2026-04-03
- **现象**: 在发送中心不选择模板、直接切换到 `Markdown` 等消息类型开始编辑时，自定义变量面板不会出现；只有先选模板才会显示。
- **根因**: 前端把 `MessageEditor` 的 `showVariables` 条件写成了 `!!selectedTemplate`，把“是否支持变量”误绑成了“是否引用模板”。
- **复现条件**: 打开发送中心，不选任何模板，直接把消息类型切到 `Markdown` 并开始编辑。
- **解决方案**: 发送中心改为按“消息类型是否支持变量”控制显示，并保留“已选模板时一定显示”的兜底逻辑，不再依赖模板选择状态。
- **关联文件**: frontend/src/views/SendCenter/components/MessageForm.vue

## Bug #13: 运营编排中心迁移在 MySQL 下给 TEXT 列声明默认值，导致应用启动失败

- **日期**: 2026-04-04
- **现象**: 新增运营编排中心后，后端启动在 `ensure_plan_schema(engine)` 阶段失败，报错 `BLOB, TEXT, GEOMETRY or JSON column 'description' can't have a default value`。
- **根因**: `schema_migrations.py` 里的原始建表 SQL 为 `plans.description`、`plan_days.focus`、`plan_nodes.content_json`、`plan_nodes.variables_json` 这些 `TEXT` 列写了 `DEFAULT ''` 或 `DEFAULT '{}'`，该写法在 MySQL 上不兼容。
- **复现条件**: 使用 MySQL 数据库启动包含运营编排中心迁移逻辑的后端应用。
- **解决方案**: 移除这些 `TEXT` 列的数据库默认值，改为由应用写入链路显式提供内容，保持 SQLite/MySQL 双端兼容。
- **关联文件**: app/schema_migrations.py, app/routers/api_operation_plans.py

## Bug #14: SOP 导入器引入 openpyxl 但未同步运行时依赖，导致后端启动失败

- **日期**: 2026-04-06
- **现象**: 新增 `sheet1` SOP 导入功能后，后端启动时报错 `ModuleNotFoundError: No module named 'openpyxl'`，应用在导入路由加载阶段直接失败。
- **根因**: `app/services/operation_plan_import.py` 新增了 `openpyxl` 依赖，但项目的 `.venv` 和 `requirements.txt` 没有同步补齐该包，导致开发环境与代码真值漂移。
- **复现条件**: 在未安装 `openpyxl` 的环境中启动包含 SOP 导入器的后端应用。
- **解决方案**: 将 `openpyxl==3.1.5` 正式加入 `requirements.txt`，并在当前 `.venv` 中安装后重新执行启动验证。
- **关联文件**: app/services/operation_plan_import.py, requirements.txt

## Bug #15: 登录系统只认本地 users 表，无法直接复用 CRM 运营成员账号

- **日期**: 2026-04-06
- **现象**: 企微运营平台登录只支持本地 seed 出来的 `admin/coach` 账号，CRM 后台真实运营成员即使存在于外部 `mfgcrmdb.admins` 表中，也无法登录当前系统。
- **根因**: 认证逻辑完全绑定本地 `users` 表和 PBKDF2 密码哈希，没有预留外部用户库认证或本地镜像同步能力。
- **复现条件**: 使用 CRM `admins` 表中的任意运营成员账号尝试登录当前系统。
- **解决方案**: 保留本地 `admin` 账号为正式管理员入口；其余账号接入 CRM `admins` 表认证，并在登录成功后自动同步到本地 `users` 表作为镜像账号，继续复用现有 JWT、权限和 owner_id 体系。
- **关联文件**: app/config.py, app/security.py, app/services/crm_admin_auth.py, app/routers/api.py, app/routers/auth.py, frontend/src/views/Login.vue, .env

## Bug #16: 个人中心长期停留在占位页，导致账号安全和头像管理没有正式入口

- **日期**: 2026-04-07
- **现象**: 个人中心只有“账号信息 / 权限说明 / 账户安全”三块静态展示，其中“账户安全”仍提示开发中，用户无法修改本地密码，也不能上传个人头像。
- **根因**: 系统缺少独立的 profile 资源层，`users` 表也没有头像来源字段；前端个人中心页只是说明性 UI，没有与后端正式账户能力打通。
- **复现条件**: 登录系统后进入个人中心，尝试修改密码或更换头像。
- **解决方案**: 为 `users` 增加 `avatar_url` / `auth_source` 字段并补迁移；新增 `/api/v1/profile` 资源支持资料更新、头像上传和本地账号改密；前端个人中心重构为正式工作台，并在 CRM 账号下明确显示“密码由外部系统统一管理”。
- **关联文件**: app/models.py, app/schema_migrations.py, app/main.py, app/routers/api_profile.py, app/security.py, app/services/crm_admin_auth.py, app/services/seed.py, frontend/src/views/Profile.vue, frontend/src/stores/user.ts, frontend/src/layout/index.vue

## Bug #17: 定时任务可创建但应用启动时未拉起调度器，导致“到点自动发送”不生效

- **日期**: 2026-04-08
- **现象**: 发送中心和定时任务页都可以创建、查看、克隆、手动运行任务，但服务重启后没有自动恢复和执行数据库里的定时任务。
- **根因**: `ScheduleService` 已实现 APScheduler 调度与 `sync_from_db()`，但 `app.main` 的生命周期里没有调用 `schedule_service.start()` 和 `schedule_service.sync_from_db()`，调度器从未正式接入应用启动流程。
- **复现条件**: 创建一个一次性或 cron 定时任务，保持应用运行并等待触发时间，或重启应用后观察任务是否自动恢复执行。
- **解决方案**: 在应用 lifespan 启动阶段拉起调度器并从数据库同步任务，在关闭阶段优雅 shutdown，让定时任务从“仅能管理”升级为“真正随服务运行自动执行”。
- **关联文件**: app/main.py, app/services/scheduler_service.py, app/routers/api.py, frontend/src/views/SendCenter/composables/useSendLogic.ts, frontend/src/views/Schedules.vue

## Bug #18: 定时任务触发成功但不实际发送消息（Celery 无 worker + 时区偏移）

- **日期**: 2026-04-08
- **现象**: 定时任务到点后前端显示"已完成"，但实际没有发送消息到企业微信群；后端日志无 `Executing job` 输出，也无报错；前端显示的"最近执行时间"比设定时间早 8 小时（如设定 11:40 却显示 03:40）。
- **根因**: 三层问题叠加：
  1. **Celery 无 worker**：`do_send_to_groups` 非测试模式先走 `send_message_task.delay()`，Redis 可达时 `delay()` 不报错返回，但无 worker 消费队列，消息永远不发送。函数返回 `success: True, response: 'Queued'` 有误导性。
  2. **时区偏移 8 小时**：APScheduler 默认 UTC、`DateTrigger` 未注入时区、`last_sent_at` 使用 `datetime.utcnow()`，三层 UTC 和 Asia/Shanghai 混用导致 8 小时偏移。
  3. **诊断不足**：`sync_from_db` 和 `add_or_update_job` 无日志输出，问题定位困难。
- **复现条件**: 创建一次性定时任务，等待到达触发时间，观察消息是否实际发送到企微群。
- **解决方案**：
  1. 去掉 Celery 异步队列，`do_send_to_groups` 所有模式统一改为直接同步发送。
  2. APScheduler 全链路统一 `Asia/Shanghai` 时区：scheduler 初始化、`DateTrigger`、`compute_next_runs`、`last_sent_at`。
  3. 为 `sync_from_db`、`add_or_update_job`、`execute_job` 增加详细诊断日志。
  4. `misfire_grace_time` 从 60 秒增加到 300 秒，避免 uvicorn 热重载短暂中断导致 misfire 跳过。
- **关联文件**: app/routers/api.py, app/services/scheduler_service.py, app/tasks.py, app/celery_app.py

## Bug #19: 素材存储记录表在 MySQL 下使用 TEXT 默认值，导致应用启动失败

- **日期**: 2026-04-08
- **现象**: 接入七牛素材存储记录表后，后端启动在 `ensure_asset_folders_schema -> _ensure_material_storage_schema` 阶段失败，MySQL 报错 `BLOB, TEXT, GEOMETRY or JSON column 'extra_json' can't have a default value`。
- **根因**: `schema_migrations.py` 手写建表 SQL 为 `material_storage_records.extra_json` 声明了 `TEXT DEFAULT '{}'`，该写法在 MySQL 方言下不兼容。
- **复现条件**: 使用 MySQL 作为主数据库，启动包含素材存储记录表迁移逻辑的应用。
- **解决方案**: 去掉 `extra_json` 的数据库默认值，保持为纯 `TEXT` 列，并由应用层在写入记录时显式传入 `{}`。
- **关联文件**: app/schema_migrations.py

## Bug #20: 素材迁移脚本从仓库根目录直接运行时拿不到 app 包

- **日期**: 2026-04-08
- **现象**: 执行 `python scripts/migrate_materials_storage.py --help` 时，脚本在导入阶段直接报 `ModuleNotFoundError: No module named 'app'`。
- **根因**: 脚本位于 `scripts/` 目录，直接执行时 Python 的模块搜索路径不包含仓库根目录，导致 `from app...` 的绝对导入失效。
- **复现条件**: 从项目根目录直接运行迁移脚本。
- **解决方案**: 在脚本入口显式把仓库根目录注入 `sys.path`，保证 CLI 模式下也能稳定导入 `app` 包。
- **关联文件**: scripts/migrate_materials_storage.py

## Bug #21: 七牛上传 token 去掉 Base64 padding 且 region 配错时会直接触发 BadToken / region mismatch

- **日期**: 2026-04-08
- **现象**: `.env` 已补齐七牛配置后，最小上传探针先返回 `401 BadToken`，修掉签名后又返回 `incorrect region, please use up-z0.qiniup.com`。
- **根因**: 自写的七牛上传 token 把 URL-safe Base64 的 `=` padding 去掉了，导致 token 非法；同时当前 bucket 实际在 `z0`，而配置写成了 `z2`。
- **复现条件**: 用错误 region 或错误 token 编码方式调用七牛表单上传接口。
- **解决方案**: 保留 Base64 padding，不再 `rstrip('=')`；并在上传返回 region mismatch 提示时自动提取推荐 upload host 重试一次。
- **关联文件**: app/services/storage/qiniu.py

## Bug #22: 素材迁移 dry-run 写审计记录时直接塞 dict，导致 MySQL 提交失败

- **日期**: 2026-04-08
- **现象**: 执行 `scripts/migrate_materials_storage.py --dry-run` 时，扫描流程完成但提交数据库阶段报 `TypeError: dict can not be used as parameter`。
- **根因**: `material_storage_records.extra_json` 在模型中是 `TEXT` 列，迁移脚本却直接把 Python `dict` 作为参数写入。
- **复现条件**: 运行素材迁移脚本并让其写入 `migrate` 审计记录。
- **解决方案**: 在迁移脚本写审计记录前显式用 `json_dumps` 序列化 `extra_json`。
- **关联文件**: app/services/material_storage_migration.py

## Bug #23: 七牛对象 key 只基于文件名生成时，同名素材迁移会互相覆盖

- **日期**: 2026-04-08
- **现象**: 两条不同素材 `ID 1 / ID 2` 在迁移到七牛后，落成了同一个 `public_url` 和 `storage_key`，后迁移的对象会覆盖先迁移的对象。
- **根因**: 七牛对象 key 生成规则只依赖文件名 slug，没有引入素材级唯一因子，导致同名文件在同一天迁移时生成相同 key。
- **复现条件**: 迁移两条名字相同或标准化后相同的素材到七牛。
- **解决方案**: 对象 key 改为 `slug + 随机唯一后缀`，保证同名素材也能得到不同对象路径；对已受影响素材执行强制重迁。
- **关联文件**: app/services/storage/qiniu.py, scripts/migrate_materials_storage.py

## Bug #24: 素材上传接口在切对象存储后漏导入 Path，导致上传直接 500

- **日期**: 2026-04-08
- **现象**: 素材库上传新资源时后端直接 500，日志报 `NameError: name 'Path' is not defined`。
- **根因**: `upload_asset` 重构为对象存储上传后，代码里使用了 `Path(file.filename).name`，但 `app/routers/api.py` 顶部没有同步导入 `Path`。
- **复现条件**: 在素材库上传任意新图片或文件。
- **解决方案**: 在 `app/routers/api.py` 顶部补 `from pathlib import Path`。
- **关联文件**: app/routers/api.py

## Bug #25: 素材库上传时间显示偏差，原因是后端把 UTC naive 时间直接下发给前端

- **日期**: 2026-04-08
- **现象**: 素材库里新上传资源的“上传时间”显示不对，和实际本地时间存在偏差。
- **根因**: `materials.created_at` 由 `datetime.utcnow` 生成，后端序列化时直接 `isoformat()` 下发为无时区字符串，前端按浏览器本地方式解释，造成时区歧义。
- **复现条件**: 上传素材后查看素材库中的时间显示。
- **解决方案**: 后端在 `serialize_material` 中把素材时间显式转换到 `Asia/Shanghai` 后再返回，前端再按统一格式展示。
- **关联文件**: app/routers/api.py, frontend/src/utils/assets.ts, frontend/src/views/Assets/components/AssetGrid.vue

## Bug #26: 坏素材未在发送链路和素材选择器中设门禁，容易混进正常发送

- **日期**: 2026-04-08
- **现象**: 已经缺失源文件或已删除的素材，如果仍残留在引用链路中，前端选择和后端发送阶段可能出现行为不一致。
- **根因**: `attach_asset_paths` 之前只校验素材是否存在，没有显式拦截 `source_missing/deleted`；素材选择器也没有过滤坏素材。
- **复现条件**: 选择或引用一条已损坏的素材进行发送。
- **解决方案**: 后端在 `attach_asset_paths` 中拦截不可用素材；前端素材选择器过滤 `source_missing`，素材库页面对不可用素材禁用预览/下载。
- **关联文件**: app/routers/api.py, frontend/src/components/message-editor/AssetPicker.vue, frontend/src/views/Assets/components/AssetGrid.vue

## Bug #27: 图片消息预览在对象存储接入后被静态方法/类方法漂移击穿

- **日期**: 2026-04-08
- **现象**: 素材上传、列表、预览、下载都正常，但发送中心对 `image` 类型做消息预览时后端直接抛 `NameError: name 'cls' is not defined`。
- **根因**: `WeComService.build_payload` 仍被声明成 `@staticmethod`，但图片分支已经改成调用 `cls._read_asset_bytes(...)` 以兼容对象存储素材，导致运行时找不到 `cls`。
- **复现条件**: 上传图片素材后，在发送中心选择图片消息并调用 `/api/v1/preview`。
- **解决方案**: 将 `build_payload` 调整为 `@classmethod`，让图片分支和后续可能复用存储读取能力的消息类型都能合法访问类级辅助方法。
- **关联文件**: app/services/wecom.py

## Bug #28: 前端 TypeScript 配置把 ignoreDeprecations 设成 6.0，直接阻断构建

- **日期**: 2026-04-09
- **现象**: 执行 `npm run build` 时，`vue-tsc` 直接报 `tsconfig.json(16,27): error TS5103: Invalid value for '--ignoreDeprecations'`。
- **根因**: 当前前端依赖里的 TypeScript 版本是 `5.2.x`，但 `frontend/tsconfig.json` 把 `ignoreDeprecations` 配成了 `6.0`，超出了当前编译器支持范围。
- **复现条件**: 在当前仓库执行前端构建或类型检查。
- **解决方案**: 将 `ignoreDeprecations` 调整回当前 TS 版本可接受的 `5.0`，恢复前端构建链路。
- **关联文件**: frontend/tsconfig.json

## Bug #28: 前端构建被 tsconfig 的 ignoreDeprecations 配置拦住

- **日期**: 2026-04-09
- **现象**: 执行 `npm run build` 时，`vue-tsc -b` 在读取 `frontend/tsconfig.json` 阶段直接报 `TS5103: Invalid value for '--ignoreDeprecations'`。
- **根因**: 当前环境里的 TypeScript / vue-tsc 组合不接受仓库里现有的 `ignoreDeprecations: \"5.0\"` 配置，导致即使业务代码正确也会被构建门禁拦下。
- **复现条件**: 在 `frontend` 目录执行 `npm run build`。
- **解决方案**: 从 `frontend/tsconfig.json` 去掉这项非必要配置，让构建回到正式编译路径。
- **关联文件**: frontend/tsconfig.json

## Bug #29: 用户管理创建失败时前端静默吞错，容易被误判成“账号已创建但登录没反应”

- **日期**: 2026-04-10
- **现象**: 管理员在“用户管理”点击“新增用户”后，界面没有明确报错；随后再去登录新账号，表现成“没反应”或误以为账号已经创建成功。
- **根因**: 后端 `/api/v1/users` 之前没有对“重复用户名”“创建时缺少密码”给出清晰业务校验；前端 `Users.vue` 捕获失败后只 `console.error`，没有把错误提示给操作者。与此同时，当前系统又同时存在“本地账号创建”和“CRM 成员同步授权”两套口径，进一步放大了误解。
- **复现条件**: 在用户管理页创建重名用户、和 CRM 镜像账号重名的本地用户，或触发创建失败的其他情况。
- **解决方案**: 后端为 `/api/v1/users` 增加用户名唯一性和创建密码必填校验，并在重名时明确提示该用户名当前属于本地账号还是 CRM 同步账号；前端在保存失败时弹出错误信息，并在页面头部写清“这里只创建本地登录账号，CRM 成员请去权限管理页同步授权”。
- **关联文件**: app/routers/api.py, frontend/src/views/Users.vue

## Bug #30: 登录先按账号来源分流会把本地账号也拖进 CRM 慢链路，表现成登录超时

- **日期**: 2026-04-11
- **现象**: 用户名已经存在于本地 `users` 表，但登录时前端没有立即得到“账号密码错误”或“登录成功”，而是长时间等待后超时。
- **根因**: 原认证逻辑先根据 `auth_source` 判断账号类型，再决定是否走本地或 CRM；当用户名同时存在“本地可认证需求”和“CRM 镜像背景”时，本地库没有被优先当作正式第一道门禁，导致请求容易被外部 CRM 查询拖慢。
- **复现条件**: 输入本地表里已有的用户名登录，且当前账号路径会继续触发 CRM 校验分支，或 CRM 库响应较慢。
- **解决方案**: 将认证顺序改为“先查本地 `users` 表并验证本地 hash；本地通过就直接登录；仅当本地未命中或当前是 CRM 镜像且本地密码不匹配时，才回源 CRM”。这样本地账号走本地快路径，CRM 账号仍保留外部真值校验。
- **关联文件**: app/security.py
