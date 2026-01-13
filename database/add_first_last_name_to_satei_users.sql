-- satei_usersテーブルに姓と名のカラムを追加
USE mirai_base;

ALTER TABLE satei_users
ADD COLUMN first_name VARCHAR(255) NULL COMMENT '名（フォーム入力）' AFTER name,
ADD COLUMN last_name VARCHAR(255) NULL COMMENT '姓（フォーム入力）' AFTER first_name;



