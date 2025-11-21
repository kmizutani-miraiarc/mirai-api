#!/usr/bin/env python3
"""
HubSpotコンタクトの販売バッジ（契約数など）を更新するバッチスクリプト
"""

import asyncio
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, Optional, List

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hubspot.config import Config
from hubspot.deals import HubSpotDealsClient
from hubspot.contacts import HubSpotContactsClient

# ログ設定
log_dir = "/var/www/mirai-api/logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "contact_sales_badge.log"))
    ]
)
logger = logging.getLogger("contact_sales_badge")


SALES_PIPELINE_ID = os.getenv("HUBSPOT_SALES_PIPELINE_ID", "682910274")
DEAL_FETCH_LIMIT = int(os.getenv("HUBSPOT_SALES_BATCH_LIMIT", "100"))
CONTACT_UPDATE_DELAY = float(os.getenv("HUBSPOT_CONTACT_UPDATE_DELAY", "0.2"))

DEAL_PROPERTIES = [
    "dealname",
    "dealstage",
    "pipeline",
    "hubspot_owner_id",
    "createdate",
    "hs_lastmodifieddate",
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


class ContactSalesBadgeUpdater:
    """販売パイプラインの取引を集計し、HubSpotコンタクトのカスタム項目を更新するクラス"""

    def __init__(self):
        self.deals_client = HubSpotDealsClient()
        self.contacts_client = HubSpotContactsClient()
        self.stage_labels: Dict[str, str] = {}
        self.total_deals_processed = 0
        self.contact_counters = defaultdict(lambda: {
            "contact_property_acquisition": 0,  # 物件取得数
            "contact_documents_disclosed": 0,   # 資料開示数
            "contact_surveys_considered": 0,    # 調査検討数
            "contact_purchases": 0,             # 買付取得数
            "contact_probability_b": 0,         # 見込み確度B数
            "contact_probability_a": 0,         # 見込み確度A数
            "contact_contracts": 0,             # 契約数
            "contact_settlement": 0,            # 決済数
            "contact_seeing_off": 0,            # 見送り数
            "contact_lost_order": 0             # 失注数
        })

    async def run(self):
        """バッチ処理のエントリーポイント"""
        if not Config.validate_config():
            logger.error("HubSpot API設定が正しくありません。環境変数HUBSPOT_API_KEYとHUBSPOT_IDを確認してください。")
            return

        logger.info("販売パイプラインのコンタクトバッジ更新を開始します。")
        await self._load_stage_labels()
        await self._aggregate_contact_counts()
        await self._update_contacts()
        logger.info("販売パイプラインのコンタクトバッジ更新が完了しました。")

    async def _load_stage_labels(self):
        """販売パイプラインのステージラベルを取得（ログ用に保持）"""
        stages = await self.deals_client.get_pipeline_stages(SALES_PIPELINE_ID)
        self.stage_labels = {
            stage.get("id"): stage.get("label", "")
            for stage in stages
        }
        logger.info(f"販売パイプライン {SALES_PIPELINE_ID} のステージを {len(self.stage_labels)} 件取得しました。")

    async def _aggregate_contact_counts(self):
        """販売パイプラインの取引を集計して、コンタクトごとの件数を計算"""
        after: Optional[str] = None
        page = 1

        while True:
            search_payload = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "pipeline",
                                "operator": "EQ",
                                "value": SALES_PIPELINE_ID
                            }
                        ]
                    }
                ],
                "properties": DEAL_PROPERTIES,
                "limit": DEAL_FETCH_LIMIT
            }

            if after:
                search_payload["after"] = after

            logger.info(f"販売取引を取得中... page={page}, after={after}")
            response = await self.deals_client.search_deals(search_payload)
            if not isinstance(response, dict):
                logger.warning("検索レスポンスが無効です。処理を終了します。")
                break

            deals: List[Dict[str, Any]] = response.get("results", [])
            logger.info(f"{len(deals)}件の取引を取得しました。")

            if not deals:
                break

            for deal in deals:
                await self._process_deal(deal)

            self.total_deals_processed += len(deals)
            paging = response.get("paging", {})
            next_after = paging.get("next", {}).get("after")
            if next_after:
                after = str(next_after)
                page += 1
            else:
                break

        logger.info(f"販売取引の集計が完了しました。処理対象取引数: {self.total_deals_processed}, "
                    f"カウント対象コンタクト数: {len(self.contact_counters)}")

    async def _process_deal(self, deal: Dict[str, Any]):
        """1件の取引を処理し、日付フィールドの値の有無でコンタクトのカウンターを更新"""
        properties = deal.get("properties", {})
        
        # 販売パイプラインの取引のみを処理
        if properties.get("pipeline") != SALES_PIPELINE_ID:
            return

        contact_ids = await self.deals_client.get_deal_contact_ids(deal.get("id"))
        if not contact_ids:
            logger.debug(f"取引 {deal.get('id')} にはコンタクトの関連がありません。")
            return

        # 日付フィールドの値の有無をチェックしてカウンターを更新
        counters_to_update = set()
        
        # introduction_datetime → contact_property_acquisition
        if properties.get("introduction_datetime"):
            counters_to_update.add("contact_property_acquisition")
        
        # deal_disclosure_date → contact_documents_disclosed
        if properties.get("deal_disclosure_date"):
            counters_to_update.add("contact_documents_disclosed")
        
        # deal_survey_review_date → contact_surveys_considered
        if properties.get("deal_survey_review_date"):
            counters_to_update.add("contact_surveys_considered")
        
        # purchase_date → contact_purchases
        if properties.get("purchase_date"):
            counters_to_update.add("contact_purchases")
        
        # deal_probability_b_date → contact_probability_b
        if properties.get("deal_probability_b_date"):
            counters_to_update.add("contact_probability_b")
        
        # deal_probability_a_date → contact_probability_a
        if properties.get("deal_probability_a_date"):
            counters_to_update.add("contact_probability_a")
        
        # contract_date → contact_contracts
        if properties.get("contract_date"):
            counters_to_update.add("contact_contracts")
        
        # settlement_date → contact_settlement
        if properties.get("settlement_date"):
            counters_to_update.add("contact_settlement")
        
        # deal_farewell_date → contact_seeing_off
        if properties.get("deal_farewell_date"):
            counters_to_update.add("contact_seeing_off")
        
        # deal_lost_date → contact_lost_order
        if properties.get("deal_lost_date"):
            counters_to_update.add("contact_lost_order")

        if not counters_to_update:
            logger.debug(f"取引 {deal.get('id')} には集計対象の日付フィールドがありません。")
            return

        # 関連コンタクトごとにカウンターを更新
        for contact_id in contact_ids:
            stats = self.contact_counters[contact_id]
            for counter_name in counters_to_update:
                stats[counter_name] += 1

        logger.debug(f"取引 {deal.get('id')} を集計しました。 "
                     f"関連コンタクト: {len(contact_ids)}件, 更新カウンター: {counters_to_update}")

    async def _update_contacts(self):
        """集計した結果をHubSpotコンタクトに反映"""
        if not self.contact_counters:
            logger.info("更新対象のコンタクトがありません。")
            return

        updated = 0
        for contact_id, counters in self.contact_counters.items():
            payload = {
                "properties": {
                    "contact_property_acquisition": counters["contact_property_acquisition"],
                    "contact_documents_disclosed": counters["contact_documents_disclosed"],
                    "contact_surveys_considered": counters["contact_surveys_considered"],
                    "contact_purchases": counters["contact_purchases"],
                    "contact_probability_b": counters["contact_probability_b"],
                    "contact_probability_a": counters["contact_probability_a"],
                    "contact_contracts": counters["contact_contracts"],
                    "contact_settlement": counters["contact_settlement"],
                    "contact_seeing_off": counters["contact_seeing_off"],
                    "contact_lost_order": counters["contact_lost_order"]
                }
            }

            try:
                await self.contacts_client.update_contact(contact_id, payload)
                updated += 1
                logger.info(f"コンタクト {contact_id} を更新しました: {payload['properties']}")
                await asyncio.sleep(CONTACT_UPDATE_DELAY)
            except Exception as e:
                logger.error(f"コンタクト {contact_id} の更新に失敗しました: {str(e)}")

        logger.info(f"コンタクトの更新が完了しました。更新件数: {updated}")


async def main():
    updater = ContactSalesBadgeUpdater()
    await updater.run()


if __name__ == "__main__":
    asyncio.run(main())


