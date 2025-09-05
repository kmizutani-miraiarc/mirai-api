import secrets
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from database.connection import db_connection

# ロガー設定
logger = logging.getLogger(__name__)

class APIKeyManager:
    """APIキー管理クラス"""
    
    def __init__(self):
        self.db = db_connection
    
    async def create_tables(self) -> None:
        """api_keysテーブルを作成"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_name VARCHAR(255) NOT NULL UNIQUE COMMENT 'サイト名',
            api_key_hash VARCHAR(255) NOT NULL UNIQUE COMMENT 'APIキーのハッシュ値',
            api_key_prefix VARCHAR(20) NOT NULL COMMENT 'APIキーの先頭部分（表示用）',
            description TEXT COMMENT 'APIキーの説明',
            is_active BOOLEAN DEFAULT TRUE COMMENT 'アクティブ状態',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
            last_used_at TIMESTAMP NULL COMMENT '最終使用日時',
            expires_at TIMESTAMP NULL COMMENT '有効期限（NULLの場合は無期限）',
            INDEX idx_site_name (site_name),
            INDEX idx_api_key_hash (api_key_hash),
            INDEX idx_is_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='APIキー管理テーブル'
        """
        
        try:
            await self.db.execute_update(create_table_query)
            logger.info("api_keysテーブルを作成しました")
        except Exception as e:
            logger.error(f"api_keysテーブルの作成に失敗しました: {str(e)}")
            raise
    
    def _generate_api_key(self) -> str:
        """新しいAPIキーを生成"""
        # 32バイトのランダムな文字列を生成し、hexエンコード
        return secrets.token_hex(32)
    
    def _hash_api_key(self, api_key: str) -> str:
        """APIキーをハッシュ化"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def _get_api_key_prefix(self, api_key: str) -> str:
        """APIキーの先頭部分を取得（表示用）"""
        return api_key[:10] + "..."
    
    async def create_api_key(
        self, 
        site_name: str, 
        description: str = None,
        expires_days: int = None
    ) -> Dict[str, Any]:
        """新しいAPIキーを作成"""
        try:
            # 新しいAPIキーを生成
            api_key = self._generate_api_key()
            api_key_hash = self._hash_api_key(api_key)
            api_key_prefix = self._get_api_key_prefix(api_key)
            
            # 有効期限の設定
            expires_at = None
            if expires_days:
                expires_at = datetime.now() + timedelta(days=expires_days)
            
            # データベースに保存
            insert_query = """
            INSERT INTO api_keys (site_name, api_key_hash, api_key_prefix, description, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """
            
            await self.db.execute_insert(
                insert_query, 
                (site_name, api_key_hash, api_key_prefix, description, expires_at)
            )
            
            logger.info(f"APIキーを作成しました: {site_name}")
            
            return {
                "site_name": site_name,
                "api_key": api_key,  # この時だけプレーンテキストで返す
                "api_key_prefix": api_key_prefix,
                "description": description,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"APIキーの作成に失敗しました: {str(e)}")
            raise
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """APIキーを検証"""
        try:
            api_key_hash = self._hash_api_key(api_key)
            
            # データベースから検索
            select_query = """
            SELECT id, site_name, api_key_prefix, description, is_active, 
                   created_at, updated_at, last_used_at, expires_at
            FROM api_keys 
            WHERE api_key_hash = %s AND is_active = TRUE
            """
            
            result = await self.db.execute_query(select_query, (api_key_hash,))
            
            if not result:
                return None
            
            api_key_info = result[0]
            
            # 有効期限チェック
            if api_key_info["expires_at"]:
                expires_at = api_key_info["expires_at"]
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                
                if datetime.now() > expires_at:
                    logger.warning(f"APIキーの有効期限が切れています: {api_key_info['site_name']}")
                    return None
            
            # 最終使用日時を更新
            await self._update_last_used(api_key_info["id"])
            
            return api_key_info
            
        except Exception as e:
            logger.error(f"APIキーの検証に失敗しました: {str(e)}")
            return None
    
    async def _update_last_used(self, api_key_id: int) -> None:
        """最終使用日時を更新"""
        try:
            update_query = """
            UPDATE api_keys 
            SET last_used_at = CURRENT_TIMESTAMP 
            WHERE id = %s
            """
            await self.db.execute_update(update_query, (api_key_id,))
        except Exception as e:
            logger.error(f"最終使用日時の更新に失敗しました: {str(e)}")
    
    async def get_api_keys(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """APIキー一覧を取得"""
        try:
            where_clause = "" if include_inactive else "WHERE is_active = TRUE"
            select_query = f"""
            SELECT id, site_name, api_key_prefix, description, is_active,
                   created_at, updated_at, last_used_at, expires_at
            FROM api_keys 
            {where_clause}
            ORDER BY created_at DESC
            """
            
            result = await self.db.execute_query(select_query)
            return result
            
        except Exception as e:
            logger.error(f"APIキー一覧の取得に失敗しました: {str(e)}")
            raise
    
    async def get_api_key_by_site(self, site_name: str) -> Optional[Dict[str, Any]]:
        """サイト名でAPIキー情報を取得"""
        try:
            select_query = """
            SELECT id, site_name, api_key_prefix, description, is_active,
                   created_at, updated_at, last_used_at, expires_at
            FROM api_keys 
            WHERE site_name = %s
            """
            
            result = await self.db.execute_query(select_query, (site_name,))
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"APIキー情報の取得に失敗しました: {str(e)}")
            raise
    
    async def deactivate_api_key(self, site_name: str) -> bool:
        """APIキーを無効化"""
        try:
            update_query = """
            UPDATE api_keys 
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP 
            WHERE site_name = %s
            """
            
            affected_rows = await self.db.execute_update(update_query, (site_name,))
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"APIキーの無効化に失敗しました: {str(e)}")
            raise
    
    async def activate_api_key(self, site_name: str) -> bool:
        """APIキーを有効化"""
        try:
            update_query = """
            UPDATE api_keys 
            SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP 
            WHERE site_name = %s
            """
            
            affected_rows = await self.db.execute_update(update_query, (site_name,))
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"APIキーの有効化に失敗しました: {str(e)}")
            raise
    
    async def delete_api_key(self, site_name: str) -> bool:
        """APIキーを削除"""
        try:
            delete_query = "DELETE FROM api_keys WHERE site_name = %s"
            affected_rows = await self.db.execute_update(delete_query, (site_name,))
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"APIキーの削除に失敗しました: {str(e)}")
            raise

# グローバルなAPIキー管理インスタンス
api_key_manager = APIKeyManager()
