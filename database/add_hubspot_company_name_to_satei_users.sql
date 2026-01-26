-- satei_usersテーブルにHubSpot会社名カラムを追加
USE mirai_base;

-- カラムが存在しない場合のみ追加
SET @dbname = DATABASE();
SET @tablename = 'satei_users';
SET @columnname = 'hubspot_company_name';

SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname)
    ) > 0,
    'SELECT 1', -- カラムが存在する場合は何もしない
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(255) NULL COMMENT ''HubSpot会社名（コンタクトに関連付けられた会社）'' AFTER owner_name')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;
