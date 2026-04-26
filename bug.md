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

## Bug #48: CRM 用户档案页把 AI 能力藏在 available_actions 里，导致已配置 AI 看起来像“没打通”

- **日期**: 2026-04-25
- **现象**: `.env` 已配置 CRM profile 与 AI 开关，AI 接口也已挂载，但“用户档案”页面仍看不到 AI 对话入口，用户误以为功能没有打通。
- **根因**: 后端 `profile_loader` 只在 `safety_profile.status == ok` 时把 `ai_chat` 放进 `available_actions`，而 AI 服务正式门禁允许 `ok/partial`；前端又把 AI 入口完全绑定在 `available_actions.includes('ai_chat')` 上，导致一旦条件不满足，入口直接消失且没有原因说明。
- **复现条件**: 打开 CRM 用户档案页，选择一个 AI 已全局开启但安全档案不满足首页旧判断的客户。
- **解决方案**: 后端正式返回 `ai_chat_enabled` 和 `ai_chat_reason`，并把可用判断统一成“AI 已启用 + 安全档案为 `ok/partial`”；前端增加显式 AI 助手卡片，在不可用时直接展示原因，而不是隐藏入口。
- **关联文件**: app/crm_profile/services/profile_loader.py, app/crm_profile/schemas/context.py, app/crm_profile/schemas/api.py, frontend/src/views/CrmProfile/index.vue, frontend/src/views/CrmProfile/composables/useCrmProfile.ts, frontend/src/views/CrmProfile/components/AiCoachPanel.vue, frontend/src/views/CrmProfile/styles/CrmProfile.css

## Bug #49: CRM 客户姓名虽然进入上下文，但 AI 因代词歧义把“你”理解成自己

- **日期**: 2026-04-25
- **现象**: 在客户档案页选中具体客户后，教练问“你叫什么名字”，AI 回答成“我是 AI 助手，没有名字”，而不是回答当前客户姓名。
- **根因**: `basic_profile.display_name` 实际已经进入 prompt，但 system prompt 没有明确“当前对话围绕唯一客户”“你/她/他/这个客户默认指当前客户”；同时上下文正文和抽屉顶部仍暴露 `basic_profile / display_name` 这类技术键，进一步降低模型和用户的语义对齐。
- **复现条件**: 打开任意 CRM 客户档案，在 AI 抽屉中提问“你叫什么名字”“你今年几岁”“你现在是什么状态”这类代词指向当前客户的问题。
- **解决方案**: 在 `ai_coach.py` 中补充双重指令，明确代词默认指向当前客户，并在 context header 中显式写出当前客户姓名；在 `context_builder.py` 和前端 AI 抽屉中统一把技术模块名/字段名翻译成中文业务口径。
- **关联文件**: app/crm_profile/services/ai_coach.py, app/crm_profile/services/context_builder.py, app/crm_profile/services/modules/safety_profile.py, frontend/src/views/CrmProfile/index.vue, frontend/src/views/CrmProfile/components/AiCoachPanel.vue, frontend/src/views/CrmProfile/composables/useAiCoach.ts

## Bug #52: MySQL 不支持 `CREATE INDEX IF NOT EXISTS`，导致后端启动在 schema migration 阶段报 1064

- **日期**: 2026-04-25
- **现象**: 后端启动时抛出 `sqlalchemy.exc.ProgrammingError`，MySQL 报 `1064`，指向 `CREATE INDEX IF NOT EXISTS ix_crm_ai_sessions_customer_id ...`。
- **根因**: `app/schema_migrations.py` 在 `ensure_crm_ai_indexes()` 和 `ensure_external_docs_schema()` 中直接拼接 `CREATE INDEX IF NOT EXISTS` / `CREATE UNIQUE INDEX IF NOT EXISTS`。这套写法在 SQLite 可用，但 MySQL 不支持。
- **复现条件**: 使用 MySQL 启动应用，并执行到包含 CRM AI 或 external docs 索引检查的 schema migration。
- **解决方案**: 新增统一索引 helper，改成 `inspect(conn)` 先查 `_has_named_index(...)`，确认不存在后再执行普通 `CREATE INDEX` / `CREATE UNIQUE INDEX`，不再依赖 `IF NOT EXISTS`。
- **关联文件**: app/schema_migrations.py, app/main.py

## Bug #53: 客户档案 AI 抽屉把字段缺口常驻展示，并在每条回复下重复提醒，掩盖有效回答

