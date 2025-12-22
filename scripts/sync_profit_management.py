#!/usr/bin/env python3
"""
粗利按分管理データ同期バッチ処理スクリプト
1日1回、午前2時に実行される
販売取引の決済日（settlement_date）または契約日（contract_date）が入力されている物件情報を対象に、
HubSpotから粗利按分管理データを取り込む
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from decimal import Decimal

# プロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import db_connection
from hubspot.deals import HubSpotDealsClient
from hubspot.bukken import HubSpotBukkenClient
from hubspot.owners import HubSpotOwnersClient
from services.profit_management_service import ProfitManagementService
from services.property_owner_service import PropertyOwnerService
from models.profit_management import ProfitManagementCreate, ProfitManagementUpdate
from models.property_owner import PropertyOwnerCreate, PropertyOwnerUpdate, OwnerType
from hubspot.config import Config
from utils.update_job_progress import update_progress

# ログ設定
# Docker環境では /app/logs、本番環境では /var/www/mirai-api/logs
if os.path.exists('/app'):
    log_dir = '/app/logs'
else:
    log_dir = '/var/www/mirai-api/logs'
os.makedirs(log_dir, exist_ok=True)

# ログハンドラーのバッファリングを無効化
# FileHandlerはデフォルトでバッファリングされるため、即座にフラッシュするように設定
file_handler = logging.FileHandler(os.path.join(log_dir, 'profit_management_sync.log'))
file_handler.setLevel(logging.INFO)
# 各ログ出力後に即座にフラッシュするカスタムハンドラー
class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

file_handler = FlushingFileHandler(os.path.join(log_dir, 'profit_management_sync.log'))
file_handler.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, stream_handler],
    force=True
)

# httpxのログレベルをWARNINGに設定（HTTP Requestログを削除）
logging.getLogger("httpx").setLevel(logging.WARNING)

# hubspot.dealsのログレベルをWARNINGに設定（INFO/DEBUGログを削除）
logging.getLogger("hubspot.deals").setLevel(logging.WARNING)

# ログの即時フラッシュを有効化
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

logger = logging.getLogger(__name__)

# パイプラインID
PURCHASE_PIPELINE_ID = "675713658"  # 仕入パイプライン
SALES_PIPELINE_ID = "682910274"  # 販売パイプライン

class ProfitManagementSync:
    """粗利按分管理データ同期クラス"""
    
    def __init__(self):
        self.deals_client = HubSpotDealsClient()
        self.bukken_client = HubSpotBukkenClient()
        self.owners_client = HubSpotOwnersClient()
        self.profit_service = None
        self.owner_service = None
        self.owners_cache = {}  # 担当者名のキャッシュ
    
    async def get_sales_deals_with_settlement_or_contract_date(self) -> List[Dict[str, Any]]:
        """販売パイプラインで決済日または契約日が設定されている取引を取得"""
        try:
            all_deals = []
            after = None
            
            # まず、販売パイプラインのすべての取引を取得
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
                    "properties": [
                        "dealname",
                        "dealstage",
                        "pipeline",
                        "settlement_date",
                        "contract_date",
                        "hubspot_owner_id",
                        "sales_sales_price",
                        "research_purchase_price",
                        "final_closing_price",
                        "final_closing_profit"
                    ],
                    "limit": 100
                }
                
                if after:
                    search_criteria["after"] = after
                
                response = await self.deals_client._make_request(
                    "POST",
                    "/crm/v3/objects/deals/search",
                    json=search_criteria
                )
                
                deals = response.get("results", [])
                all_deals.extend(deals)
                
                # ページネーションの確認
                paging = response.get("paging", {})
                if not paging.get("next"):
                    break
                after = paging["next"].get("after")
            
            # settlement_dateまたはcontract_dateが設定されている取引のみをフィルタリング
            filtered_deals = []
            for deal in all_deals:
                properties = deal.get("properties", {})
                settlement_date = properties.get("settlement_date")
                contract_date = properties.get("contract_date")
                if (settlement_date and settlement_date.strip()) or (contract_date and contract_date.strip()):
                    filtered_deals.append(deal)
            
            return filtered_deals
            
        except Exception as e:
            raise
    
    async def get_bukken_from_deal(self, deal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """取引に関連する物件情報を取得"""
        try:
            deal_id = deal.get("id")
            if not deal_id:
                return None
            
            # 取引の関連情報を取得（既存の実装パターンに合わせる）
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
    
    async def get_deals_by_bukken_and_pipeline(self, bukken_id: str, pipeline_id: str) -> List[Dict[str, Any]]:
        """物件に紐づく取引をパイプラインでフィルタリングして取得"""
        try:
            # 物件に紐づく取引を取得
            all_deals = await self.deals_client.get_deals_by_bukken(bukken_id)
            
            # 指定されたパイプラインの取引のみをフィルタリング
            filtered_deals = []
            for deal in all_deals:
                properties = deal.get("properties", {})
                deal_pipeline = properties.get("pipeline")
                if deal_pipeline == pipeline_id:
                    filtered_deals.append(deal)
            
            return filtered_deals
            
        except Exception as e:
            return []
    
    def parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """日付文字列をdateオブジェクトに変換"""
        if not date_str:
            return None
        
        try:
            # HubSpotの日付形式をパース（ミリ秒タイムスタンプまたはISO形式）
            if date_str.isdigit():
                # ミリ秒タイムスタンプ
                timestamp = int(date_str) / 1000
                dt = datetime.fromtimestamp(timestamp)
                return dt.date()
            else:
                # ISO形式の日付文字列
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.date()
        except Exception as e:
            return None
    
    def parse_decimal(self, value: Optional[Any]) -> Optional[Decimal]:
        """数値をDecimalに変換"""
        if value is None or value == "":
            return None
        
        try:
            if isinstance(value, str):
                # カンマを削除
                value = value.replace(",", "")
            return Decimal(str(value))
        except Exception as e:
            return None
    
    async def get_owner_name(self, owner_id: Optional[str]) -> str:
        """担当者IDから担当者名を取得（キャッシュ付き）"""
        if not owner_id:
            return ""
        
        # キャッシュを確認
        if owner_id in self.owners_cache:
            return self.owners_cache[owner_id]
        
        try:
            owner = await self.owners_client.get_owner_by_id(owner_id)
            if owner:
                # HubSpot APIでは firstName=名, lastName=姓 なので、日本の表記（姓 名）にするため順序を逆にする
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
        except Exception as e:
            pass
        
        # 取得に失敗した場合は空文字列を返す
        self.owners_cache[owner_id] = ""
        return ""
    
    async def process_sales_deal(self, sales_deal: Dict[str, Any]) -> bool:
        """販売取引を処理して粗利按分管理データを作成・更新"""
        try:
            deal_id = sales_deal.get("id")
            
            # 物件情報を取得
            bukken = await self.get_bukken_from_deal(sales_deal)
            if not bukken:
                return False
            
            bukken_id = bukken.get("id")
            bukken_properties = bukken.get("properties", {})
            bukken_name = bukken_properties.get("bukken_name", "")
            
            if not bukken_id:
                return False
            
            # 販売取引の情報を取得
            sales_properties = sales_deal.get("properties", {})
            sales_settlement_date_str = sales_properties.get("settlement_date")
            sales_settlement_date = self.parse_date(sales_settlement_date_str)
            sales_contract_date_str = sales_properties.get("contract_date")
            sales_contract_date = self.parse_date(sales_contract_date_str)
            sales_owner_id = sales_properties.get("hubspot_owner_id")
            
            # 販売取引から【最終】販売価格（final_closing_price）を取得
            # なければ取引のsales_sales_priceを使用
            final_closing_price = self.parse_decimal(sales_properties.get("final_closing_price"))
            sales_price = final_closing_price if final_closing_price is not None else self.parse_decimal(sales_properties.get("sales_sales_price"))
            
            # 販売取引から【最終】粗利（final_closing_profit）を取得
            final_closing_profit = self.parse_decimal(sales_properties.get("final_closing_profit"))
            
            # 計上年月を取得（決済日を優先、なければ契約日の年月）
            accounting_year_month = None
            if sales_settlement_date:
                accounting_year_month = date(sales_settlement_date.year, sales_settlement_date.month, 1)
            elif sales_contract_date:
                accounting_year_month = date(sales_contract_date.year, sales_contract_date.month, 1)
            
            # 物件に紐づく仕入取引を取得
            purchase_deals = await self.get_deals_by_bukken_and_pipeline(bukken_id, PURCHASE_PIPELINE_ID)
            
            # 仕入情報を取得（最初の仕入取引から）
            purchase_settlement_date = None
            purchase_price = None
            purchase_owner_id = None
            
            if purchase_deals:
                purchase_deal = purchase_deals[0]
                purchase_properties = purchase_deal.get("properties", {})
                purchase_settlement_date_str = purchase_properties.get("settlement_date")
                purchase_settlement_date = self.parse_date(purchase_settlement_date_str)
                purchase_price = self.parse_decimal(purchase_properties.get("research_purchase_price"))
                purchase_owner_id = purchase_properties.get("hubspot_owner_id")
            
            # 既存の粗利按分管理データを確認（物件番号で重複チェック）
            existing = await self.profit_service.get_profit_management_by_property_id(bukken_id)
            
            if existing:
                # 粗利確定フラグがONの場合は更新しない
                if existing.profit_confirmed:
                    return True
                
                # 更新（編集可能項目は上書きしない）
                
                # 粗利が既に入力されている場合は更新しない
                gross_profit_to_set = None
                if existing.gross_profit is None or existing.gross_profit == 0:
                    # 粗利が未入力または0の場合は、final_closing_profitを設定
                    gross_profit_to_set = final_closing_profit
                # 既に粗利が入力されている場合は更新しない（Noneのまま）
                
                update_data = ProfitManagementUpdate(
                    property_name=bukken_name,
                    # property_type は編集可能項目なので更新しない
                    purchase_settlement_date=purchase_settlement_date,
                    purchase_price=purchase_price,
                    sales_settlement_date=sales_settlement_date,
                    sales_price=sales_price,
                    gross_profit=gross_profit_to_set,  # 粗利が未入力の場合のみ更新
                    profit_confirmed=False,  # OFF
                    accounting_year_month=accounting_year_month
                )
                
                updated = await self.profit_service.update_profit_management(existing.seq_no, update_data)
                if not updated:
                    return False
                
                seq_no = existing.seq_no
            else:
                # 新規作成
                create_data = ProfitManagementCreate(
                    property_id=bukken_id,
                    property_name=bukken_name,
                    property_type=None,  # 空欄
                    purchase_settlement_date=purchase_settlement_date,
                    purchase_price=purchase_price,
                    sales_settlement_date=sales_settlement_date,
                    sales_price=sales_price,
                    gross_profit=final_closing_profit,  # 【最終】粗利を設定
                    profit_confirmed=False,  # OFF
                    accounting_year_month=accounting_year_month
                )
                
                created = await self.profit_service.create_profit_management(create_data)
                if not created:
                    return False
                
                seq_no = created.seq_no
            
            # 物件担当者情報を保存（既存の場合は更新しない）
            # 既存データがある場合は、担当者情報は更新しない
            if not existing:
                try:
                    # 仕入担当者を保存
                    if purchase_owner_id:
                        try:
                            purchase_owner_name = await self.get_owner_name(purchase_owner_id)
                            
                            purchase_owner = PropertyOwnerCreate(
                                property_id=bukken_id,
                                profit_management_seq_no=seq_no,
                                owner_type=OwnerType.PURCHASE,
                                owner_id=purchase_owner_id,
                                owner_name=purchase_owner_name if purchase_owner_name else "",
                                settlement_date=purchase_settlement_date,
                                price=purchase_price,
                                profit_rate=None,  # 空欄
                                profit_amount=None  # 空欄
                            )
                            await self.owner_service.create_property_owner(purchase_owner)
                        except Exception:
                            pass
                    
                    # 販売担当者を保存
                    if sales_owner_id:
                        try:
                            sales_owner_name = await self.get_owner_name(sales_owner_id)
                            
                            sales_owner = PropertyOwnerCreate(
                                property_id=bukken_id,
                                profit_management_seq_no=seq_no,
                                owner_type=OwnerType.SALES,
                                owner_id=sales_owner_id,
                                owner_name=sales_owner_name if sales_owner_name else "",
                                settlement_date=sales_settlement_date,
                                price=sales_price,
                                profit_rate=None,  # 空欄
                                profit_amount=None  # 空欄
                            )
                            await self.owner_service.create_property_owner(sales_owner)
                        except Exception:
                            pass
                except Exception:
                    # 担当者情報の保存に失敗しても、メインデータは保存されているので続行
                    pass
            else:
                # 既存データのため、担当者情報は更新しない
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"取引 {deal.get('id', 'Unknown')} の処理に失敗しました: {str(e)}", exc_info=True)
            return False
    
    async def sync(self):
        """粗利按分管理データを同期"""
        pool_created_by_this_call = False
        try:
            logger.info("粗利按分管理データの同期を開始します")
            
            # データベース接続を確立（既存のプールがない場合のみ作成）
            if not db_connection.pool:
                await db_connection.create_pool()
                pool_created_by_this_call = True
            else:
                pass
            
            # サービスを初期化
            self.profit_service = ProfitManagementService(db_connection.pool)
            self.owner_service = PropertyOwnerService(db_connection.pool)
            
            # 販売パイプラインで決済日または契約日が設定されている取引を取得
            sales_deals = await self.get_sales_deals_with_settlement_or_contract_date()
            
            if not sales_deals:
                logger.info("粗利按分管理データの同期が完了しました: 更新件数=0件")
                await update_progress(None, "完了: 更新件数=0件", 100)
                return
            
            # 各取引を処理
            success_count = 0
            failure_count = 0
            total_deals = len(sales_deals)
            
            for idx, deal in enumerate(sales_deals, 1):
                deal_id = deal.get("id", "Unknown")
                try:
                    if await self.process_sales_deal(deal):
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    logger.error(f"取引処理中にエラーが発生しました (取引ID: {deal.get('id', 'Unknown')}): {str(e)}", exc_info=True)
                    failure_count += 1
                
                # 進捗を更新（10件ごと、または最後）
                if idx % 10 == 0 or idx == total_deals:
                    percentage = int((idx / total_deals) * 100)
                    await update_progress(None, f"処理中: {idx}/{total_deals}件 (成功: {success_count}件, 失敗: {failure_count}件)", percentage)
            
            logger.info(f"粗利按分管理データの同期が完了しました: 成功={success_count}件, 失敗={failure_count}件")
            await update_progress(None, f"完了: 成功={success_count}件, 失敗={failure_count}件", 100)
            
        except Exception as e:
            logger.error(f"粗利按分管理データの同期に失敗しました: {str(e)}", exc_info=True)
            raise
        finally:
            # データベース接続を閉じる（この呼び出しで作成した場合のみ）
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
        sync = ProfitManagementSync()
        await sync.sync()
        
    except Exception as e:
        logger.error(f"バッチ処理中にエラーが発生しました: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

