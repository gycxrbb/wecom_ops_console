# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

企业微信消息运营后台，用于管理群机器人消息的模板、定时任务和批量发送。支持多种消息类型（text、markdown、news、image、file、template_card、raw_json），包含审批流程和发送日志。

## Commands

### Development
```bash
# 激活虚拟环境 (Windows)
.\.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker
```bash
docker compose up -d --build
```

## Architecture

```
app/
├── main.py           # FastAPI 应用入口，lifespan 管理数据库初始化和调度器
├── config.py         # 配置管理 (pydantic-settings)，从 .env 读取
├── database.py       # SQLAlchemy 引擎和会话
├── models.py         # ORM 模型: User, Group, Template, Asset, MessageJob, SendLog
├── security.py       # 密码哈希、webhook 加密、用户认证
├── routers/
│   ├── auth.py       # 登录/登出
│   ├── pages.py      # Jinja2 页面渲染
│   └── api.py        # REST API 端点
├── services/
│   ├── wecom.py          # 企业微信 API 封装，消息构建和发送，频控 (20条/分钟)
│   ├── scheduler_service.py  # APScheduler 封装，管理定时任务
│   ├── template_engine.py    # Jinja2 模板渲染，变量替换
│   └── seed.py          # 初始数据 (admin/coach 用户)
├── templates/        # HTML 模板
└── static/           # CSS/JS 前端资源
```

## Key Patterns

- **认证**: 基于 session，通过 `get_current_user` 获取当前用户
- **权限**: `require_role(user, 'admin')` 检查角色，admin 和 coach 两种角色
- **Webhook 安全**: 存储时用 Fernet 加密，不下发到前端
- **消息发送流程**: `render_message_content` → `attach_asset_paths` → `WeComService.send`
- **定时任务**: APScheduler，支持 once（一次性）和 cron（周期性），状态机: draft → scheduled/approved → completed
- **模板变量**: 内置 `today`、`tomorrow`、`weekday`、`coach_name`、`group_name`，可追加自定义 JSON

## Database

- 默认 SQLite (`data/app.db`)，通过 `database_url` 配置可切换 MySQL/PostgreSQL
- 启动时自动建表并执行 seed

## Rate Limiting

`WeComService` 内置 20 条/分钟的内存级限流，多实例部署需外部方案。

## Bug 与工程经验沉淀

工作中遇到的 bug、可复用的工程经验和解决方案必须及时沉淀到文档中。

### bug.md（Bug 沉淀）

每个 bug 记录：现象、根因、复现条件、解决方案、关联文件、日期。Bug 修复完成后必须同步更新。

### memory.md（工程经验沉淀）

可复用的工程模式、踩坑经验、调试方法论、性能优化经验、工具使用技巧。发现时必须同步更新。

**规则：不允许只修代码不沉淀文档。**
