-- 物件買取実績テーブル作成スクリプト
-- データベース: mirai_base

USE mirai_base;

-- 物件買取実績テーブル
CREATE TABLE IF NOT EXISTS purchase_achievements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    -- 一覧表示項目
    property_image_url TEXT COMMENT '物件写真URL',
    purchase_date DATE COMMENT '買取日',
    title VARCHAR(255) COMMENT 'タイトル（例：◯県◯市一棟アパート）',
    
    -- 詳細表示項目
    property_name VARCHAR(255) COMMENT '物件名',
    building_age INT COMMENT '築年数',
    structure VARCHAR(100) COMMENT '構造',
    nearest_station VARCHAR(255) COMMENT '最寄り',
    
    -- その他管理項目（HubSpot関連はオプショナル）
    hubspot_bukken_id VARCHAR(255) COMMENT 'HubSpotの物件ID',
    hubspot_bukken_created_date DATETIME COMMENT 'HubSpotの物件登録日（オブジェクトの作成日）',
    hubspot_deal_id VARCHAR(255) COMMENT 'HubSpotの取引ID',
    is_public BOOLEAN DEFAULT FALSE COMMENT '公開フラグ',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'レコード作成日',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'レコード更新日',
    
    -- インデックス
    INDEX idx_hubspot_bukken_id (hubspot_bukken_id),
    INDEX idx_hubspot_deal_id (hubspot_deal_id),
    INDEX idx_purchase_date (purchase_date),
    INDEX idx_is_public (is_public),
    INDEX idx_created_at (created_at),
    
    -- ユニーク制約（hubspot_bukken_idとhubspot_deal_idの両方が存在する場合のみ適用）
    INDEX idx_bukken_deal (hubspot_bukken_id, hubspot_deal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件買取実績テーブル';