- **日期**: 2026-04-25
- **现象**: AI 抽屉顶部长期显示“缺失关键字段 / 无数据”，同时每条 AI 回复下方也重复挂同样的缺口标签，教练阅读成本很高。
- **根因**: 前端把 `dataGaps` 设计成常驻区块，同时又把后端返回的 `missing_data_notes` 塞进每条 assistant message 的附加标签中，导致同一缺口在一个会话里被多次重复展示。
- **复现条件**: 打开任意存在数据缺口的客户 AI 抽屉，并发送至少一条问题。
- **解决方案**: 将缺口提示收口为“进入抽屉时一次性展示”，支持关闭并在开始对话后自动隐藏；同时移除消息气泡下方的 `missingDataNotes` 展示。
- **关联文件**: frontend/src/views/CrmProfile/components/AiCoachPanel.vue, frontend/src/views/CrmProfile/composables/useAiCoach.ts

## Bug #54: 客户姓名已进入上下文，但模型仍可能把字段标签当答案输出

- **日期**: 2026-04-25
- **现象**: 教练询问“这个客户叫什么名字”时，AI 可能回答成“当前客户的名字是[客户姓名]”或类似字段标签，而不是实际姓名。
- **根因**: 这类问题本质上是确定性资料问答，但系统此前完全交给模型生成；一旦 prompt 里同时存在“客户姓名”字段标签和真实姓名，模型可能复述标签而不取值。
- **复现条件**: 在客户档案 AI 抽屉中询问姓名、年龄、性别、当前状态、负责教练或所属群等基础资料问题。
- **解决方案**: 一方面在系统底线 prompt 和 context header 中明确禁止输出字段名/占位词；另一方面为明确资料问法增加本地直答捷径，直接从已加载档案返回答案。
- **关联文件**: app/crm_profile/services/ai_coach.py, app/crm_profile/services/prompt_builder.py, app/crm_profile/prompts/base/platform_guardrails.md

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

## Bug #29: 运营需要高频发送表情图时，普通素材目录入口过深导致图片消息配置效率低

- **日期**: 2026-04-14
- **现象**: 运营想把常用提醒类表情图作为独立图片消息发送，但现有素材库只有通用目录与未分类入口，发送中心选图时需要逐层翻找，且文件夹容易被误改或误删。
- **根因**: 素材库缺少面向高频运营场景的固定入口，发送中心的 `AssetPicker` 也没有为“表情包”类静态图片提供快捷筛选路径。
- **复现条件**: 在发送中心选择 `image` 消息，尝试从素材库快速找到常用表情图并发送。
- **解决方案**: 后端为素材库自动保底一个根级系统文件夹“表情包”，并禁止其重命名/删除/移动；前端在素材库页和素材选择弹窗中增加“表情包”快捷入口，让运营直接进入该目录上传和选用静态表情图。
- **关联文件**: app/routers/api_folders.py, frontend/src/views/Assets/index.vue, frontend/src/views/Assets/components/FolderSidebar.vue, frontend/src/views/Assets/composables/useFolders.ts, frontend/src/components/message-editor/AssetPicker.vue

## Bug #30: 发送中心只能把表情图当普通图片处理，运营容易误以为支持 GIF 动图发送

- **日期**: 2026-04-14
- **现象**: 发送中心虽然能选图片素材，但运营同学看不出“表情包”是独立的发送场景，也容易误解为企微支持直接发 GIF 动图。
- **根因**: 消息类型枚举里没有“表情包”这一业务语义，图片编辑器提示文案也没有明确告知企微机器人只能按静态图片发送。
- **复现条件**: 在发送中心准备发送表情图，或让运营同学首次使用“表情包”目录发送素材。
- **解决方案**: 在前后端消息类型中新增 `emotion` 作为 `image` 的业务别名；发送中心、预览、批量标签和模板类型统一显示“表情包”；图片编辑器在 `emotion` 模式下改为明确提示“企微不能直接发 GIF，需先保存静态图再上传素材库”。
- **关联文件**: frontend/src/views/Templates/composables/useTemplates.ts, frontend/src/components/message-editor/index.vue, frontend/src/components/message-editor/ImageEditor.vue, frontend/src/views/SendCenter/components/MessageForm.vue, frontend/src/views/SendCenter/composables/useSendLogic.ts, frontend/src/views/SendCenter/components/PreviewCard.vue, frontend/src/views/SendCenter/index.vue, frontend/src/views/SendCenter/components/ContentSelector.vue, app/services/wecom.py, app/routers/api.py

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

## Bug #31: 模板中心“保存并下一条”实际按草稿/跨天跳转，和当前天内顺序编辑心智不一致

