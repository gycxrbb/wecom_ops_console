-- ============================================================================
-- 在新服务器本机 MySQL 上为 wecom_ops_console 准备业务库 + 独立账号
-- ----------------------------------------------------------------------------
-- 前置：服务器已 apt install mysql-server 并跑过 mysql_secure_installation
--
-- 用法（用 MySQL root 账号执行）：
--     mysql -uroot -p < scripts/migrate/local_mysql_setup.sql
--
-- 安全要点：
--   1. 先把下方 <REPLACE_ME_STRONG_PASSWORD> 改成新生成的强密码
--      ★ 这个密码要和 .env 的 DATABASE_URL 里写的一致
--   2. 跑完把这个文件里的密码改回占位符，不要把真实密码留在 git 历史里
--   3. 账号绑定到 127.0.0.1，只能从本机连，不暴露到外网
-- ============================================================================

-- 1. 业务库（独立于 CRM 库，互不污染）
CREATE DATABASE IF NOT EXISTS `wecom_ops`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 2. 独立账号（仅限本机连接）
CREATE USER IF NOT EXISTS 'wecom_ops'@'127.0.0.1'
  IDENTIFIED BY '<REPLACE_ME_STRONG_PASSWORD>';

-- 3. 授权：只对 wecom_ops 库读写
GRANT ALL PRIVILEGES ON `wecom_ops`.* TO 'wecom_ops'@'127.0.0.1';

FLUSH PRIVILEGES;

-- 4. 验证
SHOW DATABASES LIKE 'wecom_ops';
SELECT User, Host FROM mysql.user WHERE User='wecom_ops';
SHOW GRANTS FOR 'wecom_ops'@'127.0.0.1';
