-- 粗利目標管理テーブル作成スクリプト
-- データベース: mirai_base

USE mirai_base;

-- 粗利目標管理テーブル
CREATE TABLE IF NOT EXISTS profit_target (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 基本情報
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID（HubSpotの担当者ID）',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名',
    year INT NOT NULL COMMENT '年度',
    
    -- 四半期目標
    q1_target DECIMAL(15, 2) DEFAULT NULL COMMENT '1Q目標額',
    q2_target DECIMAL(15, 2) DEFAULT NULL COMMENT '2Q目標額',
    q3_target DECIMAL(15, 2) DEFAULT NULL COMMENT '3Q目標額',
    q4_target DECIMAL(15, 2) DEFAULT NULL COMMENT '4Q目標額',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_owner_id (owner_id),
    INDEX idx_year (year),
    INDEX idx_owner_year (owner_id, year),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at),
    
    -- ユニーク制約（同じ担当者・同じ年の組み合わせは1つだけ）
    UNIQUE KEY uk_owner_year (owner_id, year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='粗利目標管理テーブル';





