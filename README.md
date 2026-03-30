# WeCom Ops Console

企业微信群消息运营后台 —— 把"写脚本 + 改配置"升级为教练/运营可自助操作的可视化平台。

## 项目背景

训练营/教练团队在企业微信群内推送内容时，长期依赖脚本和手工改配置。存在以下痛点：

- 发送内容需要研发介入，教练无法自助完成
- 群与 Webhook 映射缺乏统一管理，容易误发或泄露配置
- 定时任务、模板、素材和发送记录缺乏统一平台，排查问题成本高
- 缺乏审批、预览、测试群发送、失败重试等生产级能力

本系统将群消息发送从"开发维护"升级为"教练/运营自助操作"，支持训练营、答疑群、复训群、VIP 群等多类运营场景。

## 功能概览

| 模块 | 能力 |
|------|------|
| 群管理 | 群与 Webhook 绑定、正式群/测试群区分、标签、启停 |
| 模板中心 | 系统模板 + 自定义模板、复制、变量渲染、预览 |
| 资产库 | 图片/文件上传、标签管理、供消息直接复用 |
| 发送中心 | 立即发送、测试群发送、批量群发 |
| 定时任务 | 一次性 + Cron 周期任务、启停、复制、跳过周末、跳过日期 |
| 审批流 | 教练提交 → 管理员审批 → 自动生效 |
| 发送记录 | 成功/失败日志、请求体、返回值、失败重试 |
| 看板 | 群数、模板数、任务数、发送成功率、近期记录 |

### 支持的消息类型

`text` `markdown` `news` `image` `file` `template_card(JSON)` `raw_json`

| 类型 | 适用场景 |
|------|---------|
| text | 文本提醒，支持 @人 / @手机号 |
| markdown | 课程内容、重点强调、换行层级 |
| news | 图文卡片、活动页跳转 |
| image | 从资产库选图，自动转 base64 + md5 |
| file | 从资产库选文件，自动上传 media |
| template_card | 复杂结构化卡片 |
| raw_json | 高级模式，直接发送原始 payload |

### 用户角色

| 角色 | 职责 |
|------|------|
| admin（管理员） | 维护群/Webhook/模板/素材、审批任务、处理失败重试、查看全量数据 |
| coach（教练） | 选择群与模板、编辑内容、立即/定时发送、测试群验证、查看自己的任务和记录 |

## 典型使用流程

```
教练登录 → 选择群聊 → 选择消息类型和模板 → 自定义编辑内容
  → 选择发送方式（立即 / 定时 / 周期）
  → 可选：先发测试群验证
  → 可选：提交审批 → 管理员批准 → 自动执行
  → 在发送记录中查看结果
```

## 模板变量

模板和定时任务都支持变量渲染，内置变量：

| 变量 | 说明 |
|------|------|
| `{{today}}` | 当天日期 |
| `{{tomorrow}}` | 明天日期 |
| `{{weekday}}` | 星期几 |
| `{{coach_name}}` | 教练姓名 |
| `{{group_name}}` | 群名称 |

可追加自定义 JSON 变量：

```json
{
  "topic": "211餐盘+餐后走",
  "summary_deadline": "20:30"
}
```

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 本地启动（Windows）

```powershell
cd wecom_ops_console
Copy-Item .env.example .env          # 复制并填写配置
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 http://127.0.0.1:8000

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin` | `Admin123456` |
| 教练 | `coach` | `Coach123456` |

> 首次使用前，请先在"群管理"中把测试群/正式群的 Webhook 改为你自己的企业微信群机器人地址。

### Docker 部署

```bash
docker compose up -d --build
```

### 生产部署

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 推荐上线流程

1. **本地验证** — 建一个测试群机器人，配置到"测试群"，在发送中心用"测试群发送"验证所有模板
2. **正式上线** — 配置正式群 Webhook，创建模板和定时任务
3. **日常运营** — 教练自助选群选模板发送，管理员按需审批和监控

## 项目结构

```
wecom_ops_console/
├─ app/
│  ├─ main.py                # FastAPI 入口，lifespan 管理数据库初始化和调度器
│  ├─ config.py              # 配置管理（pydantic-settings，从 .env 读取）
│  ├─ database.py            # SQLAlchemy 引擎和会话
│  ├─ models.py              # ORM 模型：User, Group, Template, Asset, MessageJob, SendLog
│  ├─ security.py            # 密码哈希、Webhook 加密、用户认证
│  ├─ routers/
│  │  ├─ auth.py             # 登录/登出
│  │  ├─ pages.py            # Jinja2 页面渲染
│  │  └─ api.py              # REST API 端点
│  ├─ services/
│  │  ├─ wecom.py            # 企业微信 API 封装，消息构建和发送，频控（20条/分钟）
│  │  ├─ scheduler_service.py    # APScheduler 封装，定时任务管理
│  │  ├─ template_engine.py      # Jinja2 模板渲染，变量替换
│  │  └─ seed.py                 # 初始数据（admin/coach 用户）
│  ├─ templates/             # HTML 模板
│  └─ static/                # CSS/JS 前端资源
├─ data/
│  ├─ app.db                 # SQLite 数据库
│  └─ uploads/               # 上传文件存储
├─ docs/
│  ├─ PRD.md                 # 产品需求文档
│  ├─ SYSTEM_DESIGN.md       # 系统设计文档
│  └─ API_SPEC.md            # 前后端统一接口文档
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
└─ README.md
```

## 关键设计

### 认证与权限

- 基于 session 的认证，通过 `get_current_user` 获取当前用户
- `require_role(user, 'admin')` 进行角色校验
- Webhook 使用 Fernet 对称加密存储，不下发到前端

### 消息发送流程

```
render_message_content → attach_asset_paths → WeComService.send
```

1. 模板引擎渲染变量
2. 附加图片/文件素材路径
3. 根据消息类型构建企业微信 payload
4. 调用 Webhook 发送并记录日志

### 定时任务

- 基于 APScheduler，支持 `once`（一次性）和 `cron`（周期性）
- 任务状态机：`draft` → `scheduled`/`approved` → `completed`
- 支持跳过周末、跳过指定日期

### 审批流

- 教练创建任务时可选择"需要审批"
- 管理员在任务列表中审批
- 未批准任务不会被调度执行

### 频控

内置单机器人 20 条/分钟的内存级限流。多实例部署建议叠加 Redis 或消息队列。

## 注意事项

- Webhook 是密钥，加密存储，不返回前端明文
- 默认使用 SQLite，适合单机/轻量场景；生产环境可通过 `database_url` 配置切换 MySQL/PostgreSQL
- APScheduler 适合单实例调度；多实例生产环境建议使用 Celery + Redis

## 演进规划

| 阶段 | 内容 |
|------|------|
| V1（当前） | FastAPI + Jinja2 + SQLite + APScheduler，单机轻量部署 |
| V2 | Vue3 + Element Plus + TypeScript 前端重构，MySQL + Redis，Celery 调度 |
| V3 | Next.js 预览/SSR 扩展，A/B 测试，多租户，消息效果追踪 |

详细规划参见 `docs/` 目录下的产品需求文档、系统设计文档和接口规范。

## License

Private — 内部使用
