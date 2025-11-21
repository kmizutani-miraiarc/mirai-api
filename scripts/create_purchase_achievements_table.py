#!/usr/bin/env python3
"""
物件買取実績テーブル作成スクリプト
データベースにテーブルを作成する
"""

import asyncio
import sys
import os
import logging

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_connection
from hubspot.config import Config

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SQLスクリプト
CREATE_TABLE_SQL = """
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
    
    -- インデックス（hubspot_bukken_idとhubspot_deal_idの両方が存在する場合のみ適用）
    INDEX idx_bukken_deal (hubspot_bukken_id, hubspot_deal_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件買取実績テーブル';
"""

async def create_table():
    """テーブルを作成"""
    try:
        logger.info("データベース接続プールを作成中...")
        await db_connection.create_pool()
        
        logger.info("物件買取実績テーブルを作成中...")
        await db_connection.execute_update(CREATE_TABLE_SQL)
        
        logger.info("物件買取実績テーブルが正常に作成されました")
        
        # テーブルの存在確認
        check_query = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'purchase_achievements'
        """
        result = await db_connection.execute_query(check_query)
        if result and result[0]["count"] > 0:
            logger.info("テーブルの作成が確認されました")
        else:
            logger.warning("テーブルの作成が確認できませんでした")
        
    except Exception as e:
        logger.error(f"テーブル作成中にエラーが発生しました: {str(e)}")
        raise
    finally:
        await db_connection.close_pool()

async def main():
    """メイン関数"""
    try:
        logger.info("物件買取実績テーブル作成スクリプトを開始します")
        await create_table()
        logger.info("スクリプトが正常に完了しました")
        
    except Exception as e:
        logger.error(f"スクリプト実行中にエラーが発生しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())




