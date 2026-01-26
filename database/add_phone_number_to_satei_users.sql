-- satei_usersテーブルに電話番号カラムを追加
USE mirai_base;

ALTER TABLE satei_users
ADD COLUMN phone_number VARCHAR(50) NULL COMMENT '電話番号（フォーム入力）' AFTER email;
