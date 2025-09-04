import httpx
import logging
from typing import Dict, Any, Optional
from .client import HubSpotBaseClient

# ロガー設定
logger = logging.getLogger(__name__)

class HubSpotCompaniesClient(HubSpotBaseClient):
    """HubSpot Companies APIクライアントクラス"""
    
    async def get_companies(self, limit: int = 100, after: Optional[str] = None) -> Dict[str, Any]:
        """会社一覧を取得"""
        try:
            params = {"limit": limit}
            if after:
                params["after"] = after
                
            data = await self._make_request("GET", "/crm/v3/objects/companies", params=params)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return {"results": [], "paging": {}}
        except Exception as e:
            logger.error(f"Failed to get companies: {str(e)}")
            return {"results": [], "paging": {}}
    
    async def get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        """IDで会社を取得"""
        try:
            data = await self._make_request("GET", f"/crm/v3/objects/companies/{company_id}")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get company by ID {company_id}: {str(e)}")
            return None
    
    async def create_company(self, company_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """新しい会社を作成"""
        try:
            data = await self._make_request("POST", "/crm/v3/objects/companies", json=company_data)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create company: {str(e)}")
            return None
    
    async def update_company(self, company_id: str, company_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """会社情報を更新"""
        try:
            data = await self._make_request("PATCH", f"/crm/v3/objects/companies/{company_id}", json=company_data)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Company with ID {company_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update company {company_id}: {str(e)}")
            return None
    
    async def delete_company(self, company_id: str) -> bool:
        """会社を削除"""
        try:
            result = await self._make_request("DELETE", f"/crm/v3/objects/companies/{company_id}")
            return result.get("success", True)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Company with ID {company_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete company {company_id}: {str(e)}")
            return False
