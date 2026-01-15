import asyncio
import json
import logging
import os
from typing import List, Optional, Dict, Any
from datetime import date, timedelta
import aiomysql

logger = logging.getLogger(__name__)


class ContactPhaseSummaryMonthlyService:
    """コンタクトフェーズ集計サービス（月次）"""
    
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

    async def get_available_dates(self) -> List[str]:
        """利用可能な集計日のリストを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT DISTINCT aggregation_date
                    FROM contact_phase_summary_monthly
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
                    FROM contact_phase_summary_monthly
                    WHERE aggregation_date = %s
                    ORDER BY owner_id, phase_type, phase_value
                """
                await cursor.execute(query, (aggregation_date,))
                results = await cursor.fetchall()
                
                if not results:
                    # データが存在しない場合でも、空のデータ構造を返す
                    return {
                        "aggregation_date": aggregation_date.isoformat() if isinstance(aggregation_date, date) else str(aggregation_date),
                        "data": {},
                        "owner_id_to_name": {},
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
                    FROM contact_phase_summary_monthly
                """
                await cursor.execute(query)
                result = await cursor.fetchone()
                
                logger.info(f"最新の集計日取得結果（月次）: {result}")
                
                if not result or not result.get('max_date'):
                    logger.warning("集計データが存在しません（月次）")
                    # データが存在しない場合でも、空のデータ構造を返す
                    return {
                        "aggregation_date": None,
                        "data": {},
                        "owner_id_to_name": {},
                        "message": "集計データがありません"
                    }
                
                aggregation_date = result['max_date']
                logger.info(f"最新の集計日（月次）: {aggregation_date}")
                return await self.get_summary_by_date(aggregation_date)

    async def get_all_summaries(self) -> Dict[str, Any]:
        """すべての集計データを取得（グラフ表示用）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # すべての集計データを取得
                query = """
                    SELECT aggregation_date, owner_id, owner_name, phase_type, phase_value, count
                    FROM contact_phase_summary_monthly
                    ORDER BY aggregation_date ASC, owner_id, phase_type, phase_value
                """
                await cursor.execute(query)
                results = await cursor.fetchall()
                
                logger.info(f"すべての集計データ取得結果（月次）: {len(results)}件")
                
                if not results:
                    logger.warning("集計データが存在しません（月次、全データ）")
                    # データが存在しない場合でも、空のデータ構造を返す
                    return {
                        "data": {},
                        "owner_id_to_name": {},
                        "dates": [],
                        "message": "集計データがありません"
                    }
                
                # データを構造化（日付ごとにグループ化）
                # 型: {date_str: {owner_id: {phase_type: {phase_value: count}}}}
                data_by_date = {}
                owner_id_to_name: Dict[str, str] = {}
                dates = []
                
                for row in results:
                    agg_date = row.get('aggregation_date')
                    if not agg_date:
                        continue
                    
                    # 日付を文字列に変換
                    if isinstance(agg_date, date):
                        date_str = agg_date.isoformat()
                    else:
                        date_str = str(agg_date)
                    
                    if date_str not in dates:
                        dates.append(date_str)
                    
                    owner_id = row.get('owner_id')
                    owner_name = row.get('owner_name')
                    phase_type = row.get('phase_type')
                    phase_value = row.get('phase_value')
                    count = row.get('count', 0)
                    
                    if not owner_id:
                        continue
                    
                    # 担当者IDから名前へのマッピングを保存
                    if owner_id not in owner_id_to_name:
                        owner_id_to_name[owner_id] = self.OWNER_ID_TO_NAME.get(owner_id, owner_name or owner_id)
                    
                    # データ構造を初期化（必要に応じて）
                    if date_str not in data_by_date:
                        data_by_date[date_str] = {}
                    if owner_id not in data_by_date[date_str]:
                        data_by_date[date_str][owner_id] = {'buy': {}, 'sell': {}}
                    if phase_type not in data_by_date[date_str][owner_id]:
                        data_by_date[date_str][owner_id][phase_type] = {}
                    if phase_value not in data_by_date[date_str][owner_id][phase_type]:
                        data_by_date[date_str][owner_id][phase_type][phase_value] = 0
                    
                    # データを設定
                    if phase_type in ['buy', 'sell'] and phase_value in self.PHASES:
                        data_by_date[date_str][owner_id][phase_type][phase_value] = count
                
                return {
                    "data": data_by_date,
                    "owner_id_to_name": owner_id_to_name,
                    "dates": sorted(dates)
                }

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

    async def get_contact_ids(
        self,
        aggregation_date: date,
        owner_id: str,
        phase_type: str,
        phase_value: str
    ) -> Dict[str, Any]:
        """
        指定した条件のコンタクトIDリストを取得
        
        Args:
            aggregation_date: 集計日
            owner_id: 担当者ID
            phase_type: フェーズ区分（'buy' または 'sell'）
            phase_value: フェーズ値（'S', 'A', 'B', 'C', 'D', 'Z'）
        
        Returns:
            コンタクトIDリストとHubSpotリンク
        """
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT contact_ids
                    FROM contact_phase_summary_monthly
                    WHERE aggregation_date = %s
                      AND owner_id = %s
                      AND phase_type = %s
                      AND phase_value = %s
                """
                await cursor.execute(query, (aggregation_date, owner_id, phase_type, phase_value))
                result = await cursor.fetchone()
                
                if not result or not result.get('contact_ids'):
                    return {
                        "contacts": []
                    }
                
                # JSON形式のコンタクトIDと名前をパース
                contact_ids_str = result['contact_ids']
                try:
                    # JSON形式をパース
                    contacts_data = json.loads(contact_ids_str)
                    if not isinstance(contacts_data, list):
                        contacts_data = []
                except (json.JSONDecodeError, TypeError):
                    # 古いCSV形式の場合は空リストを返す（後方互換性のため）
                    contacts_data = []
                
                # HubSpotリンクを生成
                hubspot_id = os.getenv('HUBSPOT_ID', '')
                contacts = []
                
                for contact_data in contacts_data:
                    if isinstance(contact_data, dict):
                        contact_id = contact_data.get('id', '')
                        contact_name = contact_data.get('name', contact_id)
                        # バッチ処理時に取得した会社名を使用（データベースに保存済み）
                        company_name = contact_data.get('company_name', '-')
                    else:
                        # 古い形式（文字列のみ）の場合
                        contact_id = str(contact_data)
                        contact_name = contact_id
                        company_name = '-'
                    
                    if contact_id:
                        contacts.append({
                            "id": contact_id,
                            "name": contact_name,
                            "company_name": company_name,
                            "hubspot_link": f"https://app.hubspot.com/contacts/{hubspot_id}/contact/{contact_id}"
                        })
                
                return {
                    "contacts": contacts
                }
