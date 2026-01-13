-- バッチジョブキューにstop_requestedカラムを追加
ALTER TABLE batch_job_queue
ADD COLUMN stop_requested BOOLEAN DEFAULT FALSE COMMENT '停止要求フラグ' AFTER max_retries;

-- インデックスを追加（オプション、必要に応じて）
-- ALTER TABLE batch_job_queue
-- ADD INDEX idx_stop_requested (stop_requested);



