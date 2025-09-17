import httpx
import logging
from typing import Dict, Any, List, Optional
from .client import HubSpotBaseClient

# ロガー設定
logger = logging.getLogger(__name__)

class HubSpotBukkenClient(HubSpotBaseClient):
    """HubSpot物件情報カスタムオブジェクトAPIクライアントクラス"""
    
    def __init__(self):
        super().__init__()
        self.object_type = "bukken"  # カスタムオブジェクトの内部名
        self.object_type_id = "2-39155607"  # カスタムオブジェクトのID
    
    async def get_bukken_list(self, limit: int = 100, after: Optional[str] = None) -> List[Dict[str, Any]]:
        """物件情報一覧を取得（物件名、都道府県、市区町村、番地以下のみ）"""
        try:
            # 物件一覧で取得するプロパティを指定
            properties = ["bukken_name", "bukken_state", "bukken_city", "bukken_address"]
            params = {
                "limit": limit,
                "properties": ",".join(properties)
            }
            if after:
                params["after"] = after
            
            result = await self._make_request("GET", f"/crm/v3/objects/{self.object_type_id}", params=params)
            return result.get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get bukken list: {str(e)}")
            return []
    
    async def get_bukken_by_id(self, bukken_id: str) -> Optional[Dict[str, Any]]:
        """IDで物件情報を取得（すべてのプロパティ）"""
        try:
            # まず、カスタムオブジェクトの全プロパティを取得
            all_properties = await self.get_bukken_properties()
            
            # 全プロパティを指定して物件詳細を取得
            if all_properties:
                params = {"properties": ",".join(all_properties)}
                result = await self._make_request("GET", f"/crm/v3/objects/{self.object_type_id}/{bukken_id}", params=params)
            else:
                # プロパティが取得できない場合は、デフォルトで取得
                result = await self._make_request("GET", f"/crm/v3/objects/{self.object_type_id}/{bukken_id}")
            
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Bukken with ID {bukken_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get bukken {bukken_id}: {str(e)}")
            return None
    
    async def create_bukken(self, bukken_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """物件情報を作成"""
        try:
            result = await self._make_request("POST", f"/crm/v3/objects/{self.object_type_id}", json=bukken_data)
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 400:
                logger.error(f"Invalid bukken data: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to create bukken: {str(e)}")
            return None
    
    async def update_bukken(self, bukken_id: str, bukken_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """物件情報を更新"""
        try:
            result = await self._make_request("PATCH", f"/crm/v3/objects/{self.object_type_id}/{bukken_id}", json=bukken_data)
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Bukken with ID {bukken_id} not found")
            elif e.response.status_code == 400:
                logger.error(f"Invalid bukken data: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to update bukken {bukken_id}: {str(e)}")
            return None
    
    async def delete_bukken(self, bukken_id: str) -> bool:
        """物件情報を削除"""
        try:
            result = await self._make_request("DELETE", f"/crm/v3/objects/{self.object_type_id}/{bukken_id}")
            return result.get("success", True)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Bukken with ID {bukken_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete bukken {bukken_id}: {str(e)}")
            return False
    
    async def get_property_options(self, property_name: str) -> Optional[List[Dict[str, Any]]]:
        """HubSpotプロパティの選択肢を取得"""
        try:
            # プロパティの詳細情報を取得
            result = await self._make_request("GET", f"/crm/v3/properties/{self.object_type_id}/{property_name}")
            
            if result and "options" in result:
                # 選択肢を整形して返す
                options = []
                for option in result["options"]:
                    options.append({
                        "label": option.get("label", ""),
                        "value": option.get("value", ""),
                        "description": option.get("description", ""),
                        "displayOrder": option.get("displayOrder", 0)
                    })
                
                # displayOrderでソート
                options.sort(key=lambda x: x["displayOrder"])
                return options
            else:
                logger.warning(f"Property {property_name} has no options or is not a select property")
                return []
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Property {property_name} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get property options for {property_name}: {str(e)}")
            return None
    
    async def search_bukken(self, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """物件情報を検索"""
        try:
            # 空文字列のqueryパラメータをNoneに変換
            if search_criteria.get("query") == "":
                search_criteria["query"] = None
            
            # 空文字列のafterパラメータをNoneに変換
            if search_criteria.get("after") == "":
                search_criteria["after"] = None
            
            logger.info(f"Searching bukken with criteria: {search_criteria}")
            result = await self._make_request("POST", f"/crm/v3/objects/{self.object_type_id}/search", json=search_criteria)
            logger.info(f"Search result: {result}")
            results = result.get("results", [])
            paging = result.get("paging", {})
            logger.info(f"Found {len(results)} results")
            # paging情報も含めて返す
            return {
                "results": results,
                "paging": paging
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 400:
                logger.error(f"Invalid search criteria: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return {"results": [], "paging": {}}
        except Exception as e:
            logger.error(f"Failed to search bukken: {str(e)}")
            return {"results": [], "paging": {}}
    
    async def get_bukken_schema(self) -> Optional[Dict[str, Any]]:
        """物件情報カスタムオブジェクトのスキーマを取得"""
        try:
            # HubSpotのカスタムオブジェクトスキーマAPIの正しいエンドポイント
            result = await self._make_request("GET", f"/crm/v3/schemas/{self.object_type_id}")
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Custom object schema for {self.object_type_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Failed to get bukken schema: {str(e)}")
            return None
    
    async def get_bukken_properties(self) -> List[str]:
        """物件情報カスタムオブジェクトのプロパティ一覧を取得"""
        try:
            result = await self._make_request("GET", f"/crm/v3/properties/{self.object_type_id}")
            properties = result.get("results", [])
            return [prop.get("name") for prop in properties if prop.get("name")]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Custom object properties for {self.object_type_id} not found")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get bukken properties: {str(e)}")
            return []
