-- Mirai API データベース初期化スクリプト
-- データベース: mirai_base

-- データベースの作成（存在しない場合）
CREATE DATABASE IF NOT EXISTS mirai_base 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- データベースの使用
USE mirai_base;

-- APIキー管理テーブル
CREATE TABLE IF NOT EXISTS api_keys (
    id INT AUTO_INCREMENT PRIMARY KEY,
    site_name VARCHAR(255) NOT NULL UNIQUE COMMENT 'サイト名',
    api_key_hash VARCHAR(255) NOT NULL UNIQUE COMMENT 'APIキーのハッシュ値',
    api_key_prefix VARCHAR(20) NOT NULL COMMENT 'APIキーの先頭部分（表示用）',
    description TEXT COMMENT 'APIキーの説明',
    is_active BOOLEAN DEFAULT TRUE COMMENT 'アクティブ状態',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    last_used_at TIMESTAMP NULL COMMENT '最終使用日時',
    expires_at TIMESTAMP NULL COMMENT '有効期限（NULLの場合は無期限）',
    INDEX idx_site_name (site_name),
    INDEX idx_api_key_hash (api_key_hash),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='APIキー管理テーブル';

-- サンプルAPIキーの挿入（開発用）
-- 注意: 実際の運用では、APIキーはアプリケーション経由で作成してください
INSERT IGNORE INTO api_keys (site_name, api_key_hash, api_key_prefix, description, is_active) VALUES
('test-site', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'test1234567...', 'テスト用APIキー', TRUE),
('demo-site', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b856', 'demo1234567...', 'デモ用APIキー', TRUE);

-- テーブル作成確認
SHOW TABLES;

-- APIキーテーブルの構造確認
DESCRIBE api_keys;

-- サンプルデータの確認
SELECT * FROM api_keys;

-- ユーザーテーブル（user_gmail_credentialsテーブルが参照するため、先に作成）
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE NOT NULL COMMENT 'Google ID',
    email VARCHAR(255) UNIQUE NOT NULL COMMENT 'メールアドレス',
    name VARCHAR(255) NOT NULL COMMENT '名前',
    picture VARCHAR(500) COMMENT 'プロフィール画像URL',
    role ENUM('admin', 'user') DEFAULT 'user' COMMENT 'ロール',
    last_login TIMESTAMP NULL COMMENT '最終ログイン日時',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    INDEX idx_google_id (google_id),
    INDEX idx_email (email),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ユーザーテーブル';

-- 査定物件ユーザー情報テーブル
CREATE TABLE IF NOT EXISTS satei_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    unique_id VARCHAR(255) NOT NULL UNIQUE COMMENT 'ユニークID',
    email VARCHAR(255) NOT NULL COMMENT 'メールアドレス',
    contact_id VARCHAR(255) COMMENT 'HubSpotコンタクトID',
    name VARCHAR(255) COMMENT '名前',
    owner_id VARCHAR(255) COMMENT '担当者ID（HubSpot Owner ID）',
    owner_name VARCHAR(255) COMMENT '担当者名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    INDEX idx_unique_id (unique_id),
    INDEX idx_email (email),
    INDEX idx_contact_id (contact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='査定物件ユーザー情報テーブル';

-- 査定物件テーブル
CREATE TABLE IF NOT EXISTS satei_properties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '査定物件ユーザー情報ID（外部キー）',
    owner_user_id INT COMMENT '担当者ユーザーID（usersテーブルへの外部キー）',
    property_name VARCHAR(255) COMMENT '物件名',
    request_date DATE COMMENT '依頼日',
    status VARCHAR(50) DEFAULT 'parsing' COMMENT 'ステータス（parsing, evaluated, etc.）',
    estimated_price_from DECIMAL(12, 2) COMMENT '査定価格（下限）',
    estimated_price_to DECIMAL(12, 2) COMMENT '査定価格（上限）',
    comment TEXT COMMENT 'コメント',
    owner_comment TEXT COMMENT '担当者コメント',
    evaluation_date DATE COMMENT '査定日',
    for_sale BOOLEAN DEFAULT FALSE COMMENT '売却フラグ',
    evaluation_result ENUM('buyable', 'not_buyable', 'pending') COMMENT '査定結果',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    FOREIGN KEY (user_id) REFERENCES satei_users(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_owner_user_id (owner_user_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_request_date (request_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='査定物件テーブル';

-- Gmail認証情報テーブル（ユーザーごとのGmail API認証情報を保存）
CREATE TABLE IF NOT EXISTS user_gmail_credentials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'ユーザーID（usersテーブルへの外部キー）',
    email VARCHAR(255) NOT NULL COMMENT 'メールアドレス',
    gmail_client_id VARCHAR(500) NOT NULL COMMENT 'Gmail Client ID',
    gmail_client_secret VARCHAR(500) NOT NULL COMMENT 'Gmail Client Secret',
    gmail_refresh_token TEXT NOT NULL COMMENT 'Gmail Refresh Token',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_id (user_id),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Gmail認証情報テーブル';

-- 配配メールログテーブル
CREATE TABLE IF NOT EXISTS haihai_click_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL COMMENT 'メールアドレス',
    mail_type VARCHAR(50) NOT NULL COMMENT 'メール種別',
    mail_id VARCHAR(255) NOT NULL COMMENT 'メールID',
    subject VARCHAR(255) NOT NULL COMMENT '件名',
    click_date DATETIME NOT NULL COMMENT 'クリック日時',
    url TEXT NOT NULL COMMENT 'URL',
    hubspot_contact_id VARCHAR(255) DEFAULT NULL COMMENT 'HubSpot連絡先ID',
    hubspot_owner_email VARCHAR(255) DEFAULT NULL COMMENT 'HubSpot担当者メールアドレス',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    INDEX idx_email (email),
    INDEX idx_click_date (click_date),
    INDEX idx_mail_id (mail_id),
    INDEX idx_hubspot_contact_id (hubspot_contact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配配メールログテーブル';

-- アップロードファイルテーブル
CREATE TABLE IF NOT EXISTS upload_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL COMMENT 'エンティティタイプ（例: satei_property）',
    entity_id INT NOT NULL COMMENT 'エンティティID',
    file_name VARCHAR(500) NOT NULL COMMENT 'ファイル名',
    file_path TEXT NOT NULL COMMENT 'ファイルパス',
    file_size BIGINT NOT NULL COMMENT 'ファイルサイズ（バイト）',
    mime_type VARCHAR(255) COMMENT 'MIMEタイプ',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    INDEX idx_entity_type_id (entity_type, entity_id),
    INDEX idx_entity_type (entity_type),
    INDEX idx_entity_id (entity_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='アップロードファイルテーブル';

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
    
    -- 住所情報
    prefecture VARCHAR(50) COMMENT '都道府県',
    city VARCHAR(100) COMMENT '市区町村',
    address_detail VARCHAR(255) COMMENT '番地以下',
    
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
    INDEX idx_prefecture (prefecture),
    INDEX idx_city (city),
    
    -- インデックス（hubspot_bukken_idとhubspot_deal_idの両方が存在する場合のみ適用）
    INDEX idx_bukken_deal (hubspot_bukken_id, hubspot_deal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件買取実績テーブル';

-- 粗利按分管理テーブル
CREATE TABLE IF NOT EXISTS profit_management (
    seq_no INT AUTO_INCREMENT PRIMARY KEY COMMENT '登録時自動採番する番号',
    
    -- 基本情報
    property_id VARCHAR(255) NOT NULL COMMENT '物件番号（HubSpotの物件ID）',
    property_name VARCHAR(255) NOT NULL COMMENT '物件名',
    property_type VARCHAR(100) DEFAULT NULL COMMENT '種別',
    
    -- 粗利情報
    gross_profit DECIMAL(15, 2) DEFAULT NULL COMMENT '粗利',
    profit_confirmed BOOLEAN DEFAULT FALSE COMMENT '粗利確定',
    
    -- 粗利按分情報
    purchase_owner_profit_rate DECIMAL(5, 2) DEFAULT NULL COMMENT '仕入担当粗利率(%)',
    purchase_owner_profit DECIMAL(15, 2) DEFAULT NULL COMMENT '仕入担当粗利',
    sales_owner_profit_rate DECIMAL(5, 2) DEFAULT NULL COMMENT '販売担当粗利率(%)',
    sales_owner_profit DECIMAL(15, 2) DEFAULT NULL COMMENT '販売担当粗利',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_property_id (property_id),
    INDEX idx_property_name (property_name),
    INDEX idx_profit_confirmed (profit_confirmed),
    INDEX idx_accounting_year_month (accounting_year_month),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='粗利按分管理テーブル';

-- 物件担当者テーブル
CREATE TABLE IF NOT EXISTS property_owners (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 基本情報
    property_id VARCHAR(255) NOT NULL COMMENT '物件番号（HubSpotの物件ID）',
    profit_management_seq_no INT DEFAULT NULL COMMENT '粗利按分管理レコードのseq_no（外部キー）',
    owner_type ENUM('purchase', 'sales') NOT NULL COMMENT '種別（仕入or販売）',
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名',
    
    -- 取引情報
    settlement_date DATE DEFAULT NULL COMMENT '決済日',
    price DECIMAL(15, 2) DEFAULT NULL COMMENT '価格',
    profit_rate DECIMAL(5, 2) DEFAULT NULL COMMENT '粗利率(%)',
    profit_amount DECIMAL(15, 2) DEFAULT NULL COMMENT '粗利',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_property_id (property_id),
    INDEX idx_profit_management_seq_no (profit_management_seq_no),
    INDEX idx_owner_type (owner_type),
    INDEX idx_owner_id (owner_id),
    INDEX idx_settlement_date (settlement_date),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件担当者テーブル';

-- 粗利目標管理テーブル
CREATE TABLE IF NOT EXISTS profit_target (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
    
    -- 基本情報
    owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID（HubSpotの担当者ID）',
    owner_name VARCHAR(255) NOT NULL COMMENT '担当者名',
    year INT NOT NULL COMMENT '年度',
    
    -- 四半期目標
    q1_target DECIMAL(15, 2) DEFAULT NULL COMMENT '1Q目標額',
    q2_target DECIMAL(15, 2) DEFAULT NULL COMMENT '2Q目標額',
    q3_target DECIMAL(15, 2) DEFAULT NULL COMMENT '3Q目標額',
    q4_target DECIMAL(15, 2) DEFAULT NULL COMMENT '4Q目標額',
    
    -- タイムスタンプ
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    
    -- インデックス
    INDEX idx_owner_id (owner_id),
    INDEX idx_year (year),
    INDEX idx_owner_year (owner_id, year),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at),
    
    -- ユニーク制約（同じ担当者・同じ年の組み合わせは1つだけ）
    UNIQUE KEY uk_owner_year (owner_id, year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='粗利目標管理テーブル';
