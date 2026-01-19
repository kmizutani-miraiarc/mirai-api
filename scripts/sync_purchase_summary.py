#!/usr/bin/env python3
"""
仕入集計レポート集計バッチスクリプト
毎日午前2時に実行され、担当者別・月別の仕入集計データを集計してDBに保存
"""

import asyncio
import json
import logging
import os
import re
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
        logging.FileHandler(os.path.join(log_dir, "purchase_summary.log"))
    ]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hubspot.deals").setLevel(logging.WARNING)
logger = logging.getLogger("purchase_summary")

# 仕入パイプラインID
PURCHASE_PIPELINE_ID = '675713658'

# 非表示担当者（フロントエンドと同じロジック）
HIDDEN_OWNERS = ['甲谷', '水谷', '権正', '中山', '楽待', '宇田', '猪股', '太田']
BOTTOM_OWNERS = ['山岡', '鈴木']


class PurchaseSummarySync:
    """仕入集計レポート集計クラス"""

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
            logger.info("仕入集計レポート集計を開始します。")
            
            # 担当者キャッシュを事前に読み込む
            await self._load_owners_cache()
            
            # ステージ情報を取得
            self.stages = await self.deals_client.get_pipeline_stages(PURCHASE_PIPELINE_ID)
            if not self.stages:
                logger.error("仕入パイプラインのステージ情報が取得できませんでした。")
                return
            
            # 集計年を取得（去年と今年）
            current_year = datetime.now().year
            last_year = current_year - 1
            
            # 仕入取引を取得
            all_deals = await self._get_purchase_deals()
            
            if not all_deals:
                logger.info("取引が取得できませんでした。")
                return
            
            logger.info(f"取得した取引数: {len(all_deals)}件")
            
            # リアルタイム集計と同じロジック：非表示担当者の取引を除外
            visible_owner_ids = []
            for owner_id, owner_name in self.owners_cache.items():
                if self._should_include_owner(owner_name):
                    visible_owner_ids.append(owner_id)
            
            filtered_deals = []
            for deal in all_deals:
                properties = deal.get("properties", {})
                owner_id = properties.get("hubspot_owner_id")
                if owner_id and owner_id in visible_owner_ids:
                    filtered_deals.append(deal)
            
            logger.info(f"非表示担当者除外後の取引数: {len(filtered_deals)}件（除外: {len(all_deals) - len(filtered_deals)}件）")
            
            # リアルタイム集計と同じロジック：去年1月1日から今年12月31日までを一度に処理
            from_date = datetime(last_year, 1, 1)
            to_date = datetime(current_year, 12, 31, 23, 59, 59)
            
            # 集計データを計算（2年分を一度に処理、非表示担当者を除外した取引データを使用）
            summary_data = await self._aggregate_summary(filtered_deals, from_date, to_date)
            
            # デバッグ: 集計結果のサマリーをログ出力
            total_deals_count = 0
            for owner_id, owner_data in summary_data.items():
                for year_month, month_data in owner_data.get('monthly_data', {}).items():
                    total_deals_count += month_data.get('total_deals', 0)
            logger.info(f"集計結果サマリー: 担当者数={len([k for k in summary_data.keys() if k not in ['_ownerOrder', '_totalSummary']])}, 総取引数={total_deals_count}")
            
            # 去年と今年のデータを分けて保存
            for year in [last_year, current_year]:
                year_summary_data = self._filter_by_year(summary_data, year)
                await self._save_to_database(year, year_summary_data)
            
            logger.info(f"仕入集計レポート集計が完了しました。")
        except Exception as e:
            logger.error(f"仕入集計レポート集計中にエラーが発生しました: {str(e)}", exc_info=True)
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

    async def _get_purchase_deals(self) -> List[Dict[str, Any]]:
        """仕入パイプラインの全取引を取得"""
        all_deals = []
        after: Optional[str] = None
        
        # 必要なプロパティを指定（当月系のデータも含む）
        properties = [
            "dealname",
            "dealstage",
            "pipeline",
            "hubspot_owner_id",
            "bukken_created",
            "deal_non_applicable",
            "deal_survey_review_date",
            "research_purchase_price_date",
            "deal_probability_a_date",
            "deal_probability_b_date",
            "deal_farewell_date",
            "deal_lost_date",
            "contract_date",
            "settlement_date"
        ]
        
        while True:
            search_criteria = {
                "filterGroups": [{
                    "filters": [
                        {
                            "propertyName": "pipeline",
                            "operator": "EQ",
                            "value": PURCHASE_PIPELINE_ID
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
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, Dict[str, Any]]:
        """担当者別・月別に集計（リアルタイム集計と同じロジック）"""
        summary_data: Dict[str, Dict[str, Any]] = {}
        
        # リアルタイム集計と同じロジック：担当者をフィルタリングして並び替え
        # 非表示担当者を除外した担当者リストを作成
        filtered_owner_ids = []
        bottom_owner_ids = []
        
        for owner_id, owner_name in self.owners_cache.items():
            # 非表示担当者を除外
            if not self._should_include_owner(owner_name):
                continue
            
            # bottomOwnersを分離
            is_bottom = any(bottom in owner_name for bottom in BOTTOM_OWNERS)
            if is_bottom:
                bottom_owner_ids.append(owner_id)
            else:
                filtered_owner_ids.append(owner_id)
        
        # 並び替えた担当者リストを作成（通常の担当者 + 一番下の担当者）
        sorted_owner_ids = filtered_owner_ids + bottom_owner_ids
        
        # 担当者別にデータを初期化（リアルタイム集計と同じ）
        for owner_id in sorted_owner_ids:
            owner_name = self.owners_cache.get(owner_id, owner_id)
            summary_data[owner_id] = {
                'owner_name': owner_name,
                'monthly_data': {}
            }
        
        # 取引データを処理（非表示担当者は既に除外済み）
        for deal in all_deals:
            properties = deal.get("properties", {})
            owner_id = properties.get("hubspot_owner_id")
            
            if not owner_id:
                continue
            
            # 担当者名を取得
            owner_name = self.owners_cache.get(owner_id, owner_id)
            
            # bukken_createdを基準に日付を取得（リアルタイム集計と同じロジック）
            bukken_created = properties.get("bukken_created")
            if bukken_created:
                try:
                    deal_date = datetime.fromisoformat(bukken_created.replace('Z', '+00:00'))
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
            
            # 日付範囲でフィルタリング（リアルタイム集計と同じ）
            if deal_date < from_date or deal_date > to_date:
                continue
            
            # 年月を取得（YYYY-MM形式、リアルタイム集計と同じ）
            year_month = f"{deal_date.year}-{str(deal_date.month).zfill(2)}"
            
            # 担当者が存在しない場合はスキップ（リアルタイム集計と同じロジック）
            if owner_id not in summary_data:
                continue
            
            # 月別データを初期化
            if year_month not in summary_data[owner_id]['monthly_data']:
                summary_data[owner_id]['monthly_data'][year_month] = {
                    'total_deals': 0,
                    'stage_breakdown': {},
                    'applicable_deals': 0,
                    'non_applicable_deals': 0
                }
            
            # 取引数をカウント
            summary_data[owner_id]['monthly_data'][year_month]['total_deals'] += 1
            
            # 該当/非該当物件をカウント
            is_non_applicable = properties.get("deal_non_applicable") == 'true' or properties.get("deal_non_applicable") == True
            if is_non_applicable:
                summary_data[owner_id]['monthly_data'][year_month]['non_applicable_deals'] += 1
            else:
                summary_data[owner_id]['monthly_data'][year_month]['applicable_deals'] += 1
            
            # ステージ別の内訳をカウント
            stage_id = properties.get("dealstage")
            stage = next((s for s in self.stages if s.get("id") == stage_id), None)
            stage_name = stage.get("label", "不明") if stage else "不明"
            
            if stage_name not in summary_data[owner_id]['monthly_data'][year_month]['stage_breakdown']:
                summary_data[owner_id]['monthly_data'][year_month]['stage_breakdown'][stage_name] = 0
            summary_data[owner_id]['monthly_data'][year_month]['stage_breakdown'][stage_name] += 1
        
        # 当月系のデータを集計（リアルタイム集計と同じロジック）
        for owner_id in summary_data.keys():
            summary_data[owner_id]['monthly_bukken_created_counts'] = {}
            summary_data[owner_id]['monthly_survey_review_counts'] = {}
            summary_data[owner_id]['monthly_purchase_counts'] = {}
            summary_data[owner_id]['monthly_probability_b_counts'] = {}
            summary_data[owner_id]['monthly_probability_a_counts'] = {}
            summary_data[owner_id]['monthly_farewell_counts'] = {}
            summary_data[owner_id]['monthly_lost_counts'] = {}
            summary_data[owner_id]['monthly_contract_counts'] = {}
            summary_data[owner_id]['monthly_settlement_counts'] = {}
        
        # 全取引を再度処理して当月系のデータを集計
        for deal in all_deals:
            properties = deal.get("properties", {})
            owner_id = properties.get("hubspot_owner_id")
            
            if not owner_id or owner_id not in summary_data:
                continue
            
            # 当月情報登録（bukken_created）
            bukken_created = properties.get("bukken_created")
            if bukken_created:
                try:
                    year_month = bukken_created[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_bukken_created_counts']:
                        summary_data[owner_id]['monthly_bukken_created_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_bukken_created_counts'][year_month] += 1
                except:
                    pass
            
            # 当月調査検討（deal_survey_review_date）
            survey_review_date = properties.get("deal_survey_review_date")
            if survey_review_date:
                try:
                    year_month = survey_review_date[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_survey_review_counts']:
                        summary_data[owner_id]['monthly_survey_review_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_survey_review_counts'][year_month] += 1
                except:
                    pass
            
            # 当月買付提出（research_purchase_price_date）
            purchase_date = properties.get("research_purchase_price_date")
            if purchase_date and purchase_date.strip():
                try:
                    year_month = purchase_date[:7]  # YYYY-MM形式
                    if year_month and re.match(r'^\d{4}-\d{2}$', year_month):
                        if year_month not in summary_data[owner_id]['monthly_purchase_counts']:
                            summary_data[owner_id]['monthly_purchase_counts'][year_month] = 0
                        summary_data[owner_id]['monthly_purchase_counts'][year_month] += 1
                except:
                    pass
            
            # 当月見込み確度B（deal_probability_a_date）
            probability_b_date = properties.get("deal_probability_a_date")
            if probability_b_date:
                try:
                    year_month = probability_b_date[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_probability_b_counts']:
                        summary_data[owner_id]['monthly_probability_b_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_probability_b_counts'][year_month] += 1
                except:
                    pass
            
            # 当月見込み確度A（deal_probability_b_date）
            probability_a_date = properties.get("deal_probability_b_date")
            if probability_a_date:
                try:
                    year_month = probability_a_date[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_probability_a_counts']:
                        summary_data[owner_id]['monthly_probability_a_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_probability_a_counts'][year_month] += 1
                except:
                    pass
            
            # 当月見送り（deal_farewell_date）
            farewell_date = properties.get("deal_farewell_date")
            if farewell_date:
                try:
                    year_month = farewell_date[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_farewell_counts']:
                        summary_data[owner_id]['monthly_farewell_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_farewell_counts'][year_month] += 1
                except:
                    pass
            
            # 当月失注（deal_lost_date）
            lost_date = properties.get("deal_lost_date")
            if lost_date:
                try:
                    year_month = lost_date[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_lost_counts']:
                        summary_data[owner_id]['monthly_lost_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_lost_counts'][year_month] += 1
                except:
                    pass
            
            # 契約（contract_date）
            contract_date = properties.get("contract_date")
            if contract_date:
                try:
                    year_month = contract_date[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_contract_counts']:
                        summary_data[owner_id]['monthly_contract_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_contract_counts'][year_month] += 1
                except:
                    pass
            
            # 決済（settlement_date）
            settlement_date = properties.get("settlement_date")
            if settlement_date:
                try:
                    year_month = settlement_date[:7]  # YYYY-MM形式
                    if year_month not in summary_data[owner_id]['monthly_settlement_counts']:
                        summary_data[owner_id]['monthly_settlement_counts'][year_month] = 0
                    summary_data[owner_id]['monthly_settlement_counts'][year_month] += 1
                except:
                    pass
        
        return summary_data

    def _filter_by_year(
        self,
        summary_data: Dict[str, Dict[str, Any]],
        year: int
    ) -> Dict[str, Dict[str, Any]]:
        """指定年のデータのみをフィルタリング（当月系のデータも含む）"""
        filtered_data = {}
        
        for owner_id, owner_data in summary_data.items():
            filtered_monthly_data = {}
            
            # 通常の月別データをフィルタリング
            for year_month, month_data in owner_data.get('monthly_data', {}).items():
                # 年月が指定年と一致する場合のみ含める
                if year_month.startswith(f"{year}-"):
                    # 月のみを抽出（1-12）
                    month = int(year_month.split('-')[1])
                    filtered_monthly_data[month] = month_data.copy()
            
            # 当月系のデータを月別に集計して追加
            monthly_counts_mapping = {
                'monthly_bukken_created_counts': 'bukken_created',
                'monthly_survey_review_counts': 'survey_review',
                'monthly_purchase_counts': 'purchase',
                'monthly_probability_b_counts': 'probability_b',
                'monthly_probability_a_counts': 'probability_a',
                'monthly_farewell_counts': 'farewell',
                'monthly_lost_counts': 'lost',
                'monthly_contract_counts': 'contract',
                'monthly_settlement_counts': 'settlement'
            }
            
            for field, field_key in monthly_counts_mapping.items():
                counts = owner_data.get(field, {})
                for year_month, count in counts.items():
                    if year_month.startswith(f"{year}-"):
                        month = int(year_month.split('-')[1])
                        if month not in filtered_monthly_data:
                            filtered_monthly_data[month] = {
                                'total_deals': 0,
                                'stage_breakdown': {},
                                'applicable_deals': 0,
                                'non_applicable_deals': 0
                            }
                        # 当月系のデータを追加
                        if 'monthly_counts' not in filtered_monthly_data[month]:
                            filtered_monthly_data[month]['monthly_counts'] = {}
                        filtered_monthly_data[month]['monthly_counts'][field_key] = count
            
            if filtered_monthly_data:
                filtered_data[owner_id] = {
                    'owner_name': owner_data['owner_name'],
                    'monthly_data': filtered_monthly_data
                }
        
        return filtered_data

    async def _save_to_database(
        self,
        year: int,
        summary_data: Dict[str, Dict[str, Any]]
    ):
        """データベースに保存"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                insert_query = """
                    INSERT INTO purchase_summary
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
                        # monthは1-12の整数
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
    sync = PurchaseSummarySync()
    await sync.run()


if __name__ == "__main__":
    asyncio.run(main())
