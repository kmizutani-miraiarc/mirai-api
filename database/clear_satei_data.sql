-- 査定物件依頼と査定ユーザーのデータをクリアするSQL
-- 注意: このSQLを実行すると、すべての査定データが削除されます
-- 実行前に必ずバックアップを取得してください

USE mirai_base;

-- 外部キー制約を一時的に無効化（削除を容易にするため）
SET FOREIGN_KEY_CHECKS = 0;

-- 1. アップロードファイルを削除（satei_propertiesに関連するファイル）
-- 注意: 実際のファイルはファイルシステムからも削除する必要があります
DELETE FROM upload_files 
WHERE entity_type = 'satei_property';

-- 2. 査定物件を削除
DELETE FROM satei_properties;

-- 3. 査定ユーザーを削除
DELETE FROM satei_users;

-- 外部キー制約を再有効化
SET FOREIGN_KEY_CHECKS = 1;

-- 削除結果を確認
SELECT 
    (SELECT COUNT(*) FROM satei_users) AS satei_users_count,
    (SELECT COUNT(*) FROM satei_properties) AS satei_properties_count,
    (SELECT COUNT(*) FROM upload_files WHERE entity_type = 'satei_property') AS upload_files_count;
