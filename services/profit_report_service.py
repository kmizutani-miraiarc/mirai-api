import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import aiomysql

logger = logging.getLogger(__name__)


class ProfitReportService:
    """粗利集計レポートサービス"""
    
    # 担当者名のマッピング（表示順序）
    # 表示名 => データベースの担当者名（姓名）
    OWNER_NAME_MAPPING = {
        "久世": "久世 健人",
        "藤森": "藤森 日加里",
        "赤瀬": "赤瀬 公平",
        "根本": "根本",
        "山岡": "山岡 弘明",
        "岩崎": "岩崎 陽",
        "藤村": "藤村 ひかり",
        "鈴木": "鈴木 勇汰"
    }
    
    # 表示順序
    OWNER_NAMES = ["久世", "藤森", "赤瀬", "根本", "山岡", "岩崎", "藤村", "鈴木"]
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool
        # データベースの担当者名リスト（SQLクエリ用）
        self.owner_db_names = list(self.OWNER_NAME_MAPPING.values())

    async def get_purchase_summary(self, year: int) -> Dict[str, Any]:
        """仕入集計を取得（仕入決済日を基準に仕入価格を集計）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 担当者名のプレースホルダーを生成
                placeholders = ','.join(['%s'] * len(self.owner_db_names))
                query = f"""
                SELECT 
                    po.owner_name,
                    MONTH(pm.purchase_settlement_date) as month,
                    COALESCE(SUM(pm.purchase_price), 0) as total_amount
                FROM profit_management pm
                INNER JOIN property_owners po ON pm.seq_no = po.profit_management_seq_no
                WHERE YEAR(pm.purchase_settlement_date) = %s
                    AND po.owner_type = 'purchase'
                    AND pm.purchase_settlement_date IS NOT NULL
                    AND pm.profit_confirmed = 1
                    AND po.owner_name IN ({placeholders})
                GROUP BY po.owner_name, MONTH(pm.purchase_settlement_date)
                ORDER BY po.owner_name, MONTH(pm.purchase_settlement_date)
                """
                
                await cursor.execute(query, [year] + self.owner_db_names)
                results = await cursor.fetchall()
                
                # データを構造化
                summary = self._structure_monthly_data(results, "purchase", year)
                
                return summary

    async def get_sales_summary(self, year: int) -> Dict[str, Any]:
        """販売集計を取得（販売決済日を基準に販売価格を集計）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 担当者名のプレースホルダーを生成
                placeholders = ','.join(['%s'] * len(self.owner_db_names))
                query = f"""
                SELECT 
                    po.owner_name,
                    MONTH(pm.sales_settlement_date) as month,
                    COALESCE(SUM(pm.sales_price), 0) as total_amount
                FROM profit_management pm
                INNER JOIN property_owners po ON pm.seq_no = po.profit_management_seq_no
                WHERE YEAR(pm.sales_settlement_date) = %s
                    AND po.owner_type = 'sales'
                    AND pm.sales_settlement_date IS NOT NULL
                    AND pm.profit_confirmed = 1
                    AND po.owner_name IN ({placeholders})
                GROUP BY po.owner_name, MONTH(pm.sales_settlement_date)
                ORDER BY po.owner_name, MONTH(pm.sales_settlement_date)
                """
                
                await cursor.execute(query, [year] + self.owner_db_names)
                results = await cursor.fetchall()
                
                # データを構造化
                summary = self._structure_monthly_data(results, "sales", year)
                
                return summary

    async def get_profit_summary(self, year: int) -> Dict[str, Any]:
        """粗利集計を取得（計上年月を基準に仕入担当者と販売担当者の粗利額の合計を集計）"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 担当者名のプレースホルダーを生成
                placeholders = ','.join(['%s'] * len(self.owner_db_names))
                query = f"""
                SELECT 
                    po.owner_name,
                    MONTH(pm.accounting_year_month) as month,
                    COALESCE(SUM(po.profit_amount), 0) as total_amount
                FROM profit_management pm
                INNER JOIN property_owners po ON pm.seq_no = po.profit_management_seq_no
                WHERE YEAR(pm.accounting_year_month) = %s
                    AND pm.accounting_year_month IS NOT NULL
                    AND pm.profit_confirmed = 1
                    AND po.owner_name IN ({placeholders})
                GROUP BY po.owner_name, MONTH(pm.accounting_year_month)
                ORDER BY po.owner_name, MONTH(pm.accounting_year_month)
                """
                
                await cursor.execute(query, [year] + self.owner_db_names)
                results = await cursor.fetchall()
                
                # データを構造化
                summary = self._structure_monthly_data(results, "profit", year)
                
                return summary

    def _structure_monthly_data(self, results: List[Dict[str, Any]], report_type: str, year: int) -> Dict[str, Any]:
        """月次データを構造化（担当者別、月別、四半期別、半期別、年間合計）"""
        # 初期化：担当者ごとのデータ構造
        owner_data = {name: {
            "months": {i: Decimal(0) for i in range(1, 13)},
            "quarters": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)},
            "half_years": {"first": Decimal(0), "second": Decimal(0)},
            "total": Decimal(0)
        } for name in self.OWNER_NAMES}
        
        # 合計行
        total_row = {
            "months": {i: Decimal(0) for i in range(1, 13)},
            "quarters": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)},
            "half_years": {"first": Decimal(0), "second": Decimal(0)},
            "total": Decimal(0)
        }
        
        # データを集計
        # データベースの担当者名（姓名）から表示名（苗字）への逆マッピング
        db_name_to_display_name = {v: k for k, v in self.OWNER_NAME_MAPPING.items()}
        
        for row in results:
            owner_db_name = row.get('owner_name')
            month = row.get('month')
            amount = Decimal(str(row.get('total_amount') or 0))
            
            if not owner_db_name or not month:
                continue
            
            # データベースの担当者名（姓名）を表示名（苗字）に変換
            owner_name = db_name_to_display_name.get(owner_db_name)
            if not owner_name:
                # マッピングにない場合は、そのまま使用（後方互換性のため）
                owner_name = owner_db_name
            
            if owner_name in owner_data:
                # 月次データ
                owner_data[owner_name]["months"][month] += amount
                
                # 四半期データ
                if month in [1, 2, 3]:
                    owner_data[owner_name]["quarters"][1] += amount
                elif month in [4, 5, 6]:
                    owner_data[owner_name]["quarters"][2] += amount
                elif month in [7, 8, 9]:
                    owner_data[owner_name]["quarters"][3] += amount
                elif month in [10, 11, 12]:
                    owner_data[owner_name]["quarters"][4] += amount
                
                # 半期データ
                if month in [1, 2, 3, 4, 5, 6]:
                    owner_data[owner_name]["half_years"]["first"] += amount
                elif month in [7, 8, 9, 10, 11, 12]:
                    owner_data[owner_name]["half_years"]["second"] += amount
                
                # 年間合計
                owner_data[owner_name]["total"] += amount
                
                # 合計行にも追加
                total_row["months"][month] += amount
                if month in [1, 2, 3]:
                    total_row["quarters"][1] += amount
                elif month in [4, 5, 6]:
                    total_row["quarters"][2] += amount
                elif month in [7, 8, 9]:
                    total_row["quarters"][3] += amount
                elif month in [10, 11, 12]:
                    total_row["quarters"][4] += amount
                if month in [1, 2, 3, 4, 5, 6]:
                    total_row["half_years"]["first"] += amount
                elif month in [7, 8, 9, 10, 11, 12]:
                    total_row["half_years"]["second"] += amount
                total_row["total"] += amount
        
        # Decimal型をfloat型に変換（JSONシリアライズ対応）
        def convert_decimal(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimal(item) for item in obj]
            return obj
        
        return {
            "report_type": report_type,
            "year": year,
            "owners": convert_decimal(owner_data),
            "total": convert_decimal(total_row)
        }

