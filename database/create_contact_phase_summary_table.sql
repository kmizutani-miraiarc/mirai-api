-- コンタクトフェーズ集計テーブル作成スクリプト
-- データベース: mirai_base

USE mirai_base;

-- コンタクトフェーズ集計テーブル
CREATE TABLE IF NOT EXISTS contact_phase_summary (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 集計情報
    aggregation_date DATE NOT NULL COMMENT '集計日（週の開始日、月曜日）',
    
    -- 担当者情報
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名（姓名）',
    
    -- フェーズ情報
    buy_phase ENUM('S', 'A', 'B', 'C', 'D', 'Z') NOT NULL COMMENT '仕入フェーズ',
    sell_phase ENUM('S', 'A', 'B', 'C', 'D', 'Z') NOT NULL COMMENT '販売フェーズ',
    
    -- 集計値
    count INT NOT NULL DEFAULT 0 COMMENT '件数',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_aggregation_date (aggregation_date),
    INDEX idx_owner_name (owner_name),
    INDEX idx_buy_phase (buy_phase),
    INDEX idx_sell_phase (sell_phase),
    INDEX idx_aggregation_date_owner (aggregation_date, owner_name),
    
    -- ユニーク制約（同じ集計日、担当者、フェーズの組み合わせは1つだけ）
    UNIQUE KEY uk_aggregation_owner_phases (aggregation_date, owner_name, buy_phase, sell_phase)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='コンタクトフェーズ集計テーブル';

