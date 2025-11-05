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
    file_name VARCHAR(255) NOT NULL COMMENT 'ファイル名',
    file_path VARCHAR(500) NOT NULL COMMENT 'ファイルパス',
    file_size INT COMMENT 'ファイルサイズ（バイト）',
    mime_type VARCHAR(100) COMMENT 'MIMEタイプ',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
    FOREIGN KEY (user_id) REFERENCES satei_users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
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
