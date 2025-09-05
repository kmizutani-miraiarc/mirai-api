import httpx
import logging
from typing import Dict, Any, List, Optional
from .client import HubSpotBaseClient

# ロガー設定
logger = logging.getLogger(__name__)

class HubSpotDealsClient(HubSpotBaseClient):
    """HubSpot取引APIクライアントクラス"""
    
    async def get_deals(self, limit: int = 100, after: Optional[str] = None) -> List[Dict[str, Any]]:
        """取引一覧を取得"""
        try:
            params = {"limit": limit}
            if after:
                params["after"] = after
            
            result = await self._make_request("GET", "/crm/v3/objects/deals", params=params)
            return result.get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get deals: {str(e)}")
            return []
    
    async def get_deal_by_id(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """IDで取引を取得"""
        try:
            result = await self._make_request("GET", f"/crm/v3/objects/deals/{deal_id}")
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Deal with ID {deal_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get deal {deal_id}: {str(e)}")
            return None
    
    async def create_deal(self, deal_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """取引を作成"""
        try:
            result = await self._make_request("POST", "/crm/v3/objects/deals", json=deal_data)
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 400:
                logger.error(f"Invalid deal data: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create deal: {str(e)}")
            return None
    
    async def update_deal(self, deal_id: str, deal_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """取引を更新"""
        try:
            result = await self._make_request("PATCH", f"/crm/v3/objects/deals/{deal_id}", json=deal_data)
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Deal with ID {deal_id} not found")
            elif e.response.status_code == 400:
                logger.error(f"Invalid deal data: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update deal {deal_id}: {str(e)}")
            return None
    
    async def delete_deal(self, deal_id: str) -> bool:
        """取引を削除"""
        try:
            result = await self._make_request("DELETE", f"/crm/v3/objects/deals/{deal_id}")
            return result.get("success", True)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Deal with ID {deal_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete deal {deal_id}: {str(e)}")
            return False
    
    async def search_deals(self, search_criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """取引を検索（パイプライン、取引名、ステージ、取引担当者で検索）"""
        try:
            # 空文字列のパラメータをNoneに変換
            if search_criteria.get("query") == "":
                search_criteria["query"] = None
            if search_criteria.get("after") == "":
                search_criteria["after"] = None
            
            logger.info(f"Searching deals with criteria: {search_criteria}")
            result = await self._make_request("POST", "/crm/v3/objects/deals/search", json=search_criteria)
            logger.info(f"Search result: {result}")
            results = result.get("results", [])
            logger.info(f"Found {len(results)} results")
            return results
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 400:
                logger.error(f"Invalid search criteria: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to search deals: {str(e)}")
            return []
    
    async def get_pipelines(self) -> List[Dict[str, Any]]:
        """パイプライン一覧を取得"""
        try:
            result = await self._make_request("GET", "/crm/v3/pipelines/deals")
            return result.get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get pipelines: {str(e)}")
            return []
    
    async def get_pipeline_stages(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """パイプラインに紐づくステージ一覧を取得"""
        try:
            result = await self._make_request("GET", f"/crm/v3/pipelines/deals/{pipeline_id}")
            return result.get("stages", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Pipeline with ID {pipeline_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get pipeline stages for {pipeline_id}: {str(e)}")
            return []
    
    async def get_deals_by_bukken(self, bukken_id: str) -> List[Dict[str, Any]]:
        """物件に関連づけられた取引を取得"""
        try:
            # 物件と取引の関連を検索
            search_criteria = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "associated_bukken",
                                "operator": "EQ",
                                "value": bukken_id
                            }
                        ]
                    }
                ],
                "properties": [
                    "dealname",
                    "pipeline",
                    "dealstage",
                    "hubspot_owner_id",
                    "amount",
                    "closedate",
                    "createdate",
                    "hs_lastmodifieddate"
                ],
                "limit": 100
            }
            
            logger.info(f"Searching deals for bukken {bukken_id}")
            result = await self._make_request("POST", "/crm/v3/objects/deals/search", json=search_criteria)
            results = result.get("results", [])
            logger.info(f"Found {len(results)} deals for bukken {bukken_id}")
            return results
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 400:
                logger.error(f"Invalid search criteria for bukken {bukken_id}: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get deals for bukken {bukken_id}: {str(e)}")
            return []