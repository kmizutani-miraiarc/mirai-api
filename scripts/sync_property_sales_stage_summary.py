#!/usr/bin/env python3
"""
物件別販売取引レポート集計バッチスクリプト
毎日午前2時に実行され、物件別の販売取引ステージ別件数を集計してDBに保存
"""

import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hubspot.config import Config
from hubspot.deals import HubSpotDealsClient
from hubspot.owners import HubSpotOwnersClient
from database.connection import get_db_pool
import aiomysql

# ログ設定
if os.path.exists("/var/www/mirai-api/logs"):
    log_dir = "/var/www/mirai-api/logs"
else:
    log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "property_sales_stage_summary.log"))
    ]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hubspot.deals").setLevel(logging.WARNING)
logger = logging.getLogger("property_sales_stage_summary")

# 販売パイプラインID
SALES_PIPELINE_ID = '682910274'

# 非表示担当者（フロントエンドと同じロジック）
HIDDEN_OWNERS = ['甲谷', '水谷', '権正', '中山', '楽待', '宇田', '猪股', '太田']
BOTTOM_OWNERS = ['山岡', '鈴木']

# ステージ名と日付フィールドのマッピング
STAGE_DATE_MAPPING = {
    '物件紹介': 'introduction_datetime',
    '資料開示': 'deal_disclosure_date',
    '調査/検討': 'deal_survey_review_date',
    '調査／検討': 'deal_survey_review_date',
    '買付取得': 'purchase_date',
    '見込み確度B': 'deal_probability_b_date',
    '見込み確度A': 'deal_probability_a_date',
    '契約': 'contract_date',
    '決済': 'settlement_date',
    '見送り': 'deal_farewell_date',
    '失注': 'deal_lost_date',
    '矢注': 'deal_lost_date'
}


