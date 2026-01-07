-- 査定物件テーブルに担当者コメントカラムを追加
-- データベース: mirai_base

USE mirai_base;

-- 担当者コメントカラムを追加
ALTER TABLE satei_properties 
ADD COLUMN owner_comment TEXT COMMENT '担当者コメント' AFTER comment;






