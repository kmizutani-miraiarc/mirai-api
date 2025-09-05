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
