# 新服务器部署 + CRM 数据库切换计划

> 制定日期：2026-05-20
> 适用场景：把 `wecom_ops_console` 从旧服务器迁到新服务器，同时把 CRM 数据源从测试库 `mfgcrmdb` 切到生产库 `habitilitydb`。
> 关联文档：[`deploy-guide.md`](../deploy-guide.md)（原始部署手册）、[`部署文档.txt`](../部署文档.txt)（运维速查）

---

## 0. 一句话结论

- **代码层**：只要 `habitilitydb` 与 `mfgcrmdb` **表名/字段名完全一致**，就**只改 `.env`**，零代码变动。
  目前代码里直连 CRM 的所有 SQL 都硬编码了 `customers / admins / customer_*` 等表名（详见 §2.2），如果新库表名不同，必须做兼容层。**这一点上线前必须先核对**。
- **部署层**：新服务器走和旧服务器同一套 Docker 流程（`docker compose -f docker-compose.prod.yml`），只是 `.env` 里所有外部地址（MySQL/Redis/CRM/Qdrant/Nginx 域名）需要按新机器实际情况重填。
- **数据层**：本地 `wecom_ops` 业务库（消息模板、定时任务、AI 审计等）必须从旧服务器 dump 后导入新服务器，否则会丢历史数据。

---

## 1. 现状梳理

### 1.1 当前架构（来自 [`deploy-guide.md`](../deploy-guide.md)）

```
浏览器 → Nginx(:80/443/8080)
  └── 反代 → Docker(:8000) FastAPI + Vue SPA
                ├── 本机 MySQL(:3306, 数据库 wecom_ops)        ← 项目自有业务数据
                ├── 本机 Redis(:6379)                          ← 缓存 / 流式 / token
                ├── 本机 Qdrant(:6333)                         ← RAG 向量库
                ├── 远程 MySQL CRM (mfgcrmdb)                  ← 即将切到 habitilitydb
                └── 七牛云（素材存储）                          ← 不变
```

### 1.2 数据库切换信息

| 维度 | 旧 (现 .env) | 新 (要切到) |
|---|---|---|
| 角色 | 测试环境 | **生产环境** |
| Host | `rm-2zedqey0120581pj9do.mysql.rds.aliyuncs.com` | `rm-2zew061b0tlpd75m2.mysql.rds.aliyuncs.com` |
| User | `mfgcrmuser` | `habituser` |
| Password | `Mfg@135!%` | `hbt@135!%` |
| DB Name | `mfgcrmdb` | `habitilitydb` |
| 用途 | CRM 管理员登录 + 用户 profile + 习惯打卡 + 群成员目录 等 | 同左（前提：schema 一致） |

---

## 2. 代码侧影响评估

### 2.1 配置入口（[`app/config.py`](../app/config.py:24)）

涉及 CRM 的配置项已经做了字段化，**没有硬编码连接串**：

```python
crm_admin_db_host: str = ''
crm_admin_db_port: int = 3306
crm_admin_db_user: str = ''
crm_admin_db_password: str = ''
crm_admin_db_name: str = 'mfgcrmdb'          # ← 默认值不影响生产，生产从 .env 读
crm_admin_table_name: str = 'admins'         # ← 表名是配置项！登录链路天然解耦
```

→ **`.env` 替换四件套（HOST/USER/PASSWORD/DB_NAME）即可让连接切到新库**。

### 2.2 硬编码的 CRM 表名清单（关键风险点）

代码里走 [`app/clients/crm_db.py`](../app/clients/crm_db.py) 直连 CRM 的所有 SQL **直接写死表名**（不是配置项），新库必须有这些同名表 + 同名字段：

