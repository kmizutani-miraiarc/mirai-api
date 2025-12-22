#!/usr/bin/env python3
"""
HubSpotコンタクトのスコアリング（仕入）集計バッチスクリプト
毎週月曜日午前2時半に実行され、コンタクトのスコアリング項目を集計してDBに保存
"""

import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hubspot.config import Config
from hubspot.contacts import HubSpotContactsClient
from hubspot.owners import HubSpotOwnersClient
from database.connection import get_db_pool
import aiomysql

# ログ設定
# 本番環境とローカル環境の両方に対応
if os.path.exists("/var/www/mirai-api/logs"):
    log_dir = "/var/www/mirai-api/logs"
else:
    # ローカル環境ではプロジェクトルートのlogsディレクトリを使用
    log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "contact_scoring_summary.log"))
    ]
)

# httpxのログレベルをWARNINGに設定（HTTP Requestログを削除）
logging.getLogger("httpx").setLevel(logging.WARNING)

# hubspot.dealsのログレベルをWARNINGに設定（INFO/DEBUGログを削除）
logging.getLogger("hubspot.deals").setLevel(logging.WARNING)
logger = logging.getLogger("contact_scoring_summary")

# 対象担当者名（姓名）
TARGET_OWNERS = [
    "岩崎 陽",
    "久世 健人",
    "赤瀬 公平",
    "藤森 日加里",
    "藤村 ひかり"
]

# 対象担当者ID（初期化時に設定される）
TARGET_OWNER_IDS: List[str] = []

# 対象ターゲットの指定項目
SPECIFIED_INDUSTRIES = ['売買仲介（エンド）', '買取']
SPECIFIED_PROPERTY_TYPES = ['1棟AP', '1棟MS']
SPECIFIED_AREAS = ['東京', '神奈川', '千葉', '埼玉']
SPECIFIED_AREA_CATEGORIES = ['狭域の郊外(地元特化)', '1都3県（郊外寄り）', '1都3県（23区寄り）']
SPECIFIED_GROSSES = ['〜1億', '1〜3億']


