-- 首次初始化 MySQL：用 root 执行
-- mysql -u root -p < sql/init_mysql.sql
-- 然后把 .env 的 DATABASE_URL 密码改成与这里一致
-- 仅本地开发使用；公网部署请改成强密码并限制来源。

CREATE DATABASE IF NOT EXISTS comment_ai
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 同时创建 localhost / 127.0.0.1，避免 MySQL 反解主机名导致匹配不上
CREATE USER IF NOT EXISTS 'comment_ai'@'localhost'
  IDENTIFIED BY 'change-me';
ALTER USER 'comment_ai'@'localhost'
  IDENTIFIED BY 'change-me';

CREATE USER IF NOT EXISTS 'comment_ai'@'127.0.0.1'
  IDENTIFIED BY 'change-me';
ALTER USER 'comment_ai'@'127.0.0.1'
  IDENTIFIED BY 'change-me';

GRANT ALL PRIVILEGES ON comment_ai.* TO 'comment_ai'@'localhost';
GRANT ALL PRIVILEGES ON comment_ai.* TO 'comment_ai'@'127.0.0.1';
FLUSH PRIVILEGES;
