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
    INDEX idx_published_at (published_at),
    -- 去重按 url 查，没有索引就是全表扫描；utf8mb4 下 500 字符超长，用前缀索引。
    -- 名字与 app/models/news.py 里的 Index 一致，两者由测试守住。
    INDEX ix_gold_news_url (url(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 消息板块：高权威黄金消息精选。与 gold_news 隔离，不进入 LLM prompt 窗口。
CREATE TABLE IF NOT EXISTS news_digest_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    source VARCHAR(100) NOT NULL,
    -- 归一化来源标识：聚类时按它统计「多少家不同来源」同题报道
    source_key VARCHAR(100) NOT NULL,
    -- 1 = 官方 / 通讯社 / 行业机构；2 = 专业财经媒体
    authority_tier INT NOT NULL DEFAULT 2,
    -- Google News 的文章链接实测超过 500 字符（2026-10-02 事故），用 TEXT。
    url TEXT NOT NULL,
    published_at TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 中文译文（叠加在英文原文之上；NULL = 尚未翻译）。
    -- translation_model 让「换了模型」可判定，translated_at 让
    -- 「这条中文什么时候生成的」可回答（见 app/models/news_digest.py）。
    title_zh VARCHAR(500),
    brief_zh TEXT,
    translated_at TIMESTAMP,
    translation_model VARCHAR(100),
    INDEX idx_news_digest_published (published_at),
    -- 去重按 url 查；TEXT 在 MySQL 下必须用前缀索引。
    -- 名字与 app/models/news_digest.py 的 Index 一致，两者由测试守住。
    INDEX ix_news_digest_items_url (url(191))
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
    -- 该预测最近一次被核实/抓取入库的日期与线索来源（web_search / news_scan /
    -- legacy）。迁移只给缺失真实目标价的规范行补数据，从不删除任何行，
    -- 见 scripts/migrate_institution_views.py。
    as_of_date DATE NULL,
    source VARCHAR(50) NULL,
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
    -- 量化引擎列（services/quant）。全部可空：老库由 scripts/migrate_quant.py 补齐，
    -- 不重建表、不动既有数据。
    direction VARCHAR(20),
    horizon_days INT,
    as_of DATE,
    base_price DECIMAL(10, 2),
    score DECIMAL(10, 4),
    expected_return DECIMAL(10, 6),
    uncertainty DECIMAL(10, 6),
    model_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 量化因子观测：一行 = 一个因子在一个交易日的原始值。
-- 唯一约束保证重复抓取是幂等的（写入走 upsert）。
CREATE TABLE IF NOT EXISTS factor_observations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factor_key VARCHAR(64) NOT NULL,
    obs_date DATE NOT NULL,
    value DOUBLE NOT NULL,
    source VARCHAR(120),
    meta JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_factor_observation (factor_key, obs_date),
    INDEX ix_factor_observations_factor_key (factor_key),
    INDEX ix_factor_observations_obs_date (obs_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 因子观测的追加式修订流水：一行 = 一次写入（首见或回修），永不改写。
-- 有它才能按「当时可见的输入」重建回测面板（storage.load_series_as_of），
-- 预注册裁决才是可复现的第二次实验，而不是被后续回填悄悄改掉结论的历史快照。
CREATE TABLE IF NOT EXISTS factor_observation_revisions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    factor_key VARCHAR(64) NOT NULL,
    obs_date DATE NOT NULL,
    value DOUBLE NOT NULL,
    source VARCHAR(120),
    meta JSON,
    recorded_at DATETIME NOT NULL,
    INDEX ix_factor_observation_revisions_factor_key (factor_key),
    INDEX ix_factor_observation_revisions_obs_date (obs_date),
    INDEX ix_factor_observation_revisions_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 抓取通道的尝试流水：一行 = 一次尝试，只追加、不覆盖。
-- /api/gold/sources/status 按 (channel, source_key) 取最近一行汇总可用性。
CREATE TABLE IF NOT EXISTS fetch_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    channel VARCHAR(50) NOT NULL,
    source_key VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    items INT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_fetch_attempts_channel_source (channel, source_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 走查式回测结果：每次评估追加一行，形成准确率的时间序列。
CREATE TABLE IF NOT EXISTS model_evaluations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_version VARCHAR(50) NOT NULL,
    horizon_days INT NOT NULL,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    window_start DATE,
    window_end DATE,
    sample_size INT,
    accuracy DOUBLE,
    baseline_up_accuracy DOUBLE,
    baseline_momentum_accuracy DOUBLE,
    brier_score DOUBLE,
    metrics JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

