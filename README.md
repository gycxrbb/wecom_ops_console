# WeCom Ops Console

企业微信运营后台 —— 面向训练营教练/运营团队的群消息自动化平台，集成客户 360 档案与 AI 教练助手。

## 功能概览

### 核心消息发送

| 能力 | 说明 |
|------|------|
| 多类型消息 | text、markdown、news（图文）、image、file、voice（AMR）、template_card、raw_json |
| 发送中心 | 单条/批量发送、测试群验证、消息队列、预览 |
| 定时调度 | 一次性 + Cron 周期任务、跳过周末/指定日期、日历视图 |
| 审批流 | 教练提交 → 管理员审批 → 自动执行 |
| AI 润色 | 调用 LLM 优化消息文案 |
| 频控 | 单机器人 20 条/分钟，内置限流 |

### 运营计划

| 能力 | 说明 |
|------|------|
| 日程编排 | Plan → Day → Node 三级结构，节点关联模板 |
| 导入/导出 | 支持 Excel (.xlsx) 和 JSON 格式 |
| 一键发布 | 将计划各天节点批量创建为定时任务 |
| 积分活动模式 | 专属活动阶段编排与批量建任务 |

### CRM 客户档案与 AI 教练

| 能力 | 说明 |
|------|------|
| 客户 360 档案 | 7 个模块：基础档案、体成分、目标偏好、健康摘要、积分活跃、安全档案、服务关系 |
| AI 教练助手 | 流式 SSE 对话，基于客户档案回答问题，支持可见思考链 |
| 多场景 Prompt | 6 个场景：餐评、数据监测、异常干预、答疑、周期复盘、长期维护 |
| 安全门禁 | 医疗内容过滤、需医生确认标记 |
| 客户专属配置 | 教练可编辑沟通风格、阶段重点、执行障碍等长期备注 |
| 上下文预加载 | 进入客户详情页后自动预热 AI 上下文缓存 |
| 消息选发 | 从 AI 对话中选择消息一键跳转发送中心 |

### CRM 积分运营

| 能力 | 说明 |
|------|------|
| 群绑定 | CRM 外部群 ↔ 本地微信群映射 |
| 积分排名 | 12 种话术场景、多种风格模板，支持单人/群排名 |
| 全局排名 | 跨群 TOP10 汇总 |
| 话术模板 | 按场景/风格管理可复用话术 |

### 外部文档管理

| 能力 | 说明 |
|------|------|
| 资源注册 | 飞书等外部链接统一管理 |
| 工作空间 | 项目级文档组织，阶段跟踪 |
| 术语体系 | 可配置的阶段/交付物/分类词汇 |
| 治理队列 | 过期/未验证文档追踪 |

### 系统管理

| 能力 | 说明 |
|------|------|
| 看板 | 群/模板/任务统计、发送成功率、趋势图 |
| 用户管理 | admin/coach 角色、权限精细控制（10 项权限） |
| 登录安全 | RSA 密码加密、JWT Token、暴力破解防护、CRM 账号联动登录 |
| 素材存储 | 本地 / 七牛云双存储，支持迁移和降级回退 |
| 系统教学文档 | Markdown 文档系统，草稿/发布模式 |
| 暗色主题 | 用户偏好主题切换 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Element Plus + Pinia + Vue Router + Vite |
| 后端 | Python FastAPI + SQLAlchemy + APScheduler + Celery + Redis |
| 数据库 | SQLite（开发）/ MySQL 8.0（生产） |
| AI/LLM | OpenAI 兼容 API（支持 aihubmix / DeepSeek） |
| 存储 | 本地文件系统 / 七牛云对象存储 |
| 部署 | Docker Compose（多阶段构建，单容器交付） |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Redis（Celery 依赖）

### 1. 启动后端

```powershell
Copy-Item .env.example .env          # 复制并填写配置
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173（Vite 自动代理 `/api` 到后端 8000 端口）。

### 3. VS Code 一键启动

在 VS Code 中执行 `Tasks: Run Task` → `dev:start-all`，自动双开终端启动前后端。

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin` | `Admin123456` |
| 教练 | `coach` | `Coach123456` |

### Docker 部署

```bash
docker compose up -d --build
```

生产环境使用 `docker-compose.prod.yml`（单容器 + 宿主机 MySQL/Redis/Nginx）。

## 项目结构

