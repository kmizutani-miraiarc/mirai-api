-- 物件担当者テーブル作成スクリプト
-- データベース: mirai_base

USE mirai_base;

-- 物件担当者テーブル
CREATE TABLE IF NOT EXISTS property_owners (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 基本情報
    property_id VARCHAR(255) NOT NULL COMMENT '物件番号（HubSpotの物件ID）',
    profit_management_seq_no INT DEFAULT NULL COMMENT '粗利按分管理レコードのseq_no（外部キー）',
    owner_type ENUM('purchase', 'sales') NOT NULL COMMENT '種別（仕入or販売）',
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名',
    
    -- 取引情報
    settlement_date DATE DEFAULT NULL COMMENT '決済日',
    price DECIMAL(15, 2) DEFAULT NULL COMMENT '価格',
    profit_rate DECIMAL(5, 2) DEFAULT NULL COMMENT '粗利率(%)',
    profit_amount DECIMAL(15, 2) DEFAULT NULL COMMENT '粗利',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_property_id (property_id),
    INDEX idx_profit_management_seq_no (profit_management_seq_no),
    INDEX idx_owner_type (owner_type),
    INDEX idx_owner_id (owner_id),
    INDEX idx_settlement_date (settlement_date),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件担当者テーブル';

