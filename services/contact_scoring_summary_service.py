import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, timedelta
import aiomysql

logger = logging.getLogger(__name__)


class ContactScoringSummaryService:
    """コンタクトスコアリング（仕入）集計サービス"""
    
    # 対象担当者名（姓名）
    TARGET_OWNERS = [
        "岩崎 陽",
        "久世 健人",
        "赤瀬 公平",
        "藤森 日加里",
        "藤村 ひかり"
    ]
    
    # owner_idからowner_nameへのマッピング（データベースの文字化け対策）
    OWNER_ID_TO_NAME = {
        "75947324": "久世 健人",
        "75947364": "赤瀬 公平",
        "75947430": "藤森 日加里",
        "75947440": "岩崎 陽",
        "78042426": "藤村 ひかり"
    }
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool

    def _get_this_week_monday(self) -> date:
        """今週の月曜日の日付を取得"""
        today = date.today()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        return monday

    def _get_last_week_monday(self) -> date:
        """先週の月曜日の日付を取得"""
        this_week_monday = self._get_this_week_monday()
        return this_week_monday - timedelta(days=7)

    async def get_available_dates(self) -> List[str]:
        """利用可能な集計日のリストを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT DISTINCT aggregation_date
                    FROM contact_scoring_summary
                    ORDER BY aggregation_date DESC
                """
                await cursor.execute(query)
                results = await cursor.fetchall()
                
                dates = []
                for row in results:
                    agg_date = row.get('aggregation_date')
                    if agg_date:
                        if isinstance(agg_date, date):
                            dates.append(agg_date.isoformat())
                        else:
                            dates.append(str(agg_date))
                
                return dates

    async def get_summary_by_date(self, aggregation_date: date, pattern_type: Optional[str] = None) -> Dict[str, Any]:
        """指定した集計日のデータを取得（パターン別）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 集計データを取得
                if pattern_type:
                    query = """
                        SELECT owner_id, owner_name, pattern_type, industry_count, property_type_count, 
                               area_count, area_category_count, gross_count, 
                               all_five_items_count, target_audience_count
                        FROM contact_scoring_summary
                        WHERE aggregation_date = %s AND pattern_type = %s
                        ORDER BY owner_id
                    """
                    await cursor.execute(query, (aggregation_date, pattern_type))
                else:
                    query = """
                        SELECT owner_id, owner_name, pattern_type, industry_count, property_type_count, 
                               area_count, area_category_count, gross_count, 
                               all_five_items_count, target_audience_count
                        FROM contact_scoring_summary
                        WHERE aggregation_date = %s
                        ORDER BY pattern_type, owner_id
                    """
                    await cursor.execute(query, (aggregation_date,))
                results = await cursor.fetchall()
                
                if not results:
                    return {
                        "aggregation_date": aggregation_date.isoformat() if isinstance(aggregation_date, date) else str(aggregation_date),
                        "data": {},
                        "message": "指定した集計日のデータがありません"
                    }
                
                # データを構造化
                data, owner_id_to_name = self._structure_data(results)
                
                return {
                    "aggregation_date": aggregation_date.isoformat() if isinstance(aggregation_date, date) else str(aggregation_date),
                    "data": data,
                    "owner_id_to_name": owner_id_to_name
                }

    async def get_latest_summary(self, pattern_type: Optional[str] = None) -> Dict[str, Any]:
        """最新の集計データを取得（パターン別）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 最新の集計日を取得
                query = """
                    SELECT MAX(aggregation_date) as max_date
                    FROM contact_scoring_summary
                """
                await cursor.execute(query)
                result = await cursor.fetchone()
                
                if not result or not result.get('max_date'):
                    return {
                        "aggregation_date": None,
                        "data": {},
                        "message": "集計データがありません"
                    }
                
                aggregation_date = result['max_date']
                return await self.get_summary_by_date(aggregation_date, pattern_type)

    async def get_comparison(self, current_date: date, previous_date: date, pattern_type: Optional[str] = None) -> Dict[str, Any]:
        """指定した2つの集計日を比較（パターン別）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 現在のデータを取得
                if pattern_type:
                    query = """
                        SELECT owner_id, owner_name, pattern_type, industry_count, property_type_count, 
                               area_count, area_category_count, gross_count, 
                               all_five_items_count, target_audience_count
                        FROM contact_scoring_summary
                        WHERE aggregation_date = %s AND pattern_type = %s
                        ORDER BY owner_id
                    """
                    await cursor.execute(query, (current_date, pattern_type))
                else:
                    query = """
                        SELECT owner_id, owner_name, pattern_type, industry_count, property_type_count, 
                               area_count, area_category_count, gross_count, 
                               all_five_items_count, target_audience_count
                        FROM contact_scoring_summary
                        WHERE aggregation_date = %s
                        ORDER BY pattern_type, owner_id
                    """
                    await cursor.execute(query, (current_date,))
                current_results = await cursor.fetchall()
                current_data, current_owner_id_to_name = self._structure_data(current_results)
                
                # 比較対象のデータを取得
                if pattern_type:
                    await cursor.execute(query, (previous_date, pattern_type))
                else:
                    query = """
                        SELECT owner_id, owner_name, pattern_type, industry_count, property_type_count, 
                               area_count, area_category_count, gross_count, 
                               all_five_items_count, target_audience_count
                        FROM contact_scoring_summary
                        WHERE aggregation_date = %s
                        ORDER BY pattern_type, owner_id
                    """
                    await cursor.execute(query, (previous_date,))
                previous_results = await cursor.fetchall()
                previous_data, previous_owner_id_to_name = self._structure_data(previous_results)
                
                # 比較を計算（パターンごと）
                comparison = {}
                for pattern in ['all', 'buy', 'sell', 'buy_or_sell']:
                    if pattern_type and pattern != pattern_type:
                        continue
                    comparison[pattern] = self._calculate_comparison(
                        current_data.get(pattern, {}),
                        previous_data.get(pattern, {})
                    )
                
                # owner_id_to_nameマッピングを統合（currentを優先）
                owner_id_to_name = {**previous_owner_id_to_name, **current_owner_id_to_name}
                
                return {
                    "current": {
                        "aggregation_date": current_date.isoformat() if isinstance(current_date, date) else str(current_date),
                        "data": current_data
                    },
                    "previous": {
                        "aggregation_date": previous_date.isoformat() if isinstance(previous_date, date) else str(previous_date),
                        "data": previous_data
                    },
                    "comparison": comparison,
                    "owner_id_to_name": owner_id_to_name
                }

    async def get_summary_with_comparison(self, pattern_type: Optional[str] = None) -> Dict[str, Any]:
        """最新の集計データと前週比を取得（パターン別）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 最新の集計日を取得
                query = """
                    SELECT MAX(aggregation_date) as max_date
                    FROM contact_scoring_summary
                """
                await cursor.execute(query)
                result = await cursor.fetchone()
                
                if not result or not result.get('max_date'):
                    return {
                        "current": {
                            "aggregation_date": None,
                            "data": {}
                        },
                        "previous": {
                            "aggregation_date": None,
                            "data": {}
                        },
                        "comparison": {},
                        "message": "集計データがありません"
                    }
                
                current_date = result['max_date']
                previous_date = current_date - timedelta(days=7)
                
                return await self.get_comparison(current_date, previous_date, pattern_type)

    def _structure_data(self, results: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Dict[str, int]]], Dict[str, str]]:
        """
        データを構造化（パターン別）
        戻り値: ({pattern_type: {owner_id: {metric: count}}}, {owner_id: owner_name})
        """
        data: Dict[str, Dict[str, Dict[str, int]]] = {
            'all': {},
            'buy': {},
            'sell': {},
            'buy_or_sell': {}
        }
        owner_id_to_name: Dict[str, str] = {}
        
        # データを設定
        for row in results:
            owner_id = row.get('owner_id')
            owner_name = row.get('owner_name')
            pattern_type = row.get('pattern_type', 'all')
            
            if not owner_id:
                continue
            
            # パターンタイプが無効な場合はスキップ
            if pattern_type not in ['all', 'buy', 'sell', 'buy_or_sell']:
                continue
            
            # 担当者IDから名前へのマッピングを保存
            if owner_id not in owner_id_to_name:
                owner_id_to_name[owner_id] = self.OWNER_ID_TO_NAME.get(owner_id, owner_name or owner_id)
            
            # データ構造を初期化
            if owner_id not in data[pattern_type]:
                data[pattern_type][owner_id] = {
                    'industry': 0,
                    'property_type': 0,
                    'area': 0,
                    'area_category': 0,
                    'gross': 0,
                    'all_five_items': 0,
                    'target_audience': 0
                }
            
            # データを設定
            data[pattern_type][owner_id]['industry'] = row.get('industry_count', 0)
            data[pattern_type][owner_id]['property_type'] = row.get('property_type_count', 0)
            data[pattern_type][owner_id]['area'] = row.get('area_count', 0)
            data[pattern_type][owner_id]['area_category'] = row.get('area_category_count', 0)
            data[pattern_type][owner_id]['gross'] = row.get('gross_count', 0)
            data[pattern_type][owner_id]['all_five_items'] = row.get('all_five_items_count', 0)
            data[pattern_type][owner_id]['target_audience'] = row.get('target_audience_count', 0)
        
        return data, owner_id_to_name

    def _calculate_comparison(
        self,
        current_data: Dict[str, Dict[str, int]],
        previous_data: Dict[str, Dict[str, int]]
    ) -> Dict[str, Dict[str, int]]:
        """
        前週比を計算
        戻り値: {owner_id: {metric: diff}}
        """
        comparison: Dict[str, Dict[str, int]] = {}
        
        # すべてのowner_idを取得（current_dataとprevious_dataの両方から）
        all_owner_ids = set(current_data.keys()) | set(previous_data.keys())
        
        metrics = ['industry', 'property_type', 'area', 'area_category', 'gross', 'all_five_items', 'target_audience']
        
        for owner_id in all_owner_ids:
            comparison[owner_id] = {}
            for metric in metrics:
                current_count = current_data.get(owner_id, {}).get(metric, 0)
                previous_count = previous_data.get(owner_id, {}).get(metric, 0)
                diff = current_count - previous_count
                comparison[owner_id][metric] = diff
        
        return comparison

