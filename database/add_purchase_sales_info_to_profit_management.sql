-- profit_managementテーブルに仕入・販売情報カラムを追加
-- データベース: mirai_base

USE mirai_base;

-- 仕入情報カラムを追加
ALTER TABLE profit_management 
ADD COLUMN purchase_settlement_date DATE DEFAULT NULL COMMENT '仕入決済日' 
AFTER property_type;

ALTER TABLE profit_management 
ADD COLUMN purchase_price DECIMAL(15, 2) DEFAULT NULL COMMENT '仕入価格' 
AFTER purchase_settlement_date;

-- 販売情報カラムを追加
ALTER TABLE profit_management 
ADD COLUMN sales_settlement_date DATE DEFAULT NULL COMMENT '販売決済日' 
AFTER purchase_price;

ALTER TABLE profit_management 
ADD COLUMN sales_price DECIMAL(15, 2) DEFAULT NULL COMMENT '販売価格' 
AFTER sales_settlement_date;

-- インデックスを追加
ALTER TABLE profit_management 
ADD INDEX idx_purchase_settlement_date (purchase_settlement_date);

ALTER TABLE profit_management 
ADD INDEX idx_sales_settlement_date (sales_settlement_date);