- **日期**: 2026-04-11
- **现象**: 在模板中心选择某一天后，点击右侧详情区底部的“保存并下一条”，不会稳定切到当前天的下一个节点；当已在当天最后一个节点时，也没有提示是否新增节点。
- **根因**: `useWorkbenchActions.ts` 中的 `saveAndNext` 逻辑按“优先找后续 draft 节点，再跨天跳到下一个仍有 draft 的天”实现，和按钮文案表达的“当前天内顺序处理下一条”不一致。
- **复现条件**: 在运营编排中心任意选择一天和一个节点，编辑后点击“保存并下一条”；尤其在当天最后一个节点时观察按钮行为。
- **解决方案**: 将按钮逻辑改为：先保存当前节点；若当前天仍有后续节点，则直接切到下一个节点；若当前节点已是该天最后一个节点，则弹窗确认是否新增节点，确认后直接在当前节点后新增并选中新节点，取消则仅保留已保存结果。
- **关联文件**: frontend/src/views/Templates/composables/useWorkbenchActions.ts, frontend/src/views/Templates/index.vue

## Bug #32: 模板中心素材弹窗上传缺少进行中反馈，用户点击后只能被动等待

- **日期**: 2026-04-11
- **现象**: 在模板中心配置图片/文件节点时，如果从素材弹窗点击“上传到当前目录”，上传过程中界面没有明确的 loading 状态，用户看不到是否正在上传、也不知道是否可以继续操作。
- **根因**: `AssetPicker.vue` 的上传逻辑只有成功/失败消息，没有暴露独立的 `uploading` 视图状态，也没有把弹窗按钮、内容区和关闭行为切到上传中模式。
- **复现条件**: 打开模板中心任意图片或文件节点的素材选择弹窗，选择本地文件上传到当前目录，尤其在较大文件或网络较慢时更明显。
- **解决方案**: 为素材弹窗增加 `uploading` 状态，上传中时显示按钮 loading、顶部状态卡片和内容区 loading 文案，并临时禁用关闭/确认等易造成误解的操作，上传完成后自动刷新并选中新素材。
- **关联文件**: frontend/src/components/message-editor/AssetPicker.vue

## Bug #33: 模板卡片默认结构过于抽象，运营不知道该从哪一种卡片开始配置

- **日期**: 2026-04-14
- **现象**: 模板卡片入口虽然能编辑基础字段，但没有把 `text_notice` 和 `news_notice` 的差异及推荐用法讲清楚，运营同学通常只能看到半成品结构，不知道该直接套哪个模板。
- **根因**: 系统把“支持模板卡片”停留在技术能力层，没有同时内置完整示例和场景化默认结构，导致前端入口只提供 support 信息，没有提供 official 的可复用操作路径。
- **复现条件**: 在模板中心或发送中心切到 `template_card`，不参考外部文档时很难判断文本通知和图文展示分别该怎么用。
- **解决方案**: 为模板卡片编辑器补充完整示例预设，并新增文本通知/图文展示两套系统模板示例；同时把默认结构切换成可直接复用的完整卡片。
- **关联文件**: frontend/src/components/message-editor/TemplateCardEditor.vue, frontend/src/components/message-editor/templateCardPresets.ts, app/services/seed.py
## Bug #34: 素材上传接口仍按旧权限签名调用，运行时直接抛 TypeError

- **日期**: 2026-04-14
- **现象**: 访问 `/api/v1/assets/prepare-upload` 或 `/api/v1/assets/confirm-upload` 时，后端抛出 `TypeError: require_permission() takes 2 positional arguments but 3 were given`，导致素材上传前置流程直接失败。
- **根因**: `security.py` 中的权限校验函数已经统一为 `require_permission(user, key)`，但 `app/routers/api.py` 里的两个素材上传接口仍保留旧的 `require_permission(request, db, key)` 调用方式。
- **复现条件**: 登录后进入素材上传链路，触发“准备上传”或“确认上传”接口。
- **解决方案**: 将两个接口统一改为先通过 `get_user_or_401(request, db)` 获取 `user`，再调用 `require_permission(user, 'asset')`，和当前权限体系保持一致。
- **关联文件**: app/routers/api.py, app/security.py
## Bug #35: 语音目录的粘贴上传会把 `audio/mpeg` 误落成 `.mpeg` 文件名，导致前后端识别不一致

- **日期**: 2026-04-14
- **现象**: 在素材库“语音”目录里直接上传 `mp3` 没问题，但通过剪贴板粘贴音频时，系统可能把文件名落成 `.mpeg`，随后前端提示和后端白名单判断容易与用户认知的 `mp3` 脱节。
- **根因**: 浏览器从剪贴板给出的往往是 MIME `audio/mpeg`，而不是稳定的原始文件名后缀；原实现直接拿 `mime.split('/')` 的结果拼扩展名，导致把 MIME 子类型 `mpeg` 当成最终文件后缀。
- **复现条件**: 在素材库或素材选择弹窗中，向“语音”目录粘贴来自本地播放器/系统剪贴板的音频文件。
- **解决方案**: 前端在粘贴命名时增加 MIME -> 标准扩展名映射，把 `audio/mpeg` 统一规范成 `.mp3`；后端语音上传也同时按 MIME 和后缀双重识别，接受 `.mpeg` / `audio/mpeg` 并在转码前归一化为标准音频扩展名。
- **关联文件**: frontend/src/views/Assets/index.vue, frontend/src/components/message-editor/AssetPicker.vue, app/services/audio_transcode.py, app/routers/api.py

