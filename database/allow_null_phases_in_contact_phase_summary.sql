-- コンタクトフェーズ集計テーブルのbuy_phaseとsell_phaseをNULL許可に変更
-- データベース: mirai_base
-- 目的: 空欄のフェーズと実際の'Z'フェーズを区別するため

USE mirai_base;

-- 既存のユニーク制約を削除（NULLを許可する前に削除が必要）
ALTER TABLE contact_phase_summary
DROP INDEX uk_aggregation_owner_phases;

-- buy_phaseをNULL許可に変更
ALTER TABLE contact_phase_summary
MODIFY COLUMN buy_phase ENUM('S', 'A', 'B', 'C', 'D', 'Z') NULL COMMENT '仕入フェーズ（NULL=空欄）';

-- sell_phaseをNULL許可に変更
ALTER TABLE contact_phase_summary
MODIFY COLUMN sell_phase ENUM('S', 'A', 'B', 'C', 'D', 'Z') NULL COMMENT '販売フェーズ（NULL=空欄）';

-- 新しいユニーク制約を追加（NULLを考慮）
-- MySQLでは、NULL値はユニーク制約で区別されるため、同じNULL値でも複数の行が存在可能
-- ただし、owner_idがNULLでない場合、同じaggregation_date, owner_id, buy_phase, sell_phaseの組み合わせは1つだけ
ALTER TABLE contact_phase_summary
ADD UNIQUE KEY uk_aggregation_owner_phases (aggregation_date, owner_id, buy_phase, sell_phase);


