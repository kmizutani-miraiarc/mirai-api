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
            
            # 去年と今年の集計データを計算（2年分を一度に処理）
            from_date = datetime(last_year, 1, 1)
            to_date = datetime(current_year, 12, 31, 23, 59, 59)
            
            # 集計データを計算（2年分を一度に処理、非表示担当者を除外した取引データを使用）
            summary_data = await self._aggregate_summary(filtered_deals, from_date, to_date)
            
            # 取引詳細を取得して保存（エラーが発生してもバッチ処理は続行）
            try:
                await self._update_deal_details(summary_data, filtered_deals)
            except Exception as e:
                logger.error(f"取引詳細の取得中にエラーが発生しましたが、バッチ処理は続行します: {str(e)}", exc_info=True)
            
            # 去年と今年のデータを分けて保存
            for year in [last_year, current_year]:
                year_summary_data = self._filter_by_year(summary_data, year)
                await self._save_to_database(year, year_summary_data)
            
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
            archived_count = 0
            for owner in owners:
                owner_id = owner.get("id")
                if not owner_id:
                    continue
                
                # 無効（アーカイブ済み）な担当者を除外
                if owner.get("archived", False):
                    archived_count += 1
                    logger.debug(f"無効な担当者を除外: {owner_id} (archived=true)")
                    continue
                
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
            
            if archived_count > 0:
                logger.info(f"無効な担当者を除外しました: {archived_count}件")
        except Exception as e:
            logger.warning(f"担当者情報の読み込みに失敗しました: {str(e)}")

    async def _get_sales_deals(self) -> List[Dict[str, Any]]:
        """販売パイプラインの全取引を取得"""
        all_deals = []
        after: Optional[str] = None
        
        # 必要なプロパティを指定（当月系のデータも含む）
        properties = [
            "dealname",
            "dealstage",
            "pipeline",
            "hubspot_owner_id",
            "introduction_datetime",
            "deal_disclosure_date",
            "deal_survey_review_date",
            "purchase_date",
            "deal_hold_date",
            "bukken_created",
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
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, Dict[str, Any]]:
        """担当者別・月別に集計（2年分を一度に処理）"""
        # 表示対象の担当者のみを初期化
        summary_data = {}
        for owner_id, owner_name in self.owners_cache.items():
            if self._should_include_owner(owner_name):
                summary_data[owner_id] = {
                    'owner_name': owner_name,
                    'monthly_data': {}
                }
        
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
                    # ISO形式の文字列をパース
                    if 'Z' in introduction_datetime:
                        deal_date = datetime.fromisoformat(introduction_datetime.replace('Z', '+00:00'))
                    elif '+' in introduction_datetime or introduction_datetime.count('-') > 2:
                        deal_date = datetime.fromisoformat(introduction_datetime)
                    else:
                        # YYYY-MM-DD形式の場合
                        deal_date = datetime.fromisoformat(introduction_datetime)
                    # offset-awareをoffset-naiveに変換
                    if deal_date.tzinfo is not None:
                        deal_date = deal_date.replace(tzinfo=None)
                except Exception as e:
                    logger.debug(f"introduction_datetimeのパースに失敗: {introduction_datetime}, エラー: {str(e)}")
                    createdate_str = properties.get("createdate", "")
                    if createdate_str:
                        try:
                            if 'Z' in createdate_str:
                                deal_date = datetime.fromisoformat(createdate_str.replace('Z', '+00:00'))
                            else:
                                deal_date = datetime.fromisoformat(createdate_str)
                            if deal_date.tzinfo is not None:
                                deal_date = deal_date.replace(tzinfo=None)
                        except:
                            continue
                    else:
                        continue
            else:
                createdate_str = properties.get("createdate", "")
                if createdate_str:
                    try:
                        if 'Z' in createdate_str:
                            deal_date = datetime.fromisoformat(createdate_str.replace('Z', '+00:00'))
                        else:
                            deal_date = datetime.fromisoformat(createdate_str)
                        if deal_date.tzinfo is not None:
                            deal_date = deal_date.replace(tzinfo=None)
                    except:
                        continue
                else:
                    continue
            
            # 日付範囲でフィルタリング
            if deal_date < from_date or deal_date > to_date:
                continue
            
            # 年月を取得（YYYY-MM形式）
            year_month = f"{deal_date.year}-{str(deal_date.month).zfill(2)}"
            month = deal_date.month
            
            # 担当者データが存在しない場合はスキップ（非表示担当者は除外済み）
            if owner_id not in summary_data:
                continue
            
            # 月別データを初期化
            if year_month not in summary_data[owner_id]['monthly_data']:
                summary_data[owner_id]['monthly_data'][year_month] = {
                    'total_deals': 0,
                    'stage_breakdown': {},
                    'deal_ids_by_stage': {},  # ステージ別の取引IDリスト
                    'deal_ids_by_monthly_item': {}  # 当月系項目別の取引IDリスト
                }
            
            # 取引IDを取得
            deal_id = deal.get("id")
            
            # 取引数をカウント
            summary_data[owner_id]['monthly_data'][year_month]['total_deals'] += 1
            
            # ステージ別の内訳をカウント
            stage_id = properties.get("dealstage")
            stage = next((s for s in self.stages if s.get("id") == stage_id), None)
            stage_name = stage.get("label", "不明") if stage else "不明"
            
            if stage_name not in summary_data[owner_id]['monthly_data'][year_month]['stage_breakdown']:
                summary_data[owner_id]['monthly_data'][year_month]['stage_breakdown'][stage_name] = 0
                summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage'][stage_name] = []
            summary_data[owner_id]['monthly_data'][year_month]['stage_breakdown'][stage_name] += 1
            
            # ステージ別の取引IDを保存
            if deal_id and stage_name in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage']:
                if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage'][stage_name]:
                    summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage'][stage_name].append(deal_id)
            
            # 「全体」（登録数）の取引IDを保存
            if deal_id:
                if '全体' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage']:
                    summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage']['全体'] = []
                if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage']['全体']:
                    summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_stage']['全体'].append(deal_id)
        
        # 当月系項目の取引IDを収集（2回目のループ）
        for deal in all_deals:
            properties = deal.get("properties", {})
            owner_id = properties.get("hubspot_owner_id")
            
            if not owner_id or owner_id not in summary_data:
                continue
            
            deal_id = deal.get("id")
            if not deal_id:
                continue
            
            # 当月物件紹介（introduction_datetime）
            introduction_datetime = properties.get("introduction_datetime")
            if introduction_datetime:
                try:
                    year_month = introduction_datetime[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月物件紹介' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月物件紹介'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月物件紹介']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月物件紹介'].append(deal_id)
                except:
                    pass
            
            # 当月資料開示（deal_disclosure_date）
            disclosure_date = properties.get("deal_disclosure_date")
            if disclosure_date:
                try:
                    year_month = disclosure_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月資料開示' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月資料開示'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月資料開示']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月資料開示'].append(deal_id)
                except:
                    pass
            
            # 当月調査/検討（deal_survey_review_date）
            survey_review_date = properties.get("deal_survey_review_date")
            if survey_review_date:
                try:
                    year_month = survey_review_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月調査/検討' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月調査/検討'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月調査/検討']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月調査/検討'].append(deal_id)
                except:
                    pass
            
            # 当月買付取得（purchase_date）
            purchase_date = properties.get("purchase_date")
            if purchase_date:
                try:
                    year_month = purchase_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月買付取得' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月買付取得'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月買付取得']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月買付取得'].append(deal_id)
                except:
                    pass
            
            # 当月見込み確度B（deal_probability_a_date）
            probability_b_date = properties.get("deal_probability_a_date")
            if probability_b_date:
                try:
                    year_month = probability_b_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月見込み確度B' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見込み確度B'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見込み確度B']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見込み確度B'].append(deal_id)
                except:
                    pass
            
            # 当月見込み確度A（deal_probability_b_date）
            probability_a_date = properties.get("deal_probability_b_date")
            if probability_a_date:
                try:
                    year_month = probability_a_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月見込み確度A' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見込み確度A'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見込み確度A']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見込み確度A'].append(deal_id)
                except:
                    pass
            
            # 当月見送り（deal_farewell_date）
            farewell_date = properties.get("deal_farewell_date")
            if farewell_date:
                try:
                    year_month = farewell_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月見送り' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見送り'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見送り']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月見送り'].append(deal_id)
                except:
                    pass
            
            # 当月失注（deal_lost_date）
            lost_date = properties.get("deal_lost_date")
            if lost_date:
                try:
                    year_month = lost_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月失注' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月失注'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月失注']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月失注'].append(deal_id)
                except:
                    pass
            
            # 当月契約（contract_date）
            contract_date = properties.get("contract_date")
            if contract_date:
                try:
                    year_month = contract_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月契約' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月契約'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月契約']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月契約'].append(deal_id)
                except:
                    pass
            
            # 当月決済（settlement_date）
            settlement_date = properties.get("settlement_date")
            if settlement_date:
                try:
                    year_month = settlement_date[:7]  # YYYY-MM形式
                    if year_month in summary_data[owner_id].get('monthly_data', {}):
                        if 'deal_ids_by_monthly_item' not in summary_data[owner_id]['monthly_data'][year_month]:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item'] = {}
                        if '当月決済' not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月決済'] = []
                        if deal_id not in summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月決済']:
                            summary_data[owner_id]['monthly_data'][year_month]['deal_ids_by_monthly_item']['当月決済'].append(deal_id)
                except:
                    pass
        
        return summary_data

    def _filter_by_year(
        self,
        summary_data: Dict[str, Dict[str, Any]],
        year: int
    ) -> Dict[str, Dict[str, Any]]:
        """指定年のデータのみをフィルタリング（YYYY-MM形式から月のみに変換、当月系のカウントも計算）"""
        filtered_data = {}
        
        for owner_id, owner_data in summary_data.items():
            filtered_data[owner_id] = {
                'owner_name': owner_data['owner_name'],
                'monthly_data': {}
            }
            
            for year_month, month_data in owner_data.get('monthly_data', {}).items():
                # 年月から年を抽出
                year_from_month = int(year_month.split('-')[0])
                month = int(year_month.split('-')[1])
                
                # 指定年のデータのみをフィルタリング
                if year_from_month == year:
                    # 当月系のカウントを計算
                    monthly_counts = {}
                    deal_ids_by_monthly_item = month_data.get('deal_ids_by_monthly_item', {})
                    
                    # 各当月系項目のカウントを計算
                    if '当月物件紹介' in deal_ids_by_monthly_item:
                        monthly_counts['introduction'] = len(deal_ids_by_monthly_item['当月物件紹介'])
                    if '当月資料開示' in deal_ids_by_monthly_item:
                        monthly_counts['disclosure'] = len(deal_ids_by_monthly_item['当月資料開示'])
                    if '当月調査/検討' in deal_ids_by_monthly_item:
                        monthly_counts['survey_review'] = len(deal_ids_by_monthly_item['当月調査/検討'])
                    if '当月買付取得' in deal_ids_by_monthly_item:
                        monthly_counts['purchase'] = len(deal_ids_by_monthly_item['当月買付取得'])
                    if '当月見込み確度B' in deal_ids_by_monthly_item:
                        monthly_counts['probability_b'] = len(deal_ids_by_monthly_item['当月見込み確度B'])
                    if '当月見込み確度A' in deal_ids_by_monthly_item:
                        monthly_counts['probability_a'] = len(deal_ids_by_monthly_item['当月見込み確度A'])
                    if '当月見送り' in deal_ids_by_monthly_item:
                        monthly_counts['farewell'] = len(deal_ids_by_monthly_item['当月見送り'])
                    if '当月失注' in deal_ids_by_monthly_item:
                        monthly_counts['lost'] = len(deal_ids_by_monthly_item['当月失注'])
                    if '当月契約' in deal_ids_by_monthly_item:
                        monthly_counts['contract'] = len(deal_ids_by_monthly_item['当月契約'])
                    if '当月決済' in deal_ids_by_monthly_item:
                        monthly_counts['settlement'] = len(deal_ids_by_monthly_item['当月決済'])
                    
                    # monthly_countsをmonthly_dataに追加
                    month_data['monthly_counts'] = monthly_counts
                    filtered_data[owner_id]['monthly_data'][month] = month_data
        
        return filtered_data

    async def _update_deal_details(
        self,
        summary_data: Dict[str, Dict[str, Any]],
        all_deals: List[Dict[str, Any]]
    ):
        """取引詳細を取得してsummary_dataに追加（会社名・コンタクト名を含む）"""
        # 全取引IDを収集（重複を除去）
        all_deal_ids = set()
        deal_id_to_context = {}  # {deal_id: [(owner_id, year_month, stage_name, item_type)]}
        
        for owner_id, owner_data in summary_data.items():
            for year_month, month_data in owner_data.get('monthly_data', {}).items():
                # ステージ別の取引IDを収集
                deal_ids_by_stage = month_data.get('deal_ids_by_stage', {})
                for stage_name, deal_ids in deal_ids_by_stage.items():
                    for deal_id in deal_ids:
                        if deal_id:
                            all_deal_ids.add(deal_id)
                            if deal_id not in deal_id_to_context:
                                deal_id_to_context[deal_id] = []
                            deal_id_to_context[deal_id].append((owner_id, year_month, stage_name, 'stage'))
                
                # 当月系項目別の取引IDを収集
                deal_ids_by_monthly_item = month_data.get('deal_ids_by_monthly_item', {})
                for item_name, deal_ids in deal_ids_by_monthly_item.items():
                    for deal_id in deal_ids:
                        if deal_id:
                            all_deal_ids.add(deal_id)
                            if deal_id not in deal_id_to_context:
                                deal_id_to_context[deal_id] = []
                            deal_id_to_context[deal_id].append((owner_id, year_month, item_name, 'monthly_item'))
        
        if not all_deal_ids:
            logger.info("取引詳細更新対象の取引がありません")
            return
        
        # 並列処理で取引詳細を取得（3件ずつ、レート制限を考慮）
        semaphore = asyncio.Semaphore(3)
        deal_details_map = {}
        processed_count = 0
        total_count = len(all_deal_ids)
        
        async def fetch_deal_details(deal_id: str):
            nonlocal processed_count
            async with semaphore:
                await asyncio.sleep(0.5)  # レート制限対策（0.5秒待機）
                try:
                    deal = await self.deals_client.get_deal_by_id_with_associations(deal_id)
                    if not deal:
                        processed_count += 1
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
                    if processed_count % 100 == 0:
                        logger.info(f"取引詳細取得進捗: {processed_count}/{total_count}")
                    
                    return deal_id, deal_detail
                except Exception as e:
                    logger.warning(f"取引ID {deal_id} の詳細取得に失敗: {str(e)}")
                    processed_count += 1
                    return deal_id, None
        
        # 全取引の詳細を並列取得
        logger.info(f"取引詳細取得を開始: {total_count}件")
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
        
        logger.info(f"取引詳細取得完了: {len(deal_details_map)}件")
        
        # summary_dataに取引詳細を追加
        for deal_id, deal_detail in deal_details_map.items():
            if deal_id not in deal_id_to_context:
                continue
            
            for owner_id, year_month, stage_or_item_name, item_type in deal_id_to_context[deal_id]:
                if owner_id not in summary_data:
                    continue
                
                if year_month not in summary_data[owner_id].get('monthly_data', {}):
                    continue
                
                month_data = summary_data[owner_id]['monthly_data'][year_month]
                
                if item_type == 'stage':
                    # ステージ別の取引詳細を保存
                    if 'deal_details_by_stage' not in month_data:
                        month_data['deal_details_by_stage'] = {}
                    if stage_or_item_name not in month_data['deal_details_by_stage']:
                        month_data['deal_details_by_stage'][stage_or_item_name] = []
                    # 重複チェック
                    if not any(d.get('id') == deal_id for d in month_data['deal_details_by_stage'][stage_or_item_name]):
                        month_data['deal_details_by_stage'][stage_or_item_name].append(deal_detail)
                
                elif item_type == 'monthly_item':
                    # 当月系項目別の取引詳細を保存
                    if 'deal_details_by_monthly_item' not in month_data:
                        month_data['deal_details_by_monthly_item'] = {}
                    if stage_or_item_name not in month_data['deal_details_by_monthly_item']:
                        month_data['deal_details_by_monthly_item'][stage_or_item_name] = []
                    # 重複チェック
                    if not any(d.get('id') == deal_id for d in month_data['deal_details_by_monthly_item'][stage_or_item_name]):
                        month_data['deal_details_by_monthly_item'][stage_or_item_name].append(deal_detail)

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
                        stage_breakdown_json = json.dumps(month_data.get('stage_breakdown', {}), ensure_ascii=False)
                        monthly_data_json = json.dumps(month_data, ensure_ascii=False)
                        
                        await cursor.execute(
                            insert_query,
                            (
                                year,
                                owner_id,
                                owner_name,
                                month,
                                month_data.get('total_deals', 0),
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
