CREATE DATABASE IF NOT EXISTS gold_analysis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gold_analysis;

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
    sentiment ENUM('positive', 'negative', 'neutral') DEFAULT 'neutral',
    keywords TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_published_at (published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS market_factors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type ENUM('bullish', 'bearish') NOT NULL,
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(200),
    description TEXT,
    details JSON,
    impact ENUM('high', 'medium', 'low') DEFAULT 'medium',
    confidence DECIMAL(3, 2) DEFAULT 0.80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS institution_views (
    id INT AUTO_INCREMENT PRIMARY KEY,
    institution_name VARCHAR(100) NOT NULL,
    logo VARCHAR(50),
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

CREATE TABLE IF NOT EXISTS update_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_type VARCHAR(50) NOT NULL,
    status ENUM('success', 'failed') NOT NULL,
    records_affected INT,
    error_message TEXT,
    duration_seconds DECIMAL(10, 3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_data_type (data_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
