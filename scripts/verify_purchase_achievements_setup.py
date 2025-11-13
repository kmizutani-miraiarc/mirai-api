#!/usr/bin/env python3
"""
物件買取実績機能のセットアップ検証スクリプト
データベース接続、テーブル作成、API動作確認を行う
"""

import asyncio
import sys
import os
import logging

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_connection
from hubspot.config import Config
from services.purchase_achievement_service import PurchaseAchievementService
from models.purchase_achievement import PurchaseAchievementCreate
from datetime import date

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_database_connection():
    """データベース接続を確認"""
    try:
        logger.info("データベース接続を確認中...")
        await db_connection.create_pool()
        
        # 接続テスト
        test_result = await db_connection.test_connection()
        if test_result:
            logger.info("✅ データベース接続に成功しました")
            return True
        else:
            logger.error("❌ データベース接続テストに失敗しました")
            return False
            
    except Exception as e:
        logger.error(f"❌ データベース接続エラー: {str(e)}")
        return False

async def check_table_exists():
    """テーブルが存在するか確認"""
    try:
        logger.info("テーブルの存在を確認中...")
        
        query = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'purchase_achievements'
        """
        result = await db_connection.execute_query(query)
        
        if result and result[0]["count"] > 0:
            logger.info("✅ purchase_achievements テーブルが存在します")
            
            # テーブル構造を確認
            describe_query = "DESCRIBE purchase_achievements"
            try:
                columns = await db_connection.execute_query(describe_query)
                logger.info(f"テーブルカラム数: {len(columns)}")
                for column in columns:
                    field_name = column.get('Field') or column.get('field')
                    field_type = column.get('Type') or column.get('type')
                    logger.info(f"  - {field_name}: {field_type}")
            except Exception as e:
                logger.warning(f"テーブル構造の取得に失敗しました: {str(e)}")
            
            return True
        else:
            logger.warning("⚠️ purchase_achievements テーブルが存在しません")
            return False
            
    except Exception as e:
        logger.error(f"❌ テーブル確認エラー: {str(e)}")
        return False

async def create_table_if_not_exists():
    """テーブルが存在しない場合、作成する"""
    try:
        logger.info("テーブルを作成中...")
        
        CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS purchase_achievements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            property_image_url TEXT COMMENT '物件写真URL',
            purchase_date DATE COMMENT '買取日',
            title VARCHAR(255) COMMENT 'タイトル（例：◯県◯市一棟アパート）',
            property_name VARCHAR(255) COMMENT '物件名',
            building_age INT COMMENT '築年数',
            structure VARCHAR(100) COMMENT '構造',
            nearest_station VARCHAR(255) COMMENT '最寄り',
            hubspot_bukken_id VARCHAR(255) COMMENT 'HubSpotの物件ID',
            hubspot_bukken_created_date DATETIME COMMENT 'HubSpotの物件登録日（オブジェクトの作成日）',
            hubspot_deal_id VARCHAR(255) COMMENT 'HubSpotの取引ID',
            is_public BOOLEAN DEFAULT FALSE COMMENT '公開フラグ',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'レコード作成日',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'レコード更新日',
            INDEX idx_hubspot_bukken_id (hubspot_bukken_id),
            INDEX idx_hubspot_deal_id (hubspot_deal_id),
            INDEX idx_purchase_date (purchase_date),
            INDEX idx_is_public (is_public),
            INDEX idx_created_at (created_at),
            INDEX idx_bukken_deal (hubspot_bukken_id, hubspot_deal_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件買取実績テーブル';
        """
        
        await db_connection.execute_update(CREATE_TABLE_SQL)
        logger.info("✅ テーブルを作成しました")
        return True
        
    except Exception as e:
        logger.error(f"❌ テーブル作成エラー: {str(e)}")
        return False

async def test_service():
    """サービスの動作確認"""
    try:
        logger.info("サービスの動作確認中...")
        
        service = PurchaseAchievementService()
        
        # テストデータを作成
        test_achievement = PurchaseAchievementCreate(
            title="テスト物件：千葉県柏市一棟アパート",
            property_name="柏市一棟アパート",
            purchase_date=date.today(),
            building_age=10,
            structure="RC造",
            nearest_station="柏駅",
            is_public=False
        )
        
        # 作成
        achievement_id = await service.create(test_achievement)
        logger.info(f"✅ テストデータを作成しました (ID: {achievement_id})")
        
        # 取得
        achievement = await service.get_by_id(achievement_id)
        if achievement:
            logger.info(f"✅ テストデータを取得しました: {achievement.get('title')}")
        
        # 一覧取得
        achievements = await service.get_list(limit=10)
        logger.info(f"✅ 一覧を取得しました ({len(achievements)}件)")
        
        # テストデータを削除（直接SQLで削除）
        delete_query = "DELETE FROM purchase_achievements WHERE id = %s"
        await db_connection.execute_update(delete_query, (achievement_id,))
        logger.info(f"✅ テストデータを削除しました (ID: {achievement_id})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ サービス動作確認エラー: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """メイン関数"""
    try:
        logger.info("=" * 60)
        logger.info("物件買取実績機能のセットアップ検証を開始します")
        logger.info("=" * 60)
        
        # 1. データベース接続確認
        if not await check_database_connection():
            logger.error("データベース接続に失敗しました。環境変数を確認してください。")
            sys.exit(1)
        
        # 2. テーブル存在確認
        table_exists = await check_table_exists()
        
        # 3. テーブルが存在しない場合、作成
        if not table_exists:
            logger.info("テーブルが存在しないため、作成します...")
            if not await create_table_if_not_exists():
                logger.error("テーブル作成に失敗しました")
                sys.exit(1)
            # 再度確認
            if not await check_table_exists():
                logger.error("テーブル作成後に確認に失敗しました")
                sys.exit(1)
        
        # 4. サービスの動作確認
        if not await test_service():
            logger.error("サービスの動作確認に失敗しました")
            sys.exit(1)
        
        logger.info("=" * 60)
        logger.info("✅ すべての検証が正常に完了しました")
        logger.info("=" * 60)
        logger.info("次のステップ:")
        logger.info("1. APIサーバーを再起動: sudo systemctl restart mirai-api")
        logger.info("2. APIエンドポイントをテスト:")
        logger.info("   curl -X GET 'http://localhost:8000/purchase-achievements?limit=10' \\")
        logger.info("     -H 'X-API-Key: your-api-key'")
        
    except Exception as e:
        logger.error(f"検証中にエラーが発生しました: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        await db_connection.close_pool()

if __name__ == "__main__":
    asyncio.run(main())

