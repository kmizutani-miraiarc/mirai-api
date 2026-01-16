import asyncio
import json
import logging
import os
from typing import List, Optional, Dict, Any
from datetime import date
import aiomysql

logger = logging.getLogger(__name__)


class PropertySalesStageSummaryService:
    """物件別販売取引レポート集計サービス"""
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool

    async def get_latest_summary(self) -> Dict[str, Any]:
        """最新の集計データを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 最新の集計日を取得
                query = """
                    SELECT MAX(aggregation_date) as max_date
                    FROM property_sales_stage_summary
                """
                await cursor.execute(query)
                result = await cursor.fetchone()
                
                if not result or not result.get('max_date'):
                    return {
                        "aggregation_date": None,
                        "data": {},
                        "message": "集計データがありません"
                    }
                
                aggregation_date = result['max_date']
                return await self.get_summary_by_date(aggregation_date)

    async def get_summary_by_date(self, aggregation_date: date) -> Dict[str, Any]:
        """指定した集計日のデータを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 物件別ステージ別件数を取得
                query1 = """
                    SELECT property_id, property_name, stage_id, stage_label, count, deal_ids
                    FROM property_sales_stage_summary
                    WHERE aggregation_date = %s
                    ORDER BY property_name, stage_id
                """
                await cursor.execute(query1, (aggregation_date,))
                property_results = await cursor.fetchall()
                
                # 担当者物件別ステージ別件数を取得
                query2 = """
                    SELECT owner_id, owner_name, property_id, property_name, stage_id, stage_label, count, deal_ids
                    FROM owner_property_sales_stage_summary
                    WHERE aggregation_date = %s
                    ORDER BY owner_id, property_name, stage_id
                """
                await cursor.execute(query2, (aggregation_date,))
                owner_results = await cursor.fetchall()
                
                if not property_results and not owner_results:
                    return {
                        "aggregation_date": aggregation_date.isoformat() if isinstance(aggregation_date, date) else str(aggregation_date),
                        "data": {},
                        "message": "指定した集計日のデータがありません"
                    }
                
                # データを構造化
                property_stage_counts = self._structure_property_data(property_results)
                owner_property_stage_counts = self._structure_owner_property_data(owner_results)
                
                return {
                    "aggregation_date": aggregation_date.isoformat() if isinstance(aggregation_date, date) else str(aggregation_date),
                    "data": {
                        "propertyStageCounts": property_stage_counts,
                        "ownerPropertyStageCounts": owner_property_stage_counts
                    }
                }

    def _structure_property_data(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """物件別データを構造化"""
        property_stage_counts = {}
        
        for row in results:
            property_id = row.get('property_id')
            property_name = row.get('property_name')
            stage_id = row.get('stage_id')
            stage_label = row.get('stage_label')
            count = row.get('count', 0)
            
            if not property_id:
                continue
            
            if property_id not in property_stage_counts:
                property_stage_counts[property_id] = {
                    'property_id': property_id,
                    'property_name': property_name,
                    'stage_counts': {}
                }
            
            property_stage_counts[property_id]['stage_counts'][stage_id] = {
                'stage_label': stage_label,
                'count': count
            }
        
        return property_stage_counts

    def _structure_owner_property_data(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """担当者物件別データを構造化"""
        owner_property_stage_counts = {}
        
        for row in results:
            owner_id = row.get('owner_id')
            owner_name = row.get('owner_name')
            property_id = row.get('property_id')
            property_name = row.get('property_name')
            stage_id = row.get('stage_id')
            stage_label = row.get('stage_label')
            count = row.get('count', 0)
            
            if not owner_id or not property_id:
                continue
            
            if owner_id not in owner_property_stage_counts:
                owner_property_stage_counts[owner_id] = {
                    'owner_name': owner_name,
                    'properties': {}
                }
            
            if property_id not in owner_property_stage_counts[owner_id]['properties']:
                owner_property_stage_counts[owner_id]['properties'][property_id] = {
                    'property_name': property_name,
                    'stage_counts': {}
                }
            
            owner_property_stage_counts[owner_id]['properties'][property_id]['stage_counts'][stage_id] = {
                'stage_label': stage_label,
                'count': count
            }
        
        return owner_property_stage_counts

    async def get_deal_ids(
        self,
        aggregation_date: date,
        property_id: str,
        stage_id: str
    ) -> Dict[str, Any]:
        """指定した条件の取引IDリストを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT deal_ids
                    FROM property_sales_stage_summary
                    WHERE aggregation_date = %s
                      AND property_id = %s
                      AND stage_id = %s
                """
                await cursor.execute(query, (aggregation_date, property_id, stage_id))
                result = await cursor.fetchone()
                
                if not result or not result.get('deal_ids'):
                    return {
                        "deals": []
                    }
                
                # JSON形式の取引IDリストをパース
                deal_ids_str = result['deal_ids']
                try:
                    deal_ids = json.loads(deal_ids_str)
                    if not isinstance(deal_ids, list):
                        deal_ids = []
                except (json.JSONDecodeError, TypeError):
                    deal_ids = []
                
                # HubSpotリンクを生成
                hubspot_id = os.getenv('HUBSPOT_ID', '')
                deals = []
                for deal_id in deal_ids:
                    if deal_id:
                        deals.append({
                            "id": deal_id,
                            "hubspot_link": f"https://app.hubspot.com/contacts/{hubspot_id}/record/0-3/{deal_id}/"
                        })
                
                return {
                    "deals": deals
                }

    async def get_deal_details_with_company_and_contact(
        self,
        aggregation_date: date,
        property_id: str,
        stage_id: str
    ) -> Dict[str, Any]:
        """指定した条件の取引詳細を取得（会社名・コンタクト名を含む）"""
        from hubspot.deals import HubSpotDealsClient
        
        deals_client = HubSpotDealsClient()
        
        # 取引IDリストを取得
        deal_ids_result = await self.get_deal_ids(aggregation_date, property_id, stage_id)
        deal_ids = [deal['id'] for deal in deal_ids_result.get('deals', [])]
        
        if not deal_ids:
            return {
                "deals": []
            }
        
        # 各取引の詳細情報を取得（会社・コンタクト情報を含む）
        deals = []
        for deal_id in deal_ids:
            try:
                deal = await deals_client.get_deal_by_id_with_associations(deal_id)
                if not deal:
                    continue
                
                properties = deal.get("properties", {})
                associations = deal.get("associations", {})
                
                # 会社名を取得（最初の関連会社）
                company_name = '-'
                companies = associations.get("companies", [])
                if companies and len(companies) > 0:
                    company = companies[0]
                    company_properties = company.get("properties", {})
                    company_name = company_properties.get("name", '-')
                
                # コンタクト名を取得（最初の関連コンタクト）
                contact_name = '-'
                contacts = associations.get("contacts", [])
                if contacts and len(contacts) > 0:
                    contact = contacts[0]
                    contact_properties = contact.get("properties", {})
                    firstname = contact_properties.get("firstname", "").strip()
                    lastname = contact_properties.get("lastname", "").strip()
                    if lastname and firstname:
                        contact_name = f"{lastname} {firstname}"
                    elif lastname:
                        contact_name = lastname
                    elif firstname:
                        contact_name = firstname
                    else:
                        contact_name = contact_properties.get("email", '-')
                
                # 担当者名を取得（オプション）
                owner_id = properties.get("hubspot_owner_id", "")
                owner_name = owner_id  # デフォルトはID
                
                deals.append({
                    "id": deal_id,
                    "name": properties.get("dealname", "取引名なし"),
                    "amount": properties.get("amount", 0),
                    "stage": properties.get("dealstage", ""),
                    "owner": owner_name,
                    "company_name": company_name,
                    "contact_name": contact_name,
                    "createdDate": properties.get("createdate", ""),
                    "hubspot_link": f"https://app.hubspot.com/contacts/{os.getenv('HUBSPOT_ID', '')}/record/0-3/{deal_id}/"
                })
            except Exception as e:
                logger.warning(f"取引ID {deal_id} の詳細取得に失敗: {str(e)}")
                continue
        
        return {
            "deals": deals
        }

    async def get_owner_property_deal_details_with_company_and_contact(
        self,
        aggregation_date: date,
        owner_id: str,
        property_id: str,
        stage_id: str
    ) -> Dict[str, Any]:
        """指定した条件の取引詳細を取得（担当者物件別、会社名・コンタクト名を含む、データベースから直接取得）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT deal_details
                    FROM owner_property_sales_stage_summary
                    WHERE aggregation_date = %s
                      AND owner_id = %s
                      AND property_id = %s
                      AND stage_id = %s
                """
                await cursor.execute(query, (aggregation_date, owner_id, property_id, stage_id))
                result = await cursor.fetchone()
                
                if not result or not result.get('deal_details'):
                    return {
                        "deals": []
                    }
                
                # JSON形式の取引詳細をパース
                deal_details_str = result['deal_details']
                try:
                    deals = json.loads(deal_details_str)
                    if not isinstance(deals, list):
                        deals = []
                except (json.JSONDecodeError, TypeError):
                    deals = []
                
        return {
            "deals": deals
        }

    async def get_deal_details_with_company_and_contact(
        self,
        aggregation_date: date,
        property_id: str,
        stage_id: str
    ) -> Dict[str, Any]:
        """指定した条件の取引詳細を取得（会社名・コンタクト名を含む、データベースから直接取得）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT deal_details
                    FROM property_sales_stage_summary
                    WHERE aggregation_date = %s
                      AND property_id = %s
                      AND stage_id = %s
                """
                await cursor.execute(query, (aggregation_date, property_id, stage_id))
                result = await cursor.fetchone()
                
                if not result or not result.get('deal_details'):
                    return {
                        "deals": []
                    }
                
                # JSON形式の取引詳細をパース
                deal_details_str = result['deal_details']
                try:
                    deals = json.loads(deal_details_str)
                    if not isinstance(deals, list):
                        deals = []
                except (json.JSONDecodeError, TypeError):
                    deals = []
                
                return {
                    "deals": deals
                }

    async def get_owner_property_deal_ids(
        self,
        aggregation_date: date,
        owner_id: str,
        property_id: str,
        stage_id: str
    ) -> Dict[str, Any]:
        """指定した条件の取引IDリストを取得（担当者物件別）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT deal_ids
                    FROM owner_property_sales_stage_summary
                    WHERE aggregation_date = %s
                      AND owner_id = %s
                      AND property_id = %s
                      AND stage_id = %s
                """
                await cursor.execute(query, (aggregation_date, owner_id, property_id, stage_id))
                result = await cursor.fetchone()
                
                if not result or not result.get('deal_ids'):
                    return {
                        "deals": []
                    }
                
                # JSON形式の取引IDリストをパース
                deal_ids_str = result['deal_ids']
                try:
                    deal_ids = json.loads(deal_ids_str)
                    if not isinstance(deal_ids, list):
                        deal_ids = []
                except (json.JSONDecodeError, TypeError):
                    deal_ids = []
                
                # HubSpotリンクを生成
                hubspot_id = os.getenv('HUBSPOT_ID', '')
                deals = []
                for deal_id in deal_ids:
                    if deal_id:
                        deals.append({
                            "id": deal_id,
                            "hubspot_link": f"https://app.hubspot.com/contacts/{hubspot_id}/record/0-3/{deal_id}/"
                        })
                
                return {
                    "deals": deals
                }

    async def get_deal_details_with_company_and_contact(
        self,
        aggregation_date: date,
        property_id: str,
        stage_id: str
    ) -> Dict[str, Any]:
        """指定した条件の取引詳細を取得（会社名・コンタクト名を含む、データベースから直接取得）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT deal_details
                    FROM property_sales_stage_summary
                    WHERE aggregation_date = %s
                      AND property_id = %s
                      AND stage_id = %s
                """
                await cursor.execute(query, (aggregation_date, property_id, stage_id))
                result = await cursor.fetchone()
                
                if not result or not result.get('deal_details'):
                    return {
                        "deals": []
                    }
                
                # JSON形式の取引詳細をパース
                deal_details_str = result['deal_details']
                try:
                    deals = json.loads(deal_details_str)
                    if not isinstance(deals, list):
                        deals = []
                except (json.JSONDecodeError, TypeError):
                    deals = []
                
                return {
                    "deals": deals
                }

    async def get_owner_property_deal_details_with_company_and_contact(
        self,
        aggregation_date: date,
        owner_id: str,
        property_id: str,
        stage_id: str
    ) -> Dict[str, Any]:
        """指定した条件の取引詳細を取得（担当者物件別、会社名・コンタクト名を含む、データベースから直接取得）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT deal_details
                    FROM owner_property_sales_stage_summary
                    WHERE aggregation_date = %s
                      AND owner_id = %s
                      AND property_id = %s
                      AND stage_id = %s
                """
                await cursor.execute(query, (aggregation_date, owner_id, property_id, stage_id))
                result = await cursor.fetchone()
                
                if not result or not result.get('deal_details'):
                    return {
                        "deals": []
                    }
                
                # JSON形式の取引詳細をパース
                deal_details_str = result['deal_details']
                try:
                    deals = json.loads(deal_details_str)
                    if not isinstance(deals, list):
                        deals = []
                except (json.JSONDecodeError, TypeError):
                    deals = []
                
                return {
                    "deals": deals
                }
