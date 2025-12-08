import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import aiomysql
from services.profit_target_service import ProfitTargetService

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
        self.profit_target_service = ProfitTargetService(db_pool)

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
                
                # 目標額を計算して追加
                summary = await self._add_targets_to_summary(summary, year, "purchase")
                
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
                
                # 目標額を計算して追加
                summary = await self._add_targets_to_summary(summary, year, "sales")
                
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
                
                # 目標額を計算して追加
                summary = await self._add_targets_to_summary(summary, year, "profit")
                
                return summary

    async def _get_profit_targets_by_year(self, year: int) -> Dict[str, Dict[int, Decimal]]:
        """年度別に粗利目標を取得（担当者名（表示名） => Q => 目標額）"""
        targets = {}
        
        # 粗利目標管理テーブルから年度で検索
        from models.profit_target import ProfitTargetSearchRequest
        search_request = ProfitTargetSearchRequest(year=year, limit=1000, offset=0)
        target_list = await self.profit_target_service.search_profit_target(search_request)
        
        # データベースの担当者名（姓名）から表示名（苗字）への逆マッピング
        db_name_to_display_name = {v: k for k, v in self.OWNER_NAME_MAPPING.items()}
        
        for target in target_list.items:
            # データベースの担当者名（姓名）を表示名（苗字）に変換
            owner_name = db_name_to_display_name.get(target.owner_name)
            if not owner_name:
                # マッピングにない場合は、そのまま使用
                owner_name = target.owner_name
            
            if owner_name not in targets:
                targets[owner_name] = {}
            
            # 各Qの目標額を設定
            if target.q1_target:
                targets[owner_name][1] = Decimal(str(target.q1_target))
            if target.q2_target:
                targets[owner_name][2] = Decimal(str(target.q2_target))
            if target.q3_target:
                targets[owner_name][3] = Decimal(str(target.q3_target))
            if target.q4_target:
                targets[owner_name][4] = Decimal(str(target.q4_target))
        
        return targets

    async def _add_targets_to_summary(self, summary: Dict[str, Any], year: int, report_type: str) -> Dict[str, Any]:
        """集計データに目標額を追加"""
        # 粗利目標を取得
        profit_targets = await self._get_profit_targets_by_year(year)
        
        # 粗利目標の合計を計算（各Qごと）- レポートに出力している担当者のみ
        profit_target_totals = {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)}
        for owner_name in self.OWNER_NAMES:
            if owner_name in profit_targets:
                for q, target in profit_targets[owner_name].items():
                    profit_target_totals[q] += target
        
        # 販売目標の合計を計算（各Qごと）
        # 販売の各Qの目標合計 = 粗利の目標合計 / 8.4%
        # スプレッドシートの計算式: =粗利の各Qの合計/8.4%
        # 8.4% = 0.084 なので、粗利の目標合計 / 0.084
        sales_target_totals = {}
        for q in [1, 2, 3, 4]:
            if profit_target_totals[q] > 0:
                # 8.4% = 8.4 / 100 = 0.084
                # 小数点以下を四捨五入
                sales_target_totals[q] = (profit_target_totals[q] / (Decimal("8.4") / Decimal("100"))).quantize(Decimal("1"), rounding="ROUND_HALF_UP")
            else:
                sales_target_totals[q] = Decimal(0)
        
        # 各担当者の目標額を計算
        owner_targets = {}
        for owner_name in self.OWNER_NAMES:
            owner_targets[owner_name] = {
                "profit": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)},
                "sales": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)},
                "purchase": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)}
            }
            
            # 粗利目標を取得
            if owner_name in profit_targets:
                for q in [1, 2, 3, 4]:
                    if q in profit_targets[owner_name]:
                        owner_targets[owner_name]["profit"][q] = profit_targets[owner_name][q]
            
            # 販売目標を計算
            # 各担当者の各Qの目標額 = 販売の目標合計 * 粗利の目標 / 粗利の目標合計
            for q in [1, 2, 3, 4]:
                if profit_target_totals[q] > 0 and owner_targets[owner_name]["profit"][q] > 0:
                    # 小数点以下を四捨五入
                    owner_targets[owner_name]["sales"][q] = (
                        sales_target_totals[q] * owner_targets[owner_name]["profit"][q] / profit_target_totals[q]
                    ).quantize(Decimal("1"), rounding="ROUND_HALF_UP")
                else:
                    owner_targets[owner_name]["sales"][q] = Decimal(0)
            
            # 仕入目標を計算
            # 仕入の各Qの各担当者の目標額 = 担当者の同Qの目標額 * (1 - 8.6%)
            for q in [1, 2, 3, 4]:
                # 小数点以下を四捨五入
                owner_targets[owner_name]["purchase"][q] = (
                    owner_targets[owner_name]["sales"][q] * Decimal("0.914")
                ).quantize(Decimal("1"), rounding="ROUND_HALF_UP")
        
        # 合計行の目標額を計算（レポートに出力している担当者のみの合計）
        total_targets = {
            "profit": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)},
            "sales": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)},
            "purchase": {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)}
        }
        
        # レポートに出力している担当者のみの合計を計算
        for owner_name in self.OWNER_NAMES:
            for q in [1, 2, 3, 4]:
                total_targets["profit"][q] += owner_targets[owner_name]["profit"][q]
                total_targets["sales"][q] += owner_targets[owner_name]["sales"][q]
                total_targets["purchase"][q] += owner_targets[owner_name]["purchase"][q]
        
        # データ構造に目標額を追加
        for owner_name in self.OWNER_NAMES:
            # 上期目標 = 1Q目標額 + 2Q目標額
            first_half_target = owner_targets[owner_name][report_type][1] + owner_targets[owner_name][report_type][2]
            # 下期目標 = 3Q目標額 + 4Q目標額
            second_half_target = owner_targets[owner_name][report_type][3] + owner_targets[owner_name][report_type][4]
            # 年間目標 = 上期目標 + 下期目標
            annual_target = first_half_target + second_half_target
            
            if owner_name in summary["owners"]:
                summary["owners"][owner_name]["targets"] = {
                    "quarters": {
                        1: float(owner_targets[owner_name][report_type][1]),
                        2: float(owner_targets[owner_name][report_type][2]),
                        3: float(owner_targets[owner_name][report_type][3]),
                        4: float(owner_targets[owner_name][report_type][4])
                    },
                    "half_years": {
                        "first": float(first_half_target),
                        "second": float(second_half_target)
                    },
                    "total": float(annual_target)
                }
            else:
                summary["owners"][owner_name] = {
                    "months": {i: 0 for i in range(1, 13)},
                    "quarters": {1: 0, 2: 0, 3: 0, 4: 0},
                    "half_years": {"first": 0, "second": 0},
                    "total": 0,
                    "targets": {
                        "quarters": {
                            1: float(owner_targets[owner_name][report_type][1]),
                            2: float(owner_targets[owner_name][report_type][2]),
                            3: float(owner_targets[owner_name][report_type][3]),
                            4: float(owner_targets[owner_name][report_type][4])
                        },
                        "half_years": {
                            "first": float(first_half_target),
                            "second": float(second_half_target)
                        },
                        "total": float(annual_target)
                    }
                }
        
        # 合計行の上期目標と下期目標を計算
        total_first_half_target = total_targets[report_type][1] + total_targets[report_type][2]
        total_second_half_target = total_targets[report_type][3] + total_targets[report_type][4]
        # 合計行の年間目標 = 上期目標 + 下期目標
        total_annual_target = total_first_half_target + total_second_half_target
        
        # 合計行に目標額を追加
        summary["total"]["targets"] = {
            "quarters": {
                1: float(total_targets[report_type][1]),
                2: float(total_targets[report_type][2]),
                3: float(total_targets[report_type][3]),
                4: float(total_targets[report_type][4])
            },
            "half_years": {
                "first": float(total_first_half_target),
                "second": float(total_second_half_target)
            },
            "total": float(total_annual_target)
        }
        
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

