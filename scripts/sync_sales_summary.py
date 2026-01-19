#!/usr/bin/env python3
"""
販売集計レポート集計バッチスクリプト
毎日午前2時に実行され、担当者別・月別の販売集計データを集計してDBに保存
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
        logging.FileHandler(os.path.join(log_dir, "sales_summary.log"))
    ]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hubspot.deals").setLevel(logging.WARNING)
logger = logging.getLogger("sales_summary")

# 販売パイプラインID
SALES_PIPELINE_ID = '682910274'

# 非表示担当者（フロントエンドと同じロジック）
HIDDEN_OWNERS = ['甲谷', '水谷', '権正', '中山', '楽待', '宇田', '猪股', '太田']
BOTTOM_OWNERS = ['山岡', '鈴木']


class SalesSummarySync:
    """販売集計レポート集計クラス"""

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
            logger.info("販売集計レポート集計を開始します。")
            
            # 担当者キャッシュを事前に読み込む
            await self._load_owners_cache()
            
            # ステージ情報を取得
            self.stages = await self.deals_client.get_pipeline_stages(SALES_PIPELINE_ID)
            if not self.stages:
                logger.error("販売パイプラインのステージ情報が取得できませんでした。")
                return
            
            # 集計年を取得（去年と今年）
            current_year = datetime.now().year
            last_year = current_year - 1
            
            # 販売取引を取得
            all_deals = await self._get_sales_deals()
            
            if not all_deals:
                logger.info("取引が取得できませんでした。")
                return
            
            # 去年と今年の集計データを計算
            for year in [last_year, current_year]:
                summary_data = await self._aggregate_summary(all_deals, year)
                
                # データベースに保存
                await self._save_to_database(year, summary_data)
            
            logger.info(f"販売集計レポート集計が完了しました。")
        except Exception as e:
            logger.error(f"販売集計レポート集計中にエラーが発生しました: {str(e)}", exc_info=True)
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
            "introduction_datetime"
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

    def _should_include_owner(self, owner_name: str) -> bool:
        """担当者を表示対象に含めるかどうかを判定"""
        # 非表示担当者を除外
        for hidden in HIDDEN_OWNERS:
            if hidden in owner_name:
                return False
        return True

    async def _aggregate_summary(
        self, 
        all_deals: List[Dict[str, Any]],
        year: int
    ) -> Dict[str, Dict[str, Any]]:
        """担当者別・月別に集計"""
        summary_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'owner_name': '',
            'monthly_data': {}
        })
        
        # 日付範囲を設定
        from_date = datetime(year, 1, 1)
        to_date = datetime(year, 12, 31, 23, 59, 59)
        
        # 取引データを処理
        for deal in all_deals:
            properties = deal.get("properties", {})
            owner_id = properties.get("hubspot_owner_id")
            
            if not owner_id:
                continue
            
            # 担当者名を取得
            owner_name = self.owners_cache.get(owner_id, owner_id)
            
            # 非表示担当者を除外
            if not self._should_include_owner(owner_name):
                continue
            
            # introduction_datetimeを基準に日付を取得
            introduction_datetime = properties.get("introduction_datetime")
            if introduction_datetime:
                try:
                    deal_date = datetime.fromisoformat(introduction_datetime.replace('Z', '+00:00'))
                    # offset-awareをoffset-naiveに変換（UTCからローカルタイムに変換）
                    if deal_date.tzinfo:
                        deal_date = deal_date.replace(tzinfo=None)
                except:
                    createdate_str = properties.get("createdate", "")
                    if createdate_str:
                        deal_date = datetime.fromisoformat(createdate_str.replace('Z', '+00:00'))
                        if deal_date.tzinfo:
                            deal_date = deal_date.replace(tzinfo=None)
                    else:
                        continue
            else:
                createdate_str = properties.get("createdate", "")
                if createdate_str:
                    deal_date = datetime.fromisoformat(createdate_str.replace('Z', '+00:00'))
                    if deal_date.tzinfo:
                        deal_date = deal_date.replace(tzinfo=None)
                else:
                    continue
            
            # 日付範囲でフィルタリング
            if deal_date < from_date or deal_date > to_date:
                continue
            
            # 月を取得
            month = deal_date.month
            
            # 担当者データを初期化
            if owner_id not in summary_data:
                summary_data[owner_id] = {
                    'owner_name': owner_name,
                    'monthly_data': {}
                }
            
            # 月別データを初期化
            if month not in summary_data[owner_id]['monthly_data']:
                summary_data[owner_id]['monthly_data'][month] = {
                    'total_deals': 0,
                    'stage_breakdown': {}
                }
            
            # 取引数をカウント
            summary_data[owner_id]['monthly_data'][month]['total_deals'] += 1
            
            # ステージ別の内訳をカウント
            stage_id = properties.get("dealstage")
            stage = next((s for s in self.stages if s.get("id") == stage_id), None)
            stage_name = stage.get("label", "不明") if stage else "不明"
            
            if stage_name not in summary_data[owner_id]['monthly_data'][month]['stage_breakdown']:
                summary_data[owner_id]['monthly_data'][month]['stage_breakdown'][stage_name] = 0
            summary_data[owner_id]['monthly_data'][month]['stage_breakdown'][stage_name] += 1
        
        return summary_data

    async def _save_to_database(
        self,
        year: int,
        summary_data: Dict[str, Dict[str, Any]]
    ):
        """データベースに保存"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                insert_query = """
                    INSERT INTO sales_summary
                    (aggregation_year, owner_id, owner_name, month, total_deals, stage_breakdown, monthly_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) AS new
                    ON DUPLICATE KEY UPDATE
                        total_deals = new.total_deals,
                        stage_breakdown = new.stage_breakdown,
                        monthly_data = new.monthly_data,
                        updated_at = CURRENT_TIMESTAMP
                """
                
                for owner_id, owner_data in summary_data.items():
                    owner_name = owner_data['owner_name']
                    for month, month_data in owner_data['monthly_data'].items():
                        stage_breakdown_json = json.dumps(month_data['stage_breakdown'], ensure_ascii=False)
                        monthly_data_json = json.dumps(month_data, ensure_ascii=False)
                        
                        await cursor.execute(
                            insert_query,
                            (
                                year,
                                owner_id,
                                owner_name,
                                month,
                                month_data['total_deals'],
                                stage_breakdown_json,
                                monthly_data_json
                            )
                        )
                
                await conn.commit()


async def main():
    """メイン関数"""
    sync = SalesSummarySync()
    await sync.run()


if __name__ == "__main__":
    asyncio.run(main())