| 表名 | 出现位置（节选） | 使用方 |
|---|---|---|
| `admins` | [`app/services/crm_admin_auth.py:56`](../app/services/crm_admin_auth.py)（通过 `crm_admin_table_name` 配置可改名）<br>[`app/crm_profile/routers/customers.py:24`](../app/crm_profile/routers/customers.py) | CRM 后台账号登录 / 列表 |
| `customers` | `crm_profile/routers/customers.py`<br>`crm_profile/services/modules/basic_profile.py`<br>`crm_profile/services/modules/points_engagement.py`<br>`crm_profile/services/invocation_audit/_query.py`<br>`crm_profile/services/modules/_loaders.py` | 客户基础信息 / 积分 / 身高 |
| `customer_info` | `safety_profile.py`、`goals_preferences.py` | 客户健康档案 / 偏好 |
| `customer_health` | `_loaders.py` | 健康体征记录 |
| `customer_glucose` | `_loaders.py` | 血糖记录 |
| `customer_habits` | `habit_adherence.py` | 习惯定义 |
| `customer_checkin_records` | `habit_adherence.py` | 打卡记录 |
| `customer_obstacles` | `habit_adherence.py` | 障碍记录 |
| `customer_reminders` | `reminder_adherence.py` | 提醒任务 |
| `customer_plans` | `plan_progress.py` | 计划 |
| `customer_todos` | `plan_progress.py` | 待办 |
| `customer_course_record` | `learning_engagement.py` | 课程学习记录 |
| `customer_label_values` | `ai_decision_labels.py` | 标签 |
| `customer_staff` | `customers.py`、`service_scope.py`、`permission.py` | 客户-员工绑定 |
| `customer_groups` | `customers.py`、`service_scope.py`、`crm_group_directory.py` | 客户-群绑定 |
| `service_issues` | `crm_profile/services/modules/service_issues.py` | 客诉 |
| `groups` | `app/services/crm_group_directory.py` | 群目录 |

> 检索口径：`grep -rn "FROM \(admins\|customers\|customer_\)" app/` 得到 ~40 处命中，覆盖 18 张表。

### 2.3 兼容性核查（**上线前由数据方提供答案**）

请数据库管理员对照下表确认 `habitilitydb` 的现状，**任何一行答"否"都需要走 §2.4 兼容方案 B**：

| # | 核查项 | 是否一致 | 备注 |
|---|---|---|---|
| 1 | 表名 `admins` 存在 | ☐ | 字段需含 `id, username, password, salt, nick_name, real_name, status, type, wxwork` |
| 2 | `customers` 存在 + 字段（`id, name, points, total_points, height, ...`） | ☐ | |
| 3 | `customer_info` 存在 + 字段（safety / goals 用到的字段） | ☐ | |
| 4 | `customer_health` / `customer_glucose` 存在 + 字段 | ☐ | |
| 5 | `customer_habits` / `customer_checkin_records` / `customer_obstacles` 存在 | ☐ | |
| 6 | `customer_reminders` / `customer_plans` / `customer_todos` 存在 | ☐ | |
| 7 | `customer_course_record` 存在 | ☐ | |
| 8 | `customer_label_values` 存在 | ☐ | |
| 9 | `customer_staff` / `customer_groups` 存在 | ☐ | |
| 10 | `service_issues` 存在 | ☐ | |
| 11 | `groups` 存在 | ☐ | |
| 12 | 字符集 `utf8mb4`、整理 `utf8mb4_unicode_ci` 或兼容 | ☐ | [`crm_db.py:31`](../app/clients/crm_db.py) 硬编码 `charset='utf8mb4'` |
| 13 | 给 `habituser` 授权 `SELECT` 权限到上述全部表 | ☐ | 业务只读 CRM，**不需要写权限** |

### 2.4 兼容方案

#### 方案 A：零代码改动（前提 §2.3 全部✅）

只改 `.env`：

```env
CRM_ADMIN_DB_HOST=rm-2zew061b0tlpd75m2.mysql.rds.aliyuncs.com
CRM_ADMIN_DB_PORT=3306
CRM_ADMIN_DB_USER=habituser
CRM_ADMIN_DB_PASSWORD=hbt@135!%
CRM_ADMIN_DB_NAME=habitilitydb
CRM_ADMIN_TABLE_NAME=admins
```

→ 重启容器即可。**强烈推荐**。

#### 方案 B：兼容层（如果 §2.3 部分字段/表名变了）

按差异类型选择：

