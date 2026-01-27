-- satei_usersテーブルにフォーム入力の会社名、姓、名、電話番号カラムを追加
USE mirai_base;

-- 会社名カラムを追加（フォーム入力）
ALTER TABLE satei_users
ADD COLUMN company_name VARCHAR(255) NULL COMMENT '会社名（フォーム入力）' AFTER hubspot_company_name;

-- 姓カラムを追加（フォーム入力）
ALTER TABLE satei_users
ADD COLUMN last_name VARCHAR(255) NULL COMMENT '姓（フォーム入力）' AFTER company_name;

-- 名カラムを追加（フォーム入力）
ALTER TABLE satei_users
ADD COLUMN first_name VARCHAR(255) NULL COMMENT '名（フォーム入力）' AFTER last_name;

-- 電話番号カラムを追加（フォーム入力）
ALTER TABLE satei_users
ADD COLUMN phone_number VARCHAR(50) NULL COMMENT '電話番号（フォーム入力）' AFTER first_name;