## Bug #36: 积分排行批量生成会静默跳过部分群，队列数量与勾选数量不一致但界面不解释原因

- **日期**: 2026-04-17
- **现象**: 在发送中心勾选多个外部群生成“积分推送”时，界面显示已勾选 22 个群，但真正进入发送队列的只有 21 条；用户无法直观看到是哪一个群被跳过，也不知道是无积分成员还是未绑定发送群。
- **根因**: `PointsRankingTab.vue` 在生成后直接过滤 `item.skipped` 和未绑定项，只保留可发消息进入 `batchItems`，但没有把跳过原因回显给用户；同时后端对“无正积分成员”的群会直接返回空结果，导致数量差异被静默吞掉。
- **复现条件**: 在发送中心的“积分排行”中勾选多个 CRM 群，其中至少一个群没有正积分成员或没有绑定本地发送群，然后点击“生成排行消息”。
- **解决方案**: 后端积分排行预览统一保留 skipped 元数据；前端生成后展示“选中 / 入队 / 跳过 / 未绑定”的结果摘要，并逐条列出被跳过群的原因。
- **关联文件**: frontend/src/views/SendCenter/components/PointsRankingTab.vue, app/services/crm_points_ranking.py

## Bug #37: 积分排行预览会在冷缓存或多群场景下超时，前端只能看到请求失败但看不到后端慢在哪一段

- **日期**: 2026-04-17
- **现象**: 在发送中心勾选较多外部群后点击“生成排行消息”，前端可能直接报超时；用户看不到当前是在查 CRM 成员、算周月积分，还是卡在 `point_logs` 洞察分析阶段。
- **根因**: 预览接口之前为了补群名会调用全量 `fetch_crm_groups()`，连带触发整库群积分统计；同时每个群生成消息时又会单独做一轮 `point_logs` 近 14 天洞察分析，且查询对象覆盖整群成员。路由层还按群逐条查绑定信息，进一步放大耗时，但接口和前端都没有阶段耗时日志与可视化进度。
- **复现条件**: 在 CRM 数据量较大、缓存未命中，或一次选择多个成员较多的外部群时，点击“生成排行消息”。
- **解决方案**: 后端改为按需查询所选群名称、批量查询绑定关系、洞察分析只覆盖实际上榜成员且限制分析人数，并在路由/服务层输出阶段耗时日志与慢群诊断；前端新增进度卡片、耗时展示和后端返回的分段耗时摘要。
- **关联文件**: app/routers/api_crm_points.py, app/services/crm_group_directory.py, app/services/crm_group_bindings.py, app/services/crm_points_insights.py, app/services/crm_points_ranking.py, frontend/src/views/SendCenter/components/PointsRankingTab.vue

## Bug #38: 后端认证链路硬依赖 passlib，环境少装一个包就会导致整站无法启动

- **日期**: 2026-04-21
- **现象**: 执行 `uvicorn app.main:app --host 0.0.0.0 --port 8000` 时，应用在 import `app.security` 阶段直接报 `ModuleNotFoundError: No module named 'passlib'`，系统教学等任意新功能都无法继续做真实启动验证。
- **根因**: `app/security.py` 和 `app/services/crm_admin_auth.py` 都直接从 `passlib.context` 导入 `CryptContext`，把一个本应可替换的密码哈希实现变成了启动期硬依赖；一旦当前解释器环境缺少 `passlib`，整个 FastAPI 应用会在路由注册前直接失败。
- **复现条件**: 在未安装 `passlib` 的 Python 环境里启动后端。
- **解决方案**: 新增 `app/password_utils.py` 作为共享密码上下文入口；优先使用 `passlib`，缺失时回退到兼容 `passlib pbkdf2_sha256` 格式的内置实现，从而保持现有本地账号 hash 仍可验证并让应用正常启动。
- **关联文件**: app/password_utils.py, app/security.py, app/services/crm_admin_auth.py

## Bug #39: 前端 tsconfig 的 ignoreDeprecations 配置高于当前 TypeScript 版本，导致类型检查在配置层直接失败

