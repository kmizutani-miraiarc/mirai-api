#!/usr/bin/env python3
"""
物件買取実績同期バッチ処理スクリプト
1日1回、午前3時に実行される
仕入パイプラインの「決済」または「契約」ステージの取引を取得し、物件情報をMySQLに保存
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_connection
from hubspot.deals import HubSpotDealsClient
from hubspot.bukken import HubSpotBukkenClient
from services.purchase_achievement_service import PurchaseAchievementService
from models.purchase_achievement import PurchaseAchievementCreate, PurchaseAchievementUpdate
from hubspot.config import Config
from utils.update_job_progress import update_progress

# ログ設定
log_dir = '/var/www/mirai-api/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'purchase_achievements_sync.log')),
        logging.StreamHandler()
    ]
)

# httpxのログレベルをWARNINGに設定（HTTP Requestログを削除）
logging.getLogger("httpx").setLevel(logging.WARNING)

# hubspot.dealsのログレベルをWARNINGに設定（INFO/DEBUGログを削除）
logging.getLogger("hubspot.deals").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# 仕入パイプラインID
PURCHASE_PIPELINE_ID = "675713658"

class PurchaseAchievementsSync:
    """物件買取実績同期クラス"""
    
    def __init__(self):
        self.deals_client = HubSpotDealsClient()
        self.bukken_client = HubSpotBukkenClient()
        self.achievement_service = PurchaseAchievementService()
        self.settlement_stage_ids = []
        self.contract_stage_ids = []
    
    async def get_target_stage_ids(self) -> tuple[List[str], List[str]]:
        """「決済」と「契約」ステージのIDを取得"""
        try:
            stages = await self.deals_client.get_pipeline_stages(PURCHASE_PIPELINE_ID)
            
            settlement_ids = []
            contract_ids = []
            
            for stage in stages:
                stage_label = stage.get("label", "").lower()
                stage_id = stage.get("id")
                
                # 「決済」または「settlement」を含むステージ
                if "決済" in stage_label or "settlement" in stage_label:
                    settlement_ids.append(stage_id)
                
                # 「契約」または「contract」を含むステージ
                if "契約" in stage_label or "contract" in stage_label:
                    contract_ids.append(stage_id)
            
            return settlement_ids, contract_ids
            
        except Exception as e:
            logger.error(f"ステージIDの取得に失敗しました: {str(e)}", exc_info=True)
            raise
    
    async def get_deals_by_stages(self, stage_ids: List[str]) -> List[Dict[str, Any]]:
        """指定されたステージの取引を取得"""
        try:
            all_deals = []
            
            for stage_id in stage_ids:
                search_criteria = {
                    "filterGroups": [{
                        "filters": [
                            {
                                "propertyName": "pipeline",
                                "operator": "EQ",
                                "value": PURCHASE_PIPELINE_ID
                            },
                            {
                                "propertyName": "dealstage",
                                "operator": "EQ",
                                "value": stage_id
                            }
                        ]
                    }],
                    "properties": [
                        "dealname",
                        "dealstage",
                        "pipeline",
                        "createdate",
                        "hs_createdate",
                        "settlement_date",
                        "contract_date",
                        "purchase_date"
                    ],
                    "limit": 100
                }
                
                # ページネーションで全取引を取得
                after = None
                while True:
                    if after:
                        search_criteria["after"] = after
                    
                    result = await self.deals_client.search_deals(search_criteria)
                    deals = result.get("results", [])
                    
                    if not deals:
                        break
                    
                    all_deals.extend(deals)
                    
                    paging = result.get("paging", {})
                    if not paging.get("next"):
                        break
                    after = paging["next"].get("after")
            
            return all_deals
            
        except Exception as e:
            logger.error(f"取引の取得に失敗しました: {str(e)}", exc_info=True)
            raise
    
    async def get_bukken_from_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """取引に関連する物件情報を取得"""
        try:
            # 取引の関連情報を取得
            deal_with_associations = await self.deals_client.get_deal_by_id_with_associations(deal_id)
            if not deal_with_associations:
                return None
            
            associations = deal_with_associations.get("associations", {})
            bukken_list = associations.get("2-39155607", [])  # 物件オブジェクトタイプID
            
            if not bukken_list:
                return None
            
            # 最初の物件を取得
            bukken = bukken_list[0]
            bukken_id = bukken.get("id")
            
            if not bukken_id:
                return None
            
            # 物件の詳細情報を取得
            bukken_detail = await self.bukken_client.get_bukken_by_id(bukken_id)
            
            if not bukken_detail:
                return None
            
            return bukken_detail
            
        except Exception as e:
            return None
    
    def extract_purchase_date(self, deal: Dict[str, Any]) -> Optional[date]:
        """取引から買取日を抽出"""
        try:
            properties = deal.get("properties", {})
            
            # 決済日を優先
            settlement_date = properties.get("settlement_date")
            if settlement_date:
                try:
                    # HubSpotの日付形式を変換
                    dt = datetime.fromtimestamp(int(settlement_date) / 1000)
                    return dt.date()
                except:
                    pass
            
            # 契約日
            contract_date = properties.get("contract_date")
            if contract_date:
                try:
                    dt = datetime.fromtimestamp(int(contract_date) / 1000)
                    return dt.date()
                except:
                    pass
            
            # 買取日
            purchase_date = properties.get("purchase_date")
            if purchase_date:
                try:
                    dt = datetime.fromtimestamp(int(purchase_date) / 1000)
                    return dt.date()
                except:
                    pass
            
            # 取引の作成日
            createdate = properties.get("createdate")
            if createdate:
                try:
                    dt = datetime.fromtimestamp(int(createdate) / 1000)
                    return dt.date()
                except:
                    pass
            
            return None
            
        except Exception as e:
            return None
    
    def create_title(self, bukken: Dict[str, Any]) -> str:
        """物件情報からタイトルを生成"""
        try:
            properties = bukken.get("properties", {})
            
            state = properties.get("bukken_state", "")
            city = properties.get("bukken_city", "")
            name = properties.get("bukken_name", "")
            
            if state and city:
                if name:
                    return f"{state}{city}{name}"
                else:
                    return f"{state}{city}一棟アパート"
            elif name:
                return name
            else:
                return "物件情報"
                
        except Exception as e:
            return "物件情報"
    
    async def process_deal(self, deal: Dict[str, Any]) -> bool:
        """取引を処理して物件買取実績を保存"""
        try:
            deal_id = deal.get("id")
            deal_properties = deal.get("properties", {})
            
            # 物件情報を取得
            bukken = await self.get_bukken_from_deal(deal_id)
            if not bukken:
                return False
            
            bukken_id = bukken.get("id")
            bukken_properties = bukken.get("properties", {})
            
            # 既に取り込み済みかチェック（hubspot_bukken_idで照合）
            existing = await self.achievement_service.get_by_bukken_id(bukken_id)
            
            if existing:
                # 既存の物件がある場合は、HubSpotから取得できる項目のみを更新
                # 既に取り込み済みのため更新処理を実行
                
                # 築年数の処理
                building_age = None
                if bukken_properties.get("bukken_age"):
                    try:
                        building_age = int(bukken_properties.get("bukken_age"))
                    except (ValueError, TypeError):
                        pass
                
                # 更新対象の項目のみを含むUpdateモデルを作成
                # HubSpotから取得できる項目のみ更新（物件名、都道府県、市区町村、番地以下、築年数、最寄り）
                update_data = PurchaseAchievementUpdate(
                    property_name=bukken_properties.get("bukken_name"),
                    building_age=building_age,
                    nearest_station=bukken_properties.get("bukken_nearest_station") or bukken_properties.get("nearest_station"),
                    prefecture=bukken_properties.get("bukken_state"),
                    city=bukken_properties.get("bukken_city"),
                    address_detail=bukken_properties.get("bukken_address")
                )
                
                # 更新処理を実行
                success = await self.achievement_service.update(existing.get("id"), update_data)
                if success:
                    return True
                else:
                    return False
            
            # 買取日を取得
            purchase_date = self.extract_purchase_date(deal)
            
            # タイトルを生成
            title = self.create_title(bukken)
            
            # 物件買取実績を作成
            # 築年数の処理
            building_age = None
            if bukken_properties.get("bukken_age"):
                try:
                    building_age = int(bukken_properties.get("bukken_age"))
                except (ValueError, TypeError):
                    pass
            
            # 物件登録日の処理
            bukken_created_date = None
            if bukken.get("createdAt"):
                try:
                    bukken_created_date = datetime.fromtimestamp(int(bukken.get("createdAt")) / 1000)
                except (ValueError, TypeError):
                    pass
            
            achievement = PurchaseAchievementCreate(
                property_image_url=bukken_properties.get("bukken_image_url") or bukken_properties.get("property_image_url"),  # 物件画像URL
                purchase_date=purchase_date,
                title=title,
                property_name=bukken_properties.get("bukken_name"),
                building_age=building_age,
                structure=bukken_properties.get("bukken_structure"),
                nearest_station=bukken_properties.get("bukken_nearest_station") or bukken_properties.get("nearest_station"),  # 最寄り駅
                prefecture=bukken_properties.get("bukken_state"),  # 都道府県
                city=bukken_properties.get("bukken_city"),  # 市区町村
                address_detail=bukken_properties.get("bukken_address"),  # 番地以下
                hubspot_bukken_id=bukken_id,
                hubspot_bukken_created_date=bukken_created_date,
                hubspot_deal_id=deal_id,
                is_public=False  # デフォルトは非公開
            )
            
            # データベースに保存（upsert）
            achievement_id = await self.achievement_service.upsert(achievement)
            
            return True
            
        except Exception as e:
            logger.error(f"取引 {deal.get('id', 'Unknown')} の処理に失敗しました: {str(e)}", exc_info=True)
            return False
    
    async def sync(self):
        """物件買取実績を同期"""
        pool_created_by_this_call = False
        try:
            logger.info("物件買取実績の同期を開始します")
            
            # データベース接続を確立（既存のプールがない場合のみ作成）
            if not db_connection.pool:
                await db_connection.create_pool()
                pool_created_by_this_call = True
            else:
                pass
            
            # ステージIDを取得
            settlement_ids, contract_ids = await self.get_target_stage_ids()
            target_stage_ids = settlement_ids + contract_ids
            
            if not target_stage_ids:
                logger.info("物件買取実績の同期が完了しました: 更新件数=0件")
                try:
                    await update_progress(None, "完了: 更新件数=0件", 100)
                except Exception as e:
                    logger.error(f"進捗更新中にエラーが発生しました: {str(e)}", exc_info=True)
                return
            
            # 取引を取得
            deals = await self.get_deals_by_stages(target_stage_ids)
            
            if not deals:
                logger.info("物件買取実績の同期が完了しました: 更新件数=0件")
                try:
                    await update_progress(None, "完了: 更新件数=0件", 100)
                except Exception as e:
                    logger.error(f"進捗更新中にエラーが発生しました: {str(e)}", exc_info=True)
                return
            
            # 各取引を処理
            success_count = 0
            failure_count = 0
            total_deals = len(deals)
            
            for idx, deal in enumerate(deals, 1):
                try:
                    if await self.process_deal(deal):
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    logger.error(f"取引処理中にエラーが発生しました: {str(e)}", exc_info=True)
                    failure_count += 1
                
                # 進捗を更新（10件ごと、または最後）
                if idx % 10 == 0 or idx == total_deals:
                    percentage = int((idx / total_deals) * 100)
                    try:
                        await update_progress(None, f"処理中: {idx}/{total_deals}件 (成功: {success_count}件, 失敗: {failure_count}件)", percentage)
                    except Exception as e:
                        logger.error(f"進捗更新中にエラーが発生しました: {str(e)}", exc_info=True)
            
            logger.info(f"物件買取実績の同期が完了しました: 成功={success_count}件, 失敗={failure_count}件")
            try:
                await update_progress(None, f"完了: 成功={success_count}件, 失敗={failure_count}件", 100)
            except Exception as e:
                logger.error(f"進捗更新中にエラーが発生しました: {str(e)}", exc_info=True)
            
        except Exception as e:
            logger.error(f"物件買取実績の同期に失敗しました: {str(e)}")
            raise
        finally:
            # データベース接続を閉じる（この呼び出しで作成した場合のみ）
            # APIエンドポイントから呼び出された場合は、既存の接続プールを閉じない
            if pool_created_by_this_call and db_connection.pool:
                await db_connection.close_pool()
            else:
                pass

async def main():
    """メイン関数"""
    try:
        # HubSpot設定の検証
        if not Config.validate_config():
            logger.error("HubSpot API設定が正しくありません")
            sys.exit(1)
        
        # 同期処理を実行
        sync = PurchaseAchievementsSync()
        await sync.sync()
        
    except Exception as e:
        logger.error(f"バッチ処理中にエラーが発生しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

