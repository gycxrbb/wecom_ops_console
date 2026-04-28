# 项目部署全流程记录

> 环境：Ubuntu 18.04 + 宝塔面板 + Docker + MySQL 5.7
> 项目：wecom_ops_console（FastAPI + Vue 3 SPA）
> 日期：2026-04-10

---

## 一、架构总览

```
浏览器 → Nginx(:8080)
  ├── /api/*, /auth/*, /webhook/* → Docker(:8000) (FastAPI + Vue SPA)
  └── 其余路径 → Docker(:8000) (Vue SPA catch-all)

Docker 容器 (network_mode: host)
  → 宝塔 MySQL(:3306, 数据库 wecom_ops)
  → 宝塔 Redis(:6379)
  → CRM 远程 MySQL (登录认证)
  → 七牛云 (素材存储)
```

---

## 二、服务器环境准备

### 2.1 宝塔安装
- MySQL 5.7、Redis、Nginx 通过宝塔软件商店安装
- Docker 和 Docker Compose 通过宝塔或命令行安装

### 2.2 Docker 镜像加速（国内必配）

```bash
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF
systemctl daemon-reload
systemctl restart docker
```

### 2.3 Git 网络修复（国内服务器必配）

```bash
git config --global http.sslVerify false
git config --global https.sslVerify false
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf
```

---

## 三、项目部署

### 3.1 克隆代码

```bash
cd /www/wwwroot
git clone https://github.com/gycxrbb/wecom_ops_console.git wecom-ops-console
```

如果 git clone 超时，用国内镜像：

```bash
git clone https://ghproxy.cn/https://github.com/gycxrbb/wecom_ops_console.git wecom-ops-console
```

### 3.2 创建 .env 文件

在 `/www/wwwroot/wecom-ops-console/` 下创建 `.env`，**不要提交到 git**：

```env
APP_ENV=production
APP_SECRET_KEY=【随机生成的密钥】
JWT_SECRET_KEY=【随机生成的密钥】

ADMIN_USERNAME=admin
ADMIN_PASSWORD=【强密码】
COACH_USERNAME=coach
COACH_PASSWORD=【强密码】

DATABASE_URL=mysql+pymysql://wecom_ops:【MySQL密码】@127.0.0.1:3306/wecom_ops
REDIS_URL=redis://127.0.0.1:6379/0

CRM_ADMIN_AUTH_ENABLED=true
CRM_PROFILE_ENABLED=true  # 是否启用 CRM 个人资料功能
AI_COACH_ENABLED=true # 是否启用 AI 教练功能
CRM_ADMIN_DB_HOST=【CRM地址】
CRM_ADMIN_DB_PORT=3306
CRM_ADMIN_DB_USER=【CRM用户名】
CRM_ADMIN_DB_PASSWORD=【CRM密码】
CRM_ADMIN_DB_NAME=mfgcrmdb
CRM_ADMIN_TABLE_NAME=admins

QINIU_ENABLED=true
QINIU_ACCESS_KEY=【AK】
QINIU_SECRET_KEY=【SK】
QINIU_BUCKET=【bucket】
QINIU_REGION=z2
QINIU_PUBLIC_DOMAIN=【CDN域名】
QINIU_PREFIX=qiwei/
QINIU_USE_HTTPS=true
QINIU_SIGNED_URL_EXPIRE_SECONDS=3600
DEFAULT_TIMEZONE=Asia/Shanghai  # 上海时区

# AI 润色服务配置 (OpenAI 兼容 API)
AI_API_KEY=【密钥】
AI_BASE_URL=https://aihubmix.com/v1
AI_MODEL=gpt-4o-mini

# AI Provider 切换 (aihubmix | deepseek)
AI_PROVIDER=deepseek

# DeepSeek 配置 (当 AI_PROVIDER=deepseek 时生效)
DEEPSEEK_API_KEY=【密钥】
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro



# 发送超时处理机制
SEND_TIMEOUT_SECONDS=30
FILE_UPLOAD_TIMEOUT_SECONDS=120
SEND_MAX_RETRIES=3
SEND_RETRY_DELAY_SECONDS=2.0
FILE_SEND_MAX_RETRIES=3
FILE_SEND_RETRY_DELAY_SECONDS=3.0

RAG_ENABLED=true
QDRANT_MODE=remote
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
QDRANT_COLLECTION=wecom_health_rag
RAG_EMBEDDING_BASE_URL=https://aihubmix.com/v1
RAG_EMBEDDING_MODEL=text-embedding-3-large
RAG_EMBEDDING_DIMENSION=1024
# RAG_EMBEDDING_API_KEY 可留空复用 AI_API_KEY；如供应商单独分配 embedding key，再单独填写。

```

