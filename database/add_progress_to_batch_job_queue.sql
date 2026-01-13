-- バッチジョブキューに進捗情報カラムを追加
-- データベース: mirai_base

USE mirai_base;

-- 進捗メッセージカラムを追加
ALTER TABLE batch_job_queue 
ADD COLUMN progress_message TEXT NULL COMMENT '進捗メッセージ' 
AFTER error_message;

-- 進捗パーセンテージカラムを追加
ALTER TABLE batch_job_queue 
ADD COLUMN progress_percentage INT DEFAULT NULL COMMENT '進捗パーセンテージ（0-100）' 
AFTER progress_message;



