import logging
from typing import Optional, Dict, Any
from database.connection import db_connection

# ロガー設定
logger = logging.getLogger(__name__)


class GmailCredentialsManager:
    """Gmail認証情報管理クラス"""
    
    def __init__(self):
        self.db = db_connection
    
    async def create_tables(self) -> None:
        """user_gmail_credentialsテーブルを作成"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS user_gmail_credentials (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL COMMENT 'ユーザーID（usersテーブルへの外部キー）',
            email VARCHAR(255) NOT NULL COMMENT 'メールアドレス',
            gmail_client_id VARCHAR(500) NOT NULL COMMENT 'Gmail Client ID',
            gmail_client_secret VARCHAR(500) NOT NULL COMMENT 'Gmail Client Secret',
            gmail_refresh_token TEXT NOT NULL COMMENT 'Gmail Refresh Token',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE KEY uk_user_id (user_id),
            INDEX idx_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Gmail認証情報テーブル'
        """
        
        try:
            await self.db.execute_update(create_table_query)
            logger.info("user_gmail_credentialsテーブルを作成しました")
        except Exception as e:
            logger.error(f"user_gmail_credentialsテーブルの作成に失敗しました: {str(e)}")
            # 外部キー制約エラーの場合は無視（usersテーブルが存在しない可能性）
            if "FOREIGN KEY" not in str(e):
                raise
    
    async def get_credentials_by_user_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """ユーザーIDからGmail認証情報を取得"""
        try:
            select_query = """
            SELECT user_id, email, gmail_client_id, gmail_client_secret, gmail_refresh_token
            FROM user_gmail_credentials
            WHERE user_id = %s
            """
            
            result = await self.db.execute_query(select_query, (user_id,))
            
            if not result:
                return None
            
            return {
                "user_id": result[0]["user_id"],
                "email": result[0]["email"],
                "gmail_client_id": result[0]["gmail_client_id"],
                "gmail_client_secret": result[0]["gmail_client_secret"],
                "gmail_refresh_token": result[0]["gmail_refresh_token"]
            }
            
        except Exception as e:
            logger.error(f"Gmail認証情報の取得に失敗しました: {str(e)}")
            return None
    
    async def save_credentials(
        self,
        user_id: int,
        email: str,
        gmail_client_id: str,
        gmail_client_secret: str,
        gmail_refresh_token: str
    ) -> bool:
        """Gmail認証情報を保存または更新"""
        try:
            # 既存の認証情報があるか確認
            existing = await self.get_credentials_by_user_id(user_id)
            
            if existing:
                # 更新
                update_query = """
                UPDATE user_gmail_credentials
                SET email = %s,
                    gmail_client_id = %s,
                    gmail_client_secret = %s,
                    gmail_refresh_token = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                """
                await self.db.execute_update(
                    update_query,
                    (email, gmail_client_id, gmail_client_secret, gmail_refresh_token, user_id)
                )
                logger.info(f"Gmail認証情報を更新しました: user_id={user_id}, email={email}")
            else:
                # 新規作成
                insert_query = """
                INSERT INTO user_gmail_credentials
                (user_id, email, gmail_client_id, gmail_client_secret, gmail_refresh_token)
                VALUES (%s, %s, %s, %s, %s)
                """
                await self.db.execute_insert(
                    insert_query,
                    (user_id, email, gmail_client_id, gmail_client_secret, gmail_refresh_token)
                )
                logger.info(f"Gmail認証情報を保存しました: user_id={user_id}, email={email}")
            
            return True
            
        except Exception as e:
            logger.error(f"Gmail認証情報の保存に失敗しました: {str(e)}")
            return False
    
    async def delete_credentials(self, user_id: int) -> bool:
        """Gmail認証情報を削除"""
        try:
            delete_query = "DELETE FROM user_gmail_credentials WHERE user_id = %s"
            affected_rows = await self.db.execute_update(delete_query, (user_id,))
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"Gmail認証情報の削除に失敗しました: {str(e)}")
            return False


# グローバルなGmail認証情報管理インスタンス
gmail_credentials_manager = GmailCredentialsManager()



