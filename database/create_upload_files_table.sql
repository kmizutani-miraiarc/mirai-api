-- アップロードファイルテーブル作成SQL
-- データベース: mirai_base

USE mirai_base;

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