class ContactScoringSummarySync:
    """コンタクトスコアリング（仕入）集計クラス"""

    def __init__(self):
        self.contacts_client = HubSpotContactsClient()
        self.owners_client = HubSpotOwnersClient()
        self.owners_cache: Dict[str, str] = {}
        self.db_pool = None

    async def run(self):
        """バッチ処理のエントリーポイント"""
        if not Config.validate_config():
            logger.error("HubSpot API設定が正しくありません。環境変数HUBSPOT_API_KEYとHUBSPOT_IDを確認してください。")
            return

        # データベース接続プールを取得
        self.db_pool = await get_db_pool()
        if not self.db_pool:
            logger.error("データベース接続プールの取得に失敗しました。")
            return

        try:
            logger.info("コンタクトスコアリング（仕入）集計を開始します。")
            
            # 担当者キャッシュを事前に読み込む
            await self._load_owners_cache()
            
            # 今週の月曜日を集計日として取得
            aggregation_date = self._get_this_week_monday()
            
            # 対象担当者IDが取得できているか確認
            if not TARGET_OWNER_IDS:
                logger.info("コンタクトスコアリング（仕入）集計が完了しました: 更新件数=0件")
                return
            
            # コンタクトデータを取得して集計
            scoring_counts = await self._aggregate_contact_scoring()
            
            # 集計結果を確認
            total_count = 0
            for pattern_type in ['all', 'buy', 'sell', 'buy_or_sell']:
                pattern_counts = scoring_counts.get(pattern_type, {})
                for owner_id in TARGET_OWNER_IDS:
                    counts = pattern_counts.get(owner_id, {})
                    total_count += sum(counts.values())
            
            if total_count == 0:
                logger.info("コンタクトスコアリング（仕入）集計が完了しました: 更新件数=0件")
                return
            
            # データベースに保存
            await self._save_to_database(aggregation_date, scoring_counts)
            
            logger.info(f"コンタクトスコアリング（仕入）集計が完了しました: 保存件数={total_count}件")
        except Exception as e:
            logger.error(f"コンタクトスコアリング（仕入）集計中にエラーが発生しました: {str(e)}", exc_info=True)
        finally:
            if self.db_pool:
                self.db_pool.close()
                await self.db_pool.wait_closed()

    def _get_this_week_monday(self) -> date:
        """今週の月曜日の日付を取得"""
        today = date.today()
        # 月曜日は0、日曜日は6
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        return monday

    async def _load_owners_cache(self):
        """担当者情報をキャッシュに読み込む"""
        global TARGET_OWNER_IDS
        try:
            owners = await self.owners_client.get_owners()
            for owner in owners:
                owner_id = owner.get("id")
                if owner_id:
                    # HubSpot APIでは firstName=名, lastName=姓 なので、日本の表記（姓 名）にする
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
                    
                    # 対象担当者のIDをリストに追加
                    if owner_name in TARGET_OWNERS:
                        TARGET_OWNER_IDS.append(owner_id)
            pass
        except Exception as e:
            pass

    def _get_array_property(self, property_value: Any) -> List[str]:
        """プロパティを配列として取得（HubSpotの複数選択フィールド用）"""
        if not property_value:
            return []
        if isinstance(property_value, list):
            result = []
            for item in property_value:
                if isinstance(item, str):
                    # セミコロンやカンマで区切られている場合も分割
                    result.extend([s.strip() for s in item.split(';') if s.strip()])
                    result.extend([s.strip() for s in item.split(',') if s.strip()])
                else:
                    result.append(str(item))
            return result
        if isinstance(property_value, str):
            # セミコロンやカンマで区切られている場合も分割
            result = []
            for separator in [';', ',']:
                result.extend([s.strip() for s in property_value.split(separator) if s.strip()])
            return result if result else [property_value.strip()]
        return [str(property_value)]

    def _get_contact_patterns(self, contact: Dict[str, Any]) -> List[str]:
        """
        コンタクトのパターンを判定（all, buy, sell, buy_or_sell）
        
        パターン判定ロジック:
        - all: すべてのコンタクト
        - buy: 仕入のみ（仕入が含まれ、売却が含まれない）
        - sell: 売却のみ（売却が含まれ、仕入が含まれない）
        - buy_or_sell: 仕入と売却の両方が含まれる
        """
        patterns = ['all']  # すべてのコンタクトは'all'に含まれる
        
        properties = contact.get("properties", {})
        buy_or_sell_raw = properties.get("contractor_buy_or_sell")
        buy_or_sell_array = self._get_array_property(buy_or_sell_raw)
        
        has_buy = '仕入' in buy_or_sell_array
        has_sell = '売却' in buy_or_sell_array
        
        # 仕入のみ（仕入が含まれ、売却が含まれない）
        if has_buy and not has_sell:
            patterns.append('buy')
        
        # 売却のみ（売却が含まれ、仕入が含まれない）
        if not has_buy and has_sell:
            patterns.append('sell')
        
        # 仕入と売却の両方が含まれる
        if has_buy and has_sell:
            patterns.append('buy_or_sell')
        
        return patterns

    def _has_specified_items(self, items: List[str], specified_items: List[str]) -> bool:
        """指定項目が含まれているかチェック"""
        if not items:
            return False
        return any(item in specified_items for item in items)

    def _is_target_audience(self, properties: Dict[str, Any]) -> bool:
        """対象ターゲットかどうかを判定"""
        # 各項目を配列として取得
        industries = self._get_array_property(properties.get('contractor_industry'))
        property_types = self._get_array_property(properties.get('contractor_property_type'))
        areas = self._get_array_property(properties.get('contractor_area'))
        area_categories = self._get_array_property(properties.get('contractor_area_category'))
        grosses = self._get_array_property(properties.get('contractor_gross2'))

        # 各項目を個別に判定
        # 指定項目が含まれていない場合は除外（ただし空の場合は通知対象）
        should_exclude_industry = len(industries) > 0 and not self._has_specified_items(industries, SPECIFIED_INDUSTRIES)
        should_exclude_property_type = len(property_types) > 0 and not self._has_specified_items(property_types, SPECIFIED_PROPERTY_TYPES)
        should_exclude_area = len(areas) > 0 and not self._has_specified_items(areas, SPECIFIED_AREAS)
        should_exclude_area_category = len(area_categories) > 0 and not self._has_specified_items(area_categories, SPECIFIED_AREA_CATEGORIES)
        should_exclude_gross = len(grosses) > 0 and not self._has_specified_items(grosses, SPECIFIED_GROSSES)

        should_exclude = should_exclude_industry or should_exclude_property_type or should_exclude_area or \
               should_exclude_area_category or should_exclude_gross

        # 除外されない場合が対象ターゲット
        return not should_exclude

    async def _aggregate_contact_scoring(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """
        コンタクトデータを取得してスコアリング項目別に集計（パターン別）
        戻り値: {pattern_type: {owner_id: {metric: count}}}
        """
        # パターンごとの集計データ
        scoring_counts: Dict[str, Dict[str, Dict[str, int]]] = {
            'all': defaultdict(lambda: {
                'industry': 0,
                'property_type': 0,
                'area': 0,
                'area_category': 0,
                'gross': 0,
                'all_five_items': 0,
                'target_audience': 0
            }),
            'buy': defaultdict(lambda: {
                'industry': 0,
                'property_type': 0,
                'area': 0,
                'area_category': 0,
                'gross': 0,
                'all_five_items': 0,
                'target_audience': 0
            }),
            'sell': defaultdict(lambda: {
                'industry': 0,
                'property_type': 0,
                'area': 0,
                'area_category': 0,
                'gross': 0,
                'all_five_items': 0,
                'target_audience': 0
            }),
            'buy_or_sell': defaultdict(lambda: {
                'industry': 0,
                'property_type': 0,
                'area': 0,
                'area_category': 0,
                'gross': 0,
                'all_five_items': 0,
                'target_audience': 0
            })
        }
        
        # 対象担当者IDが空の場合はエラー
        if not TARGET_OWNER_IDS:
            return scoring_counts
        
        # 対象担当者IDを各パターンで初期化
        for pattern_type in ['all', 'buy', 'sell', 'buy_or_sell']:
            for owner_id in TARGET_OWNER_IDS:
                scoring_counts[pattern_type][owner_id] = {
                    'industry': 0,
                    'property_type': 0,
                    'area': 0,
                    'area_category': 0,
                    'gross': 0,
                    'all_five_items': 0,
                    'target_audience': 0
                }
        
        # 集計統計
        stats = {
            "total_contacts": 0,
            "no_owner_id": 0,
            "not_target_owner": 0,
            "successfully_aggregated": 0
        }
        
        # 必要なプロパティを指定
        properties = [
            "hubspot_owner_id",
            "contractor_industry",
            "contractor_property_type",
            "contractor_area",
            "contractor_area_category",
            "contractor_gross2",
            "contractor_buy_or_sell"
        ]
        
        after: Optional[str] = None
        page = 1
        total_contacts = 0
        processed_contacts = 0
        
        while True:
            try:
                response = await self.contacts_client.get_contacts(
                    limit=100,
                    after=after,
                    properties=properties
                )
                
                if not isinstance(response, dict):
                    break
                
                contacts: List[Dict[str, Any]] = response.get("results", [])
                
                if not contacts:
                    break
                
                for contact in contacts:
                    total_contacts += 1
                    # パターンを判定
                    patterns = self._get_contact_patterns(contact)
                    # 各パターンごとに処理
                    for pattern_type in patterns:
                        await self._process_contact(contact, scoring_counts[pattern_type], stats, pattern_type)
                    processed_contacts += 1
                    
                    # 進捗を更新（100件ごと、または最後）
                    if total_contacts % 100 == 0 or (not response.get("paging", {}).get("next")):
                        percentage = int((processed_contacts / max(total_contacts, 1)) * 100) if total_contacts > 0 else 0
                
                paging = response.get("paging", {})
                next_after = paging.get("next", {}).get("after")
                if next_after:
                    after = str(next_after)
                    page += 1
                else:
                    break
                    
            except Exception as e:
                logger.error(f"コンタクト取得中にエラーが発生しました: {str(e)}", exc_info=True)
                break
        
        return scoring_counts

    async def _process_contact(
        self,
        contact: Dict[str, Any],
        scoring_counts: Dict[str, Dict[str, int]],
        stats: Dict[str, int],
        pattern_type: str = 'all'
    ):
        """1件のコンタクトを処理してスコアリング集計に追加"""
        properties = contact.get("properties", {})
        stats["total_contacts"] += 1
        
        # 担当者IDを取得
        owner_id = properties.get("hubspot_owner_id")
        if not owner_id:
            stats["no_owner_id"] += 1
            return
        
        # 対象担当者IDかチェック
        if owner_id not in TARGET_OWNER_IDS:
            stats["not_target_owner"] += 1
            return
        
        # 担当者名を取得（表示用）
        owner_name = self.owners_cache.get(owner_id, owner_id)
        
        # 各項目の入力チェック（空文字列やnullも除外）
        has_industry = bool(properties.get('contractor_industry') and str(properties.get('contractor_industry')).strip())
        has_property_type = bool(properties.get('contractor_property_type') and str(properties.get('contractor_property_type')).strip())
        has_area = bool(properties.get('contractor_area') and str(properties.get('contractor_area')).strip())
        has_area_category = bool(properties.get('contractor_area_category') and str(properties.get('contractor_area_category')).strip())
        has_gross = bool(properties.get('contractor_gross2') and str(properties.get('contractor_gross2')).strip())
        
        # 各項目の集計
        if has_industry:
            scoring_counts[owner_id]['industry'] += 1
        
        if has_property_type:
            scoring_counts[owner_id]['property_type'] += 1
        
        if has_area:
            scoring_counts[owner_id]['area'] += 1
        
        if has_area_category:
            scoring_counts[owner_id]['area_category'] += 1
        
        if has_gross:
            scoring_counts[owner_id]['gross'] += 1
        
        # ５項目すべてに入力がある場合
        if has_industry and has_property_type and has_area and has_area_category and has_gross:
            scoring_counts[owner_id]['all_five_items'] += 1
        
        # 対象ターゲットの判定
        if self._is_target_audience(properties):
            scoring_counts[owner_id]['target_audience'] += 1
        
        stats["successfully_aggregated"] += 1

    async def _save_to_database(
        self,
        aggregation_date: date,
        scoring_counts: Dict[str, Dict[str, Dict[str, int]]]
    ):
        """集計結果をデータベースに保存（パターン別）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 既存のデータを削除（同じ集計日のデータ）
                delete_query = """
                    DELETE FROM contact_scoring_summary
                    WHERE aggregation_date = %s
                """
                await cursor.execute(delete_query, (aggregation_date,))
                deleted_count = cursor.rowcount
                
                # 新しいデータを挿入
                try:
                    insert_query = """
                        INSERT INTO contact_scoring_summary
                        (aggregation_date, owner_id, owner_name, pattern_type, industry_count, property_type_count, 
                         area_count, area_category_count, gross_count, all_five_items_count, target_audience_count)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    insert_count = 0
                    for pattern_type in ['all', 'buy', 'sell', 'buy_or_sell']:
                        pattern_counts = scoring_counts.get(pattern_type, {})
                        for owner_id in TARGET_OWNER_IDS:
                            owner_name = self.owners_cache.get(owner_id, owner_id)
                            counts = pattern_counts.get(owner_id, {
                                'industry': 0,
                                'property_type': 0,
                                'area': 0,
                                'area_category': 0,
                                'gross': 0,
                                'all_five_items': 0,
                                'target_audience': 0
                            })
                            
                            await cursor.execute(
                                insert_query,
                                (
                                    aggregation_date,
                                    owner_id,
                                    owner_name,
                                    pattern_type,
                                    counts['industry'],
                                    counts['property_type'],
                                    counts['area'],
                                    counts['area_category'],
                                    counts['gross'],
                                    counts['all_five_items'],
                                    counts['target_audience']
                                )
                            )
                            insert_count += 1
                    
                    await conn.commit()
                except Exception as e:
                    logger.error(f"データベースへの保存中にエラーが発生しました: {str(e)}", exc_info=True)
                    await conn.rollback()
                    raise


async def main():
    sync = ContactScoringSummarySync()
    await sync.run()


if __name__ == "__main__":
    asyncio.run(main())

