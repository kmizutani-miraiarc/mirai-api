import httpx
import logging
from typing import Dict, Any, Optional, List
from .client import HubSpotBaseClient

# ロガー設定
logger = logging.getLogger(__name__)

class HubSpotContactsClient(HubSpotBaseClient):
    """HubSpot Contacts APIクライアントクラス"""
    
    async def get_contacts(self, limit: int = 100, after: Optional[str] = None, properties: Optional[list] = None) -> Dict[str, Any]:
        """コンタクト一覧を取得"""
        try:
            params = {"limit": limit}
            if after:
                params["after"] = after
            
            # 必要なプロパティを指定
            if properties:
                params["properties"] = ",".join(properties)
            else:
                # デフォルトで必要なプロパティを指定
                params["properties"] = ",".join([
                    "firstname",
                    "lastname",
                    "email",
                    "phone",
                    "hubspot_owner_id",
                    "contractor_industry",
                    "contractor_property_type",
                    "contractor_area",
                    "contractor_area_category",
                    "contractor_gross2",
                    "contractor_buy_or_sell"
                ])
                
            data = await self._make_request("GET", "/crm/v3/objects/contacts", params=params)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return {"results": [], "paging": {}}
        except Exception as e:
            logger.error(f"Failed to get contacts: {str(e)}")
            return {"results": [], "paging": {}}
    
    async def get_contact_by_id(self, contact_id: str, include_associations: bool = False) -> Optional[Dict[str, Any]]:
        """IDでコンタクトを取得"""
        try:
            params = {}
            if include_associations:
                params["associations"] = "companies"
            data = await self._make_request("GET", f"/crm/v3/objects/contacts/{contact_id}", params=params)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get contact by ID {contact_id}: {str(e)}")
            return None
    
    async def create_contact(self, contact_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """新しいコンタクトを作成"""
        try:
            data = await self._make_request("POST", "/crm/v3/objects/contacts", json=contact_data)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create contact: {str(e)}")
            return None
    
    async def update_contact(self, contact_id: str, contact_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """コンタクト情報を更新"""
        try:
            data = await self._make_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", json=contact_data)
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Contact with ID {contact_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update contact {contact_id}: {str(e)}")
            return None
    
    async def delete_contact(self, contact_id: str) -> bool:
        """コンタクトを削除"""
        try:
            result = await self._make_request("DELETE", f"/crm/v3/objects/contacts/{contact_id}")
            return result.get("success", True)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Contact with ID {contact_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete contact {contact_id}: {str(e)}")
            return False
    
    async def get_contact_properties(self) -> List[Dict[str, Any]]:
        """コンタクトの全プロパティ情報を取得"""
        try:
            data = await self._make_request("GET", "/crm/v3/properties/contacts")
            return data.get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get contact properties: {str(e)}")
            return []
    
    async def find_property_by_label(self, label: str) -> Optional[str]:
        """ラベル名からプロパティの内部名を取得"""
        try:
            properties = await self.get_contact_properties()
            for prop in properties:
                prop_label = prop.get("label", "")
                if prop_label == label:
                    return prop.get("name")
            return None
        except Exception as e:
            logger.error(f"Failed to find property by label {label}: {str(e)}")
            return None
    
    async def get_property_options(self, property_name: str) -> Optional[List[Dict[str, Any]]]:
        """プロパティの選択肢（オプション）を取得"""
        try:
            data = await self._make_request("GET", f"/crm/v3/properties/contacts/{property_name}")
            if data and "options" in data:
                return data.get("options", [])
            return []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Property {property_name} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get property options for {property_name}: {str(e)}")
            return None