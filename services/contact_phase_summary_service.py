import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import date, timedelta
import aiomysql

logger = logging.getLogger(__name__)


class ContactPhaseSummaryService:
    """コンタクトフェーズ集計サービス"""
    
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
    
    # フェーズの順序
    PHASES = ['S', 'A', 'B', 'C', 'D', 'Z']
    
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
                    FROM contact_phase_summary
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

    async def get_summary_by_date(self, aggregation_date: date) -> Dict[str, Any]:
        """指定した集計日のデータを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 集計データを取得（owner_idとowner_nameの両方を取得）
                query = """
                    SELECT owner_id, owner_name, phase_type, phase_value, count
                    FROM contact_phase_summary
                    WHERE aggregation_date = %s
                    ORDER BY owner_id, phase_type, phase_value
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

    async def get_latest_summary(self) -> Dict[str, Any]:
        """最新の集計データを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 最新の集計日を取得
                query = """
                    SELECT MAX(aggregation_date) as max_date
                    FROM contact_phase_summary
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
                return await self.get_summary_by_date(aggregation_date)

    async def get_comparison(self, current_date: date, previous_date: date) -> Dict[str, Any]:
        """指定した2つの集計日を比較"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 現在のデータを取得（owner_idとowner_nameの両方を取得）
                query = """
                    SELECT owner_id, owner_name, phase_type, phase_value, count
                    FROM contact_phase_summary
                    WHERE aggregation_date = %s
                    ORDER BY owner_id, phase_type, phase_value
                """
                await cursor.execute(query, (current_date,))
                current_results = await cursor.fetchall()
                current_data, current_owner_id_to_name = self._structure_data(current_results)
                
                # 比較対象のデータを取得
                await cursor.execute(query, (previous_date,))
                previous_results = await cursor.fetchall()
                previous_data, previous_owner_id_to_name = self._structure_data(previous_results)
                
                # 比較を計算
                comparison = self._calculate_comparison(current_data, previous_data)
                
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

    async def get_summary_with_comparison(self) -> Dict[str, Any]:
        """最新の集計データと前週比を取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 最新の集計日を取得
                query = """
                    SELECT MAX(aggregation_date) as max_date
                    FROM contact_phase_summary
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
                
                return await self.get_comparison(current_date, previous_date)

    def _structure_data(self, results: List[Dict[str, Any]]) -> tuple[Dict[str, Dict[str, Dict[str, int]]], Dict[str, str]]:
        """
        データを構造化
        戻り値: ({owner_id: {phase_type: {phase_value: count}}}, {owner_id: owner_name})
        phase_type: 'buy' または 'sell'
        phase_value: 'S', 'A', 'B', 'C', 'D', 'Z'
        """
        data: Dict[str, Dict[str, Dict[str, int]]] = {}
        owner_id_to_name: Dict[str, str] = {}
        
        # データを設定
        for row in results:
            owner_id = row.get('owner_id')
            owner_name = row.get('owner_name')
            phase_type = row.get('phase_type')
            phase_value = row.get('phase_value')
            count = row.get('count', 0)
            
            if not owner_id:
                continue
            
            # 担当者IDから名前へのマッピングを保存
            # データベースのowner_nameが文字化けしている可能性があるため、
            # マッピングテーブルから取得する（なければデータベースの値を使用）
            if owner_id not in owner_id_to_name:
                owner_id_to_name[owner_id] = self.OWNER_ID_TO_NAME.get(owner_id, owner_name or owner_id)
            
            # データ構造を初期化（必要に応じて）
            if owner_id not in data:
                data[owner_id] = {'buy': {}, 'sell': {}}
            if phase_type not in data[owner_id]:
                data[owner_id][phase_type] = {}
            if phase_value not in data[owner_id][phase_type]:
                data[owner_id][phase_type][phase_value] = 0
            
            # データを設定
            if phase_type in ['buy', 'sell'] and phase_value in self.PHASES:
                data[owner_id][phase_type][phase_value] = count
        
        return data, owner_id_to_name

    def _calculate_comparison(
        self,
        current_data: Dict[str, Dict[str, Dict[str, int]]],
        previous_data: Dict[str, Dict[str, Dict[str, int]]]
    ) -> Dict[str, Dict[str, Dict[str, int]]]:
        """
        前週比を計算
        戻り値: {owner_id: {phase_type: {phase_value: diff}}}
        phase_type: 'buy' または 'sell'
        phase_value: 'S', 'A', 'B', 'C', 'D', 'Z'
        """
        comparison: Dict[str, Dict[str, Dict[str, int]]] = {}
        
        # すべてのowner_idを取得（current_dataとprevious_dataの両方から）
        all_owner_ids = set(current_data.keys()) | set(previous_data.keys())
        
        for owner_id in all_owner_ids:
            comparison[owner_id] = {'buy': {}, 'sell': {}}
            for phase_type in ['buy', 'sell']:
                for phase_value in self.PHASES:
                    current_count = current_data.get(owner_id, {}).get(phase_type, {}).get(phase_value, 0)
                    previous_count = previous_data.get(owner_id, {}).get(phase_type, {}).get(phase_value, 0)
                    diff = current_count - previous_count
                    comparison[owner_id][phase_type][phase_value] = diff
        
        return comparison

