-- コンタクトスコアリング（仕入）集計テーブルにpattern_typeカラムを追加
-- データベース: mirai_base

USE mirai_base;

-- 既存のユニーク制約を削除
ALTER TABLE contact_scoring_summary
DROP INDEX uk_aggregation_owner;

-- pattern_typeカラムを追加
ALTER TABLE contact_scoring_summary
ADD COLUMN pattern_type ENUM('all', 'buy', 'sell', 'buy_or_sell') NOT NULL DEFAULT 'all' COMMENT 'パターン区分（all=総数, buy=仕入, sell=売却, buy_or_sell=仕入・売却）' AFTER owner_name;

-- 既存データにpattern_type='all'を設定
UPDATE contact_scoring_summary
SET pattern_type = 'all'
WHERE pattern_type IS NULL OR pattern_type = '';

-- 新しいユニーク制約を追加（同じ集計日、担当者、パターン区分の組み合わせは1つだけ）
ALTER TABLE contact_scoring_summary
ADD UNIQUE KEY uk_aggregation_owner_pattern (aggregation_date, owner_id, pattern_type);

-- pattern_typeのインデックスを追加
ALTER TABLE contact_scoring_summary
ADD INDEX idx_pattern_type (pattern_type);


