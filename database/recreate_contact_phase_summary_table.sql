-- コンタクトフェーズ集計テーブルを削除して再作成
-- データベース: mirai_base
-- 新しい構造: phase_type（仕入/販売）とphase_value（S, A, B, C, D, Z）で1レコードに1つのフェーズを保存

USE mirai_base;

-- 既存のテーブルを削除
DROP TABLE IF EXISTS contact_phase_summary;

-- 新しいテーブル構造で作成
CREATE TABLE contact_phase_summary (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 集計情報
    aggregation_date DATE NOT NULL COMMENT '集計日（週の開始日、月曜日）',
    
    -- 担当者情報
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID（HubSpot）',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名（姓名）',
    
    -- フェーズ情報
    phase_type ENUM('buy', 'sell') NOT NULL COMMENT 'フェーズ区分（buy=仕入, sell=販売）',
    phase_value ENUM('S', 'A', 'B', 'C', 'D', 'Z') NOT NULL COMMENT 'フェーズ値',
    
    -- 集計値
    count INT NOT NULL DEFAULT 0 COMMENT '件数',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_aggregation_date (aggregation_date),
    INDEX idx_owner_id (owner_id),
    INDEX idx_owner_name (owner_name),
    INDEX idx_phase_type (phase_type),
    INDEX idx_phase_value (phase_value),
    INDEX idx_aggregation_date_owner (aggregation_date, owner_id),
    INDEX idx_aggregation_date_owner_type (aggregation_date, owner_id, phase_type),
    
    -- ユニーク制約（同じ集計日、担当者、フェーズ区分、フェーズ値の組み合わせは1つだけ）
    UNIQUE KEY uk_aggregation_owner_phase (aggregation_date, owner_id, phase_type, phase_value)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='コンタクトフェーズ集計テーブル';

