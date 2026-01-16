-- 査定物件テーブルに姓と名のカラムを追加（フォーム入力用）
USE mirai_base;

-- カラムが存在しない場合のみ追加
SET @dbname = DATABASE();
SET @tablename = 'satei_properties';
SET @columnname_first = 'first_name';
SET @columnname_last = 'last_name';

-- first_nameカラムを追加
SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname_first)
    ) > 0,
    'SELECT 1', -- カラムが存在する場合は何もしない
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname_first, ' VARCHAR(255) NULL COMMENT ''名（フォーム入力）'' AFTER property_name')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- last_nameカラムを追加
SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname_last)
    ) > 0,
    'SELECT 1', -- カラムが存在する場合は何もしない
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname_last, ' VARCHAR(255) NULL COMMENT ''姓（フォーム入力）'' AFTER first_name')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;
