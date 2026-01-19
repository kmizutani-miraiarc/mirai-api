import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import aiomysql

logger = logging.getLogger(__name__)


class PurchaseSummaryService:
    """仕入集計レポート集計サービス"""
    
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
                    FROM purchase_summary
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
                'stageBreakdown': stage_breakdown,
                'applicableDeals': monthly_data.get('applicable_deals', 0),
                'nonApplicableDeals': monthly_data.get('non_applicable_deals', 0)
            }
            
            # 総取引数を更新
            summary_data[owner_id]['totalDeals'] += total_deals
            
            # 当月系のデータを取得（monthly_countsから）
            monthly_counts = monthly_data.get('monthly_counts', {})
            if monthly_counts:
                # 当月系のデータを担当者別に集計
                if '_monthlyBukkenCreatedCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlyBukkenCreatedCounts'] = {}
                if '_monthlySurveyReviewCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlySurveyReviewCounts'] = {}
                if '_monthlyPurchaseCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlyPurchaseCounts'] = {}
                if '_monthlyProbabilityBCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlyProbabilityBCounts'] = {}
                if '_monthlyProbabilityACounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlyProbabilityACounts'] = {}
                if '_monthlyFarewellCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlyFarewellCounts'] = {}
                if '_monthlyLostCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlyLostCounts'] = {}
                if '_monthlyContractCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlyContractCounts'] = {}
                if '_monthlySettlementCounts' not in summary_data[owner_id]:
                    summary_data[owner_id]['_monthlySettlementCounts'] = {}
                
                # 当月系のデータを追加
                if 'bukken_created' in monthly_counts:
                    summary_data[owner_id]['_monthlyBukkenCreatedCounts'][year_month] = monthly_counts['bukken_created']
                if 'survey_review' in monthly_counts:
                    summary_data[owner_id]['_monthlySurveyReviewCounts'][year_month] = monthly_counts['survey_review']
                if 'purchase' in monthly_counts:
                    summary_data[owner_id]['_monthlyPurchaseCounts'][year_month] = monthly_counts['purchase']
                if 'probability_b' in monthly_counts:
                    summary_data[owner_id]['_monthlyProbabilityBCounts'][year_month] = monthly_counts['probability_b']
                if 'probability_a' in monthly_counts:
                    summary_data[owner_id]['_monthlyProbabilityACounts'][year_month] = monthly_counts['probability_a']
                if 'farewell' in monthly_counts:
                    summary_data[owner_id]['_monthlyFarewellCounts'][year_month] = monthly_counts['farewell']
                if 'lost' in monthly_counts:
                    summary_data[owner_id]['_monthlyLostCounts'][year_month] = monthly_counts['lost']
                if 'contract' in monthly_counts:
                    summary_data[owner_id]['_monthlyContractCounts'][year_month] = monthly_counts['contract']
                if 'settlement' in monthly_counts:
                    summary_data[owner_id]['_monthlySettlementCounts'][year_month] = monthly_counts['settlement']
        
        # 担当者の順序を保持
        summary_data['_ownerOrder'] = owner_order
        
        # 全体の当月系のデータを集計
        summary_data['_monthlyBukkenCreatedCounts'] = {}
        summary_data['_monthlySurveyReviewCounts'] = {}
        summary_data['_monthlyPurchaseCounts'] = {}
        summary_data['_monthlyProbabilityBCounts'] = {}
        summary_data['_monthlyProbabilityACounts'] = {}
        summary_data['_monthlyFarewellCounts'] = {}
        summary_data['_monthlyLostCounts'] = {}
        summary_data['_monthlyContractCounts'] = {}
        summary_data['_monthlySettlementCounts'] = {}
        
        for owner_id, owner_data in summary_data.items():
            if owner_id in ['_ownerOrder', '_totalSummary', '_monthlyBukkenCreatedCounts', '_monthlySurveyReviewCounts',
                           '_monthlyPurchaseCounts', '_monthlyProbabilityBCounts', '_monthlyProbabilityACounts',
                           '_monthlyFarewellCounts', '_monthlyLostCounts', '_monthlyContractCounts', '_monthlySettlementCounts']:
                continue
            
            # 各担当者の当月系のデータを全体に集計
            for field in ['_monthlyBukkenCreatedCounts', '_monthlySurveyReviewCounts', '_monthlyPurchaseCounts',
                         '_monthlyProbabilityBCounts', '_monthlyProbabilityACounts', '_monthlyFarewellCounts',
                         '_monthlyLostCounts', '_monthlyContractCounts', '_monthlySettlementCounts']:
                owner_counts = owner_data.get(field, {})
                for year_month, count in owner_counts.items():
                    if year_month not in summary_data[field]:
                        summary_data[field][year_month] = 0
                    summary_data[field][year_month] += count
        
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
                'stageBreakdown': {},
                'applicableDeals': 0,
                'nonApplicableDeals': 0
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
                    total_summary['monthlyData'][year_month]['applicableDeals'] += month_data.get('applicableDeals', 0)
                    total_summary['monthlyData'][year_month]['nonApplicableDeals'] += month_data.get('nonApplicableDeals', 0)
                    
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

    async def get_deal_ids(
        self,
        year: int,
        owner_id: str,
        year_month: str,
        stage_name: str
    ) -> Dict[str, Any]:
        """指定した条件の取引IDリストを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 年月から月を抽出
                month = int(year_month.split('-')[1])
                
                # owner_idが'total'の場合は全担当者のデータを取得
                if owner_id == 'total':
                    query = """
                        SELECT monthly_data
                        FROM purchase_summary
                        WHERE aggregation_year = %s
                          AND month = %s
                    """
                    await cursor.execute(query, (year, month))
                    results = await cursor.fetchall()
                else:
                    query = """
                        SELECT monthly_data
                        FROM purchase_summary
                        WHERE aggregation_year = %s
                          AND owner_id = %s
                          AND month = %s
                    """
                    await cursor.execute(query, (year, owner_id, month))
                    result = await cursor.fetchone()
                    results = [result] if result else []
                
                if not results:
                    return {
                        "deal_ids": []
                    }
                
                # 全担当者のデータをマージ
                all_deal_ids = []
                for result in results:
                    if not result or not result.get('monthly_data'):
                        continue
                    
                    # JSON形式の月別データをパース
                    monthly_data_str = result['monthly_data']
                    try:
                        monthly_data = json.loads(monthly_data_str)
                        
                        # ステージ別または当月系項目別の取引IDリストを取得
                        deal_ids = []
                        
                        # ステージ別の取引IDリスト
                        if 'deal_ids_by_stage' in monthly_data and stage_name in monthly_data['deal_ids_by_stage']:
                            deal_ids = monthly_data['deal_ids_by_stage'][stage_name]
                        
                        # 当月系項目別の取引IDリスト
                        elif 'deal_ids_by_monthly_item' in monthly_data and stage_name in monthly_data['deal_ids_by_monthly_item']:
                            deal_ids = monthly_data['deal_ids_by_monthly_item'][stage_name]
                        
                        if isinstance(deal_ids, list):
                            # 重複を除去してマージ
                            for deal_id in deal_ids:
                                if deal_id not in all_deal_ids:
                                    all_deal_ids.append(deal_id)
                                    
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"月別データのパースエラー: {str(e)}")
                        continue
                
                return {
                    "deal_ids": all_deal_ids
                }

    async def get_deal_details(
        self,
        year: int,
        owner_id: str,
        year_month: str,
        stage_name: str
    ) -> Dict[str, Any]:
        """指定した条件の取引詳細を取得（バッチ処理で保存されたデータから）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 年月から月を抽出
                month = int(year_month.split('-')[1])
                
                # owner_idが'total'の場合は全担当者のデータを取得
                if owner_id == 'total':
                    query = """
                        SELECT owner_id, monthly_data
                        FROM purchase_summary
                        WHERE aggregation_year = %s
                          AND month = %s
                    """
                    await cursor.execute(query, (year, month))
                    results = await cursor.fetchall()
                else:
                    query = """
                        SELECT owner_id, monthly_data
                        FROM purchase_summary
                        WHERE aggregation_year = %s
                          AND owner_id = %s
                          AND month = %s
                    """
                    await cursor.execute(query, (year, owner_id, month))
                    result = await cursor.fetchone()
                    results = [result] if result else []
                
                if not results:
                    return {
                        "deals": []
                    }
                
                # 全担当者のデータをマージ
                all_deal_details = []
                for result in results:
                    if not result or not result.get('monthly_data'):
                        continue
                    
                    # JSON形式の月別データをパース
                    monthly_data_str = result['monthly_data']
                    try:
                        monthly_data = json.loads(monthly_data_str)
                        
                        # ステージ別または当月系項目別の取引詳細を取得
                        deal_details = []
                        
                        # ステージ別の取引詳細
                        if 'deal_details_by_stage' in monthly_data and stage_name in monthly_data['deal_details_by_stage']:
                            deal_details = monthly_data['deal_details_by_stage'][stage_name]
                        
                        # 当月系項目別の取引詳細
                        elif 'deal_details_by_monthly_item' in monthly_data and stage_name in monthly_data['deal_details_by_monthly_item']:
                            deal_details = monthly_data['deal_details_by_monthly_item'][stage_name]
                        
                        if isinstance(deal_details, list):
                            # 重複を除去してマージ（IDで判定）
                            existing_ids = {d.get('id') for d in all_deal_details}
                            for deal_detail in deal_details:
                                if deal_detail.get('id') and deal_detail.get('id') not in existing_ids:
                                    all_deal_details.append(deal_detail)
                                    existing_ids.add(deal_detail.get('id'))
                                    
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"月別データのパースエラー: {str(e)}")
                        continue
                
                return {
                    "deals": all_deal_details
                }
