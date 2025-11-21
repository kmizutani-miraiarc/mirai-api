#!/usr/bin/env python3
"""
買取実績テーブルに住所カラムを追加するスクリプト
"""
import sys
import os
import asyncio
import logging

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_and_add_columns():
    """カラムの存在確認と追加"""
    try:
        # データベース接続プールを作成
        await db_connection.create_pool()
        logger.info("データベース接続プールを作成しました")
        
        # カラムの存在確認
        check_columns_query = """
            SELECT COLUMN_NAME 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'purchase_achievements'
            AND COLUMN_NAME IN ('prefecture', 'city', 'address_detail')
        """
        
        logger.info("既存カラムを確認中...")
        existing_columns_result = await db_connection.execute_query(check_columns_query)
        
        # 辞書またはタプルで返される可能性があるため、両方に対応
        existing_columns = set()
        if existing_columns_result:
            for row in existing_columns_result:
                if isinstance(row, dict):
                    column_name = row.get("COLUMN_NAME") or row.get("column_name")
                else:
                    column_name = row[0] if len(row) > 0 else None
                if column_name:
                    existing_columns.add(column_name)
        
        logger.info(f"既存カラム: {existing_columns}")
        
        # カラムを追加
        alter_queries = []
        if "prefecture" not in existing_columns:
            alter_queries.append((
                "ALTER TABLE purchase_achievements ADD COLUMN prefecture VARCHAR(50) COMMENT '都道府県' AFTER nearest_station",
                "prefecture"
            ))
        if "city" not in existing_columns:
            alter_queries.append((
                "ALTER TABLE purchase_achievements ADD COLUMN city VARCHAR(100) COMMENT '市区町村' AFTER prefecture",
                "city"
            ))
        if "address_detail" not in existing_columns:
            alter_queries.append((
                "ALTER TABLE purchase_achievements ADD COLUMN address_detail VARCHAR(255) COMMENT '番地以下' AFTER city",
                "address_detail"
            ))
        
        if not alter_queries:
            logger.info("すべてのカラムは既に存在しています。")
            return
        
        logger.info(f"{len(alter_queries)}個のカラムを追加します...")
        
        for query, column_name in alter_queries:
            try:
                await db_connection.execute_update(query)
                logger.info(f"✓ カラム '{column_name}' を追加しました")
            except Exception as e:
                error_msg = str(e)
                # カラムが既に存在する場合のエラーは無視
                if "Duplicate column name" not in error_msg and "already exists" not in error_msg.lower():
                    logger.error(f"✗ カラム '{column_name}' の追加に失敗しました: {error_msg}")
                    raise
                else:
                    logger.warning(f"カラム '{column_name}' は既に存在しています")
        
        # インデックスの存在確認と追加
        check_indexes_query = """
            SELECT INDEX_NAME 
            FROM information_schema.STATISTICS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'purchase_achievements'
            AND INDEX_NAME IN ('idx_prefecture', 'idx_city')
        """
        
        logger.info("既存インデックスを確認中...")
        existing_indexes_result = await db_connection.execute_query(check_indexes_query)
        
        existing_indexes = set()
        if existing_indexes_result:
            for row in existing_indexes_result:
                if isinstance(row, dict):
                    index_name = row.get("INDEX_NAME") or row.get("index_name")
                else:
                    index_name = row[0] if len(row) > 0 else None
                if index_name:
                    existing_indexes.add(index_name)
        
        logger.info(f"既存インデックス: {existing_indexes}")
        
        # インデックスを追加
        if "idx_prefecture" not in existing_indexes:
            try:
                await db_connection.execute_update("CREATE INDEX idx_prefecture ON purchase_achievements (prefecture)")
                logger.info("✓ インデックス 'idx_prefecture' を追加しました")
            except Exception as e:
                error_msg = str(e)
                if "Duplicate key name" not in error_msg and "already exists" not in error_msg.lower():
                    logger.error(f"✗ インデックス 'idx_prefecture' の追加に失敗しました: {error_msg}")
                else:
                    logger.warning("インデックス 'idx_prefecture' は既に存在しています")
        else:
            logger.info("インデックス 'idx_prefecture' は既に存在します")
        
        if "idx_city" not in existing_indexes:
            try:
                await db_connection.execute_update("CREATE INDEX idx_city ON purchase_achievements (city)")
                logger.info("✓ インデックス 'idx_city' を追加しました")
            except Exception as e:
                error_msg = str(e)
                if "Duplicate key name" not in error_msg and "already exists" not in error_msg.lower():
                    logger.error(f"✗ インデックス 'idx_city' の追加に失敗しました: {error_msg}")
                else:
                    logger.warning("インデックス 'idx_city' は既に存在しています")
        else:
            logger.info("インデックス 'idx_city' は既に存在します")
        
        logger.info("カラム追加処理が完了しました。")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {str(e)}")
        logger.exception(e)
        raise
    finally:
        # データベース接続プールを閉じる
        await db_connection.close_pool()
        logger.info("データベース接続プールを閉じました")

if __name__ == "__main__":
    asyncio.run(check_and_add_columns())

