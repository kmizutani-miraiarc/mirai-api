-- 査定物件テーブルにコメントカラムを追加
-- カラムが既に存在する場合はエラーになりますが、無視して問題ありません

-- 方法1: カラムが存在しない場合のみ追加（MySQL 5.7以降でサポート）
-- 注意: この方法は一部のMySQLバージョンではサポートされていない場合があります
SET @dbname = DATABASE();
SET @tablename = 'satei_properties';
SET @columnname = 'comment';
SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname)
    ) > 0,
    'SELECT 1', -- カラムが存在する場合は何もしない
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' TEXT COMMENT ''コメント'' AFTER estimated_price_to')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 方法2: 直接ALTER TABLEを実行（カラムが既に存在する場合はエラーになりますが、無視して問題ありません）
-- ALTER TABLE satei_properties 
-- ADD COLUMN comment TEXT COMMENT 'コメント' AFTER estimated_price_to;

