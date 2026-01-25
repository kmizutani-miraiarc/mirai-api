-- satei_usersテーブルにメール無効フラグを追加
USE mirai_base;

-- カラムが存在しない場合のみ追加
SET @dbname = DATABASE();
SET @tablename = 'satei_users';
SET @columnname = 'is_email_invalid';

SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname)
    ) > 0,
    'SELECT 1', -- カラムが存在する場合は何もしない
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' BOOLEAN DEFAULT FALSE COMMENT ''メールアドレスが無効かどうか（送信失敗時に設定）'' AFTER email')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;
