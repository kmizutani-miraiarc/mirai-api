import aiomysql
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from hubspot.config import Config

# ロガー設定
logger = logging.getLogger(__name__)

class DatabaseConnection:
    """MySQLデータベース接続管理クラス"""
    
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
    
    async def create_pool(self) -> None:
        """データベース接続プールを作成"""
        try:
            config = Config.get_mysql_config()
            self.pool = await aiomysql.create_pool(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                db=config["db"],
                charset=config["charset"],
                minsize=1,
                maxsize=10,
                autocommit=True
            )
            logger.info("データベース接続プールを作成しました")
        except Exception as e:
            logger.error(f"データベース接続プールの作成に失敗しました: {str(e)}")
            raise
    
    async def close_pool(self) -> None:
        """データベース接続プールを閉じる"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("データベース接続プールを閉じました")
    
    @asynccontextmanager
    async def get_connection(self):
        """データベース接続を取得（コンテキストマネージャー）"""
        if not self.pool:
            await self.create_pool()
        
        conn = None
        try:
            conn = await self.pool.acquire()
            yield conn
        finally:
            if conn:
                self.pool.release(conn)
    
    async def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """SELECTクエリを実行して結果を返す"""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                result = await cursor.fetchall()
                return result
    
    async def execute_update(self, query: str, params: tuple = None) -> int:
        """INSERT/UPDATE/DELETEクエリを実行して影響を受けた行数を返す"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.rowcount
    
    async def execute_insert(self, query: str, params: tuple = None) -> int:
        """INSERTクエリを実行して挿入されたIDを返す"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.lastrowid
    
    async def test_connection(self) -> bool:
        """データベース接続をテスト"""
        try:
            result = await self.execute_query("SELECT 1 as test")
            return len(result) > 0 and result[0]["test"] == 1
        except Exception as e:
            logger.error(f"データベース接続テストに失敗しました: {str(e)}")
            return False

# グローバルなデータベース接続インスタンス
db_connection = DatabaseConnection()
