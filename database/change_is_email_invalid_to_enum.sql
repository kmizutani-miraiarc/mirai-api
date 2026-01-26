-- satei_usersテーブルのis_email_invalidカラムをENUM型に変更
-- 値: 'pending' (確認中), 'valid' (有効), 'invalid' (無効)

USE mirai_base;

-- 既存のデータを変換
-- FALSE -> 'valid' (有効)
-- TRUE -> 'invalid' (無効)
-- NULL -> 'pending' (確認中)

-- ステップ1: 一時カラムを追加
ALTER TABLE satei_users 
ADD COLUMN is_email_invalid_temp VARCHAR(10) NULL COMMENT '一時カラム（メールアドレス有効性: pending=確認中, valid=有効, invalid=無効）' AFTER email;

-- ステップ2: 既存データを変換
UPDATE satei_users 
SET is_email_invalid_temp = CASE
    WHEN is_email_invalid IS NULL THEN 'pending'
    WHEN is_email_invalid = FALSE THEN 'valid'
    WHEN is_email_invalid = TRUE THEN 'invalid'
    ELSE 'pending'
END;

-- ステップ3: 古いカラムを削除
ALTER TABLE satei_users DROP COLUMN is_email_invalid;

-- ステップ4: 新しいENUM型カラムを追加
ALTER TABLE satei_users 
ADD COLUMN is_email_invalid ENUM('pending', 'valid', 'invalid') DEFAULT 'pending' COMMENT 'メールアドレス有効性: pending=確認中, valid=有効, invalid=無効' AFTER email;

-- ステップ5: 一時カラムのデータを新しいカラムにコピー
UPDATE satei_users 
SET is_email_invalid = is_email_invalid_temp;

-- ステップ6: 一時カラムを削除
ALTER TABLE satei_users DROP COLUMN is_email_invalid_temp;