- **日期**: 2026-04-21
- **现象**: 执行 `cd frontend && .\\node_modules\\.bin\\vue-tsc.cmd --noEmit` 时，直接报 `TS5103: Invalid value for '--ignoreDeprecations'`，导致连新增页面的真实类型错误都看不到。
- **根因**: 仓库锁定的 TypeScript 版本是 `5.2.2`，但 `frontend/tsconfig.json` 中把 `ignoreDeprecations` 写成了 `6.0`，超出了当前编译器支持范围。
- **复现条件**: 在当前仓库依赖版本下执行 `vue-tsc --noEmit` 或 `npm run build`。
- **解决方案**: 将 `frontend/tsconfig.json` 中的 `ignoreDeprecations` 改为当前编译器兼容的 `5.0`，让类型检查重新落到真实源码层；随后继续修复暴露出来的实际类型错误。
- **关联文件**: frontend/tsconfig.json, frontend/src/views/SendCenter/components/PointsRankingTab.vue, frontend/src/views/Templates/components/PublishPlanDialog.vue

## Bug #40: crm_points_ranking 合并时把赋值表达式塞进 items.append，导致后端启动直接语法错误

- **日期**: 2026-04-22
- **现象**: 执行 `uvicorn` 启动后端时，Python 在导入 `app/services/crm_points_ranking.py` 时报 `SyntaxError: invalid syntax. Perhaps you forgot a comma?`，整站无法启动。
- **根因**: `preview_ranking_batch()` 在生成积分排行项时，本应先计算 `followup = generate_1v1_actions(...)`，再把结果放入 `items.append({...})`。但一次合并后误写成把赋值语句和日志语句直接塞进 `items.append(...)` 参数里，形成了非法 Python 语法。
- **复现条件**: 启动后端并导入 `app.main`，加载到 `app.services.crm_points_ranking`。
- **解决方案**: 将该段逻辑还原为三步：1) 单独计算 `followup`；2) 打印洞察和 1v1 动作日志；3) 再将完整消息对象追加到 `items`。
- **关联文件**: app/services/crm_points_ranking.py

## Bug #41: 七牛直传确认上传未给 `materials.storage_path` 保底，素材入库时被 MySQL 非空约束拦下

- **日期**: 2026-04-22
- **现象**: 在素材库通过七牛直传上传图片/文件后，请求 `/api/v1/assets/confirm-upload` 时后端抛出 `sqlalchemy.exc.IntegrityError: Column 'storage_path' cannot be null`，素材无法入库。
- **根因**: 直传确认接口只写入了 `storage_key`、`public_url`、`storage_provider` 等新对象存储字段，但 `materials.storage_path` 这个历史正式列仍是 MySQL 非空字段，且接口没有给它提供兼容保底值。
- **复现条件**: 开启七牛对象存储后，在素材库走“准备上传 -> 客户端直传 -> 确认上传”链路上传任意素材。
- **解决方案**: 为素材存储新增统一的 `storage_path` 兼容保底逻辑；确认上传时在没有本地路径时回填 `object_key`，同时补齐 `url/domain/source_filename/owner_id` 等元信息；构建 `StorageResult` 时仅在本地存储场景把 `storage_path` 当作真实本地回退路径，避免对象存储素材误走本地文件兜底。
- **关联文件**: app/routers/api.py, app/services/material_storage_service.py

## Bug #42: CRM 群积分排行连接层被重复定义覆盖成 5 秒超时，导致周/月积分查询频繁丢连接

- **日期**: 2026-04-23
- **现象**: 在发送中心“引用内容 -> 积分排行”里选择多个 CRM 群生成排行时，后端日志频繁出现 `CRM 数据库连接失败: (2013, 'Lost connection to MySQL server during query')` 与 `CRM 群组周/月积分联合查询失败`；接口虽然仍返回 200，但阶段耗时明显升高，并伴随数据降级。
- **根因**: `app/services/crm_group_directory.py` 里已经补过一套带简单连接池、`read_timeout=30` 的 `_get_connection()`，但文件下半段又残留了一份同名函数，实际运行时被 Python 后定义覆盖成了“无池化 + connect/read/write timeout 全是 5 秒”的版本。积分排行和 CRM 群列表中的联合聚合查询一旦稍慢，就会被 MySQL 直接打断。
- **复现条件**: 打开发送中心积分排行或 CRM 群列表，在冷缓存、群成员较多或 `point_logs` 较大的环境下触发 `fetch_crm_groups()`、`fetch_crm_group_members_bulk()`、`fetch_group_period_points_dual()` 等查询。
- **解决方案**: 删除重复的 5 秒 `_get_connection()` 定义，恢复统一的连接池与较宽松的超时配置；所有 CRM 群目录、群成员、周/月积分、CRM 管理员认证继续共用同一套 `_get_connection()` / `_return_connection()`。
- **关联文件**: app/services/crm_group_directory.py, app/services/crm_points_metrics.py, app/services/crm_points_insights.py, app/services/crm_admin_auth.py
## Bug #16: 系统教学编辑弹窗样式未命中根节点，导致弹窗偏顶且专注模式只在内容区内“伪全屏”

