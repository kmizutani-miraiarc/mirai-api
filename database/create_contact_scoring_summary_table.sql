-- コンタクトスコアリング（仕入）集計テーブル作成スクリプト
-- データベース: mirai_base

USE mirai_base;

-- コンタクトスコアリング（仕入）集計テーブル
CREATE TABLE IF NOT EXISTS contact_scoring_summary (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 集計情報
    aggregation_date DATE NOT NULL COMMENT '集計日（週の開始日、月曜日）',
    
    -- 担当者情報
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID（HubSpot）',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名（姓名）',
    
    -- パターン区分
    pattern_type ENUM('all', 'buy', 'sell', 'buy_or_sell') NOT NULL DEFAULT 'all' COMMENT 'パターン区分（all=総数, buy=仕入, sell=売却, buy_or_sell=仕入・売却）',
    
    -- 集計項目
    industry_count INT NOT NULL DEFAULT 0 COMMENT '業種に入力があるコンタクト数',
    property_type_count INT NOT NULL DEFAULT 0 COMMENT '取扱種別に入力があるコンタクト数',
    area_count INT NOT NULL DEFAULT 0 COMMENT '取扱エリアに入力があるコンタクト数',
    area_category_count INT NOT NULL DEFAULT 0 COMMENT 'エリアカテゴリに入力があるコンタクト数',
    gross_count INT NOT NULL DEFAULT 0 COMMENT 'グロスに入力があるコンタクト数',
    all_five_items_count INT NOT NULL DEFAULT 0 COMMENT '５項目すべてに入力があるコンタクト数',
    target_audience_count INT NOT NULL DEFAULT 0 COMMENT '対象ターゲットのコンタクト数',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_aggregation_date (aggregation_date),
    INDEX idx_owner_id (owner_id),
    INDEX idx_owner_name (owner_name),
    INDEX idx_pattern_type (pattern_type),
    INDEX idx_aggregation_date_owner (aggregation_date, owner_id),
    
    -- ユニーク制約（同じ集計日、担当者、パターン区分の組み合わせは1つだけ）
    UNIQUE KEY uk_aggregation_owner_pattern (aggregation_date, owner_id, pattern_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='コンタクトスコアリング（仕入）集計テーブル';

