#!/usr/bin/env bash
# ============================================================================
# 在新服务器上执行：从迁移包恢复 wecom_ops + Qdrant + uploads，并启动 Docker。
# ----------------------------------------------------------------------------
# 前置：
#   1. 已 git clone 项目到 PROJECT_DIR
#   2. 已写好 PROJECT_DIR/.env（DATABASE_URL 指向新服务器本机 MySQL）
#   3. 新服务器已装 Docker / docker compose v2 / 本机 MySQL
#   4. 已经从旧服务器把迁移包 scp 到 /tmp/wecom-ops-migrate-XXX
#
# 用法：
#     bash /www/wwwroot/wecom-ops-console/scripts/migrate/import_on_new_server.sh /tmp/wecom-ops-migrate-XXX
#
# 可选环境变量：
#     PROJECT_DIR           默认 /www/wwwroot/wecom-ops-console
#     SKIP_DOCKER_BUILD     设为 1 跳过 docker build（适合只换数据，不换代码）
#     SKIP_QDRANT_RESTORE   设为 1 跳过 Qdrant 恢复
#     SKIP_UPLOADS_RESTORE  设为 1 跳过 uploads 恢复
#     FORCE_DROP_DB         设为 1 在导入前先 DROP DATABASE（危险！默认不开）
# ============================================================================
set -euo pipefail

# 自动定位项目根：脚本位于 scripts/migrate/，向上两层就是项目根。
# 这样无论你把代码放在 /www/wwwroot、/home/xr 还是其他路径都能正常工作。
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=${PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}
COMPOSE_FILE=docker-compose.prod.yml

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
blue()  { printf '\033[34m%s\033[0m\n' "$*"; }

if [[ -z "${1:-}" ]]; then
  red "用法：$0 <迁移包目录>"
  echo  "例如：$0 /tmp/wecom-ops-migrate-20260520-143012"
  exit 1
fi

PACKAGE_DIR=$(cd "$1" && pwd)
[[ -d "$PROJECT_DIR" ]] || { red "项目目录不存在：$PROJECT_DIR"; exit 1; }
[[ -f "$PROJECT_DIR/.env" ]] || { red "请先准备好 .env：$PROJECT_DIR/.env"; exit 1; }
[[ -f "$PACKAGE_DIR/wecom_ops.sql.gz" ]] || { red "迁移包缺少 wecom_ops.sql.gz"; exit 1; }

# -- 0. 显示元数据 ----------------------------------------------------------
if [[ -f "$PACKAGE_DIR/_meta.txt" ]]; then
  blue "==> 迁移包元数据："
  cat "$PACKAGE_DIR/_meta.txt"
fi

# -- 1. 解析新服务器的 DATABASE_URL ----------------------------------------
DB_URL=$(grep -E '^DATABASE_URL=' "$PROJECT_DIR/.env" | head -n1 | sed 's/^DATABASE_URL=//' | tr -d '"' | tr -d "'")
read -r DB_USER DB_PASS DB_HOST DB_PORT DB_NAME < <(python3 - <<PY
from urllib.parse import urlparse, unquote
u = urlparse("${DB_URL}".replace("mysql+pymysql", "mysql"))
print(unquote(u.username or ""), unquote(u.password or ""),
      u.hostname or "127.0.0.1", u.port or 3306,
      (u.path or "/").lstrip("/"))
PY
)
blue "==> 新服务器 wecom_ops 库：user=$DB_USER host=$DB_HOST:$DB_PORT db=$DB_NAME"

# -- 2. 停旧容器（如果有的话） ---------------------------------------------
cd "$PROJECT_DIR"
if docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | grep -q .; then
  yellow "==> 关停当前运行的容器 ..."
  docker compose -f "$COMPOSE_FILE" down
fi

# -- 3. 恢复 MySQL ---------------------------------------------------------
blue "==> [1/6] 恢复 wecom_ops 数据库 ..."
export MYSQL_PWD="$DB_PASS"

# 自动识别是 RDS（aliyuncs.com / amazonaws.com 等）还是本机
if [[ "$DB_HOST" =~ aliyuncs|amazonaws|rds ]]; then
  IS_REMOTE=1
  blue "    数据库目标：远程 RDS ($DB_HOST)"
else
  IS_REMOTE=0
  blue "    数据库目标：本机 MySQL ($DB_HOST)"
fi

# 测试连接（同时验证白名单是否放行）
if ! mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -e "SELECT 1" >/dev/null 2>&1; then
  red "    无法连接 MySQL：host=$DB_HOST, user=$DB_USER"
  red "    检查：a) .env 里 DATABASE_URL 是否正确"
  red "          b) 如果是 RDS，确认本机内网 IP 已加入 RDS 白名单"
  red "          c) 账号密码是否正确"
  exit 1
fi
green "    连接 OK"

# 检查库是否已存在（远程 DB 用户多半没 CREATE DATABASE 权限）
DB_EXISTS=$(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -N -e \
  "SELECT 1 FROM information_schema.schemata WHERE schema_name='$DB_NAME' LIMIT 1" 2>/dev/null || true)

if [[ "${FORCE_DROP_DB:-0}" == "1" ]]; then
  yellow "    [危险] FORCE_DROP_DB=1，正在 DROP DATABASE $DB_NAME ..."
  if ! mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -e "DROP DATABASE IF EXISTS \`$DB_NAME\`" 2>&1; then
    red "    DROP DATABASE 失败：账号 $DB_USER 可能没有 DROP 权限"
    exit 1
  fi
  DB_EXISTS=""
fi

