-- コンタクトIDカラムを追加（JSON形式対応、MEDIUMTEXT型）
-- データベース: mirai_base
-- すべての集計テーブルにコンタクトIDと名前をJSON形式で保存するカラムを追加
-- 
-- 注意: 既にカラムが存在する場合はエラーになります。
-- 既存のカラムをMEDIUMTEXTに変更する場合は、change_contact_ids_to_mediumtext.sqlを使用してください。
-- 新しい環境で初めて実行する場合に使用してください。

USE mirai_base;

-- contact_phase_summaryテーブルにcontact_idsカラムを追加
ALTER TABLE contact_phase_summary
ADD COLUMN contact_ids MEDIUMTEXT NULL COMMENT '集計対象のコンタクトIDと名前（JSON形式）' AFTER count;

-- contact_phase_summary_monthlyテーブルにcontact_idsカラムを追加
ALTER TABLE contact_phase_summary_monthly
ADD COLUMN contact_ids MEDIUMTEXT NULL COMMENT '集計対象のコンタクトIDと名前（JSON形式）' AFTER count;

-- contact_scoring_summaryテーブルに各集計項目用のcontact_idsカラムを追加
ALTER TABLE contact_scoring_summary
ADD COLUMN industry_contact_ids MEDIUMTEXT NULL COMMENT '業種に入力があるコンタクトIDと名前（JSON形式）' AFTER industry_count,
ADD COLUMN property_type_contact_ids MEDIUMTEXT NULL COMMENT '取扱種別に入力があるコンタクトIDと名前（JSON形式）' AFTER property_type_count,
ADD COLUMN area_contact_ids MEDIUMTEXT NULL COMMENT '取扱エリアに入力があるコンタクトIDと名前（JSON形式）' AFTER area_count,
ADD COLUMN area_category_contact_ids MEDIUMTEXT NULL COMMENT 'エリアカテゴリに入力があるコンタクトIDと名前（JSON形式）' AFTER area_category_count,
ADD COLUMN gross_contact_ids MEDIUMTEXT NULL COMMENT 'グロスに入力があるコンタクトIDと名前（JSON形式）' AFTER gross_count,
ADD COLUMN all_five_items_contact_ids MEDIUMTEXT NULL COMMENT '５項目すべてに入力があるコンタクトIDと名前（JSON形式）' AFTER all_five_items_count,
ADD COLUMN target_audience_contact_ids MEDIUMTEXT NULL COMMENT '対象ターゲットのコンタクトIDと名前（JSON形式）' AFTER target_audience_count;

-- インデックスは不要（MEDIUMTEXT型のため）

