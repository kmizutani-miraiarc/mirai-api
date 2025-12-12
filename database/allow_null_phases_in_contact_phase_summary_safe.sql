-- コンタクトフェーズ集計テーブルのbuy_phaseとsell_phaseをNULL許可に変更
-- データベース: mirai_base
-- 目的: 空欄のフェーズと実際の'Z'フェーズを区別するため
-- 安全なバージョン（テーブル存在確認付き）

USE mirai_base;

-- テーブルが存在するか確認
SET @table_exists = (
    SELECT COUNT(*) 
    FROM information_schema.TABLES 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'contact_phase_summary'
);

-- テーブルが存在する場合のみスキーマ変更を実行
SET @sql = IF(@table_exists > 0,
    CONCAT(
        'ALTER TABLE contact_phase_summary ',
        'DROP INDEX IF EXISTS uk_aggregation_owner_phases;'
    ),
    'SELECT "テーブル contact_phase_summary が存在しません。先にテーブルを作成してください。" AS message;'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- buy_phaseをNULL許可に変更
SET @sql = IF(@table_exists > 0,
    CONCAT(
        'ALTER TABLE contact_phase_summary ',
        'MODIFY COLUMN buy_phase ENUM(\'S\', \'A\', \'B\', \'C\', \'D\', \'Z\') NULL ',
        'COMMENT \'仕入フェーズ（NULL=空欄）\';'
    ),
    'SELECT "スキップ: テーブルが存在しません" AS message;'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- sell_phaseをNULL許可に変更
SET @sql = IF(@table_exists > 0,
    CONCAT(
        'ALTER TABLE contact_phase_summary ',
        'MODIFY COLUMN sell_phase ENUM(\'S\', \'A\', \'B\', \'C\', \'D\', \'Z\') NULL ',
        'COMMENT \'販売フェーズ（NULL=空欄）\';'
    ),
    'SELECT "スキップ: テーブルが存在しません" AS message;'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 新しいユニーク制約を追加
SET @sql = IF(@table_exists > 0,
    CONCAT(
        'ALTER TABLE contact_phase_summary ',
        'ADD UNIQUE KEY uk_aggregation_owner_phases ',
        '(aggregation_date, owner_id, buy_phase, sell_phase);'
    ),
    'SELECT "スキップ: テーブルが存在しません" AS message;'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;