- **表名映射差异**（如 `customers` → `users`）：
  在 [`app/clients/crm_db.py`](../app/clients/crm_db.py) 旁新增 `crm_tables.py`，把表名集中起来，**所有 SQL 改用 `{tables.customer}` 风格的 f-string**。改动量约 18 张表 × 平均 3 处 ≈ 50+ 处 SQL，工作量 0.5–1 人天。
- **字段名差异**（如 `nick_name` → `nickname`）：
  在各 module 的 `_fetch_*` 函数里加 `COALESCE(new_col, old_col) AS canonical_col` 兼容；或在 Python 层做字段映射字典。工作量按差异量定。
- **结构差异（拆表/合表）**：必须改业务逻辑，不属于"切库"范畴，需走专项需求。

#### 方案 C：双库并存（过渡期，可选）

如果担心切换有问题、要做 A/B 验证：

1. 新增 `CRM_PROFILE_DB_*` 一组配置，**和登录用的 `CRM_ADMIN_DB_*` 分开**。
2. 在 [`app/clients/crm_db.py`](../app/clients/crm_db.py) 新增 `get_profile_connection()`，登录走旧库、profile 走新库。
3. 全量验证通过后再统一到一组配置。

工作量约 0.5 人天，但**只在切换需要回滚保险时才做**。

---

## 3. 新服务器部署步骤

> 假设：你已 ssh 到新服务器，OS 大概率是 Ubuntu/CentOS + 宝塔；具体差异在 [`deploy-guide.md §2`](../deploy-guide.md) 里。

### 3.1 环境准备清单（一次性）

| # | 步骤 | 命令 / 路径 | 备注 |
|---|---|---|---|
| 1 | 装宝塔（可选） | 按宝塔官网 | 用宝塔管 MySQL/Redis/Nginx 最省事 |
| 2 | 装 Docker + Docker Compose v2 | `curl -fsSL https://get.docker.com \| sh` | v2 命令是 `docker compose`，不是 `docker-compose` |
| 3 | 配 Docker 国内镜像 | `/etc/docker/daemon.json` 见 [`deploy-guide.md §2.2`](../deploy-guide.md) | 不配国内拉镜像会超时 |
| 4 | 配 Git 网络 | `git config --global http.sslVerify false` + 改 `/etc/resolv.conf` | 国内 GitHub 偶发不通 |
| 5 | 装宝塔 MySQL 5.7（或 8.0） | 宝塔软件商店 | 业务库 `wecom_ops` 放这里 |
| 6 | 装宝塔 Redis | 宝塔软件商店 | 默认 `127.0.0.1:6379` |
| 7 | 装 Nginx | 宝塔或 apt | **只装一套**，不要系统 Nginx + 宝塔 Nginx 共存（[`deploy-guide.md §6.9` 踩坑](../deploy-guide.md)） |
| 8 | 开端口（云安全组 + 宝塔防火墙） | TCP 80 / 443 / 8080 / 8000 | 8000 给容器健康检查；80/443 给公网入口 |

### 3.2 拉代码

```bash
mkdir -p /www/wwwroot && cd /www/wwwroot
git clone https://ghproxy.cn/https://github.com/gycxrbb/wecom_ops_console.git wecom-ops-console
cd wecom-ops-console
# 切回正式 origin，方便以后 push（如果该机不需要 push 则可以跳过）
git remote set-url origin https://github.com/gycxrbb/wecom_ops_console.git
```

### 3.3 准备 `.env`（**不入 git**）

从旧服务器 `scp` 一份过来，然后**改下面这些字段**：

