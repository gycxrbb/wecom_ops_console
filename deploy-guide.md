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
QINIU_PREFIX=materials/
QINIU_USE_HTTPS=true

DEFAULT_TIMEZONE=Asia/Shanghai
SEND_TIMEOUT_SECONDS=30
SEND_MAX_RETRIES=3
SEND_RETRY_DELAY_SECONDS=1.0
```

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
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

查看日志确认启动成功：
```bash
docker logs wecom-ops-console
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
```
