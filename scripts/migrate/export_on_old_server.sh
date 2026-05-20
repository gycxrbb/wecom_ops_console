#!/usr/bin/env bash
# ============================================================================
# 在旧服务器（gezelling.com）上执行：导出 wecom_ops 业务库 + Qdrant + uploads。
# ----------------------------------------------------------------------------
# 用法（在旧服务器上 ssh 后）：
#     bash /www/wwwroot/wecom-ops-console/scripts/migrate/export_on_old_server.sh
#
# 可选环境变量：
#     PROJECT_DIR   项目路径，默认 /www/wwwroot/wecom-ops-console
#     OUT_DIR       导出包目录，默认 /tmp/wecom-ops-migrate-<时间戳>
#     SKIP_QDRANT   设为 1 跳过 Qdrant
#     SKIP_UPLOADS  设为 1 跳过 uploads
#
# 安全：脚本只读 .env 中的本机 wecom_ops 库凭证，不会动 CRM 远程库。
# ============================================================================
set -euo pipefail

# 自动定位项目根：脚本位于 scripts/migrate/，向上两层就是项目根。
# 如果你把脚本/项目放在其他位置，可以显式设 PROJECT_DIR=/your/path 覆盖。
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=${PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}

TS=$(date +%Y%m%d-%H%M%S)
OUT_DIR=${OUT_DIR:-/tmp/wecom-ops-migrate-$TS}

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
blue()  { printf '\033[34m%s\033[0m\n' "$*"; }

[[ -d "$PROJECT_DIR" ]] || { red "项目目录不存在：$PROJECT_DIR"; exit 1; }
[[ -f "$PROJECT_DIR/.env" ]] || { red ".env 不存在：$PROJECT_DIR/.env"; exit 1; }

mkdir -p "$OUT_DIR"
blue "==> 导出包路径：$OUT_DIR"

# -- 1. 解析 DATABASE_URL ---------------------------------------------------
DB_URL=$(grep -E '^DATABASE_URL=' "$PROJECT_DIR/.env" | head -n1 | sed 's/^DATABASE_URL=//' | tr -d '"' | tr -d "'")
if [[ -z "$DB_URL" ]]; then
  red "无法从 .env 读取 DATABASE_URL"
  exit 1
fi

read -r DB_USER DB_PASS DB_HOST DB_PORT DB_NAME < <(python3 - <<PY
from urllib.parse import urlparse, unquote
u = urlparse("${DB_URL}".replace("mysql+pymysql", "mysql"))
print(unquote(u.username or ""), unquote(u.password or ""),
      u.hostname or "127.0.0.1", u.port or 3306,
      (u.path or "/").lstrip("/"))
PY
)

blue "==> wecom_ops 库连接：user=$DB_USER host=$DB_HOST:$DB_PORT db=$DB_NAME"

# -- 2. mysqldump -----------------------------------------------------------
blue "==> [1/4] mysqldump $DB_NAME ..."
SQL_GZ="$OUT_DIR/wecom_ops.sql.gz"
# --single-transaction 保证 InnoDB 表一致性快照；--routines/--triggers/--events 把存储过程/触发器/事件也带走
MYSQL_PWD="$DB_PASS" mysqldump \
  -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
  --single-transaction --routines --triggers --events --hex-blob \
  --default-character-set=utf8mb4 \
  --set-gtid-purged=OFF \
  "$DB_NAME" | gzip > "$SQL_GZ"
SQL_SIZE=$(du -h "$SQL_GZ" | awk '{print $1}')
green "    OK  $SQL_GZ ($SQL_SIZE)"

# -- 3. Qdrant --------------------------------------------------------------
if [[ "${SKIP_QDRANT:-0}" != "1" && -d "$PROJECT_DIR/data/qdrant_storage" ]]; then
  blue "==> [2/4] 打包 Qdrant 向量存储 ..."
  QDRANT_TGZ="$OUT_DIR/qdrant_storage.tgz"
  tar -czf "$QDRANT_TGZ" -C "$PROJECT_DIR/data" qdrant_storage
  Q_SIZE=$(du -h "$QDRANT_TGZ" | awk '{print $1}')
  green "    OK  $QDRANT_TGZ ($Q_SIZE)"
else
  yellow "==> [2/4] 跳过 Qdrant（SKIP_QDRANT=1 或目录不存在）"
fi

# -- 4. uploads -------------------------------------------------------------
if [[ "${SKIP_UPLOADS:-0}" != "1" && -d "$PROJECT_DIR/data/uploads" ]]; then
  blue "==> [3/4] 打包 uploads（本地素材兜底） ..."
  UPLOADS_TGZ="$OUT_DIR/uploads.tgz"
  tar -czf "$UPLOADS_TGZ" -C "$PROJECT_DIR/data" uploads
  U_SIZE=$(du -h "$UPLOADS_TGZ" | awk '{print $1}')
  green "    OK  $UPLOADS_TGZ ($U_SIZE)"
else
  yellow "==> [3/4] 跳过 uploads"
fi

# -- 5. 写元数据 -------------------------------------------------------------
META="$OUT_DIR/_meta.txt"
{
  echo "exported_at=$(date -Iseconds)"
  echo "source_host=$(hostname)"
  echo "source_ip=$(hostname -I | awk '{print $1}')"
  echo "project_dir=$PROJECT_DIR"
  echo "db_name=$DB_NAME"
  echo "git_commit=$(cd "$PROJECT_DIR" && git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "git_branch=$(cd "$PROJECT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
} > "$META"

blue "==> [4/4] 元数据：$META"
cat "$META"

# -- 6. 总结 ----------------------------------------------------------------
echo
green "================================================================"
green "  导出完成！包路径：$OUT_DIR"
green "================================================================"
ls -lh "$OUT_DIR"

cat <<EOF

== 下一步（在你本地或新服务器执行）==

# 方式 A：从本地中转
scp -r root@【旧服务器IP】:$OUT_DIR /tmp/
scp -r /tmp/$(basename "$OUT_DIR") root@【新服务器IP】:/tmp/

# 方式 B：旧机直接推到新机（更快，需要旧机能 ssh 到新机）
scp -r $OUT_DIR root@【新服务器IP】:/tmp/

== 然后在新服务器执行 ==

bash /www/wwwroot/wecom-ops-console/scripts/migrate/import_on_new_server.sh \\
     /tmp/$(basename "$OUT_DIR")

EOF
