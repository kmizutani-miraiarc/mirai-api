import asyncio
import httpx
import logging
from typing import Dict, Any
from .config import Config

# ロガー設定
logger = logging.getLogger(__name__)

class HubSpotBaseClient:
    """HubSpot API基底クライアントクラス"""
    
    def __init__(self):
        self.api_key = Config.HUBSPOT_API_KEY
        self.base_url = Config.HUBSPOT_BASE_URL
        self.headers = Config.get_headers()
        self.hubspot_id = Config.HUBSPOT_ID
        self.timeout = Config.API_TIMEOUT
        
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """HubSpot APIへのリクエストを実行"""
        url = f"{self.base_url}{endpoint}"
        
        # タイムアウト設定
        timeout = kwargs.pop('timeout', self.timeout)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    **kwargs
                )
                response.raise_for_status()
                
                # DELETE操作や204 No Contentの場合は空のレスポンスを返す
                if method == "DELETE" or response.status_code == 204:
                    return {"success": True}
                
                # レスポンスが空の場合は空の辞書を返す
                if not response.content:
                    return {"success": True}
                
                # httpxのresponse.json()は既に最適化されており、通常は高速
                # 大きなJSONレスポンスの場合でも、同期的に実行しても問題ない
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.TimeoutException as e:
                logger.error(f"HubSpot API timeout: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"HubSpot API request failed: {str(e)}")
                raise
