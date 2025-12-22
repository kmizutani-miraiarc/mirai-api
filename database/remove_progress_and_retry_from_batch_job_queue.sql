-- バッチジョブキューから進捗とリトライ回数のカラムを削除
-- 各カラムを個別に削除（エラーが発生しても続行）
SET @sql = 'ALTER TABLE batch_job_queue DROP COLUMN progress_message';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'batch_job_queue' 
    AND COLUMN_NAME = 'progress_message') > 0, @sql, 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'ALTER TABLE batch_job_queue DROP COLUMN progress_percentage';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'batch_job_queue' 
    AND COLUMN_NAME = 'progress_percentage') > 0, @sql, 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'ALTER TABLE batch_job_queue DROP COLUMN retry_count';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'batch_job_queue' 
    AND COLUMN_NAME = 'retry_count') > 0, @sql, 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = 'ALTER TABLE batch_job_queue DROP COLUMN max_retries';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'batch_job_queue' 
    AND COLUMN_NAME = 'max_retries') > 0, @sql, 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- インデックスも削除（存在する場合）
SET @sql = 'ALTER TABLE batch_job_queue DROP INDEX idx_progress_percentage';
SET @sql = IF((SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'batch_job_queue' 
    AND INDEX_NAME = 'idx_progress_percentage') > 0, @sql, 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

