-- 物件別販売取引レポート集計テーブル作成スクリプト
-- データベース: mirai_base

USE mirai_base;

-- 物件別ステージ別件数テーブル
CREATE TABLE IF NOT EXISTS property_sales_stage_summary (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 集計情報
    aggregation_date DATE NOT NULL COMMENT '集計日',
    
    -- 物件情報
    property_id VARCHAR(255) NOT NULL COMMENT '物件ID（物件名）',
    property_name VARCHAR(255) NOT NULL COMMENT '物件名',
    
    -- ステージ情報
    stage_id VARCHAR(255) NOT NULL COMMENT 'ステージID（HubSpot）',
    stage_label VARCHAR(255) NOT NULL COMMENT 'ステージ名',
    
    -- 集計値
    count INT NOT NULL DEFAULT 0 COMMENT '件数',
    
    -- 取引IDリスト（JSON形式）
    deal_ids MEDIUMTEXT NULL COMMENT '取引IDリスト（JSON形式）',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_aggregation_date (aggregation_date),
    INDEX idx_property_id (property_id),
    INDEX idx_property_name (property_name),
    INDEX idx_stage_id (stage_id),
    INDEX idx_aggregation_date_property (aggregation_date, property_id),
    
    -- ユニーク制約（同じ集計日、物件、ステージの組み合わせは1つだけ）
    UNIQUE KEY uk_aggregation_property_stage (aggregation_date, property_id, stage_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件別販売取引レポート集計テーブル';

-- 担当者物件別ステージ別件数テーブル
CREATE TABLE IF NOT EXISTS owner_property_sales_stage_summary (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 集計情報
    aggregation_date DATE NOT NULL COMMENT '集計日',
    
    -- 担当者情報
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID（HubSpot）',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名（姓名）',
    
    -- 物件情報
    property_id VARCHAR(255) NOT NULL COMMENT '物件ID（物件名）',
    property_name VARCHAR(255) NOT NULL COMMENT '物件名',
    
    -- ステージ情報
    stage_id VARCHAR(255) NOT NULL COMMENT 'ステージID（HubSpot）',
    stage_label VARCHAR(255) NOT NULL COMMENT 'ステージ名',
    
    -- 集計値
    count INT NOT NULL DEFAULT 0 COMMENT '件数',
    
    -- 取引IDリスト（JSON形式）
    deal_ids MEDIUMTEXT NULL COMMENT '取引IDリスト（JSON形式）',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_aggregation_date (aggregation_date),
    INDEX idx_owner_id (owner_id),
    INDEX idx_owner_name (owner_name),
    INDEX idx_property_id (property_id),
    INDEX idx_property_name (property_name),
    INDEX idx_stage_id (stage_id),
    INDEX idx_aggregation_date_owner (aggregation_date, owner_id),
    INDEX idx_aggregation_date_owner_property (aggregation_date, owner_id, property_id),
    
    -- ユニーク制約（同じ集計日、担当者、物件、ステージの組み合わせは1つだけ）
    UNIQUE KEY uk_aggregation_owner_property_stage (aggregation_date, owner_id, property_id, stage_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='担当者物件別販売取引レポート集計テーブル';