```env
APP_ENV=production
APP_SECRET_KEY=【重新随机生成，不要复用旧密钥*】
JWT_SECRET_KEY=【重新随机生成】

# ── 项目自有业务库（新服务器本机 MySQL） ─────────────────
DATABASE_URL=mysql+pymysql://wecom_ops:【新MySQL密码】@127.0.0.1:3306/wecom_ops
REDIS_URL=redis://127.0.0.1:6379/0

# ── CRM 数据库（切到 habitilitydb 生产库） ──────────────
CRM_ADMIN_AUTH_ENABLED=true
CRM_PROFILE_ENABLED=true
AI_COACH_ENABLED=true
CRM_ADMIN_DB_HOST=rm-2zew061b0tlpd75m2.mysql.rds.aliyuncs.com
CRM_ADMIN_DB_PORT=3306
CRM_ADMIN_DB_USER=habituser
CRM_ADMIN_DB_PASSWORD=hbt@135!%
CRM_ADMIN_DB_NAME=habitilitydb
CRM_ADMIN_TABLE_NAME=admins

# ── 其他外部依赖（不变） ─────────────────────────────
ASSET_STORAGE_PROVIDER=qiniu
QINIU_ENABLED=true
QINIU_ACCESS_KEY=【沿用】
QINIU_SECRET_KEY=【沿用】
QINIU_BUCKET=【沿用】
QINIU_REGION=z0
QINIU_PUBLIC_DOMAIN=cdn.mengfugui.com
QINIU_PREFIX=qiwei/
QINIU_USE_HTTPS=true
QINIU_PRIVATE_BUCKET=false
QINIU_SIGNED_URL_EXPIRE_SECONDS=3600

# ── AI（沿用） ──────────────────────────────────────
AI_API_KEY=【沿用】
AI_BASE_URL=https://aihubmix.com/v1
AI_MODEL=gpt-4o-mini
AI_PROVIDER=aihubmix
DEEPSEEK_API_KEY=【沿用】
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro

# ── AI Visual / RAG 等其他配置全部沿用 ────────────────
AI_VISUAL_ENABLED=true
RAG_ENABLED=true
QDRANT_MODE=remote
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
QDRANT_COLLECTION=wecom_health_rag
RAG_EMBEDDING_BASE_URL=https://aihubmix.com/v1
RAG_EMBEDDING_MODEL=text-embedding-3-large
RAG_EMBEDDING_DIMENSION=1024
```

> *`APP_SECRET_KEY` 决定 webhook 密文的 Fernet 加密。**如果迁数据**且想保留旧 webhook，要么沿用旧 SECRET_KEY，要么按 [`deploy-guide.md §6.4` 踩坑](../deploy-guide.md) 让 webhook 走"解密失败时静默忽略"路径再重新填一次密钥。**重新生成是更干净的做法**。

### 3.4 迁移 `wecom_ops` 业务库（**关键**，否则丢历史数据）

在**旧**服务器：

```bash
mysqldump -u wecom_ops -p --single-transaction --routines --triggers \
  wecom_ops > /tmp/wecom_ops_$(date +%F).sql
scp /tmp/wecom_ops_*.sql root@【新服务器IP】:/tmp/
```

在**新**服务器：

```bash
# 宝塔面板 → 数据库 → 新建数据库 wecom_ops + 用户 wecom_ops
mysql -u wecom_ops -p wecom_ops < /tmp/wecom_ops_2026-05-20.sql
```

### 3.5 迁移本地素材 / Qdrant 向量数据（**可选，按需要**）

```bash
# 旧服务器：
tar -czf /tmp/data_uploads.tgz -C /www/wwwroot/wecom-ops-console/data uploads
tar -czf /tmp/data_qdrant.tgz -C /www/wwwroot/wecom-ops-console/data qdrant_storage
scp /tmp/data_*.tgz root@【新服务器IP】:/tmp/

# 新服务器：
mkdir -p /www/wwwroot/wecom-ops-console/data
tar -xzf /tmp/data_uploads.tgz -C /www/wwwroot/wecom-ops-console/data
tar -xzf /tmp/data_qdrant.tgz -C /www/wwwroot/wecom-ops-console/data
```

> 七牛云素材不需要迁，CDN 域名沿用。`data/uploads` 里是本地兜底素材。
> Qdrant 向量是 RAG 知识库，**不迁就需要重建索引**（跑 `scripts/rebuild_rag_index.py` 之类）。

### 3.6 构建并启动

```bash
cd /www/wwwroot/wecom-ops-console

# 先把 Qdrant 拉起来
docker compose -f docker-compose.prod.yml up -d qdrant
curl http://127.0.0.1:6333/collections   # 应返回 200

# 再构建并启动应用
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 看日志
docker logs --tail 100 wecom-ops-console
curl http://127.0.0.1:8000/api/v1/health
```

启动成功标志：

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3.7 配 Nginx

参考 [`deploy-guide.md §4`](../deploy-guide.md)。**要点**：

