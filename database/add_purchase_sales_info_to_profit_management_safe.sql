-- profit_managementテーブルに仕入・販売情報カラムを追加（安全版：既存カラムをチェック）
-- データベース: mirai_base

USE mirai_base;

-- 仕入決済日カラムを追加（存在しない場合のみ）
SET @dbname = DATABASE();
SET @tablename = "profit_management";
SET @columnname = "purchase_settlement_date";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  "SELECT 'Column purchase_settlement_date already exists.' AS result;",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " DATE DEFAULT NULL COMMENT '仕入決済日' AFTER property_type;")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 仕入価格カラムを追加（存在しない場合のみ）
SET @columnname = "purchase_price";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  "SELECT 'Column purchase_price already exists.' AS result;",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " DECIMAL(15, 2) DEFAULT NULL COMMENT '仕入価格' AFTER purchase_settlement_date;")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 販売決済日カラムを追加（存在しない場合のみ）
SET @columnname = "sales_settlement_date";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  "SELECT 'Column sales_settlement_date already exists.' AS result;",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " DATE DEFAULT NULL COMMENT '販売決済日' AFTER purchase_price;")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 販売価格カラムを追加（存在しない場合のみ）
SET @columnname = "sales_price";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  "SELECT 'Column sales_price already exists.' AS result;",
  CONCAT("ALTER TABLE ", @tablename, " ADD COLUMN ", @columnname, " DECIMAL(15, 2) DEFAULT NULL COMMENT '販売価格' AFTER sales_settlement_date;")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- インデックスを追加（存在しない場合のみ）
-- purchase_settlement_dateのインデックス
SET @indexname = "idx_purchase_settlement_date";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (index_name = @indexname)
  ) > 0,
  "SELECT 'Index idx_purchase_settlement_date already exists.' AS result;",
  CONCAT("ALTER TABLE ", @tablename, " ADD INDEX ", @indexname, " (purchase_settlement_date);")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- sales_settlement_dateのインデックス
SET @indexname = "idx_sales_settlement_date";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (index_name = @indexname)
  ) > 0,
  "SELECT 'Index idx_sales_settlement_date already exists.' AS result;",
  CONCAT("ALTER TABLE ", @tablename, " ADD INDEX ", @indexname, " (sales_settlement_date);")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;


