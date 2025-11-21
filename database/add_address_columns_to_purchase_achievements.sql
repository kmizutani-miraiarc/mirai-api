-- 買取実績テーブルに住所カラムを追加するSQLスクリプト
-- 実行方法: mysql -u <user> -p <database> < add_address_columns_to_purchase_achievements.sql

-- カラムが存在しない場合のみ追加
SET @dbname = DATABASE();
SET @tablename = "purchase_achievements";

-- 都道府県カラムの追加
SET @prefecture_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
    AND TABLE_NAME = @tablename
    AND COLUMN_NAME = 'prefecture'
);

SET @sql_prefecture = IF(@prefecture_exists = 0,
    'ALTER TABLE purchase_achievements ADD COLUMN prefecture VARCHAR(50) COMMENT ''都道府県'' AFTER nearest_station',
    'SELECT ''prefectureカラムは既に存在します'' AS message'
);
PREPARE stmt FROM @sql_prefecture;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 市区町村カラムの追加
SET @city_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
    AND TABLE_NAME = @tablename
    AND COLUMN_NAME = 'city'
);

SET @sql_city = IF(@city_exists = 0,
    'ALTER TABLE purchase_achievements ADD COLUMN city VARCHAR(100) COMMENT ''市区町村'' AFTER prefecture',
    'SELECT ''cityカラムは既に存在します'' AS message'
);
PREPARE stmt FROM @sql_city;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 番地以下カラムの追加
SET @address_detail_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @dbname
    AND TABLE_NAME = @tablename
    AND COLUMN_NAME = 'address_detail'
);

SET @sql_address_detail = IF(@address_detail_exists = 0,
    'ALTER TABLE purchase_achievements ADD COLUMN address_detail VARCHAR(255) COMMENT ''番地以下'' AFTER city',
    'SELECT ''address_detailカラムは既に存在します'' AS message'
);
PREPARE stmt FROM @sql_address_detail;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 都道府県インデックスの追加
SET @idx_prefecture_exists = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @dbname
    AND TABLE_NAME = @tablename
    AND INDEX_NAME = 'idx_prefecture'
);

SET @sql_idx_prefecture = IF(@idx_prefecture_exists = 0,
    'CREATE INDEX idx_prefecture ON purchase_achievements (prefecture)',
    'SELECT ''idx_prefectureインデックスは既に存在します'' AS message'
);
PREPARE stmt FROM @sql_idx_prefecture;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 市区町村インデックスの追加
SET @idx_city_exists = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = @dbname
    AND TABLE_NAME = @tablename
    AND INDEX_NAME = 'idx_city'
);

SET @sql_idx_city = IF(@idx_city_exists = 0,
    'CREATE INDEX idx_city ON purchase_achievements (city)',
    'SELECT ''idx_cityインデックスは既に存在します'' AS message'
);
PREPARE stmt FROM @sql_idx_city;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT '住所カラムの追加処理が完了しました' AS result;