- **日期**: 2026-04-22
- **现象**: 点击“编辑文档”后，编辑弹窗整体偏向顶部，留白不足；点击“专注模式”后，界面没有真正全屏覆盖，而是只在主内容区内显示，顶部与侧边栏仍然可见，并伴随遮挡和显示不全。
- **根因**: 给 `el-dialog` 写的关键尺寸/全屏修正样式使用了错误选择器，写成了 `.system-teaching-editor-dialog .el-dialog`，但自定义 class 实际是直接挂在 `.el-dialog` 根节点上，导致这些规则没有命中。另外弹窗未 `append-to-body`，fullscreen 实际只在当前内容容器内生效。
- **复现条件**: 进入“系统教学”页面，点击“编辑文档”或切换“专注模式”。
- **解决方案**: 将编辑弹窗改为 `append-to-body`，并把根节点样式选择器修正为 `.el-dialog.system-teaching-editor-dialog` 及其 fullscreen 变体；同时把普通编辑态顶部留白调整为更合理的 `8vh`。
- **关联文件**: frontend/src/views/SystemTeaching.vue, frontend/src/views/styles/systemTeaching.css

## Bug #43: 积分排行多人洞察复用单人模板时把 `{rank}` 默认值渲染成“第0名”

- **日期**: 2026-04-23
- **现象**: 在发送中心“积分排行”里勾选 `头部领先 (TOP3)` 等洞察场景后，如果同一群有多位成员同时命中同一场景，最终消息会出现“于A、于B、于C 目前积分榜排名第0”之类明显错误的文案。
- **根因**: `app/services/crm_speech_templates.py` 的 `build_grouped_insight_speeches()` 会把同场景的多人洞察合并成一句，但它复用了单人模板，并固定传入 `rank=0` 作为占位值兜底。`top_leader` / `top_six` / `top_ten` 这类模板本身包含 `{rank}`，于是多人文案被直接格式化成“第0”。
- **复现条件**: 发送中心生成积分排行时，同一群至少两位成员同时命中带 `{rank}` 占位符的洞察场景，例如 `top_leader`。
- **解决方案**: 将多人同场景合并文案改为专门的多人表达，不再复用单人模板，也不再向模板注入 `rank=0`；单人场景仍沿用原模板，并继续使用真实 `rank`。
- **关联文件**: app/services/crm_speech_templates.py

## Bug #44: Docker 生产镜像未包含 `docs/system_teaching`，导致系统教学接口在容器内返回空列表

- **日期**: 2026-04-23
- **现象**: 服务器宿主机上 `docs/system_teaching/_meta.json` 和对应 Markdown 文档都存在，但线上访问 `/api/v1/system-docs/tree` 仍返回 `{"categories":[],"docs":[]}`，系统教学页面为空。
- **根因**: `Dockerfile` 只复制了 `app/`、`data/` 和前端构建产物，没有把 `docs/system_teaching` 打进镜像；`docker-compose.prod.yml` 也只挂载了 `./data:/app/data`，没有把文档目录映射进容器。结果容器内 `/app/docs/system_teaching/_meta.json` 缺失，后端按代码逻辑静默返回空列表。
- **复现条件**: 使用当前生产 Docker 构建/部署方式启动容器，并打开系统教学页面或调用 `/api/v1/system-docs/tree`。
- **解决方案**: 在 `Dockerfile` 中显式复制 `docs/system_teaching/` 到 `/app/docs/system_teaching/`；在 `docker-compose.prod.yml` 中增加 `./docs/system_teaching:/app/docs/system_teaching` 挂载，确保首次构建可用且后续在系统内编辑文档后不会因容器重建丢失。
- **关联文件**: Dockerfile, docker-compose.prod.yml

## Bug #45: 飞书文档工作台详情缺少阶段排序字段，导致有阶段数据时详情页直接崩溃

- **日期**: 2026-04-24
- **现象**: 打开飞书文档工作台详情页时，只要某个工作台下已经挂了带阶段的文档，后端就可能在组装 `stages` 时抛错，详情页无法正常展示。
- **根因**: `app/services/external_doc_workspace_service.py` 在构造 `term_info` 时只放了 `id/code/label`，但后续排序却直接访问 `term.sort_order`，导致实际有阶段数据时触发缺字段错误。
- **复现条件**: 创建一个带 `primary_stage_term_id` 的飞书文档绑定，然后访问对应工作台详情页。
- **解决方案**: 在 `term_info` 中补齐 `sort_order`，并继续按阶段顺序稳定排序；同时顺手把“缺少正式文档”的治理提示翻译成更面向运营的文案。
- **关联文件**: app/services/external_doc_workspace_service.py

## Bug #46: 飞书文档“快速登记”绕过正式主文档冲突校验，能写出多个“当前在用”真值

