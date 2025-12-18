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
                "hs_lastmodifieddate",
                "introduction_datetime",
                "deal_disclosure_date",
                "deal_survey_review_date",
                "purchase_date",
                "deal_probability_b_date",
                "deal_probability_a_date",
                "deal_farewell_date",
                "deal_lost_date",
                "contract_date",
                "settlement_date",
                "research_purchase_price",
                "sales_sales_price"
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
    
    async def get_deal_contact_ids(self, deal_id: str, limit: int = 100) -> List[str]:
        """取引に関連づけられたコンタクトID一覧を取得（詳細情報は取得しない）"""
        contact_ids: List[str] = []
        after: Optional[str] = None
        
        try:
            while True:
                params = {"limit": limit}
                if after:
                    params["after"] = after
                
                result = await self._make_request(
                    "GET",
                    f"/crm/v4/objects/deals/{deal_id}/associations/contacts",
                    params=params
                )
                
                batch_ids = [
                    assoc.get("toObjectId")
                    for assoc in result.get("results", [])
                    if assoc.get("toObjectId")
                ]
                contact_ids.extend(batch_ids)
                
                paging = result.get("paging", {})
                next_after = paging.get("next", {}).get("after")
                if next_after:
                    after = str(next_after)
                else:
                    break
            
            logger.debug(f"Retrieved {len(contact_ids)} contact ids for deal {deal_id}")
            return contact_ids
        
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to get contact ids for deal {deal_id}: {e.response.status_code} - {e.response.text}")
            return contact_ids
        except Exception as e:
            logger.warning(f"Failed to get contact ids for deal {deal_id}: {str(e)}")
            return contact_ids

    async def get_deal_associations(self, deal_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """取引に関連づけられた会社、コンタクト、物件を取得（レート制限対策付き）"""
        associations = {
            "companies": [],
            "contacts": [],
            "2-39155607": []  # 物件（bukken）のカスタムオブジェクトID
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
            
            # 物件の関連を取得
            try:
                bukken_result = await self._make_request(
                    "GET", 
                    f"/crm/v4/objects/deals/{deal_id}/associations/2-39155607",
                    params={"limit": 100}
                )
                bukken_ids = [assoc.get("toObjectId") for assoc in bukken_result.get("results", [])]
                logger.debug(f"Found {len(bukken_ids)} bukken associations for deal {deal_id}")
                
                # 各物件の詳細情報を取得（レート制限対策付き）
                for i, bukken_id in enumerate(bukken_ids):
                    try:
                        # レート制限対策: 複数リクエストの間に少し待機
                        if i > 0 and i % 5 == 0:
                            await asyncio.sleep(0.1)  # 100ms待機
                            
                        bukken = await self._make_request("GET", f"/crm/v3/objects/2-39155607/{bukken_id}")
                        associations["2-39155607"].append(bukken)
                        logger.debug(f"Successfully retrieved bukken {bukken_id}")
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 429:  # レート制限
                            logger.warning(f"Rate limit hit for bukken {bukken_id}, waiting...")
                            await asyncio.sleep(1.0)  # 1秒待機してリトライ
                            try:
                                bukken = await self._make_request("GET", f"/crm/v3/objects/2-39155607/{bukken_id}")
                                associations["2-39155607"].append(bukken)
                            except Exception as retry_e:
                                logger.warning(f"Failed to get bukken {bukken_id} after retry: {str(retry_e)}")
                        else:
                            logger.warning(f"Failed to get bukken {bukken_id}: {e.response.status_code} - {e.response.text}")
                    except Exception as e:
                        logger.warning(f"Failed to get bukken {bukken_id}: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to get bukken associations for deal {deal_id}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Failed to get associations for deal {deal_id}: {str(e)}")
        
        logger.debug(f"Associations summary for deal {deal_id}: {len(associations['companies'])} companies, {len(associations['contacts'])} contacts, {len(associations['2-39155607'])} bukken")
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

    async def search_deals_with_associations(self, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """取引を検索（関連会社・コンタクト情報も含む）"""
        try:
            # 基本的な検索を実行
            search_result = await self.search_deals(search_criteria)
            
            # search_resultは辞書形式 {"results": [...], "paging": {...}}
            deals = search_result.get("results", [])
            paging = search_result.get("paging", {})
            
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
                    deal["associations"] = {"companies": [], "contacts": [], "2-39155607": []}
                    deals_with_associations.append(deal)
            
            # 元の形式と同じように辞書で返す
            return {
                "results": deals_with_associations,
                "paging": paging
            }
        except Exception as e:
            logger.error(f"Failed to search deals with associations: {str(e)}")
            return {"results": [], "paging": {}}
    
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

    async def get_pipeline_history(self, pipeline_id: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """パイプラインの変更履歴を取得（mirai-baseのgetPipelineHistoryと同等）"""
        if options is None:
            options = {}
            
        try:
            logger.info(f"Getting pipeline history for pipeline {pipeline_id}")
            
            # パイプライン情報を取得
            pipeline_stages = await self.get_pipeline_stages(pipeline_id)
            if not pipeline_stages:
                logger.error(f"Pipeline {pipeline_id} not found")
                return {"success": False, "error": "Pipeline not found"}
            
            # パイプライン情報を取得（別のAPIエンドポイントを使用）
            try:
                pipeline_info = await self._make_request("GET", f"/crm/v3/pipelines/deals/{pipeline_id}")
            except Exception as e:
                logger.warning(f"Failed to get pipeline info: {str(e)}")
                pipeline_info = {"id": pipeline_id, "label": f"Pipeline {pipeline_id}", "displayOrder": 0}
            
            # 全取引を取得（履歴付き）
            deals = await self.get_all_deals_with_history(pipeline_id, options)
            
            # 各取引の詳細情報を処理
            deals_with_history = []
            for deal in deals:
                try:
                    # 担当者名を取得
                    owner_name = "-"
                    if deal.get("properties", {}).get("hubspot_owner_id"):
                        try:
                            # 担当者情報を取得（簡易版）
                            owner_id = deal["properties"]["hubspot_owner_id"]
                            # ここでは簡易的にIDを表示（実際の実装では担当者APIを呼び出す）
                            owner_name = f"Owner {owner_id}"
                        except Exception as e:
                            logger.warning(f"Failed to get owner name for {deal.get('id')}: {str(e)}")
                    
                    # ステージ名を取得
                    stage_id = deal.get("properties", {}).get("dealstage")
                    stage_label = self._get_stage_label(stage_id, pipeline_stages)
                    
                    deal_info = {
                        "id": deal.get("id"),
                        "name": deal.get("properties", {}).get("dealname", ""),
                        "stage": stage_label,
                        "stageId": stage_id,
                        "amount": deal.get("properties", {}).get("amount"),
                        "owner": owner_name,
                        "companyName": deal.get("properties", {}).get("company_name", "-"),
                        "contactName": deal.get("properties", {}).get("contact_name", "-"),
                        "createdDate": deal.get("properties", {}).get("createdate"),
                        "lastModifiedDate": deal.get("properties", {}).get("hs_lastmodifieddate"),
                        "hubspot_url": f"https://app-na2.hubspot.com/contacts/{self._get_hubspot_id()}/deal/{deal.get('id')}",
                        "propertiesWithHistory": deal.get("propertiesWithHistory", {}),
                        "pipeline": deal.get("properties", {}).get("pipeline")
                    }
                    deals_with_history.append(deal_info)
                    
                except Exception as e:
                    logger.error(f"Failed to process deal {deal.get('id')}: {str(e)}")
                    continue
            
            return {
                "success": True,
                "pipeline": {
                    "id": pipeline_id,
                    "label": pipeline_info.get("label", ""),
                    "displayOrder": pipeline_info.get("displayOrder", 0)
                },
                "deals": deals_with_history,
                "total": len(deals_with_history)
            }
            
        except Exception as e:
            logger.error(f"Failed to get pipeline history for {pipeline_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_all_deals_with_history(self, pipeline_id: str, options: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """指定されたパイプラインの全取引を取得（履歴付き）"""
        if options is None:
            options = {}
            
        try:
            logger.info(f"Getting all deals with history for pipeline {pipeline_id}")
            deals = []
            after = None
            
            # フィルター条件を構築
            filters = [
                {
                    "propertyName": "pipeline",
                    "operator": "EQ",
                    "value": pipeline_id
                }
            ]
            
            if options.get("stage"):
                filters.append({
                    "propertyName": "dealstage",
                    "operator": "EQ",
                    "value": options["stage"]
                })
            
            if options.get("owner"):
                filters.append({
                    "propertyName": "hubspot_owner_id",
                    "operator": "EQ",
                    "value": options["owner"]
                })
            
            if options.get("keyword"):
                filters.append({
                    "propertyName": "dealname",
                    "operator": "CONTAINS_TOKEN",
                    "value": options["keyword"]
                })
            
            # 年月のfrom-to条件を追加
            if options.get("fromDate"):
                filters.append({
                    "propertyName": "createdate",
                    "operator": "GTE",
                    "value": options["fromDate"]
                })
            
            if options.get("toDate"):
                filters.append({
                    "propertyName": "createdate",
                    "operator": "LTE",
                    "value": options["toDate"]
                })
            
            # ページネーションで全取引を取得
            while True:
                search_data = {
                    "filterGroups": [{"filters": filters}],
                    "properties": [
                        "dealname",
                        "dealstage",
                        "amount",
                        "hubspot_owner_id",
                        "createdate",
                        "pipeline",
                        "company_name",
                        "contact_name",
                        "hs_lastmodifieddate",
                        "introduction_datetime",
                        "deal_disclosure_date",
                        "deal_survey_review_date",
                        "purchase_date",
                        "deal_probability_b_date",
                        "deal_probability_a_date",
                        "deal_farewell_date",
                        "deal_lost_date",
                        "contract_date",
                        "settlement_date"
                    ],
                    "propertiesWithHistory": ["dealstage"],
                    "limit": options.get("limit", 100)
                }
                
                if after:
                    search_data["after"] = after
                
                response = await self._make_request(
                    "POST",
                    "/crm/v3/objects/deals/search",
                    json=search_data
                )
                
                deals.extend(response.get("results", []))
                
                # ページネーションの確認
                paging = response.get("paging", {})
                if not paging.get("next"):
                    break
                after = paging["next"].get("after")
            
            logger.info(f"Found {len(deals)} deals for pipeline {pipeline_id}")
            
            # 各取引の履歴を個別に取得
            deals_with_history = []
            for deal in deals:
                try:
                    deal_id = deal.get("id")
                    if not deal_id:
                        continue
                    
                    # 個別に履歴を取得
                    history_response = await self._make_request(
                        "GET",
                        f"/crm/v3/objects/deals/{deal_id}",
                        params={
                            "properties": "dealstage",
                            "propertiesWithHistory": "dealstage"
                        }
                    )
                    
                    # 履歴データを統合
                    deal_with_history = {
                        **deal,
                        "propertiesWithHistory": {
                            "dealstage": {
                                "versions": history_response.get("propertiesWithHistory", {}).get("dealstage", [])
                            }
                        }
                    }
                    
                    deals_with_history.append(deal_with_history)
                    
                except Exception as e:
                    logger.warning(f"Failed to get history for deal {deal.get('id')}: {str(e)}")
                    # 履歴取得に失敗した場合は元のデータを返す
                    deals_with_history.append(deal)
            
            logger.info(f"Retrieved {len(deals_with_history)} deals with history")
            return deals_with_history
            
        except Exception as e:
            logger.error(f"Failed to get all deals with history for pipeline {pipeline_id}: {str(e)}")
            return []

    def _get_stage_label(self, stage_id: str, pipeline_stages: List[Dict[str, Any]]) -> str:
        """ステージIDからステージラベルを取得"""
        if not stage_id or not pipeline_stages:
            return "Unknown"
        
        for stage in pipeline_stages:
            if stage.get("id") == stage_id:
                return stage.get("label", "Unknown")
        
        return "Unknown"

    def _get_hubspot_id(self) -> str:
        """HubSpot IDを取得（環境変数から）"""
        import os
        return os.getenv("HUBSPOT_ID", "unknown")