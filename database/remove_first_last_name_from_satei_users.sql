-- satei_usersテーブルから姓と名のカラムを削除
-- フォーム入力の氏名はsatei_propertiesテーブルに保存するため
USE mirai_base;

-- first_nameカラムを削除（存在する場合のみ）
SET @dbname = DATABASE();
SET @tablename = 'satei_users';
SET @columnname_first = 'first_name';
SET @columnname_last = 'last_name';

-- first_nameカラムを削除
SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname_first)
    ) > 0,
    CONCAT('ALTER TABLE ', @tablename, ' DROP COLUMN ', @columnname_first),
    'SELECT 1' -- カラムが存在しない場合は何もしない
));
PREPARE alterIfExists FROM @preparedStatement;
EXECUTE alterIfExists;
DEALLOCATE PREPARE alterIfExists;

-- last_nameカラムを削除
SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname_last)
    ) > 0,
    CONCAT('ALTER TABLE ', @tablename, ' DROP COLUMN ', @columnname_last),
    'SELECT 1' -- カラムが存在しない場合は何もしない
));
PREPARE alterIfExists FROM @preparedStatement;
EXECUTE alterIfExists;
DEALLOCATE PREPARE alterIfExists;
