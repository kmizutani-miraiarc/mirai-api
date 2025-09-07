import asyncio
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
            # 必要なプロパティを指定して取得
            properties = [
                "dealname",
                "dealstage", 
                "amount",
                "hubspot_owner_id",
                "createdate",
                "pipeline",
                "closedate",
                "hs_lastmodifieddate"
            ]
            result = await self._make_request(
                "GET", 
                f"/crm/v3/objects/deals/{deal_id}",
                params={"properties": ",".join(properties)}
            )
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

    async def get_deal_by_id_with_associations(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """IDで取引を取得（関連会社・コンタクト情報も含む）"""
        try:
            logger.debug(f"Getting deal with associations for deal {deal_id}")
            
            # 取引の基本情報を取得
            deal = await self.get_deal_by_id(deal_id)
            if not deal:
                logger.warning(f"Deal {deal_id} not found")
                return None
            
            logger.debug(f"Deal {deal_id} basic info retrieved: {deal.get('properties', {}).get('dealname', 'Unknown')}")
            
            # 関連情報を取得
            try:
                associations = await self.get_deal_associations(deal_id)
                logger.debug(f"Associations retrieved for deal {deal_id}: {len(associations.get('companies', []))} companies, {len(associations.get('contacts', []))} contacts")
            except Exception as assoc_e:
                logger.warning(f"Failed to get associations for deal {deal_id}: {str(assoc_e)}")
                # 関連情報の取得に失敗しても取引情報は返す
                associations = {"companies": [], "contacts": []}
            
            # 取引情報に関連情報を追加
            deal["associations"] = associations
            
            logger.debug(f"Successfully retrieved deal {deal_id} with associations")
            return deal
        except Exception as e:
            logger.error(f"Failed to get deal with associations {deal_id}: {str(e)}")
            return None

    async def get_deal_associations(self, deal_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """取引に関連づけられた会社とコンタクトを取得（レート制限対策付き）"""
        associations = {
            "companies": [],
            "contacts": []
        }
        
        try:
            logger.info(f"Getting associations for deal {deal_id}")
            
            # 会社の関連を取得
            try:
                company_result = await self._make_request(
                    "GET", 
                    f"/crm/v4/objects/deals/{deal_id}/associations/companies",
                    params={"limit": 100}
                )
                company_ids = [assoc.get("toObjectId") for assoc in company_result.get("results", [])]
                logger.info(f"Found {len(company_ids)} company associations for deal {deal_id}")
                
                # 各会社の詳細情報を取得（レート制限対策付き）
                for i, company_id in enumerate(company_ids):
                    try:
                        # レート制限対策: 複数リクエストの間に少し待機
                        if i > 0 and i % 5 == 0:
                            await asyncio.sleep(0.1)  # 100ms待機
                            
                        company = await self._make_request("GET", f"/crm/v3/objects/companies/{company_id}")
                        associations["companies"].append(company)
                        logger.debug(f"Successfully retrieved company {company_id}")
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:  # レート制限
                            logger.warning(f"Rate limit hit for company {company_id}, waiting...")
                            await asyncio.sleep(1.0)  # 1秒待機してリトライ
                            try:
                                company = await self._make_request("GET", f"/crm/v3/objects/companies/{company_id}")
                                associations["companies"].append(company)
                            except Exception as retry_e:
                                logger.warning(f"Failed to get company {company_id} after retry: {str(retry_e)}")
                        else:
                            logger.warning(f"Failed to get company {company_id}: {e.response.status_code} - {e.response.text}")
                    except Exception as e:
                        logger.warning(f"Failed to get company {company_id}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to get company associations for deal {deal_id}: {str(e)}")
            
            # コンタクトの関連を取得
            try:
                contact_result = await self._make_request(
                    "GET", 
                    f"/crm/v4/objects/deals/{deal_id}/associations/contacts",
                    params={"limit": 100}
                )
                contact_ids = [assoc.get("toObjectId") for assoc in contact_result.get("results", [])]
                logger.info(f"Found {len(contact_ids)} contact associations for deal {deal_id}")
                
                # 各コンタクトの詳細情報を取得（レート制限対策付き）
                for i, contact_id in enumerate(contact_ids):
                    try:
                        # レート制限対策: 複数リクエストの間に少し待機
                        if i > 0 and i % 5 == 0:
                            await asyncio.sleep(0.1)  # 100ms待機
                            
                        contact = await self._make_request("GET", f"/crm/v3/objects/contacts/{contact_id}")
                        associations["contacts"].append(contact)
                        logger.debug(f"Successfully retrieved contact {contact_id}")
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:  # レート制限
                            logger.warning(f"Rate limit hit for contact {contact_id}, waiting...")
                            await asyncio.sleep(1.0)  # 1秒待機してリトライ
                            try:
                                contact = await self._make_request("GET", f"/crm/v3/objects/contacts/{contact_id}")
                                associations["contacts"].append(contact)
                            except Exception as retry_e:
                                logger.warning(f"Failed to get contact {contact_id} after retry: {str(retry_e)}")
                        else:
                            logger.warning(f"Failed to get contact {contact_id}: {e.response.status_code} - {e.response.text}")
                    except Exception as e:
                        logger.warning(f"Failed to get contact {contact_id}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to get contact associations for deal {deal_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Failed to get associations for deal {deal_id}: {str(e)}")
        
        logger.info(f"Associations summary for deal {deal_id}: {len(associations['companies'])} companies, {len(associations['contacts'])} contacts")
        return associations
    
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
            
            # afterパラメータを文字列として確実に処理
            if search_criteria.get("after") is not None:
                search_criteria["after"] = str(search_criteria["after"])
            
            logger.info(f"Searching deals with criteria: {search_criteria}")
            result = await self._make_request("POST", "/crm/v3/objects/deals/search", json=search_criteria)
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
            return []
        except Exception as e:
            logger.error(f"Failed to search deals: {str(e)}")
            return []

    async def search_deals_with_associations(self, search_criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """取引を検索（関連会社・コンタクト情報も含む）"""
        try:
            # 基本的な検索を実行
            deals = await self.search_deals(search_criteria)
            
            # 各取引に関連情報を追加
            deals_with_associations = []
            for deal in deals:
                try:
                    deal_id = deal.get("id")
                    if deal_id:
                        # 関連情報を取得
                        associations = await self.get_deal_associations(deal_id)
                        deal["associations"] = associations
                        deals_with_associations.append(deal)
                except Exception as e:
                    logger.warning(f"Failed to get associations for deal {deal.get('id')}: {str(e)}")
                    # 関連情報の取得に失敗しても取引情報は含める
                    deal["associations"] = {"companies": [], "contacts": []}
                    deals_with_associations.append(deal)
            
            return deals_with_associations
        except Exception as e:
            logger.error(f"Failed to search deals with associations: {str(e)}")
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
            # HubSpotの関連オブジェクトAPIを使用して物件に関連づけられた取引を取得
            # 物件オブジェクトタイプID: 2-39155607 (bukken)
            # 取引オブジェクトタイプID: deals
            
            logger.info(f"Getting associated deals for bukken {bukken_id}")
            result = await self._make_request(
                "GET", 
                f"/crm/v4/objects/2-39155607/{bukken_id}/associations/deals",
                params={"limit": 100}
            )
            
            # 関連オブジェクトのIDを取得
            associations = result.get("results", [])
            deal_ids = [assoc.get("toObjectId") for assoc in associations if assoc.get("toObjectId")]
            
            if not deal_ids:
                logger.info(f"No deals associated with bukken {bukken_id}")
                return []
            
            logger.info(f"Found {len(deal_ids)} deal associations for bukken {bukken_id}")
            
            # 各取引の詳細情報を取得（関連情報も含む）
            # レート制限対策のため、バッチサイズを小さくして並列処理を制限
            deals = []
            batch_size = 5  # 一度に処理する取引数を制限（10→5に変更）
            
            for i in range(0, len(deal_ids), batch_size):
                batch_deal_ids = deal_ids[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}: deals {i+1}-{min(i+batch_size, len(deal_ids))}")
                
                # バッチ内で並列処理
                batch_tasks = []
                for deal_id in batch_deal_ids:
                    batch_tasks.append(self.get_deal_by_id_with_associations(deal_id))
                
                try:
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    successful_count = 0
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.warning(f"Failed to get deal in batch: {str(result)}")
                        elif result:
                            deals.append(result)
                            successful_count += 1
                    
                    logger.info(f"Batch {i//batch_size + 1} completed: {successful_count}/{len(batch_deal_ids)} deals retrieved")
                    
                    # バッチ間で少し待機（レート制限対策）
                    if i + batch_size < len(deal_ids):
                        await asyncio.sleep(0.5)  # 500ms待機
                            
                except Exception as e:
                    logger.warning(f"Failed to process batch: {str(e)}")
                    continue
            
            logger.info(f"Retrieved {len(deals)} deal details for bukken {bukken_id}")
            return deals
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            elif e.response.status_code == 404:
                logger.error(f"Bukken {bukken_id} not found or no associations")
            elif e.response.status_code == 400:
                logger.error(f"Invalid request for bukken {bukken_id}: {e.response.text}")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get deals for bukken {bukken_id}: {str(e)}")
            return []