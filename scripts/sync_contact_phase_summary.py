#!/usr/bin/env python3
"""
HubSpotコンタクトのフェーズ集計バッチスクリプト
毎週月曜日午前3時に実行され、コンタクトの仕入フェーズ・販売フェーズを集計してDBに保存
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
        logging.FileHandler(os.path.join(log_dir, "contact_phase_summary.log"))
    ]
)

# httpxのログレベルをWARNINGに設定（HTTP Requestログを削除）
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("contact_phase_summary")

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

# フェーズの順序
PHASES = ['S', 'A', 'B', 'C', 'D', 'Z']


class ContactPhaseSummarySync:
    """コンタクトフェーズ集計クラス"""

    def __init__(self):
        self.contacts_client = HubSpotContactsClient()
        self.owners_client = HubSpotOwnersClient()
        self.owners_cache: Dict[str, str] = {}
        self.db_pool = None
        # プロパティ名のキャッシュ（ラベルから内部名へのマッピング）
        self.buy_phase_property_name: Optional[str] = None
        self.sell_phase_property_name: Optional[str] = None
        # プロパティオプションのマッピング（ラベルや値からフェーズ値への変換）
        self.buy_phase_value_map: Dict[str, str] = {}
        self.sell_phase_value_map: Dict[str, str] = {}

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
            logger.info("コンタクトフェーズ集計を開始します。")
            
            # 担当者キャッシュを事前に読み込む
            await self._load_owners_cache()
            
            # プロパティ名をラベルから取得
            await self._load_property_names()
            
            # 今週の月曜日を集計日として取得
            aggregation_date = self._get_this_week_monday()
            logger.info(f"集計日: {aggregation_date}")
            
            # 対象担当者IDが取得できているか確認
            if not TARGET_OWNER_IDS:
                logger.error("対象担当者IDが取得できませんでした。処理を終了します。")
                return
            
            # コンタクトデータを取得して集計
            phase_counts = await self._aggregate_contact_phases()
            
            # 集計結果を確認
            total_count = 0
            for owner_id in TARGET_OWNER_IDS:
                for phase_type in ['buy', 'sell']:
                    for phase_value in PHASES:
                        total_count += phase_counts[owner_id].get(phase_type, {}).get(phase_value, 0)
            
            logger.info(f"集計結果: 合計 {total_count}件")
            
            if total_count == 0:
                logger.warning("集計結果が0件です。データベースへの保存をスキップします。")
                return
            
            # データベースに保存
            await self._save_to_database(aggregation_date, phase_counts)
            
            logger.info("コンタクトフェーズ集計が完了しました。")
        except Exception as e:
            logger.error(f"コンタクトフェーズ集計中にエラーが発生しました: {str(e)}", exc_info=True)
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
            logger.info(f"担当者キャッシュを読み込みました。件数: {len(self.owners_cache)}")
            # デバッグ: 対象担当者のIDと名前をログ出力
            logger.info("=== 対象担当者のIDと名前 ===")
            for owner_id in TARGET_OWNER_IDS:
                owner_name = self.owners_cache.get(owner_id, "不明")
                logger.info(f"  担当者ID: {owner_id}, 担当者名: '{owner_name}'")
            logger.info(f"対象担当者ID数: {len(TARGET_OWNER_IDS)}")
            logger.info("=== 対象担当者のIDと名前終了 ===")
        except Exception as e:
            logger.error(f"担当者キャッシュの読み込みに失敗しました: {str(e)}")

    async def _load_property_names(self):
        """プロパティ名をラベルから取得し、オプションのマッピングも作成"""
        try:
            # 仕入フェーズのプロパティ名を取得
            buy_phase_name = await self.contacts_client.find_property_by_label("仕入フェーズ")
            if buy_phase_name:
                self.buy_phase_property_name = buy_phase_name
                logger.info(f"仕入フェーズのプロパティ名: {buy_phase_name}")
                # オプションを取得してマッピングを作成
                await self._load_buy_phase_options(buy_phase_name)
            else:
                # ラベルが見つからない場合は、デフォルトの名前を試す
                logger.warning("ラベル「仕入フェーズ」のプロパティが見つかりません。デフォルト名を試します。")
                self.buy_phase_property_name = "contractor_buy_phase"
                await self._load_buy_phase_options("contractor_buy_phase")
            
            # 販売フェーズのプロパティ名を取得
            sell_phase_name = await self.contacts_client.find_property_by_label("販売フェーズ")
            if sell_phase_name:
                self.sell_phase_property_name = sell_phase_name
                logger.info(f"販売フェーズのプロパティ名: {sell_phase_name}")
                # オプションを取得してマッピングを作成
                await self._load_sell_phase_options(sell_phase_name)
            else:
                # ラベルが見つからない場合は、デフォルトの名前を試す
                logger.warning("ラベル「販売フェーズ」のプロパティが見つかりません。デフォルト名を試します。")
                self.sell_phase_property_name = "contractor_sell_phase"
                await self._load_sell_phase_options("contractor_sell_phase")
                
        except Exception as e:
            logger.error(f"プロパティ名の取得に失敗しました: {str(e)}")
            # エラーが発生した場合はデフォルト名を使用
            self.buy_phase_property_name = "contractor_buy_phase"
            self.sell_phase_property_name = "contractor_sell_phase"

    async def _load_buy_phase_options(self, property_name: str):
        """仕入フェーズのオプションを取得してマッピングを作成"""
        try:
            options = await self.contacts_client.get_property_options(property_name)
            if options:
                for option in options:
                    label = option.get("label", "")
                    value = option.get("value", "")
                    # ラベルからフェーズ値を抽出（例：「S：成約した（金額OK＋条件OK）」→「S」）
                    phase_value = self._extract_phase_from_label(label)
                    if phase_value:
                        # ラベルと値の両方からマッピングを作成
                        self.buy_phase_value_map[label] = phase_value
                        self.buy_phase_value_map[value] = phase_value
                        logger.debug(f"仕入フェーズマッピング: '{label}' / '{value}' → '{phase_value}'")
                logger.info(f"仕入フェーズのオプションを読み込みました。件数: {len(self.buy_phase_value_map)}")
            else:
                logger.warning(f"仕入フェーズのオプションが取得できませんでした: {property_name}")
        except Exception as e:
            logger.error(f"仕入フェーズのオプション取得に失敗しました: {str(e)}")

    async def _load_sell_phase_options(self, property_name: str):
        """販売フェーズのオプションを取得してマッピングを作成"""
        try:
            options = await self.contacts_client.get_property_options(property_name)
            if options:
                for option in options:
                    label = option.get("label", "")
                    value = option.get("value", "")
                    # ラベルからフェーズ値を抽出（例：「S：成約した」→「S」）
                    phase_value = self._extract_phase_from_label(label)
                    if phase_value:
                        # ラベルと値の両方からマッピングを作成
                        self.sell_phase_value_map[label] = phase_value
                        self.sell_phase_value_map[value] = phase_value
                        logger.debug(f"販売フェーズマッピング: '{label}' / '{value}' → '{phase_value}'")
                logger.info(f"販売フェーズのオプションを読み込みました。件数: {len(self.sell_phase_value_map)}")
            else:
                logger.warning(f"販売フェーズのオプションが取得できませんでした: {property_name}")
        except Exception as e:
            logger.error(f"販売フェーズのオプション取得に失敗しました: {str(e)}")

    def _extract_phase_from_label(self, label: str) -> Optional[str]:
        """ラベルからフェーズ値を抽出（例：「S：成約した（金額OK＋条件OK）」→「S」）"""
        if not label:
            return None
        
        # ラベルの最初の文字がフェーズ値（S, A, B, C, D, Z）かチェック
        label_upper = label.strip().upper()
        if label_upper and label_upper[0] in PHASES:
            return label_upper[0]
        
        # 「S：」のような形式の場合
        if '：' in label or ':' in label:
            parts = label.split('：') if '：' in label else label.split(':')
            if parts and parts[0].strip().upper() in PHASES:
                return parts[0].strip().upper()
        
        return None

    async def _get_owner_name(self, owner_id: Optional[str]) -> Optional[str]:
        """担当者IDから担当者名を取得（キャッシュ付き）"""
        if not owner_id:
            return None
        
        # キャッシュを確認
        if owner_id in self.owners_cache:
            return self.owners_cache[owner_id]
        
        try:
            owner = await self.owners_client.get_owner_by_id(owner_id)
            if owner:
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
                return owner_name
            else:
                # 担当者が見つからない場合（404など）はキャッシュにNoneを保存
                self.owners_cache[owner_id] = None
                return None
        except Exception as e:
            # 404エラー（担当者が存在しない）は無視（ログ出力しない）
            # その他のエラーのみ警告を出力
            error_str = str(e)
            if "404" not in error_str and "not found" not in error_str.lower():
                logger.warning(f"担当者 {owner_id} の名前取得に失敗しました: {error_str}")
            # 存在しない担当者もキャッシュに保存して、再度APIを呼ばないようにする
            self.owners_cache[owner_id] = None
        
        return None

    async def _aggregate_contact_phases(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """
        コンタクトデータを取得してフェーズ別に集計
        戻り値: {owner_id: {phase_type: {phase_value: count}}}
        phase_type: 'buy' または 'sell'
        phase_value: 'S', 'A', 'B', 'C', 'D', 'Z'（空欄の場合は集計しない）
        """
        phase_counts: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        
        # 対象担当者IDが空の場合はエラー
        if not TARGET_OWNER_IDS:
            logger.error("対象担当者IDが取得できませんでした。担当者キャッシュの読み込みを確認してください。")
            return phase_counts
        
        logger.info(f"対象担当者ID数: {len(TARGET_OWNER_IDS)}")
        
        # 対象担当者IDを初期化
        for owner_id in TARGET_OWNER_IDS:
            phase_counts[owner_id]['buy'] = defaultdict(int)
            phase_counts[owner_id]['sell'] = defaultdict(int)
        
        # 集計統計
        stats = {
            "total_contacts": 0,
            "no_owner_id": 0,
            "owner_not_found": 0,
            "not_target_owner": 0,
            "no_buy_phase": 0,
            "no_sell_phase": 0,
            "both_phases_missing": 0,
            "successfully_aggregated": 0
        }
        
        # 必要なプロパティを指定（プロパティ名が確定している場合はそれを使用）
        properties = ["hubspot_owner_id"]
        if self.buy_phase_property_name:
            properties.append(self.buy_phase_property_name)
        else:
            properties.append("contractor_buy_phase")
        if self.sell_phase_property_name:
            properties.append(self.sell_phase_property_name)
        else:
            properties.append("contractor_sell_phase")
        
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
                    logger.warning("検索レスポンスが無効です。処理を終了します。")
                    break
                
                contacts: List[Dict[str, Any]] = response.get("results", [])
                logger.info(f"{len(contacts)}件のコンタクトを取得しました。 (page={page})")
                
                if not contacts:
                    break
                
                # デバッグ: 最初のコンタクトのサンプルデータをログ出力
                if page == 1 and contacts:
                    sample_contact = contacts[0]
                    sample_properties = sample_contact.get("properties", {})
                    logger.info(f"サンプルコンタクトのプロパティ一覧: {list(sample_properties.keys())}")
                    logger.info(f"contractor_buy_phase: {sample_properties.get('contractor_buy_phase')} (type: {type(sample_properties.get('contractor_buy_phase'))})")
                    logger.info(f"contractor_sell_phase: {sample_properties.get('contractor_sell_phase')} (type: {type(sample_properties.get('contractor_sell_phase'))})")
                    
                    # フェーズ関連のプロパティをすべて確認
                    phase_properties = {k: v for k, v in sample_properties.items() if 'phase' in k.lower() or 'buy' in k.lower() or 'sell' in k.lower()}
                    logger.info(f"フェーズ関連プロパティ: {phase_properties}")
                    
                    # すべてのプロパティの値を確認（最初の10件）
                    logger.info(f"すべてのプロパティ（最初の10件）: {dict(list(sample_properties.items())[:10])}")
                
                for contact in contacts:
                    total_contacts += 1
                    await self._process_contact(contact, phase_counts, stats)
                    processed_contacts += 1
                
                paging = response.get("paging", {})
                next_after = paging.get("next", {}).get("after")
                if next_after:
                    after = str(next_after)
                    page += 1
                else:
                    break
                    
            except Exception as e:
                logger.error(f"コンタクト取得中にエラーが発生しました: {str(e)}")
                break
        
        logger.info(f"コンタクトの集計が完了しました。総件数: {total_contacts}, 処理件数: {processed_contacts}")
        logger.info("=" * 80)
        logger.info("集計統計:")
        logger.info(f"  - 総コンタクト数: {total_contacts:,}件")
        logger.info(f"  - 処理済みコンタクト数: {processed_contacts:,}件")
        logger.info("")
        logger.info("スキップ理由:")
        logger.info(f"  - 担当者IDなし: {stats.get('no_owner_id', 0):,}件")
        logger.info(f"  - 対象外担当者: {stats.get('not_target_owner', 0):,}件")
        logger.info(f"  - 仕入フェーズなし: {stats.get('no_buy_phase', 0):,}件")
        logger.info(f"  - 販売フェーズなし: {stats.get('no_sell_phase', 0):,}件")
        logger.info(f"  - 両方のフェーズなし: {stats.get('both_phases_missing', 0):,}件")
        logger.info("")
        logger.info(f"  - 集計成功: {stats.get('successfully_aggregated', 0):,}件")
        logger.info("")
        # 検証: 合計が一致するか確認
        total_skipped = (
            stats.get('no_owner_id', 0) +
            stats.get('not_target_owner', 0) +
            stats.get('no_buy_phase', 0) +
            stats.get('no_sell_phase', 0) +
            stats.get('both_phases_missing', 0)
        )
        total_processed = total_skipped + stats.get('successfully_aggregated', 0)
        logger.info(f"検証: スキップ合計 {total_skipped:,}件 + 集計成功 {stats.get('successfully_aggregated', 0):,}件 = {total_processed:,}件")
        if total_processed != total_contacts:
            logger.warning(f"⚠️  警告: 処理済み件数 ({total_processed:,}) と総件数 ({total_contacts:,}) が一致しません！")
        else:
            logger.info(f"✓ 検証OK: 処理済み件数と総件数が一致しています")
        logger.info("=" * 80)
        
        # 集計結果のサマリーをログ出力
        logger.info("=== 集計結果サマリー（集計後） ===")
        total_aggregated = 0
        for owner_id in TARGET_OWNER_IDS:
            owner_name = self.owners_cache.get(owner_id, owner_id)
            owner_total = 0
            for phase_type in ['buy', 'sell']:
                for phase_value in PHASES:
                    owner_total += phase_counts[owner_id].get(phase_type, {}).get(phase_value, 0)
            total_aggregated += owner_total
            if owner_total > 0:
                logger.info(f"担当者: {owner_name} (ID: {owner_id}) - 合計 {owner_total}件")
        logger.info(f"全体の集計件数: {total_aggregated}件")
        logger.info("=== 集計結果サマリー終了 ===")
        
        return phase_counts

    async def _process_contact(
        self,
        contact: Dict[str, Any],
        phase_counts: Dict[str, Dict[str, Dict[str, int]]],
        stats: Dict[str, int]
    ):
        """1件のコンタクトを処理してフェーズ集計に追加"""
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
            # デバッグ: 対象外担当者の場合（最初の数件のみ）
            if not hasattr(self, '_debug_owner_count'):
                self._debug_owner_count = 0
            if self._debug_owner_count < 10:
                owner_name = self.owners_cache.get(owner_id, "不明")
                logger.debug(f"コンタクト {contact.get('id', 'unknown')}: 対象外担当者 '{owner_name}' (ID: {owner_id})")
                self._debug_owner_count += 1
            return
        
        # 担当者名を取得（表示用）
        owner_name = self.owners_cache.get(owner_id, owner_id)
        
        # フェーズを取得（ラベルから取得したプロパティ名を使用）
        buy_phase_raw = None
        if self.buy_phase_property_name:
            buy_phase_raw = properties.get(self.buy_phase_property_name)
        # フォールバック: 複数のプロパティ名の可能性を試す
        if not buy_phase_raw:
            buy_phase_raw = (
                properties.get("contractor_buy_phase") or
                properties.get("buy_phase") or
                None
            )
        
        sell_phase_raw = None
        if self.sell_phase_property_name:
            sell_phase_raw = properties.get(self.sell_phase_property_name)
        # フォールバック: 複数のプロパティ名の可能性を試す
        if not sell_phase_raw:
            sell_phase_raw = (
                properties.get("contractor_sell_phase") or
                properties.get("sell_phase") or
                None
            )
        
        # デバッグ: 最初の数件だけログ出力
        contact_id = contact.get("id", "unknown")
        if not hasattr(self, '_debug_count'):
            self._debug_count = 0
        
        if self._debug_count < 20:
            logger.info(f"コンタクト {contact_id}: buy_phase_raw={buy_phase_raw} (type: {type(buy_phase_raw)}), sell_phase_raw={sell_phase_raw} (type: {type(sell_phase_raw)}), owner={owner_name}")
            # フェーズ関連のプロパティをすべて確認
            phase_props = {k: v for k, v in properties.items() if 'phase' in k.lower() or 'buy' in k.lower() or 'sell' in k.lower()}
            if phase_props:
                logger.info(f"  フェーズ関連プロパティ: {phase_props}")
            self._debug_count += 1
        
        # フェーズ値を正規化（空欄の場合はNoneを返す）
        def normalize_phase(phase_value, value_map: Dict[str, str], phase_type: str):
            """フェーズ値を正規化（S, A, B, C, D, Zのいずれかに変換、空欄の場合はNone）"""
            if not phase_value:
                return None  # 空欄の場合はNoneを返す（集計対象外）
            
            # 文字列に変換
            if isinstance(phase_value, (int, float)):
                phase_value = str(phase_value)
            elif not isinstance(phase_value, str):
                return None  # 文字列でない場合はNone
            
            # 空白を除去
            phase_value = phase_value.strip()
            
            # 空文字列の場合はNone
            if not phase_value:
                return None
            
            # まず大文字に変換してチェック（最もシンプルなケース）
            phase_value_upper = phase_value.upper()
            if phase_value_upper in PHASES:
                return phase_value_upper
            
            # マッピングから変換を試みる（ラベルや値からフェーズ値への変換）
            if phase_value in value_map:
                mapped_value = value_map[phase_value]
                if mapped_value in PHASES:
                    return mapped_value
            
            # 大文字に変換した値もマッピングをチェック
            if phase_value_upper in value_map:
                mapped_value = value_map[phase_value_upper]
                if mapped_value in PHASES:
                    return mapped_value
            
            # ラベルから直接抽出を試みる（例：「S：成約した」→「S」）
            extracted = self._extract_phase_from_label(phase_value)
            if extracted and extracted in PHASES:
                return extracted
            
            # 無効な値の場合はNone（集計対象外）
            # デバッグ: 正規化できなかった値をログ出力（特定の担当者の場合）
            if owner_name == "岩崎 陽" and phase_type == "buy":
                logger.warning(f"  フェーズ正規化失敗: {phase_type}_phase_raw='{phase_value}' (type: {type(phase_value)}) を正規化できませんでした。")
            return None
        
        buy_phase = normalize_phase(buy_phase_raw, self.buy_phase_value_map, "buy")
        sell_phase = normalize_phase(sell_phase_raw, self.sell_phase_value_map, "sell")
        
        # デバッグ: 正規化後の値を確認
        if self._debug_count <= 20:
            logger.info(f"  正規化後: buy_phase={buy_phase}, sell_phase={sell_phase}")
        
        # どちらか一方でも有効な値があれば集計対象にする
        # 空欄（None）のフェーズは無視する（カウントしない）
        if buy_phase is None and sell_phase is None:
            # 両方とも空欄の場合は集計対象外
            stats["both_phases_missing"] += 1
            if owner_name == "岩崎 陽":
                logger.info(f"  スキップ: コンタクト {contact_id} - buy_phaseが空欄 (raw: {buy_phase_raw}), sell_phaseが空欄 (raw: {sell_phase_raw})")
        else:
            # どちらか一方でも有効な値があれば集計
            # 空欄のフェーズは無視する（集計しない）
            
            # 仕入フェーズが有効な場合：仕入フェーズを集計
            if buy_phase is not None:
                phase_counts[owner_id]['buy'][buy_phase] += 1
                stats["successfully_aggregated"] += 1
                if owner_name == "岩崎 陽" and buy_phase == "S":
                    logger.info(f"  集計: コンタクト {contact_id} - 担当者: {owner_name} (ID: {owner_id}), 仕入フェーズ: {buy_phase}")
            
            # 販売フェーズが有効な場合：販売フェーズを集計
            if sell_phase is not None:
                phase_counts[owner_id]['sell'][sell_phase] += 1
                stats["successfully_aggregated"] += 1
                if owner_name == "岩崎 陽" and sell_phase == "S":
                    logger.info(f"  集計: コンタクト {contact_id} - 担当者: {owner_name} (ID: {owner_id}), 販売フェーズ: {sell_phase}")
            
            # 統計を更新（空欄のフェーズがある場合）
            if buy_phase is None:
                stats["no_buy_phase"] += 1
            if sell_phase is None:
                stats["no_sell_phase"] += 1

    async def _save_to_database(
        self,
        aggregation_date: date,
        phase_counts: Dict[str, Dict[str, Dict[str, int]]]
    ):
        """集計結果をデータベースに保存"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 既存のデータを削除（同じ集計日のデータ）
                delete_query = """
                    DELETE FROM contact_phase_summary
                    WHERE aggregation_date = %s
                """
                await cursor.execute(delete_query, (aggregation_date,))
                deleted_count = cursor.rowcount
                logger.info(f"既存データを削除しました。件数: {deleted_count}")
                
                # 新しいデータを挿入
                try:
                    insert_query = """
                        INSERT INTO contact_phase_summary
                        (aggregation_date, owner_id, owner_name, phase_type, phase_value, count)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    
                    insert_count = 0
                    for owner_id in TARGET_OWNER_IDS:
                        owner_name = self.owners_cache.get(owner_id, owner_id)
                        # phase_type: 'buy' または 'sell'
                        for phase_type in ['buy', 'sell']:
                            # phase_value: 'S', 'A', 'B', 'C', 'D', 'Z'
                            for phase_value in PHASES:
                                count = phase_counts[owner_id].get(phase_type, {}).get(phase_value, 0)
                                if count > 0:
                                    await cursor.execute(
                                        insert_query,
                                        (aggregation_date, owner_id, owner_name, phase_type, phase_value, count)
                                    )
                                    insert_count += 1
                    
                    await conn.commit()
                    logger.info(f"データベースに保存しました。件数: {insert_count}")
                except Exception as e:
                    logger.error(f"データベースへの保存中にエラーが発生しました: {str(e)}", exc_info=True)
                    await conn.rollback()
                    raise
                
                # 集計結果のサマリーをログ出力
                logger.info("=== 集計結果サマリー ===")
                for owner_id in TARGET_OWNER_IDS:
                    owner_name = self.owners_cache.get(owner_id, owner_id)
                    logger.info(f"担当者: {owner_name} (ID: {owner_id})")
                    for phase_type in ['buy', 'sell']:
                        phase_type_display = "仕入" if phase_type == 'buy' else "販売"
                        phase_dict = phase_counts[owner_id].get(phase_type, {})
                        total = sum(phase_dict.values())
                        if total > 0:
                            logger.info(f"  {phase_type_display}フェーズ: 合計 {total}件")
                            for phase_value in PHASES:
                                count = phase_dict.get(phase_value, 0)
                                if count > 0:
                                    logger.info(f"    - {phase_value}: {count}件")
                logger.info("=== 集計結果サマリー終了 ===")


async def main():
    sync = ContactPhaseSummarySync()
    await sync.run()


if __name__ == "__main__":
    asyncio.run(main())

