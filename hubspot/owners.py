import httpx
import logging
import asyncio
from typing import Dict, Any, List, Optional
from .client import HubSpotBaseClient

# ロガー設定
logger = logging.getLogger(__name__)

class HubSpotOwnersClient(HubSpotBaseClient):
    """HubSpot Owner APIクライアントクラス"""
    
    async def get_owners(self) -> List[Dict[str, Any]]:
        """担当者一覧を取得"""
        try:
            data = await self._make_request("GET", "/crm/v3/owners")
            return data.get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get owners: {str(e)}")
            return []
    
    async def get_owner_by_id(self, owner_id: str) -> Optional[Dict[str, Any]]:
        """IDで担当者を取得（レート制限対策付き）"""
        max_retries = 3
        retry_delay = 1.0  # 1秒から開始
        
        for attempt in range(max_retries):
            try:
                data = await self._make_request("GET", f"/crm/v3/owners/{owner_id}")
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # レート制限
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit for owner {owner_id}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # 指数バックオフ
                        continue
                    else:
                        logger.error(f"Rate limit exceeded for owner {owner_id} after {max_retries} attempts")
                        return None
                elif e.response.status_code == 404:
                    # 404エラーは無視（削除された担当者など、正常なケース）
                    # ログレベルをDEBUGに変更（必要に応じてINFOに戻す）
                    logger.debug(f"Owner {owner_id} not found (404)")
                    return None
                else:
                    logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
                    return None
            except Exception as e:
                logger.error(f"Failed to get owner by ID {owner_id}: {str(e)}")
                return None
        
        return None
    
    async def create_owner(self, owner_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """新しい担当者を作成"""
        try:
            data = await self._make_request("POST", "/crm/v3/owners", json=owner_data)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create owner: {str(e)}")
            return None
    
    async def update_owner(self, owner_id: str, owner_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """担当者情報を更新"""
        try:
            data = await self._make_request("PATCH", f"/crm/v3/owners/{owner_id}", json=owner_data)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Owner with ID {owner_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update owner {owner_id}: {str(e)}")
            return None
    
    async def delete_owner(self, owner_id: str) -> bool:
        """担当者を削除"""
        try:
            result = await self._make_request("DELETE", f"/crm/v3/owners/{owner_id}")
            return result.get("success", True)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Owner with ID {owner_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete owner {owner_id}: {str(e)}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """HubSpot API接続テスト（Owner API使用）"""
        try:
            # 簡単なAPI呼び出しで接続テスト
            data = await self._make_request("GET", "/crm/v3/owners", params={"limit": 1})
            return {
                "status": "healthy",
                "message": "HubSpot API connection successful",
                "api_version": "v3"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"HubSpot API connection failed: {str(e)}",
                "api_version": "v3"
            }
