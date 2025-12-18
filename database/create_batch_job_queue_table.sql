-- バッチジョブキュー用テーブル
CREATE TABLE IF NOT EXISTS batch_job_queue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_name VARCHAR(255) NOT NULL COMMENT 'ジョブ名',
    script_path VARCHAR(500) NOT NULL COMMENT '実行するスクリプトのパス',
    status ENUM('pending', 'running', 'completed', 'failed') DEFAULT 'pending' COMMENT 'ステータス',
    priority INT DEFAULT 0 COMMENT '優先度（数値が大きいほど優先）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
    started_at TIMESTAMP NULL COMMENT '開始日時',
    completed_at TIMESTAMP NULL COMMENT '完了日時',
    error_message TEXT NULL COMMENT 'エラーメッセージ',
    retry_count INT DEFAULT 0 COMMENT 'リトライ回数',
    max_retries INT DEFAULT 0 COMMENT '最大リトライ回数',
    INDEX idx_status (status),
    INDEX idx_priority (priority DESC),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='バッチジョブキュー';