- 只用一套 Nginx，不要系统 Nginx + 宝塔 Nginx 同时跑（已经踩过坑）。
- 新域名要重新申请 SSL 证书或复用旧证书。
- DNS A 记录指向新服务器公网 IP。
- 老服务器 8080 旧入口可以**临时保留**作为回滚通道，直到新入口验证 ≥1 周。

### 3.8 验证清单

| # | 验证项 | 期望结果 |
|---|---|---|
| 1 | `curl https://【新域名】/api/v1/health` | 200 |
| 2 | 用一个真实 CRM 管理员账号登录 | 成功跳到首页 |
| 3 | 进 CRM Profile 页面查任意一个客户 | 返回客户档案数据（验证 `habitilitydb` 联通） |
| 4 | 进定时任务页 → 看到旧服务器迁过来的任务 | 数据完整（验证 `wecom_ops` 迁移） |
| 5 | 手动触发一次群机器人推送 | 收到消息（验证企微 webhook 链路） |
| 6 | AI 对话功能 | 流式输出正常 |
| 7 | AI 生图 | 见 `bug.md #81` 修复说明 |
| 8 | 容器健康检查 | `docker ps` 显示 `healthy` |

---

## 4. 风险与回滚

| 风险 | 触发条件 | 缓解 / 回滚 |
|---|---|---|
| 新 CRM 库字段缺失 | §2.3 未核对就切 | 旧 `mfgcrmdb` 暂时**保留可访问**，`.env` 一秒回滚 |
| 新 CRM 库表名不同 | habitilitydb 是重新设计的库 | 走 §2.4 方案 B，发版前完成兼容层 |
| `wecom_ops` 数据迁失败 | 跳过 §3.4 | 先在新服务器跑 `--dry-run`；保留旧服务器至少 1 周 |
| 公网入口 SSL 证书未签发 | DNS / 证书未先备好 | 先用 IP:8080 临时跑通，再切域名 |
| 旧服务器还在跑产生数据漂移 | 双服务器同时接流量 | 切换窗口期把旧服务器**容器停掉**，只保留数据库可读用于对账 |
| Fernet 解密失败 | 新 `APP_SECRET_KEY` 与旧不一致 | 沿用旧 SECRET_KEY，或重新录入所有 webhook |

---

## 5. 落地 TODO

请按顺序勾选：

- [ ] §2.3 表/字段核查表全部填完（数据方负责）
- [ ] 根据核查结果选定方案 A / B / C
- [ ] 旧服务器 `mysqldump wecom_ops` + `scp` 到新服务器
- [ ] 新服务器 OS / Docker / 宝塔 / MySQL / Redis / Nginx 装好
- [ ] 新服务器 `.env` 按 §3.3 填好，**.env 不要 git add**
- [ ] `docker compose -f docker-compose.prod.yml up -d qdrant` 跑通
- [ ] `docker compose -f docker-compose.prod.yml build && up -d` 应用起得来
- [ ] 跑通 §3.8 8 项验证
- [ ] DNS 切到新服务器，旧服务器停容器但保留数据 ≥1 周
- [ ] 1 周后旧服务器下线

---

## 6. 我现在能直接帮你做的

> 你这边给个信号，我就开干其中之一：

1. **§2.3 核查由我来跑** —— 给我新库的临时只读账号，我跑一个 SQL 脚本一次性把 18 张表 + 关键字段全部 schema diff 出来，输出 markdown 报告。
2. **方案 B 兼容层预实现** —— 不用等核查，先把所有 CRM SQL 里的硬编码表名抽到 `app/clients/crm_tables.py`，未来真有差异时只改一个文件。零行为变更，零风险。
3. **`scripts/migrate_to_new_server.sh`** —— 把 §3.4–§3.6 全打包成一个一键迁移脚本（dump → scp → restore → docker build → up），减少 ssh 操作次数。
4. **新服务器 Nginx 配置模板** —— 按你给的新域名 + SSL 证书路径直接生成一份 `wecom-ops.conf` + `wecom-ops-【新域名】.conf`。

跟我说要哪几个，或者按你的节奏先走 §5 的 TODO。
