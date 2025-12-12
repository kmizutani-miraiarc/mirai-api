-- profit_managementテーブルにaccounting_year_monthカラムを追加
-- データベース: mirai_base

USE mirai_base;

-- accounting_year_monthカラムを追加（年月のみ、DATE型で月初の日付を保存）
ALTER TABLE profit_management 
ADD COLUMN accounting_year_month DATE DEFAULT NULL COMMENT '計上年月（年月のみ、月初の日付を保存）' 
AFTER profit_confirmed;

-- インデックスを追加
ALTER TABLE profit_management 
ADD INDEX idx_accounting_year_month (accounting_year_month);




