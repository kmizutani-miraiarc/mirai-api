-- 物件別販売取引レポート集計テーブルに取引詳細カラムを追加
-- データベース: mirai_base

USE mirai_base;

-- property_sales_stage_summaryテーブルに取引詳細カラムを追加
SET @dbname = DATABASE();
SET @tablename = 'property_sales_stage_summary';
SET @columnname = 'deal_details';

-- deal_detailsカラムを追加（存在しない場合のみ）
SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname)
    ) > 0,
    'SELECT 1', -- カラムが存在する場合は何もしない
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' MEDIUMTEXT NULL COMMENT ''取引詳細（JSON形式、会社名・コンタクト名を含む）'' AFTER deal_ids')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- owner_property_sales_stage_summaryテーブルに取引詳細カラムを追加
SET @tablename = 'owner_property_sales_stage_summary';

-- deal_detailsカラムを追加（存在しない場合のみ）
SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE
            (TABLE_SCHEMA = @dbname)
            AND (TABLE_NAME = @tablename)
            AND (COLUMN_NAME = @columnname)
    ) > 0,
    'SELECT 1', -- カラムが存在する場合は何もしない
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' MEDIUMTEXT NULL COMMENT ''取引詳細（JSON形式、会社名・コンタクト名を含む）'' AFTER deal_ids')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;