class PropertySalesStageSummarySync:
    """物件別販売取引レポート集計クラス"""

    def __init__(self):
        self.deals_client = HubSpotDealsClient()
        self.owners_client = HubSpotOwnersClient()
        self.owners_cache: Dict[str, str] = {}
        self.db_pool = None
        self.stages: List[Dict[str, Any]] = []

    async def run(self):
        """バッチ処理のエントリーポイント"""
        if not Config.validate_config():
            logger.error("HubSpot API設定が正しくありません。環境変数HUBSPOT_API_KEYとHUBSPOT_IDを確認してください。")
            return

        self.db_pool = await get_db_pool()
        if not self.db_pool:
            logger.error("データベース接続プールの取得に失敗しました。")
            return

        try:
            logger.info("物件別販売取引レポート集計を開始します。")
            
            # 担当者キャッシュを事前に読み込む
            await self._load_owners_cache()
            
            # ステージ情報を取得
            self.stages = await self.deals_client.get_pipeline_stages(SALES_PIPELINE_ID)
            if not self.stages:
                logger.error("販売パイプラインのステージ情報が取得できませんでした。")
                return
            
            # 集計日を取得（今日の日付）
            aggregation_date = date.today()
            
            # 販売取引を取得
            all_deals = await self._get_sales_deals()
            
            if not all_deals:
                logger.info("取引が取得できませんでした。")
                return
            
            # 物件別に集計
            property_stage_counts, owner_property_stage_counts = await self._aggregate_property_stages(all_deals)
            
            # データベースに保存（取引IDリストのみ）
            await self._save_to_database(aggregation_date, property_stage_counts, owner_property_stage_counts)
            
            logger.info(f"物件別販売取引レポート集計が完了しました: 物件数={len(property_stage_counts)}件")
            
            # 取引詳細を取得して更新（会社名・コンタクト名を含む）
            logger.info("取引詳細の取得を開始します。")
            updated_count = await self._update_deal_details(aggregation_date, property_stage_counts, owner_property_stage_counts)
            logger.info(f"取引詳細の取得が完了しました: 更新件数={updated_count}件")
        except Exception as e:
            logger.error(f"物件別販売取引レポート集計中にエラーが発生しました: {str(e)}", exc_info=True)
        finally:
            if self.db_pool:
                self.db_pool.close()
                await self.db_pool.wait_closed()

    async def _load_owners_cache(self):
        """担当者情報をキャッシュに読み込む"""
        try:
            owners = await self.owners_client.get_owners()
            for owner in owners:
                owner_id = owner.get("id")
                if owner_id:
                    last_name = owner.get("lastName", "").strip()
                    first_name = owner.get("firstName", "").strip()
                    if last_name and first_name:
                        owner_name = f"{last_name} {first_name}"
                    elif last_name:
                        owner_name = last_name
                    elif first_name:
                        owner_name = first_name
                    else:
                        owner_name = owner.get("email", "")
                    self.owners_cache[owner_id] = owner_name
        except Exception as e:
            logger.warning(f"担当者情報の読み込みに失敗しました: {str(e)}")

    async def _get_sales_deals(self) -> List[Dict[str, Any]]:
        """販売パイプラインの全取引を取得"""
        all_deals = []
        after: Optional[str] = None
        
        # 必要なプロパティを指定
        properties = [
            "dealname",
            "dealstage",
            "pipeline",
            "hubspot_owner_id",
            "introduction_datetime",
            "deal_disclosure_date",
            "deal_survey_review_date",
            "purchase_date",
            "deal_probability_b_date",
            "deal_probability_a_date",
            "contract_date",
            "settlement_date",
            "deal_farewell_date",
            "deal_lost_date"
        ]
        
        while True:
            search_criteria = {
                "filterGroups": [{
                    "filters": [
                        {
                            "propertyName": "pipeline",
                            "operator": "EQ",
                            "value": SALES_PIPELINE_ID
                        }
                    ]
                }],
                "properties": properties,
                "limit": 100
            }
            
            if after:
                search_criteria["after"] = after
            
            try:
                response = await self.deals_client.search_deals(search_criteria)
                if not isinstance(response, dict):
                    break
                
                deals = response.get("results", [])
                if not deals:
                    break
                
                all_deals.extend(deals)
                
                paging = response.get("paging", {})
                next_after = paging.get("next", {}).get("after")
                if next_after:
                    after = str(next_after)
                else:
                    break
            except Exception as e:
                logger.error(f"取引取得中にエラーが発生しました: {str(e)}", exc_info=True)
                break
        
        return all_deals

    def _extract_property_name(self, deal_name: str) -> str:
        """取引名から物件名を抽出"""
        if not deal_name:
            return ''
        # 取引名の最初の部分を物件名とする（スペースまたは全角スペースで分割）
        import re
        parts = re.split(r'[　\s]+', deal_name)
        return parts[0] if parts else ''

    async def _aggregate_property_stages(
        self, 
        all_deals: List[Dict[str, Any]]
    ) -> tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]]:
        """
        物件別にステージ別件数を集計
        戻り値: (property_stage_counts, owner_property_stage_counts)
        """
        # 物件別ステージ別件数
        property_stage_counts: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: {
            'property_id': '',
            'property_name': '',
            'stage_counts': defaultdict(lambda: {'stage_label': '', 'count': 0, 'deal_ids': []})
        })
        
        # 担当者物件別ステージ別件数
        owner_property_stage_counts: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = defaultdict(lambda: {
            'owner_name': '',
            'properties': defaultdict(lambda: {
                'property_name': '',
                'stage_counts': defaultdict(lambda: {'stage_label': '', 'count': 0, 'deal_ids': []})
            })
        })
        
        # 物件に関連付けられた取引を処理
        for deal in all_deals:
            properties = deal.get("properties", {})
            deal_name = properties.get("dealname", "")
            property_name = self._extract_property_name(deal_name)
            
            if not property_name:
                continue
            
            deal_id = deal.get("id")
            owner_id = properties.get("hubspot_owner_id")
            
            # 物件別集計
            if property_name not in property_stage_counts:
                property_stage_counts[property_name] = {
                    'property_id': property_name,
                    'property_name': property_name,
                    'stage_counts': {}
                }
            
            # 各ステージについて集計
            for stage in self.stages:
                stage_id = stage.get("id")
                stage_label = stage.get("label", "")
                
                if stage_id not in property_stage_counts[property_name]['stage_counts']:
                    property_stage_counts[property_name]['stage_counts'][stage_id] = {
                        'stage_label': stage_label,
                        'count': 0,
                        'deal_ids': []
                    }
                
                # 日付フィールドの有無で集計
                date_field = STAGE_DATE_MAPPING.get(stage_label)
                if date_field:
                    date_value = properties.get(date_field)
                    if date_value and str(date_value).strip():
                        property_stage_counts[property_name]['stage_counts'][stage_id]['count'] += 1
                        if deal_id:
                            property_stage_counts[property_name]['stage_counts'][stage_id]['deal_ids'].append(deal_id)
                else:
                    # 日付マッピングがない場合はステージベースで集計
                    if properties.get("dealstage") == stage_id:
                        property_stage_counts[property_name]['stage_counts'][stage_id]['count'] += 1
                        if deal_id:
                            property_stage_counts[property_name]['stage_counts'][stage_id]['deal_ids'].append(deal_id)
            
            # 担当者物件別集計
            if owner_id:
                owner_name = self.owners_cache.get(owner_id, owner_id)
                
                # 非表示担当者はスキップ
                if any(hidden in owner_name for hidden in HIDDEN_OWNERS):
                    continue
                
                if owner_id not in owner_property_stage_counts:
                    owner_property_stage_counts[owner_id] = {
                        'owner_name': owner_name,
                        'properties': {}
                    }
                
                if property_name not in owner_property_stage_counts[owner_id]['properties']:
                    owner_property_stage_counts[owner_id]['properties'][property_name] = {
                        'property_name': property_name,
                        'stage_counts': {}
                    }
                
                # 各ステージについて集計
                for stage in self.stages:
                    stage_id = stage.get("id")
                    stage_label = stage.get("label", "")
                    
                    if stage_id not in owner_property_stage_counts[owner_id]['properties'][property_name]['stage_counts']:
                        owner_property_stage_counts[owner_id]['properties'][property_name]['stage_counts'][stage_id] = {
                            'stage_label': stage_label,
                            'count': 0,
                            'deal_ids': []
                        }
                    
                    # 日付フィールドの有無で集計
                    date_field = STAGE_DATE_MAPPING.get(stage_label)
                    if date_field:
                        date_value = properties.get(date_field)
                        if date_value and str(date_value).strip():
                            owner_property_stage_counts[owner_id]['properties'][property_name]['stage_counts'][stage_id]['count'] += 1
                            if deal_id:
                                owner_property_stage_counts[owner_id]['properties'][property_name]['stage_counts'][stage_id]['deal_ids'].append(deal_id)
                    else:
                        # 日付マッピングがない場合はステージベースで集計
                        if properties.get("dealstage") == stage_id:
                            owner_property_stage_counts[owner_id]['properties'][property_name]['stage_counts'][stage_id]['count'] += 1
                            if deal_id:
                                owner_property_stage_counts[owner_id]['properties'][property_name]['stage_counts'][stage_id]['deal_ids'].append(deal_id)
        
        return property_stage_counts, owner_property_stage_counts

    async def _save_to_database(
        self,
        aggregation_date: date,
        property_stage_counts: Dict[str, Dict[str, Dict[str, Any]]],
        owner_property_stage_counts: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]
    ):
        """集計結果をデータベースに保存"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 既存のデータを削除（同じ集計日のデータ）
                delete_query1 = """
                    DELETE FROM property_sales_stage_summary
                    WHERE aggregation_date = %s
                """
                await cursor.execute(delete_query1, (aggregation_date,))
                
                delete_query2 = """
                    DELETE FROM owner_property_sales_stage_summary
                    WHERE aggregation_date = %s
                """
                await cursor.execute(delete_query2, (aggregation_date,))
                
                # 物件別ステージ別件数を保存
                insert_query1 = """
                    INSERT INTO property_sales_stage_summary
                    (aggregation_date, property_id, property_name, stage_id, stage_label, count, deal_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) AS new
                    ON DUPLICATE KEY UPDATE
                        count = new.count,
                        deal_ids = new.deal_ids,
                        updated_at = CURRENT_TIMESTAMP
                """
                
                for property_name, property_data in property_stage_counts.items():
                    for stage_id, stage_data in property_data['stage_counts'].items():
                        deal_ids_json = json.dumps(stage_data['deal_ids'], ensure_ascii=False) if stage_data['deal_ids'] else None
                        await cursor.execute(
                            insert_query1,
                            (
                                aggregation_date,
                                property_data['property_id'],
                                property_data['property_name'],
                                stage_id,
                                stage_data['stage_label'],
                                stage_data['count'],
                                deal_ids_json
                            )
                        )
                
                # 担当者物件別ステージ別件数を保存
                insert_query2 = """
                    INSERT INTO owner_property_sales_stage_summary
                    (aggregation_date, owner_id, owner_name, property_id, property_name, stage_id, stage_label, count, deal_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) AS new
                    ON DUPLICATE KEY UPDATE
                        count = new.count,
                        deal_ids = new.deal_ids,
                        updated_at = CURRENT_TIMESTAMP
                """
                
                for owner_id, owner_data in owner_property_stage_counts.items():
                    for property_name, property_data in owner_data['properties'].items():
                        for stage_id, stage_data in property_data['stage_counts'].items():
                            deal_ids_json = json.dumps(stage_data['deal_ids'], ensure_ascii=False) if stage_data['deal_ids'] else None
                            await cursor.execute(
                                insert_query2,
                                (
                                    aggregation_date,
                                    owner_id,
                                    owner_data['owner_name'],
                                    property_name,
                                    property_name,
                                    stage_id,
                                    stage_data['stage_label'],
                                    stage_data['count'],
                                    deal_ids_json
                                )
                            )
                
                await conn.commit()

    async def _update_deal_details(
        self,
        aggregation_date: date,
        property_stage_counts: Dict[str, Dict[str, Dict[str, Any]]],
        owner_property_stage_counts: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]
    ) -> int:
        """取引詳細を取得して更新（会社名・コンタクト名を含む）"""
        from hubspot.deals import HubSpotDealsClient
        
        deals_client = HubSpotDealsClient()
        updated_count = 0
        
        # 全取引IDを収集（重複を除去）
        all_deal_ids = set()
        deal_id_to_context = {}  # {deal_id: [(table_type, property_id, stage_id, owner_id)]}
        
        # 物件別の取引IDを収集
        for property_name, property_data in property_stage_counts.items():
            for stage_id, stage_data in property_data['stage_counts'].items():
                for deal_id in stage_data.get('deal_ids', []):
                    if deal_id:
                        all_deal_ids.add(deal_id)
                        if deal_id not in deal_id_to_context:
                            deal_id_to_context[deal_id] = []
                        deal_id_to_context[deal_id].append(('property', property_name, stage_id, None))
        
        # 担当者物件別の取引IDを収集
        for owner_id, owner_data in owner_property_stage_counts.items():
            for property_name, property_data in owner_data['properties'].items():
                for stage_id, stage_data in property_data['stage_counts'].items():
                    for deal_id in stage_data.get('deal_ids', []):
                        if deal_id:
                            all_deal_ids.add(deal_id)
                            if deal_id not in deal_id_to_context:
                                deal_id_to_context[deal_id] = []
                            deal_id_to_context[deal_id].append(('owner_property', property_name, stage_id, owner_id))
        
        if not all_deal_ids:
            logger.info("取引詳細更新対象の取引がありません")
            return 0
        
        # 並列処理で取引詳細を取得（2件ずつ、レート制限を考慮）
        semaphore = asyncio.Semaphore(2)
        deal_details_map = {}
        processed_count = 0
        total_count = len(all_deal_ids)
        
        async def fetch_deal_details(deal_id: str):
            nonlocal processed_count
            async with semaphore:
                await asyncio.sleep(1.0)  # レート制限対策
                try:
                    deal = await deals_client.get_deal_by_id_with_associations(deal_id)
                    if not deal:
                        return deal_id, None
                    
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
                        firstname_raw = contact_properties.get("firstname")
                        lastname_raw = contact_properties.get("lastname")
                        firstname = firstname_raw.strip() if firstname_raw else ""
                        lastname = lastname_raw.strip() if lastname_raw else ""
                        if lastname and firstname:
                            contact_name = f"{lastname} {firstname}"
                        elif lastname:
                            contact_name = lastname
                        elif firstname:
                            contact_name = firstname
                        else:
                            contact_name = contact_properties.get("email", '-')
                    
                    hubspot_id = os.getenv('HUBSPOT_ID', '')
                    deal_detail = {
                        "id": deal_id,
                        "name": properties.get("dealname", "取引名なし"),
                        "amount": properties.get("amount", 0),
                        "stage": properties.get("dealstage", ""),
                        "owner": properties.get("hubspot_owner_id", ""),
                        "company_name": company_name,
                        "contact_name": contact_name,
                        "createdDate": properties.get("createdate", ""),
                        "hubspot_link": f"https://app.hubspot.com/contacts/{hubspot_id}/record/0-3/{deal_id}/"
                    }
                    
                    processed_count += 1
                    
                    return deal_id, deal_detail
                except Exception as e:
                    logger.warning(f"取引ID {deal_id} の詳細取得に失敗: {str(e)}")
                    processed_count += 1
                    return deal_id, None
        
        # 全取引の詳細を並列取得
        tasks = [fetch_deal_details(deal_id) for deal_id in all_deal_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 結果をマップに格納
        error_count = 0
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                if error_count <= 10:
                    logger.warning(f"取引詳細取得エラー: {str(result)}")
                continue
            deal_id, deal_detail = result
            if deal_detail:
                deal_details_map[deal_id] = deal_detail
        
        if error_count > 10:
            logger.warning(f"取引詳細取得エラー: 合計{error_count}件のエラーが発生しました（最初の10件のみログ出力済み）")
        
        # データベースを更新
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 物件別の取引詳細を更新
                for property_name, property_data in property_stage_counts.items():
                    for stage_id, stage_data in property_data['stage_counts'].items():
                        deal_ids = stage_data.get('deal_ids', [])
                        deal_details = []
                        for deal_id in deal_ids:
                            if deal_id in deal_details_map:
                                deal_details.append(deal_details_map[deal_id])
                        
                        if deal_details:
                            deal_details_json = json.dumps(deal_details, ensure_ascii=False)
                            update_query1 = """
                                UPDATE property_sales_stage_summary
                                SET deal_details = %s
                                WHERE aggregation_date = %s
                                  AND property_id = %s
                                  AND stage_id = %s
                            """
                            await cursor.execute(update_query1, (deal_details_json, aggregation_date, property_name, stage_id))
                            updated_count += 1
                
                # 担当者物件別の取引詳細を更新
                for owner_id, owner_data in owner_property_stage_counts.items():
                    for property_name, property_data in owner_data['properties'].items():
                        for stage_id, stage_data in property_data['stage_counts'].items():
                            deal_ids = stage_data.get('deal_ids', [])
                            deal_details = []
                            for deal_id in deal_ids:
                                if deal_id in deal_details_map:
                                    deal_details.append(deal_details_map[deal_id])
                            
                            if deal_details:
                                deal_details_json = json.dumps(deal_details, ensure_ascii=False)
                                update_query2 = """
                                    UPDATE owner_property_sales_stage_summary
                                    SET deal_details = %s
                                    WHERE aggregation_date = %s
                                      AND owner_id = %s
                                      AND property_id = %s
                                      AND stage_id = %s
                                """
                                await cursor.execute(update_query2, (deal_details_json, aggregation_date, owner_id, property_name, stage_id))
                                updated_count += 1
                
                await conn.commit()
                return updated_count


async def main():
    sync = PropertySalesStageSummarySync()
    await sync.run()


if __name__ == "__main__":
    asyncio.run(main())
