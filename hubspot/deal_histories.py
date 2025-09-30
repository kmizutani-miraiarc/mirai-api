import asyncio
import httpx
import logging
from typing import Dict, Any, List, Optional
from .client import HubSpotBaseClient

# ロガー設定
logger = logging.getLogger(__name__)

class HubSpotDealHistoriesClient(HubSpotBaseClient):
    """HubSpot deal_historiesカスタムオブジェクトAPIクライアントクラス"""
    
    async def get_deal_histories_schema(self) -> Dict[str, Any]:
        """deal_historiesカスタムオブジェクトのスキーマを取得（ID使用）"""
        try:
            response = await self._make_request(
                "GET",
                "/crm/v3/schemas/2-172324672"
            )
            return response
        except Exception as e:
            logger.error(f"Failed to get deal_histories schema: {str(e)}")
            return {}

    async def get_deal_histories(self, limit: int = 100, after: Optional[str] = None, 
                                deal_id: Optional[str] = None, 
                                stage: Optional[str] = None,
                                from_date: Optional[str] = None,
                                to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """deal_historiesカスタムオブジェクトの一覧を取得"""
        try:
            # フィルター条件を構築
            filters = []
            
            if deal_id:
                # deal_idは関連する取引のIDなので、deal_to_deal_historiseの関連で検索
                # または、deal_history_nameに取引名が含まれているかで検索
                filters.append({
                    "propertyName": "deal_history_name",
                    "operator": "CONTAINS_TOKEN",
                    "value": deal_id
                })
            
            if stage:
                filters.append({
                    "propertyName": "deal_history_stage",
                    "operator": "EQ",
                    "value": stage
                })
            
            if from_date:
                filters.append({
                    "propertyName": "hs_createdate",
                    "operator": "GTE",
                    "value": from_date
                })
            
            if to_date:
                filters.append({
                    "propertyName": "hs_createdate",
                    "operator": "LTE",
                    "value": to_date
                })
            
            # 検索データを構築
            search_data = {
                "properties": [
                    "deal_history_name",
                    "deal_history_stage",
                    "deal_history_owner",
                    "deal_history_pipeline",
                    "deal_history_answer_price",
                    "deal_history_sales_price",
                    "hs_createdate",
                    "hs_lastmodifieddate",
                    "hubspot_owner_id"
                ],
                "limit": limit
            }
            
            if filters:
                search_data["filterGroups"] = [{"filters": filters}]
            
            if after:
                search_data["after"] = after
            
            response = await self._make_request(
                "POST",
                "/crm/v3/objects/2-172324672/search",
                json=search_data
            )
            
            return response.get("results", [])
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("HubSpot API認証エラー: 有効なAPIキーを設定してください")
            else:
                logger.error(f"HubSpot API error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to get deal histories: {str(e)}")
            return []
    
    async def get_deal_histories_by_deal_id(self, deal_id: str) -> List[Dict[str, Any]]:
        """特定の取引IDの履歴を取得"""
        return await self.get_deal_histories(deal_id=deal_id, limit=1000)
    
    async def get_deal_histories_by_stage(self, stage: str, limit: int = 100) -> List[Dict[str, Any]]:
        """特定のステージの履歴を取得"""
        return await self.get_deal_histories(stage=stage, limit=limit)
    
    async def get_deal_histories_by_date_range(self, from_date: str, to_date: str, 
                                             limit: int = 100) -> List[Dict[str, Any]]:
        """日付範囲で履歴を取得"""
        return await self.get_deal_histories(from_date=from_date, to_date=to_date, limit=limit)
    
    async def get_all_deal_histories(self, deal_id: Optional[str] = None,
                                   stage: Optional[str] = None,
                                   from_date: Optional[str] = None,
                                   to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """全履歴を取得（ページネーション対応）"""
        all_histories = []
        after = None
        
        while True:
            histories = await self.get_deal_histories(
                limit=100,
                after=after,
                deal_id=deal_id,
                stage=stage,
                from_date=from_date,
                to_date=to_date
            )
            
            if not histories:
                break
                
            all_histories.extend(histories)
            
            # ページネーションの確認
            if len(histories) < 100:  # 最後のページ
                break
                
            # 次のページのafterパラメータを取得（実際のレスポンス構造に応じて調整）
            # ここでは簡易的に最後のIDを使用
            after = histories[-1].get("id")
            
            if not after:
                break
        
        logger.info(f"Retrieved {len(all_histories)} deal histories")
        return all_histories
    
    async def get_contract_histories(self, from_date: Optional[str] = None, 
                                   to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """契約ステージの履歴を取得"""
        return await self.get_all_deal_histories(
            stage="契約",
            from_date=from_date,
            to_date=to_date
        )
    
    async def get_settlement_histories(self, from_date: Optional[str] = None, 
                                     to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """決済ステージの履歴を取得"""
        return await self.get_all_deal_histories(
            stage="決済",
            from_date=from_date,
            to_date=to_date
        )
    
    async def get_monthly_contract_counts(self, from_date: str, to_date: str) -> Dict[str, int]:
        """月別の契約件数を取得"""
        contract_histories = await self.get_contract_histories(from_date, to_date)
        
        monthly_counts = {}
        for history in contract_histories:
            created_date = history.get("hs_createdate")
            if created_date:
                # 日付から年月を抽出
                year_month = created_date[:7]  # YYYY-MM形式
                monthly_counts[year_month] = monthly_counts.get(year_month, 0) + 1
        
        return monthly_counts
    
    async def get_monthly_settlement_counts(self, from_date: str, to_date: str) -> Dict[str, int]:
        """月別の決済件数を取得"""
        settlement_histories = await self.get_settlement_histories(from_date, to_date)
        
        monthly_counts = {}
        for history in settlement_histories:
            created_date = history.get("hs_createdate")
            if created_date:
                # 日付から年月を抽出
                year_month = created_date[:7]  # YYYY-MM形式
                monthly_counts[year_month] = monthly_counts.get(year_month, 0) + 1
        
        return monthly_counts
