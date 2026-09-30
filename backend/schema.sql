-- GoldMind 表结构（MySQL）
--
-- 这份文件被两条路径使用：
--   1. Docker：挂进 /docker-entrypoint-initdb.d/，由官方 mysql 镜像执行
--      （镜像会用 MYSQL_DATABASE 选好库）
--   2. 本地：`python init_db.py` 读取并逐条执行（它用 DB_NAME 选好库）
--
-- 因此这里**不写 CREATE DATABASE / USE** —— 写死库名会让 DB_NAME 失效。
--
-- ⚠️ 枚举列的取值必须与 SQLAlchemy 模型一致。
-- `Column(Enum(SomeEnum))` 存的是**枚举名**（POSITIVE / BULLISH / HIGH / SUCCESS），
-- 不是枚举值（positive / bullish / …）。
-- 不一致的后果很隐蔽：MySQL 的 ENUM 比较不区分大小写，所以**写入会成功**
-- 并被规范成小写存下来，但读回来时 SQLAlchemy 按名字查不到，直接抛
-- `LookupError: 'neutral' is not among the defined enum values` ——
-- 也就是「写得进去、读不出来」，接口全 500。
-- 这条由 `tests/unit/test_schema_matches_models.py` 守住。

CREATE TABLE IF NOT EXISTS gold_prices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    open_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2) NOT NULL,
    volume INT,
    change_percent DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dollar_index (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    open_price DECIMAL(10, 4),
    high_price DECIMAL(10, 4),
    low_price DECIMAL(10, 4),
    close_price DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS gold_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    source VARCHAR(100),
    url VARCHAR(500),
    published_at TIMESTAMP,
    sentiment ENUM('POSITIVE', 'NEGATIVE', 'NEUTRAL') DEFAULT 'NEUTRAL',
    keywords TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_published_at (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS market_factors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type ENUM('BULLISH', 'BEARISH') NOT NULL,
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(200),
    description TEXT,
    details JSON,
    impact ENUM('HIGH', 'MEDIUM', 'LOW') DEFAULT 'MEDIUM',
    confidence DECIMAL(3, 2) DEFAULT 0.80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS institution_views (
    id INT AUTO_INCREMENT PRIMARY KEY,
    institution_name VARCHAR(100) NOT NULL,
    logo VARCHAR(50),
    -- 这一列在模型里是 String（不是 Enum），服务写入的是小写，
    -- 所以这里的 ENUM 取值保持小写是对的。
    rating ENUM('bullish', 'bearish', 'neutral') NOT NULL,
    target_price DECIMAL(10, 2),
    timeframe VARCHAR(50),
    reasoning TEXT,
    key_points JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prediction_type VARCHAR(50) NOT NULL,
    target_price DECIMAL(10, 2) NOT NULL,
    confidence DECIMAL(5, 2),
    timeframe VARCHAR(50),
    reasoning TEXT,
    factors JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