生产环境已在 `docker-compose.prod.yml` 中声明独立 Qdrant 服务。RAG 上线时不要使用 `QDRANT_MODE=local`，否则应用容器会绕开 Qdrant 服务并使用本地文件向量库，不适合多 worker 生产运行。

### 3.3 数据库准备

宝塔面板 → 数据库 → 添加数据库：
- 数据库名：`wecom_ops`
- 用户名：`wecom_ops`
- 访问权限：本地服务器

如果从本地迁移数据：
1. Navicat 右键数据库 → 转储 SQL 文件 → 结构和数据
2. 上传到服务器
3. `mysql -u wecom_ops -p wecom_ops < dump.sql`

### 3.4 Docker 构建与启动

```bash
cd /www/wwwroot/wecom-ops-console
docker compose -f docker-compose.prod.yml up -d qdrant
curl http://127.0.0.1:6333/collections
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

查看日志确认启动成功：
```bash
docker logs wecom-ops-console
curl http://127.0.0.1:8000/api/v1/health
```

---

## 四、Nginx 配置

### 4.1 创建配置文件

由于 80 端口被其他项目占用，使用 8080 端口：

```bash
cat > /etc/nginx/sites-enabled/wecom-ops.conf << 'EOF'
server {
    listen 8080;
    server_name 120.48.156.119;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1024;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
EOF
```

**注意**：Nginx 主配置只 include `/etc/nginx/conf.d/` 和 `/etc/nginx/sites-enabled/`，宝塔的 `/www/server/panel/vhost/nginx/` 目录不一定被 include。

### 4.2 放行端口

两层防火墙都要放行：
1. **云安全组**：云服务商控制台 → 安全组 → 添加 TCP 8080 入站规则
2. **宝塔防火墙**：宝塔面板 → 安全 → 添加放行端口 8080

```bash
nginx -t && systemctl restart nginx
```

### 4.3 根域名 HTTPS 配置（gezelling.com）

当前旧入口：

```text
http://120.48.156.119:8080
```

目标正式入口：

```text
https://gezelling.com
```

#### 4.3.1 DNS 解析

在域名 DNS 控制台添加根域名解析：

```text
主机记录：@
记录类型：A
记录值：120.48.156.119
TTL：600
```

如需同时支持 `www.gezelling.com`，再添加一条：

```text
主机记录：www
记录类型：CNAME
记录值：gezelling.com
```

验证解析：

```bash
nslookup gezelling.com
```

应解析到：

```text
120.48.156.119
```

#### 4.3.2 证书上传

证书文件不要放到 Git 项目目录。建议放到 Nginx 专用目录：

```bash
mkdir -p /etc/nginx/ssl/gezelling
```

上传后建议命名为：

```text
/etc/nginx/ssl/gezelling/gezelling.com.crt
/etc/nginx/ssl/gezelling/gezelling.com.key
```

设置权限：

```bash
chmod 644 /etc/nginx/ssl/gezelling/gezelling.com.crt
chmod 600 /etc/nginx/ssl/gezelling/gezelling.com.key
```

注意：SSL 证书必须覆盖 `gezelling.com`。如果证书只覆盖 `www.gezelling.com` 或其他子域名，需要重新申请包含 `gezelling.com` 的证书。

#### 4.3.3 Nginx 配置
新增一个配置文件专门为 域名服务：
在 `/etc/nginx/sites-enabled/wecom-ops-gezelling.conf` 写入：

```nginx
server {
    listen 80;
    server_name gezelling.com www.gezelling.com;

    return 301 https://gezelling.com$request_uri;
}

server {
    listen 443 ssl http2;
    server_name gezelling.com www.gezelling.com;

    ssl_certificate /etc/nginx/ssl/gezelling/gezelling.com.crt;
    ssl_certificate_key /etc/nginx/ssl/gezelling/gezelling.com.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    client_max_body_size 100m;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1024;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

如果 Nginx 实际没有 include `/etc/nginx/sites-enabled/`，先检查：

```bash
nginx -T | grep include
```

检查是否配置文件生效：
nginx -T | grep wecom-ops


再把配置文件放到实际被 include 的目录，例如：

```text
/etc/nginx/conf.d/
/www/server/panel/vhost/nginx/
```



#### 4.3.4 端口放行

云服务器安全组和宝塔防火墙都要放行：

```text
TCP 443
TCP 80
```

旧的 `8080` 可以先保留，作为回退入口。

#### 4.3.5 检查与重载

```bash
nginx -t
systemctl reload nginx
```

如果 reload 后未生效：

```bash
systemctl restart nginx
```

#### 4.3.6 验证

强制指定解析测试：

```bash
curl -Ik --resolve gezelling.com:443:120.48.156.119 https://gezelling.com
```

这一步的时候遇到问题了：
我发现系统另外一个路径也有配置文件:
/www/server/panel/vhost/nginx/wecom-ops.conf

服务器上同时跑了两套 Nginx。
系统 Nginx：/usr/sbin/nginx
宝塔 Nginx：/www/server/nginx/sbin/nginx

本次排障过程记录（2026-04-27）：

1. 最初现象：

```bash
curl -Ik --resolve gezelling.com:443:120.48.156.119 https://gezelling.com
```

返回：

```text
curl: (7) Failed to connect to gezelling.com port 443: Connection refused
```

这不是证书错误，也不是域名解析错误，而是 `443` 端口当时没有任何服务在监听。

2. 同时测试 HTTP：

```bash
curl -I http://gezelling.com
```

返回：

```text
HTTP/1.1 200 OK
Server: nginx
Content-Length: 138
```

这说明 `80` 端口有 Nginx 在响应，但命中的是默认静态页，不是我们预期的 `301` 跳转到 HTTPS。

3. 查看监听端口：

```bash
ss -lntp | grep -E ':80|:443|:8080|:8000'
```

当时结果显示：

```text
0.0.0.0:8080  -> 系统 Nginx
0.0.0.0:80    -> 宝塔 Nginx
0.0.0.0:8000  -> uvicorn
```

没有 `0.0.0.0:443`，所以 HTTPS 必然不通。

4. 查看 Nginx 进程：

```bash
ps -ef | grep '[n]ginx'
```

发现服务器同时存在两套 Nginx：

```text
系统 Nginx：/usr/sbin/nginx
宝塔 Nginx：/www/server/nginx/sbin/nginx
```

其中：

```text
系统 Nginx 使用 /etc/nginx/nginx.conf
宝塔 Nginx 使用 /www/server/nginx/conf/nginx.conf
宝塔站点配置位于 /www/server/panel/vhost/nginx/
```

5. 根因：

`gezelling.com` 的 HTTPS 配置写在系统 Nginx 的 `/etc/nginx/sites-enabled/` 下，`nginx -T` 能看到配置，`nginx -t` 也通过。

但 `80` 端口被宝塔 Nginx 占用，系统 Nginx 无法完整接管 `80/443/8080`。因此表现为：

```text
80 仍然返回宝塔默认页
443 没有监听
8080 旧入口仍可访问
```

6. 临时修复动作：

```bash
fuser -k 80/tcp
systemctl start nginx
```

这一步杀掉了占用 `80` 的宝塔 Nginx，再启动系统 Nginx。随后系统 Nginx 成功监听：

```text
0.0.0.0:80
0.0.0.0:443
0.0.0.0:8080
```

7. 修复后验证：

```bash
curl -I --resolve gezelling.com:80:127.0.0.1 http://gezelling.com
```

返回：

```text
HTTP/1.1 301 Moved Permanently
Location: https://gezelling.com/
```

继续验证 HTTPS：

```bash
curl -Ik --resolve gezelling.com:443:120.48.156.119 https://gezelling.com
```

返回：

```text
HTTP/2 405
allow: GET
```

这里的 `405` 不是 HTTPS 失败，而是 `curl -I` 发送的是 `HEAD` 请求，后端入口只允许 `GET`。这说明 HTTPS、证书、Nginx 反代链路已经打通。

可用 GET 再验证：

```bash
curl -kL https://gezelling.com -o /dev/null -w "%{http_code}\n"
curl -k https://gezelling.com/api/v1/bootstrap
```

8. 收口原则：

这台服务器以后必须明确一套 official Nginx：

```text
official：系统 Nginx
二进制：/usr/sbin/nginx
主配置：/etc/nginx/nginx.conf
站点配置：/etc/nginx/sites-enabled/wecom-ops.conf
```

不要再让宝塔 Nginx 抢占 `80/443`。否则服务器重启、宝塔重启 Nginx 后，可能再次出现：

```text
80 命中默认页
443 connection refused
systemctl restart nginx 报 bind() to 0.0.0.0:80 failed
```


验证 HTTP 自动跳转 HTTPS：

```bash
curl -I http://gezelling.com
```

预期：

```text
HTTP/1.1 301 Moved Permanently
Location: https://gezelling.com/
```

浏览器最终访问：

```text
https://gezelling.com
```

---

## 五、日常部署

### 5.1 手动部署（推荐）

在服务器上执行：

```bash
bash /www/wwwroot/wecom-ops-console/deploy.sh
```

deploy.sh 内容：

```bash
#!/bin/bash
cd /www/wwwroot/wecom-ops-console

# 网络修复
git config --global http.sslVerify false
git config --global https.sslVerify false
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf

# 用镜像拉代码
git remote set-url origin https://ghproxy.cn/https://github.com/gycxrbb/wecom_ops_console.git
for i in 1 2 3; do
    git pull && break
    echo "retry $i..." >&2
    sleep 5
done
git remote set-url origin https://github.com/gycxrbb/wecom_ops_console.git

# 构建并重启
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
echo "Deployed: $(date)"
```

### 5.2 工作流

```
本地修改代码 → git commit → git push → SSH 到服务器 → bash deploy.sh
```

### 5.3 Docker 构建缓存

- **日常更新**（只改代码）：`docker compose build`，利用层缓存，1-2 分钟
- **依赖变更**（改了 package.json/requirements.txt）：3-10 分钟
- **强制全量重建**：`docker compose build --no-cache`，30+ 分钟，仅排查问题时用

---

## 六、踩坑记录

### 6.1 .env 不要提交到 git

`.env` 包含生产密码和密钥，已在 `.gitignore` 中排除。用 `git rm --cached .env` 从追踪中移除。以后 `git pull` 不会覆盖服务器的 `.env`。

### 6.2 f-string 中不能有反斜杠（Python 3.11）

```python
# 错误
f"/uploads/{stored_name.replace('\\', '/')}"

# 正确
url_path = stored_name.replace('\\', '/')
f"/uploads/{url_path}"
```

### 6.3 SQLAlchemy create_all 要加 checkfirst=True

```python
Base.metadata.create_all(bind=engine, checkfirst=True)
```

否则 MySQL 已有表时会报 `Table already exists`。

### 6.4 Fernet 加密密钥不同会导致解密失败

本地和服务器使用不同的 `APP_SECRET_KEY`，从本地导入的数据库中 webhook 密文无法在服务器上解密。需要给所有 `decrypt_webhook` 调用加异常保护。

### 6.5 Vue SPA 要在 FastAPI 中正确挂载

1. 移除旧的 Jinja2 页面路由（pages.py、auth.py 中的 TemplateResponse）
2. 在所有 API 路由之后添加 catch-all 路由 serve `frontend/dist/index.html`
3. SPA fallback：非文件请求统一返回 `index.html`

### 6.6 Docker 容器内无法访问主机文件系统

webhook 部署脚本在 Docker 容器内执行时，`/www/wwwroot/wecom-ops-console` 路径不存在。解决方案：webhook 只写触发文件到挂载的 data 目录，主机 cron 或手动执行实际部署脚本。

### 6.7 宝塔 Webhook 端口可能被墙

GitHub Webhook 需要能访问服务器的 webhook URL。如果宝塔面板端口（如 30205）被墙或不通，可以在 FastAPI 应用内添加 webhook 端点，复用已开放的 8080 端口。

### 6.8 Dockerfile apt-get 慢

Debian 官方源在国内很慢，Dockerfile 中加阿里云镜像：

```dockerfile
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources
```

### 6.9 同时运行系统 Nginx 和宝塔 Nginx 会导致端口归属混乱

2026-04-27 配置 `https://gezelling.com` 时遇到一次典型问题：

```text
curl -Ik --resolve gezelling.com:443:120.48.156.119 https://gezelling.com
curl: (7) Failed to connect to gezelling.com port 443: Connection refused
```

当时 `nginx -T` 能看到 `gezelling.com` 配置，`nginx -t` 也通过，但 `ss -lntp` 没有 `:443` 监听。

最终确认服务器上同时存在两套 Nginx：

```text
系统 Nginx：/usr/sbin/nginx
宝塔 Nginx：/www/server/nginx/sbin/nginx
```

当时实际端口归属：

```text
8080 -> 系统 Nginx
80   -> 宝塔 Nginx
443  -> 未监听
8000 -> uvicorn
```

因此 `http://gezelling.com` 命中宝塔默认页并返回 `200 OK`，而 `https://gezelling.com` 直接 `Connection refused`。

排查命令：

```bash
ps -ef | grep '[n]ginx'
which nginx
nginx -T | grep -n "gezelling.com"
nginx -T | grep -n "include"
/www/server/nginx/sbin/nginx -t
ss -lntp | grep -E ':80|:443|:8080|:8000'
```

临时修复：

```bash
fuser -k 80/tcp
systemctl start nginx
```

修复后系统 Nginx 成功监听 `80/443/8080`，验证结果：

```text
http://gezelling.com -> 301 https://gezelling.com/
https://gezelling.com -> 已进入 Nginx 反代链路
```

注意：`curl -I https://gezelling.com` 返回 `HTTP/2 405 allow: GET` 不代表 HTTPS 失败，而是 HEAD 请求不被后端入口允许。用 GET 验证：

```bash
curl -kL https://gezelling.com -o /dev/null -w "%{http_code}\n"
curl -k https://gezelling.com/api/v1/bootstrap
```

收口建议：本项目当前应以系统 Nginx 作为 official 入口，不要再让宝塔 Nginx 管理 `80/443`。如果后续必须使用宝塔 Nginx，则需要把 official 配置整体迁移到 `/www/server/panel/vhost/nginx/`，不能两套 Nginx 同时抢占公网入口端口。

---

## 七、常用运维命令

```bash
# 查看容器状态
docker ps

# 查看应用日志
docker logs --tail 50 wecom-ops-console
docker logs -f wecom-ops-console  # 实时跟踪

# 重启容器
docker restart wecom-ops-console

# 重新构建并启动
cd /www/wwwroot/wecom-ops-console
docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml up -d

# 查看 Nginx 配置是否正确
nginx -t

# 重启 Nginx
systemctl restart nginx

# 手动部署
bash /www/wwwroot/wecom-ops-console/deploy.sh

# 查看部署日志
cat /www/wwwroot/wecom-ops-console/data/deploy.log

# 刷新远程分支跟踪
git fetch --prune --force
```
