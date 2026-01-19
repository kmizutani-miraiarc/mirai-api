import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import aiomysql

logger = logging.getLogger(__name__)


class SalesSummaryService:
    """販売集計レポート集計サービス"""
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool

    async def get_latest_summary(self, year: int) -> Dict[str, Any]:
        """最新の集計データを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 指定年の集計データを取得
                query = """
                    SELECT 
                        owner_id,
                        owner_name,
                        month,
                        total_deals,
                        stage_breakdown,
                        monthly_data
                    FROM sales_summary
                    WHERE aggregation_year = %s
                    ORDER BY owner_id, month
                """
                await cursor.execute(query, (year,))
                results = await cursor.fetchall()
                
                if not results:
                    return {
                        "year": year,
                        "data": {},
                        "message": "集計データがありません"
                    }
                
                # データを構造化
                summary = self._structure_data(results, year)
                
                return {
                    "year": year,
                    "data": summary
                }

    def _structure_data(self, results: List[Dict[str, Any]], year: int) -> Dict[str, Any]:
        """データを構造化"""
        summary_data = {}
        owner_order = []
        
        for row in results:
            owner_id = row.get('owner_id')
            owner_name = row.get('owner_name')
            month = row.get('month')
            total_deals = row.get('total_deals', 0)
            stage_breakdown_str = row.get('stage_breakdown')
            monthly_data_str = row.get('monthly_data')
            
            if not owner_id:
                continue
            
            # 担当者データを初期化
            if owner_id not in summary_data:
                summary_data[owner_id] = {
                    'ownerName': owner_name,
                    'monthlyData': {},
                    'totalDeals': 0
                }
                owner_order.append(owner_id)
            
            # 月別データをパース
            year_month = f"{year}-{str(month).zfill(2)}"
            
            stage_breakdown = {}
            if stage_breakdown_str:
                try:
                    stage_breakdown = json.loads(stage_breakdown_str)
                except:
                    pass
            
            monthly_data = {}
            if monthly_data_str:
                try:
                    monthly_data = json.loads(monthly_data_str)
                except:
                    pass
            
            summary_data[owner_id]['monthlyData'][year_month] = {
                'totalDeals': total_deals,
                'stageBreakdown': stage_breakdown
            }
            
            # 総取引数を更新
            summary_data[owner_id]['totalDeals'] += total_deals
        
        # 担当者の順序を保持
        summary_data['_ownerOrder'] = owner_order
        
        # 合計データを計算
        summary_data['_totalSummary'] = self._calculate_total_summary(summary_data, year)
        
        return summary_data

    def _calculate_total_summary(self, summary_data: Dict[str, Any], year: int) -> Dict[str, Any]:
        """合計データを計算"""
        total_summary = {
            'monthlyData': {},
            'totalDeals': 0,
            'ownerCount': 0
        }
        
        # 月の範囲を生成
        months = []
        for month in range(1, 13):
            months.append(f"{year}-{str(month).zfill(2)}")
        
        # 各月のデータを初期化
        for month in months:
            total_summary['monthlyData'][month] = {
                'totalDeals': 0,
                'stageBreakdown': {}
            }
        
        # 各担当者のデータを合計
        for owner_id, owner_data in summary_data.items():
            if owner_id in ['_ownerOrder', '_totalSummary']:
                continue
            
            if owner_data.get('totalDeals', 0) > 0:
                total_summary['ownerCount'] += 1
            
            # 各月のデータを合計
            for year_month, month_data in owner_data.get('monthlyData', {}).items():
                if year_month in total_summary['monthlyData']:
                    total_summary['monthlyData'][year_month]['totalDeals'] += month_data.get('totalDeals', 0)
                    
                    # ステージ別の内訳を合計
                    for stage_name, count in month_data.get('stageBreakdown', {}).items():
                        if stage_name not in total_summary['monthlyData'][year_month]['stageBreakdown']:
                            total_summary['monthlyData'][year_month]['stageBreakdown'][stage_name] = 0
                        total_summary['monthlyData'][year_month]['stageBreakdown'][stage_name] += count
        
        # 全体の総取引数を計算
        total_summary['totalDeals'] = sum(
            month_data.get('totalDeals', 0) 
            for month_data in total_summary['monthlyData'].values()
        )
        
        return total_summary