```
wecom_ops_console/
├─ app/                              # 后端 FastAPI 应用
│  ├─ main.py                        # 应用入口，lifespan 管理
│  ├─ config.py                      # 配置管理（65+ 环境变量）
│  ├─ database.py                    # SQLAlchemy 引擎
│  ├─ models.py                      # 核心 ORM 模型
│  ├─ models_external_docs.py        # 外部文档 ORM 模型
│  ├─ security.py                    # RSA/Fernet/JWT 认证加密
│  ├─ routers/
│  │  ├─ auth.py                     # 登录/登出
│  │  ├─ api.py                      # 核心 REST API
│  │  ├─ api_schedule_tools.py       # 调度日历/预览
│  │  ├─ api_operation_plans.py      # 运营计划管理
│  │  ├─ api_folders.py              # 素材文件夹
│  │  ├─ api_profile.py              # 用户资料
│  │  ├─ api_permissions.py          # 权限管理
│  │  ├─ api_sop.py                  # SOP 文档
│  │  ├─ api_system_docs.py          # 系统教学文档
│  │  ├─ api_crm_groups.py           # CRM 群目录
│  │  ├─ api_crm_points.py           # CRM 积分排名
│  │  ├─ api_speech_templates.py     # 话术模板
│  │  └─ api_external_docs.py        # 外部文档管理
│  ├─ services/
│  │  ├─ wecom.py                    # 企微 API 封装，消息构建和频控
│  │  ├─ scheduler_service.py        # APScheduler 封装
│  │  ├─ ai_polish.py                # AI 文案润色
│  │  ├─ storage/                    # 存储抽象层（本地/七牛）
│  │  ├─ crm_*.py                    # CRM 相关服务（积分/排名/话术/1v1）
│  │  └─ operation_plan_*.py         # 运营计划服务（导入/导出/发布）
│  ├─ clients/
│  │  ├─ ai_chat_client.py           # OpenAI 兼容聊天客户端（多 provider）
│  │  └─ crm_db.py                   # CRM 外部数据库连接池
│  └─ crm_profile/                   # 客户 360 档案模块（Feature Gate）
│     ├─ router.py                   # /api/v1/crm-customers 端点
│     ├─ services/
│     │  ├─ ai_coach.py              # AI 教练主逻辑（流式 SSE）
│     │  ├─ ai_context_preload.py    # AI 上下文后台预热
│     │  ├─ cache.py                 # Profile 缓存（TTL + stale-while-revalidate）
│     │  ├─ context_builder.py       # 上下文文本组装
│     │  ├─ prompt_builder.py        # 多层 Prompt 构建
│     │  ├─ safety_gate.py           # 安全门禁
│     │  └─ modules/                 # 7 个档案模块加载器
│     └─ prompts/                    # Markdown Prompt 模板
├─ frontend/                         # 前端 Vue3 应用
│  └─ src/
│     ├─ views/
│     │  ├─ SendCenter/              # 发送中心（消息编辑/队列/预览/调度）
│     │  ├─ Templates/               # 模板+运营计划工作台
│     │  ├─ CrmProfile/              # 客户档案 + AI 教练面板
│     │  ├─ SopDocs/                 # 外部文档管理
│     │  ├─ Groups/                  # 群管理（内部群/CRM群/排行榜）
│     │  └─ ...                      # Dashboard, Assets, Schedules, Logs 等
│     ├─ components/
│     │  ├─ markdown/                # Markdown 渲染（Shiki/KaTeX/Mermaid）
│     │  └─ message-editor/          # 多类型消息编辑器
│     └─ composables/                # 可复用逻辑（useAiCoach, useSendLogic 等）
├─ data/
│  ├─ app.db                         # SQLite 数据库
│  └─ uploads/                       # 本地素材存储
├─ docs/                             # 产品/设计/接口文档
├─ Dockerfile                        # 多阶段构建（Node构建 + Python运行）
├─ docker-compose.yml                # 开发环境（MySQL + Redis + App + Celery）
└─ docker-compose.prod.yml           # 生产环境（单容器 + 宿主机服务）
```

## 关键配置

### AI 教练（CRM 模块依赖）

```env
CRM_PROFILE_ENABLED=true
AI_COACH_ENABLED=true
AI_PROVIDER=aihubmix            # 或 deepseek
AI_API_KEY=your-key
AI_BASE_URL=https://aihubmix.com/v1
AI_MODEL=gpt-4o-mini
```

### CRM 数据库（外部 MySQL 只读）

```env
CRM_ADMIN_AUTH_ENABLED=true
CRM_ADMIN_DB_HOST=10.0.0.x
CRM_ADMIN_DB_PORT=3306
CRM_ADMIN_DB_USER=readonly
CRM_ADMIN_DB_PASSWORD=xxx
CRM_ADMIN_DB_NAME=mfgcrmdb
```

### 七牛云存储（可选）

```env
ASSET_STORAGE_PROVIDER=qiniu
QINIU_ACCESS_KEY=your-ak
QINIU_SECRET_KEY=your-sk
QINIU_BUCKET=your-bucket
QINIU_PUBLIC_DOMAIN=https://cdn.example.com
```

历史本地素材迁移：`python scripts/migrate_materials_storage.py --target qiniu`

## 关键设计

### 认证

- JWT Access Token（默认 24h 过期）+ Session 兜底
- RSA 公钥加密登录密码，bcrypt 哈希存储
- Fernet 对称加密存储 Webhook URL，不下发明文
- 支持 CRM 管理员账号联动登录

### 权限

- 10 项细粒度权限：send, schedule, group, template, plan, asset, sop, crm_profile, log, approval
- admin 拥有全部权限，coach 按需分配
- CRM 客户档案按教练-客户关系做可见性过滤

### 消息发送流程

```
模板渲染（Jinja2 变量） → 素材路径附加 → 类型构建（企微 payload）→ Webhook 发送 → 日志记录
```

### AI 教练流程

```
客户详情页加载 → 后台预热 profile 缓存
用户发问 → answer 流 + thinking 流并行 SSE
  → 统一 profile cache key（profile:{id}:hw7）
  → stale-while-revalidate 过期策略
  → 安全门禁后置检查 → 审计写入
```

### 存储架构

- 抽象层 `StorageProvider` → 本地/七牛两种实现
- `StorageFacade` 管理活跃/降级 provider
- 上传走客户端直传七牛（prepare/confirm 两步）
- 迁移脚本支持增量迁移，默认保留本地副本

## 文档

- [docs/CURRENT_STATUS.md](./docs/CURRENT_STATUS.md) — 仓库真实状态
- [docs/PRD.md](./docs/PRD.md) — 产品需求文档
- [docs/SYSTEM_DESIGN.md](./docs/SYSTEM_DESIGN.md) — 系统设计文档
- [docs/API_SPEC.md](./docs/API_SPEC.md) — 接口规范
- [CLAUDE.md](./CLAUDE.md) — AI 辅助开发指南

## License

Private — 内部使用
