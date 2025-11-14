#!/usr/bin/env python3
"""
HubSpotコンタクトの販売バッジ（契約数など）を更新するバッチスクリプト
"""

import asyncio
import logging
import os
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

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
    "hs_lastmodifieddate"
]


class ContactSalesBadgeUpdater:
    """販売パイプラインの取引を集計し、HubSpotコンタクトのカスタム項目を更新するクラス"""

    def __init__(self):
        self.deals_client = HubSpotDealsClient()
        self.contacts_client = HubSpotContactsClient()
        self.stage_labels: Dict[str, str] = {}
        self.total_deals_processed = 0
        self.contact_counters = defaultdict(lambda: {
            "contact_contracts": 0,
            "contact_purchases": 0,
            "contact_surveys_considered": 0,
            "contact_documents_disclosed": 0
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
        """販売パイプラインのステージラベルを取得"""
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
        """1件の取引を処理し、ステージに応じてコンタクトのカウンターを更新"""
        properties = deal.get("properties", {})
        if properties.get("pipeline") != SALES_PIPELINE_ID:
            return

        stage_id = properties.get("dealstage")
        stage_label = self.stage_labels.get(stage_id, "")
        counters = self._determine_counters(stage_label)

        if not counters:
            logger.debug(f"ステージ {stage_label} は集計対象外です (deal_id={deal.get('id')}).")
            return

        contact_ids = await self.deals_client.get_deal_contact_ids(deal.get("id"))
        if not contact_ids:
            logger.info(f"取引 {deal.get('id')} にはコンタクトの関連がありません。")
            return

        for contact_id in contact_ids:
            stats = self.contact_counters[contact_id]
            for counter_name in counters:
                stats[counter_name] += 1

        logger.debug(f"取引 {deal.get('id')} のステージ '{stage_label}' を集計しました。 "
                     f"関連コンタクト: {len(contact_ids)}件, カウンター: {counters}")

    def _determine_counters(self, stage_label: Optional[str]) -> Set[str]:
        """ステージラベルから更新すべきカウンターを判定"""
        if not stage_label:
            return set()

        normalized = unicodedata.normalize("NFKC", stage_label)
        label = normalized.lower()
        compact = label.replace(" ", "").replace("　", "")

        contract_keywords = ["契約", "決済"]
        purchase_keywords = ["見込み確度A", "見込み確度B", "買付取得"]
        survey_keywords = ["調査/検討"]
        disclosure_keywords = ["資料開示", "物件紹介"]

        if any(keyword in compact for keyword in contract_keywords):
            return {
                "contact_contracts",
                "contact_purchases",
                "contact_surveys_considered",
                "contact_documents_disclosed"
            }

        if any(keyword in compact for keyword in purchase_keywords):
            return {
                "contact_purchases",
                "contact_surveys_considered",
                "contact_documents_disclosed"
            }

        if any(keyword in compact for keyword in survey_keywords):
            return {
                "contact_surveys_considered",
                "contact_documents_disclosed"
            }

        if any(keyword in compact for keyword in disclosure_keywords):
            return {"contact_documents_disclosed"}

        return set()

    async def _update_contacts(self):
        """集計した結果をHubSpotコンタクトに反映"""
        if not self.contact_counters:
            logger.info("更新対象のコンタクトがありません。")
            return

        updated = 0
        for contact_id, counters in self.contact_counters.items():
            payload = {
                "properties": {
                    "contact_contracts": counters["contact_contracts"],
                    "contact_purchases": counters["contact_purchases"],
                    "contact_surveys_considered": counters["contact_surveys_considered"],
                    "contact_documents_disclosed": counters["contact_documents_disclosed"]
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


