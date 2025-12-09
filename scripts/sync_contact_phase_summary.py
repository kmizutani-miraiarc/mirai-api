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
logger = logging.getLogger("contact_phase_summary")

# 対象担当者名（姓名）
TARGET_OWNERS = [
    "岩崎 陽",
    "久世 健人",
    "赤瀬 公平",
    "藤森 日加里",
    "藤村 ひかり"
]

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
            
            # コンタクトデータを取得して集計
            phase_counts = await self._aggregate_contact_phases()
            
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
            logger.info(f"担当者キャッシュを読み込みました。件数: {len(self.owners_cache)}")
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
        戻り値: {owner_name: {buy_phase: {sell_phase: count}}}
        """
        phase_counts: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        
        # 対象担当者を初期化
        for owner_name in TARGET_OWNERS:
            phase_counts[owner_name] = defaultdict(lambda: defaultdict(int))
        
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
                    await self._process_contact(contact, phase_counts)
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
        return phase_counts

    async def _process_contact(
        self,
        contact: Dict[str, Any],
        phase_counts: Dict[str, Dict[str, Dict[str, int]]]
    ):
        """1件のコンタクトを処理してフェーズ集計に追加"""
        properties = contact.get("properties", {})
        
        # 担当者IDを取得
        owner_id = properties.get("hubspot_owner_id")
        if not owner_id:
            return
        
        # 担当者名を取得
        owner_name = await self._get_owner_name(owner_id)
        if not owner_name or owner_name not in TARGET_OWNERS:
            return
        
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
            
            # マッピングから変換を試みる（ラベルや値からフェーズ値への変換）
            if phase_value in value_map:
                mapped_value = value_map[phase_value]
                if mapped_value in PHASES:
                    return mapped_value
            
            # ラベルから直接抽出を試みる（例：「S：成約した」→「S」）
            extracted = self._extract_phase_from_label(phase_value)
            if extracted and extracted in PHASES:
                return extracted
            
            # 大文字に変換してチェック
            phase_value_upper = phase_value.upper()
            
            # 有効なフェーズ値かチェック
            if phase_value_upper in PHASES:
                return phase_value_upper
            
            # 無効な値の場合はNone（集計対象外）
            return None
        
        buy_phase = normalize_phase(buy_phase_raw, self.buy_phase_value_map, "buy")
        sell_phase = normalize_phase(sell_phase_raw, self.sell_phase_value_map, "sell")
        
        # デバッグ: 正規化後の値を確認
        if self._debug_count <= 20:
            logger.info(f"  正規化後: buy_phase={buy_phase}, sell_phase={sell_phase}")
        
        # 両方のフェーズが有効な値の場合のみ集計に追加
        # 空欄（None）の場合は集計対象外
        if buy_phase is not None and sell_phase is not None:
            phase_counts[owner_name][buy_phase][sell_phase] += 1
        else:
            # デバッグ: スキップされた理由をログ出力
            if self._debug_count <= 20:
                skip_reason = []
                if buy_phase is None:
                    skip_reason.append("buy_phaseが空欄")
                if sell_phase is None:
                    skip_reason.append("sell_phaseが空欄")
                logger.info(f"  スキップ: {', '.join(skip_reason)}")

    async def _save_to_database(
        self,
        aggregation_date: date,
        phase_counts: Dict[str, Dict[str, Dict[str, int]]]
    ):
        """集計結果をデータベースに保存"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 既存のデータを削除（同じ集計日のデータ）
                delete_query = """
                    DELETE FROM contact_phase_summary
                    WHERE aggregation_date = %s
                """
                await cursor.execute(delete_query, (aggregation_date,))
                deleted_count = cursor.rowcount
                logger.info(f"既存データを削除しました。件数: {deleted_count}")
                
                # 新しいデータを挿入
                insert_query = """
                    INSERT INTO contact_phase_summary
                    (aggregation_date, owner_name, buy_phase, sell_phase, count)
                    VALUES (%s, %s, %s, %s, %s)
                """
                
                insert_count = 0
                for owner_name in TARGET_OWNERS:
                    for buy_phase in PHASES:
                        for sell_phase in PHASES:
                            count = phase_counts[owner_name][buy_phase][sell_phase]
                            if count > 0:
                                await cursor.execute(
                                    insert_query,
                                    (aggregation_date, owner_name, buy_phase, sell_phase, count)
                                )
                                insert_count += 1
                
                await conn.commit()
                logger.info(f"データベースに保存しました。件数: {insert_count}")


async def main():
    sync = ContactPhaseSummarySync()
    await sync.run()


if __name__ == "__main__":
    asyncio.run(main())

