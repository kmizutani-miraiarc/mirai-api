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
                
                # 大きなJSONレスポンスのパースを別スレッドで実行してイベントループをブロックしないようにする
                try:
                    return await asyncio.to_thread(response.json)
                except AttributeError:
                    # Python 3.9未満の場合は通常のjson()を使用
                    import json
                    return await asyncio.to_thread(json.loads, response.content)
            except httpx.HTTPStatusError as e:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.TimeoutException as e:
                logger.error(f"HubSpot API timeout: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"HubSpot API request failed: {str(e)}")
                raise
