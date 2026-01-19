-- 仕入集計レポート用テーブル作成SQL
-- データベース: mirai_base
-- 実行方法: docker compose exec -T mysql mysql -u root -prootpassword mirai_base < create_purchase_summary_table_executable.sql

USE mirai_base;

-- 既存のテーブルを削除（必要に応じて）
-- DROP TABLE IF EXISTS purchase_summary;

-- 仕入集計レポート用テーブル
-- 年、担当者、月別の集計データを保存
CREATE TABLE IF NOT EXISTS purchase_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    aggregation_year INT NOT NULL COMMENT '集計年',
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名',
    month INT NOT NULL COMMENT '月（1-12）',
    total_deals INT DEFAULT 0 COMMENT '取引数',
    stage_breakdown JSON COMMENT 'ステージ別内訳（JSON形式）',
    monthly_data JSON COMMENT '月別詳細データ（JSON形式、当月系のデータも含む）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    UNIQUE KEY uk_purchase_summary (aggregation_year, owner_id, month),
    INDEX idx_aggregation_year (aggregation_year),
    INDEX idx_owner_id (owner_id),
    INDEX idx_month (month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='仕入集計レポート';