- **日期**: 2026-04-24
- **现象**: 通过飞书文档首页的“快速登记”弹窗，可以在同一项目、同一阶段下连续登记多个 `official + is_primary` 文档，系统不会拦截，导致“当前在用”文档真值冲突。
- **根因**: `app/services/external_doc_service.py` 的 `quick_add()` 没有复用 `create_binding()` 里的正式主文档冲突校验逻辑，直接创建了绑定记录。
- **复现条件**: 在同一工作台和阶段下，通过“快速登记”连续提交两篇角色为“正式/当前在用”的文档。
- **解决方案**: 抽出统一的 `_ensure_primary_official_conflict()` 校验函数，并让 `create_binding()`、`update_binding()`、`quick_add()` 共用；同时给 `quick_add()` 增加事务回滚，避免失败时留下半成品数据。
- **关联文件**: app/services/external_doc_service.py, app/routers/api_external_docs.py

## Bug #47: 飞书文档首页把全量数据误写成“我负责/最近打开”，并对无权限用户强拉治理队列

- **日期**: 2026-04-24
- **现象**: 飞书文档首页把系统“收件箱/模板中心”等公共工作台混进“我负责的工作台”，把按更新时间排序的全量资源误标为“最近打开”；同时页面本身不设 `sop` 权限门槛，却会在初始化时请求需要 `sop` 权限的治理接口，导致用户可见范围、页面标题和真实行为三方错位。
- **根因**: `useSopDocsHome()` 直接把 `/workspaces` 合并结果塞进 `myWorkspaces`，把 `/resources` 全量列表塞进 `recentDocs`；路由和侧边栏也没有同步 `sop` 权限控制。
- **复现条件**: 登录任意账号进入飞书文档首页，观察“我负责的工作台”“最近打开”和治理队列的实际数据来源。
- **解决方案**: 首页改成按“我负责的项目/专题”“常用入口”“其他可查看的项目”拆分工作台；最近打开改为基于当前用户打开日志；飞书文档相关路由和侧边栏统一受 `sop` 权限控制；页面文案同步改成人话，避免继续暴露内部术语。
- **关联文件**: frontend/src/router/index.ts, frontend/src/layout/SidebarContent.vue, frontend/src/views/SopDocs/index.vue, frontend/src/views/SopDocs/composables/useSopDocsHome.ts, frontend/src/views/SopDocs/components/*.vue, frontend/src/views/SopDocs/Governance.vue, frontend/src/views/SopDocs/WorkspaceDetail.vue, app/routers/api_external_docs.py, app/services/external_doc_service.py

## Bug #50: CRM 客户列表批量查群名 SQL 报语法错误，因 `groups` 是 MySQL 保留字未加反引号

- **日期**: 2026-04-25
- **现象**: 访问客户档案列表接口 `GET /api/v1/crm-customers/list` 时，后端抛出 `pymysql.err.ProgrammingError (1064)` SQL 语法错误，指向 `groups g ON g.id = cg.group_id` 附近。
- **根因**: `groups` 是 MySQL 保留关键字，在 SQL 中直接用作表名而未加反引号，导致 MySQL 解析器将其识别为关键字而非表名。同一问题出现在 `/filters` 端点和 `/list` 端点的群名批量查询中。
- **复现条件**: 访问 CRM 客户列表或筛选选项接口，触发任何涉及 `groups` 表的查询。
- **解决方案**: 在所有涉及 `groups` 表名的 SQL 语句中使用反引号 `` `groups` `` 转义。
- **关联文件**: app/crm_profile/router.py

## Bug #51: 筛选选项查询 `admins` 表使用了不存在的 `is_del` 字段

- **日期**: 2026-04-25
- **现象**: 客户档案页初始化请求 `/api/v1/crm-customers/list?include_filters=1` 时，后端抛出 `OperationalError (1054) Unknown column 'is_del' in 'where clause'`。
- **根因**: `_load_filter_options` 查询 `admins` 表时误加了 `WHERE is_del = 0 OR is_del IS NULL`，但 CRM 数据库的 `admins` 表只有 `status` 字段，没有 `is_del` 字段。`is_del` 字段仅存在于 `channels`、`customers`、`course`、`lesson` 等表。
- **复现条件**: 访问客户档案页触发筛选选项加载。
- **解决方案**: 去掉 `admins` 查询中的 `is_del` 条件。
- **关联文件**: app/crm_profile/router.py

## Bug #52: 前端 `#/*` 别名未同步到 TypeScript，导致 `vue-tsc` 和构建门禁被全量假错误淹没

- **日期**: 2026-04-25
- **现象**: 执行 `cd frontend && .\\node_modules\\.bin\\vue-tsc.cmd --noEmit` 或 `cd frontend && npm.cmd run build` 时，前端会抛出大量 `TS2307: Cannot find module '#/...'`，几乎覆盖整个项目，导致无法判断本次 CRM 客户档案改动是否真实通过类型检查。
- **根因**: Vite 运行时别名配置使用的是 `# -> ./src`，但 `frontend/tsconfig.json` 里漂成了 `@/*`，TypeScript 侧路径映射和 Vite 真值脱节；同时缺少标准的 `env.d.ts` 来声明 `vite/client` 与 `*.vue` 模块。
- **复现条件**: 在当前仓库执行 `vue-tsc --noEmit` 或 `npm run build`。
- **解决方案**: 在 `frontend/tsconfig.json` 中恢复 `#/* -> src/*` 的路径映射，补充 `types: [\"vite/client\"]`，并新增 `frontend/src/env.d.ts` 统一声明 Vite 与 `.vue` 模块类型。
- **关联文件**: frontend/tsconfig.json, frontend/src/env.d.ts

## Bug #53: CRM AI prompt 组装时漏掉第二段 system 上下文，导致模型拿不到完整客户档案说明

- **日期**: 2026-04-25
- **现象**: CRM AI 教练助手虽然看起来已经加载了客户档案，但模型侧偶尔会像没拿到完整上下文一样，出现对姓名、状态、模块边界理解不稳的情况；在继续接入流式链路时，这个问题会被进一步放大。
- **根因**: `assemble_prompt()` 返回的是“两段 system + 一段 user”的消息结构，但 `app/crm_profile/services/ai_coach.py` 旧实现只把第一段 system prompt 和最后一段 user message 真正送进模型，第二段承载客户上下文和说明的 system message 被丢掉了。
- **复现条件**: CRM AI 对话开启后，依赖客户上下文解释的问题（尤其是资料类、场景边界类问题）更容易出现理解偏差。
- **解决方案**: 重写 AI 消息组装函数，确保 prompt 中所有 system 层都进入模型调用，再叠加历史消息和当前用户问题。
- **关联文件**: app/crm_profile/services/ai_coach.py, app/crm_profile/services/prompt_builder.py

## Bug #54: CRM AI SSE 流在代理链路下容易被整包缓冲，前端只看得到固定占位语

- **日期**: 2026-04-25
- **现象**: AI 教练助手界面虽然出现了“思考过程”小框，但实际只显示固定占位句“正在整理当前客户的关键信息与回复思路...”，正式回复也像一次性返回，看起来像“根本没流起来”。
- **根因**: 流式接口第一版只返回 `StreamingResponse(text/event-stream)`，但没有显式关闭代理缓冲，也没有在快捷直读题和非流式 fallback 场景下做人眼可感知的分片推送。结果在某些链路里，SSE 分片会被吃成整包，前端自然只能看到占位语。
- **复现条件**: 通过 CRM AI 助手发起流式问答，尤其是“姓名/年龄/状态”这类会走快捷答复的直读题，更容易看到占位语不动、正式回复不呈现渐进输出。
- **解决方案**: 给 SSE 接口补充 `Cache-Control: no-cache, no-transform`、`Connection: keep-alive`、`X-Accel-Buffering: no`，首包先发注释行触发 flush；同时把快捷答复和 fallback 答复改成真正的分片输出，而不是一整段一次写完。
- **关联文件**: app/crm_profile/router.py, app/crm_profile/services/ai_coach.py, frontend/src/views/CrmProfile/composables/useAiCoach.ts

## Bug #55: 健康摘要 7/14/30 天切换缺少窗口覆盖率提示，用户误以为内容未刷新

- **日期**: 2026-04-26
- **现象**: CRM 客户档案健康摘要切换“近7天 / 近14天 / 近30天”时，页面主要指标看起来完全不变，用户无法判断是切换未生效还是窗口内没有更多数据。
- **根因**: 后端已按 `window` 查询并返回 `payload.window_days` / `data_quality.expected_days`，但前端只展示“共 N 天记录”，没有展示该 N 天属于哪个统计窗口，也没有在实际记录天数小于窗口天数时提示覆盖不足。对于近 30 天内本来只有 2 天记录的客户，7/14/30 三个窗口的有效样本相同，统计值自然相同，但 UI 没有解释这个事实。
- **复现条件**: 打开一个近 30 天内只有少量健康记录的客户档案，例如只有 2026-04-25、2026-04-26 两天记录的客户；切换 7/14/30 天窗口。
- **解决方案**: 健康摘要 meta 文案改为“近 X 天内共 N 天记录”，当 `N < X` 时展示“覆盖不足”标签和说明；同时 `switchHealthWindow` 请求成功后显式同步 `currentWindowDays`，避免状态只依赖 radio v-model。
- **关联文件**: frontend/src/views/CrmProfile/index.vue, frontend/src/views/CrmProfile/composables/useCrmProfile.ts, frontend/src/views/CrmProfile/styles/CrmProfile.css
