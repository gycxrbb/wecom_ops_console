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

## 代码组织规则

### 文件大小

- 单个 Python 文件不超过 **300 行**，超过必须拆分
- 单个 JS 文件不超过 **400 行**，超过按页面/功能拆分

### 后端分层

- **路由层**（router）：只做参数接收、校验、调用 service、返回响应，禁止写业务逻辑
- **服务层**（service）：放业务逻辑、状态编排、外部调用
- **数据层**（model）：ORM 定义 + 复杂查询封装为 classmethod
- 禁止在路由函数里直接写超过 5 行的数据库查询或业务编排

### 路由拆分

新增接口必须按资源放到对应的路由文件，结构如下：

```
routers/
├── auth.py          # 登录/登出
├── pages.py         # Jinja2 页面渲染
└── api/
    ├── __init__.py  # 汇总注册所有子路由
    ├── groups.py    # 群管理
    ├── templates.py # 模板管理
    ├── assets.py    # 素材管理
    ├── messages.py  # 消息发送、预览、重试
    ├── schedules.py # 定时任务
    ├── approvals.py # 审批
    ├── users.py     # 用户管理
    └── dashboard.py # 看板
```

禁止继续往 `api.py` 里堆叠新接口。

### 响应序列化

- 用 Pydantic schema 管理请求/响应结构，不要手拼 dict
- schema 文件按资源拆分到 `schemas/` 目录

### 错误处理

- 使用统一的业务异常类（如 `BizError`）+ 全局异常处理器
- 禁止每个路由函数各自构造不同格式的错误响应

### 前端 Vue 拆分

前端项目位于 `frontend` 目录，基于 Vue 3 + Vite 构建，使用 TypeScript。

```
frontend/src/
├── components/     # 全局公共组件
├── composables/    # 全局公共逻辑
├── layout/         # 页面布局组件
├── router/         # 路由配置
├── stores/         # Pinia 状态管理
├── utils/          # 工具函数（如 axios 封装）
└── views/          # 页面视图组件
    ├── Dashboard.vue
    ├── SendCenter/ # 复杂页面按模块拆分（如：逻辑/样式/子组件分离）
    │   ├── index.vue
    │   ├── composables/
    │   ├── components/
    │   └── styles/
    └── ...
```

### 禁止事项

- 禁止把多个不相关资源的接口写在同一个文件
- 禁止在路由函数里写业务逻辑后再复制粘贴到另一个路由
- 禁止新增代码时"顺手"往已有的大文件里追加而不拆分

## 开发完成验证规则

**每个功能开发完成后，必须执行项目启动测试，确认项目能正确启动后，才能向用户反馈"开发完成"。**

### 验证步骤

1. **后端启动测试**：执行 `uvicorn app.main:app --host 0.0.0.0 --port 8001`，【因为我本地服务在跑，8000端口被占用了】确认无报错、无 import 错误、应用正常启动
2. **前端启动测试**（如涉及前端改动）：执行 `cd frontend && npm run dev`，确认编译通过、无报错
3. **启动失败处理**：如果启动失败，必须先修复问题直到启动成功，不能把启动报错留给用户
4. 测试完成后记得释放端口！

### Windows 环境执行工具选择规则

**本项目运行在 Windows 环境，执行命令时必须用 PowerShell 工具，禁止用 Bash 工具。**

原因：
- Bash 工具底层运行在 Git Bash，无法正确解析 Windows 反斜杠路径（`.venv\Scripts\python.exe` 被吞掉 `\` 变成不可识别的路径）
- Windows 用户目录的 `.bashrc` 文件可能包含 UTF-16 BOM，导致 Bash 工具每次执行都报 `$'\377\376export': command not found`

适用场景：
- `python -m pytest`、`pip install`、`uvicorn` 等 Python 命令 → **必须用 PowerShell 工具**
- `npm run dev`、`npm install` 等 Node 命令 → **必须用 PowerShell 工具**
- 纯 POSIX 脚本或需要 `grep`/`sed`/`awk` 时才用 Bash 工具

### 强规则

- 禁止在项目无法启动的情况下反馈"开发完成"
- 禁止只检查语法不实际运行启动
- 启动测试通过是开发完成的最低标准，不是可选步骤
- 禁止用 Bash 工具执行 Python/Node 命令（Windows 路径兼容性问题）



## 行为准则 [用于减少 LLM 编程中的常见错误。]

**取舍说明：** 本准则偏向谨慎而非速度。对于简单任务，请自行判断是否适用。

---

## 1. 先思考，再编码

**不要假设。不要隐藏困惑。主动呈现权衡。**

开始实现前：

- 明确说明你的假设。如有不确定，先提问。
- 如果存在多种解读方式，逐一列出，不要默默选择其中一种。
- 如果存在更简单的方案，说出来。必要时提出异议。
- 如果有任何不清楚的地方，停下来。指出困惑所在，然后提问。

---

## 2. 简洁优先

**用最少的代码解决问题。不写投机性代码。**

- 不实现超出需求的功能。
- 不为只用一次的代码添加抽象层。
- 不添加未被要求的"灵活性"或"可配置性"。
- 不处理不可能发生的异常场景。
- 如果你写了 200 行而 50 行足够，重写它。

自我检验：「资深工程师会觉得这过度设计吗？」如果是，简化它。

---

## 3. 外科手术式修改   

**只改必须改的。只清理自己造成的混乱。**

修改现有代码时：

- 不"顺手优化"无关的代码、注释或格式。
- 不重构没有问题的东西。
- 保持现有代码风格，即使你有不同偏好。
- 发现无关的死代码时，提及它——但不要删除它。

当你的改动产生孤儿代码时：

- 移除**因你的改动**而变得无用的 import、变量、函数。
- 不删除改动前已存在的死代码，除非被明确要求。

检验标准：每一行改动都应能直接追溯到用户的需求。

---

## 4. 目标驱动执行

**定义成功标准。循环验证直至达成。**

将任务转化为可验证的目标：

- "添加校验" → "为非法输入编写测试，再让测试通过"
- "修复 bug" → "编写能复现问题的测试，再让测试通过"
- "重构 X" → "确保重构前后测试均通过"

对于多步骤任务，先简述计划：

```
1. [步骤] → 验证：[检查项]
2. [步骤] → 验证：[检查项]
3. [步骤] → 验证：[检查项]
```

清晰的成功标准让你能独立推进循环；模糊的标准（"让它能跑"）则需要反复确认。

---

**这些准则奏效的标志：** diff 中不必要的改动更少、因过度设计导致的返工更少、澄清性问题在实现前提出而非出错后补救。