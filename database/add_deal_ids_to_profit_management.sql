-- 粗利按分管理テーブルに取引IDカラムを追加
-- 仕入取引IDと販売取引IDを保存するためのカラム

USE mirai_base;

-- 仕入取引IDカラムを追加
ALTER TABLE profit_management 
ADD COLUMN purchase_deal_id VARCHAR(255) DEFAULT NULL COMMENT 'HubSpotの仕入取引ID' 
AFTER purchase_price;

-- 販売取引IDカラムを追加
ALTER TABLE profit_management 
ADD COLUMN sales_deal_id VARCHAR(255) DEFAULT NULL COMMENT 'HubSpotの販売取引ID' 
AFTER sales_price;

-- インデックスを追加（検索用）
ALTER TABLE profit_management 
ADD INDEX idx_purchase_deal_id (purchase_deal_id);

ALTER TABLE profit_management 
ADD INDEX idx_sales_deal_id (sales_deal_id);

