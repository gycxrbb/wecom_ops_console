# WeCom Ops Console

这是一个给企业微信教练/运营使用的可视化消息运营后台，目标是把“写脚本 + 改配置”升级成真正可操作的前台。

## 已实现功能

- 群管理：每个群单独绑定 webhook，前台只选群，后端自动切换 webhook
- 模板中心：系统模板、自定义模板、复制模板、变量渲染
- 发送中心：支持立即发送、定时发送、周期任务、批量群发、测试群发送
- 消息类型：`text`、`markdown`、`news`、`image`、`file`、`template_card(JSON)`、`raw_json`
- 资产库：上传图片/文件，供 image/file 消息直接复用
- 定时任务：一次性任务、cron 周期任务、启停、复制、黑名单日期、跳过周末
- 审批流：教练可提交待审批任务，管理员批准后执行
- 发送记录：成功/失败日志、请求体、返回值、失败重试
- 角色：默认提供 `admin` 和 `coach` 两个账号
- 看板：群数、模板数、任务数、发送成功率、最近记录

## 适合的使用方式

- 教练在页面选择群聊
- 选择消息类型和模板
- 自定义编辑内容
- 选择立即发送 / 一次性定时 / 周期发送
- 需要时可先发到测试群

## 快速开始（Windows）

```powershell
cd wecom_ops_console
Copy-Item .env.example .env
py -m venv .venv
.\.venv\Scriptsctivate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 `http://127.0.0.1:8000`

默认账号：

- 管理员：`admin / Admin123456`
- 教练：`coach / Coach123456`

> 第一次使用前，请先进入“群管理”，把测试群/正式群的 webhook 改成你自己的企业微信群机器人地址。

## 推荐上线方式

### 本地验证

- 先建一个测试群机器人
- 用测试群 webhook 配到“测试群”
- 在发送中心选择“测试群发送”验证所有模板

### 云端部署

```bash
docker compose up -d --build
```

或者：

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 目录结构

```text
wecom_ops_console/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ database.py
│  ├─ models.py
│  ├─ security.py
│  ├─ services/
│  ├─ routers/
│  ├─ templates/
│  └─ static/
├─ data/
│  └─ uploads/
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
└─ README.md
```

## 消息类型说明

- `text`：文本提醒，可配置 `mentioned_list` 和 `mentioned_mobile_list`
- `markdown`：适合课程内容、重点强调、换行层级
- `news`：适合图文卡片、文章、活动页跳转
- `image`：从资产库选图，后端自动转 base64 + md5
- `file`：从资产库选文件，后端自动上传 media 再发送
- `template_card(JSON)`：给需要复杂结构化卡片的场景
- `raw_json`：保底高级模式，直接发原始 payload

## 模板变量

模板和计划任务里都支持变量渲染，默认内置：

- `today`
- `tomorrow`
- `weekday`
- `coach_name`
- `group_name`

你也可以在模板或任务里追加 JSON 变量，例如：

```json
{
  "topic": "211餐盘+餐后走",
  "summary_deadline": "20:30"
}
```

## 审批规则

- `coach` 创建任务时可选择“需要审批”
- `admin` 可在任务列表里批准
- 未批准任务不会被调度执行

## 频控

项目内置单机器人 20 条/分钟的内存级限流保护；多实例部署时建议再叠加 Redis 或消息队列。

## 注意事项

- webhook 是密钥，不会下发到前端
- SQLite 适合单机/轻量场景，生产建议换 MySQL/PostgreSQL
- APScheduler 适合单实例任务调度；多实例生产环境建议使用专门任务队列
