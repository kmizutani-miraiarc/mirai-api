-- 電話番号カラムをsatei_usersからsatei_propertiesへ移動
USE mirai_base;

-- 1. satei_propertiesテーブルにphone_numberカラムを追加
ALTER TABLE satei_properties
ADD COLUMN phone_number VARCHAR(50) NULL COMMENT '電話番号（フォーム入力）' AFTER last_name;

-- 2. 既存データの移行（satei_usersのphone_numberをsatei_propertiesにコピー）
-- 注意: 1ユーザーに複数の物件がある場合、すべての物件に同じ電話番号がコピーされます
UPDATE satei_properties sp
INNER JOIN satei_users su ON sp.user_id = su.id
SET sp.phone_number = su.phone_number
WHERE su.phone_number IS NOT NULL;

-- 3. satei_usersテーブルからphone_numberカラムを削除
ALTER TABLE satei_users
DROP COLUMN phone_number;
