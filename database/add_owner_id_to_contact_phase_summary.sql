-- コンタクトフェーズ集計テーブルにowner_idカラムを追加
-- データベース: mirai_base

USE mirai_base;

-- owner_idカラムを追加
ALTER TABLE contact_phase_summary
ADD COLUMN owner_id VARCHAR(255) NULL COMMENT '担当者ID（HubSpot）' AFTER owner_name;

-- インデックスを追加
ALTER TABLE contact_phase_summary
ADD INDEX idx_owner_id (owner_id);

-- 既存のユニーク制約を削除
ALTER TABLE contact_phase_summary
DROP INDEX uk_aggregation_owner_phases;

-- 新しいユニーク制約を追加（owner_idを使用）
ALTER TABLE contact_phase_summary
ADD UNIQUE KEY uk_aggregation_owner_phases (aggregation_date, owner_id, buy_phase, sell_phase);

-- 既存のインデックスを更新（owner_idを含む）
ALTER TABLE contact_phase_summary
DROP INDEX idx_aggregation_date_owner;

ALTER TABLE contact_phase_summary
ADD INDEX idx_aggregation_date_owner (aggregation_date, owner_id);