if [[ -z "$DB_EXISTS" ]]; then
  blue "    库 $DB_NAME 不存在，尝试创建 ..."
  if ! mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
       -e "CREATE DATABASE \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" 2>/dev/null; then
    red "    CREATE DATABASE 失败：账号 $DB_USER 没有 CREATE 权限。"
    red "    本机 MySQL 请先执行：mysql -uroot -p < scripts/migrate/local_mysql_setup.sql"
    red "    （远程 RDS 场景请联系 DBA 用高权账号建库）"
    exit 1
  fi
  green "    OK 已创建 $DB_NAME"
else
  yellow "    库 $DB_NAME 已存在（远程 RDS 场景预期如此）"
  TABLE_CNT=$(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -N -e \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB_NAME'" 2>/dev/null || echo 0)
  if [[ "$TABLE_CNT" -gt 0 ]]; then
    red "    库内已经有 $TABLE_CNT 张表，导入会触发"
    red "    'Table already exists' 错误。请确认你真的要覆盖；要覆盖请加 FORCE_DROP_DB=1 重跑。"
    exit 1
  fi
fi

# 导入。pv 显示进度
blue "    正在导入 SQL ..."
if command -v pv >/dev/null 2>&1; then
  pv "$PACKAGE_DIR/wecom_ops.sql.gz" | gunzip | mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" "$DB_NAME"
else
  gunzip -c "$PACKAGE_DIR/wecom_ops.sql.gz" | mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" "$DB_NAME"
fi
unset MYSQL_PWD

ROW_CNT=$(MYSQL_PWD="$DB_PASS" mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -N -e \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB_NAME'" 2>/dev/null || echo 0)
green "    OK  导入完成，$DB_NAME 现有 $ROW_CNT 张表"

# -- 4. 恢复 Qdrant --------------------------------------------------------
if [[ "${SKIP_QDRANT_RESTORE:-0}" != "1" && -f "$PACKAGE_DIR/qdrant_storage.tgz" ]]; then
  blue "==> [2/6] 恢复 Qdrant ..."
  mkdir -p "$PROJECT_DIR/data"
  if [[ -d "$PROJECT_DIR/data/qdrant_storage" ]]; then
    yellow "    备份原 qdrant_storage 到 qdrant_storage.bak.$(date +%s)"
    mv "$PROJECT_DIR/data/qdrant_storage" "$PROJECT_DIR/data/qdrant_storage.bak.$(date +%s)"
  fi
  tar -xzf "$PACKAGE_DIR/qdrant_storage.tgz" -C "$PROJECT_DIR/data"
  green "    OK"
else
  yellow "==> [2/6] 跳过 Qdrant 恢复"
fi

# -- 5. 恢复 uploads -------------------------------------------------------
if [[ "${SKIP_UPLOADS_RESTORE:-0}" != "1" && -f "$PACKAGE_DIR/uploads.tgz" ]]; then
  blue "==> [3/6] 恢复 uploads ..."
  mkdir -p "$PROJECT_DIR/data"
  if [[ -d "$PROJECT_DIR/data/uploads" ]]; then
    yellow "    备份原 uploads 到 uploads.bak.$(date +%s)"
    mv "$PROJECT_DIR/data/uploads" "$PROJECT_DIR/data/uploads.bak.$(date +%s)"
  fi
  tar -xzf "$PACKAGE_DIR/uploads.tgz" -C "$PROJECT_DIR/data"
  green "    OK"
else
  yellow "==> [3/6] 跳过 uploads 恢复"
fi

# -- 6. 启动 Qdrant --------------------------------------------------------
blue "==> [4/6] 启动 Qdrant ..."
docker compose -f "$COMPOSE_FILE" up -d qdrant
sleep 6
if curl -fsS http://127.0.0.1:6333/collections >/dev/null; then
  green "    OK  Qdrant 健康"
else
  red "    Qdrant 健康检查失败！docker logs wecom-qdrant 查看原因。"
  exit 1
fi

# -- 7. 构建并启动 app ----------------------------------------------------
if [[ "${SKIP_DOCKER_BUILD:-0}" != "1" ]]; then
  blue "==> [5/6] 构建 app 镜像 ..."
  docker compose -f "$COMPOSE_FILE" build
fi

blue "==> [6/6] 启动 app ..."
docker compose -f "$COMPOSE_FILE" up -d
sleep 10

# 健康检查
for i in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8000/api/v1/health >/dev/null; then
    green "    OK  app 健康"
    break
  fi
  if [[ $i -eq 5 ]]; then
    red "    app 健康检查失败！查看日志：docker logs --tail 100 wecom-ops-console"
    exit 1
  fi
  yellow "    第 $i 次未通过，3 秒后重试 ..."
  sleep 3
done

# -- 8. 总结 ---------------------------------------------------------------
echo
green "================================================================"
green "  迁移完成！"
green "================================================================"
docker compose -f "$COMPOSE_FILE" ps

cat <<EOF

== 后续验证 ==

  curl http://127.0.0.1:8000/api/v1/health
  curl http://127.0.0.1:8000/api/v1/bootstrap
  docker logs --tail 100 wecom-ops-console

== 后续维护 ==

  # 重启
  cd $PROJECT_DIR && docker compose -f docker-compose.prod.yml restart

  # 拉新代码 + 重建
  cd $PROJECT_DIR
  git pull
  docker compose -f docker-compose.prod.yml build
  docker compose -f docker-compose.prod.yml up -d

  # 看 CRM 当前连到哪个库
  docker logs --tail 50 wecom-ops-console | grep "CRM DB initialized"

EOF
