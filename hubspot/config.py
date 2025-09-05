import os
from typing import Dict, Any
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

class Config:
    """HubSpot API設定クラス"""
    
    # HubSpot API設定
    HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY", "your-hubspot-api-key-here")
    HUBSPOT_BASE_URL = "https://api.hubapi.com"
    HUBSPOT_ID = os.getenv("HUBSPOT_ID", "your-hubspot-id-here")
    
    # APIヘッダー設定
    HUBSPOT_HEADERS = {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # API設定
    API_TIMEOUT = 30.0
    MAX_RETRIES = 3
    
    # Mirai API認証設定
    MIRAI_API_KEY = os.getenv("MIRAI_API_KEY", "your-mirai-api-key-here")
    
    # MySQLデータベース設定
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "mirai_base")
    MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")
    
    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        """動的にヘッダーを生成（APIキーが変更された場合に対応）"""
        return {
            "Authorization": f"Bearer {cls.HUBSPOT_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    @classmethod
    def validate_config(cls) -> bool:
        """設定の妥当性をチェック"""
        if cls.HUBSPOT_API_KEY == "your-hubspot-api-key-here":
            return False
        if cls.HUBSPOT_ID == "your-hubspot-id-here":
            return False
        return True
    
    @classmethod
    def validate_mirai_api_key(cls, api_key: str) -> bool:
        """Mirai API認証キーの妥当性をチェック"""
        if not api_key:
            return False
        if cls.MIRAI_API_KEY == "your-mirai-api-key-here":
            return False
        return api_key == cls.MIRAI_API_KEY
    
    @classmethod
    def get_mysql_url(cls) -> str:
        """MySQL接続URLを生成"""
        return f"mysql://{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DATABASE}?charset={cls.MYSQL_CHARSET}"
    
    @classmethod
    def get_mysql_config(cls) -> Dict[str, Any]:
        """MySQL接続設定を辞書で返す"""
        return {
            "host": cls.MYSQL_HOST,
            "port": cls.MYSQL_PORT,
            "user": cls.MYSQL_USER,
            "password": cls.MYSQL_PASSWORD,
            "db": cls.MYSQL_DATABASE,
            "charset": cls.MYSQL_CHARSET
        }
    
    @classmethod
    def debug_config(cls) -> Dict[str, Any]:
        """設定のデバッグ情報を返す"""
        return {
            "api_key_set": bool(cls.HUBSPOT_API_KEY and cls.HUBSPOT_API_KEY != "your-hubspot-api-key-here"),
            "api_key_prefix": cls.HUBSPOT_API_KEY[:10] + "..." if cls.HUBSPOT_API_KEY else "Not set",
            "hubspot_id_set": bool(cls.HUBSPOT_ID and cls.HUBSPOT_ID != "your-hubspot-id-here"),
            "hubspot_id": cls.HUBSPOT_ID,
            "base_url": cls.HUBSPOT_BASE_URL,
            "mirai_api_key_set": bool(cls.MIRAI_API_KEY and cls.MIRAI_API_KEY != "your-mirai-api-key-here"),
            "mirai_api_key_prefix": cls.MIRAI_API_KEY[:10] + "..." if cls.MIRAI_API_KEY else "Not set",
            "mysql_config": {
                "host": cls.MYSQL_HOST,
                "port": cls.MYSQL_PORT,
                "database": cls.MYSQL_DATABASE,
                "user": cls.MYSQL_USER,
                "password_set": bool(cls.MYSQL_PASSWORD)
            }
        }
