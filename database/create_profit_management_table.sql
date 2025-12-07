-- 粗利按分管理テーブル作成スクリプト
-- データベース: mirai_base

USE mirai_base;

-- 粗利按分管理テーブル
CREATE TABLE IF NOT EXISTS profit_management (
    seq_no INT AUTO_INCREMENT PRIMARY KEY COMMENT '登録時自動採番する番号',
    
    -- 基本情報
    property_id VARCHAR(255) NOT NULL COMMENT '物件番号（HubSpotの物件ID）',
    property_name VARCHAR(255) NOT NULL COMMENT '物件名',
    property_type VARCHAR(100) DEFAULT NULL COMMENT '種別',
    
    -- 粗利情報
    gross_profit DECIMAL(15, 2) DEFAULT NULL COMMENT '粗利',
    profit_confirmed BOOLEAN DEFAULT FALSE COMMENT '粗利確定',
    accounting_year_month DATE DEFAULT NULL COMMENT '計上年月（年月のみ、月初の日付を保存）',
    
    -- 粗利按分情報
    purchase_owner_profit_rate DECIMAL(5, 2) DEFAULT NULL COMMENT '仕入担当粗利率(%)',
    purchase_owner_profit DECIMAL(15, 2) DEFAULT NULL COMMENT '仕入担当粗利',
    sales_owner_profit_rate DECIMAL(5, 2) DEFAULT NULL COMMENT '販売担当粗利率(%)',
    sales_owner_profit DECIMAL(15, 2) DEFAULT NULL COMMENT '販売担当粗利',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_property_id (property_id),
    INDEX idx_property_name (property_name),
    INDEX idx_profit_confirmed (profit_confirmed),
    INDEX idx_accounting_year_month (accounting_year_month),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='粗利按分管理テーブル';

