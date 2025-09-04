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
    def debug_config(cls) -> Dict[str, Any]:
        """設定のデバッグ情報を返す"""
        return {
            "api_key_set": bool(cls.HUBSPOT_API_KEY and cls.HUBSPOT_API_KEY != "your-hubspot-api-key-here"),
            "api_key_prefix": cls.HUBSPOT_API_KEY[:10] + "..." if cls.HUBSPOT_API_KEY else "Not set",
            "hubspot_id_set": bool(cls.HUBSPOT_ID and cls.HUBSPOT_ID != "your-hubspot-id-here"),
            "hubspot_id": cls.HUBSPOT_ID,
            "base_url": cls.HUBSPOT_BASE_URL
        }
