import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import aiomysql
from models.profit_management import (
    ProfitManagementCreate,
    ProfitManagementUpdate,
    ProfitManagementResponse,
    ProfitManagementSearchRequest,
    ProfitManagementListResponse
)
from services.property_owner_service import PropertyOwnerService

logger = logging.getLogger(__name__)


class ProfitManagementService:
    """粗利按分管理サービス"""
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool
        self.property_owner_service = PropertyOwnerService(db_pool)

    async def create_profit_management(self, data: ProfitManagementCreate) -> ProfitManagementResponse:
        """粗利按分管理レコードを作成"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                INSERT INTO profit_management (
                    property_id, property_name, property_type,
                    purchase_settlement_date, purchase_price,
                    sales_settlement_date, sales_price,
                    gross_profit, profit_confirmed, accounting_year_month
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
                
                values = (
                    data.property_id,
                    data.property_name,
                    data.property_type,
                    data.purchase_settlement_date,
                    data.purchase_price,
                    data.sales_settlement_date,
                    data.sales_price,
                    data.gross_profit,
                    data.profit_confirmed,
                    data.accounting_year_month
                )
                
                await cursor.execute(query, values)
                await conn.commit()
                
                # 作成されたレコードを取得
                seq_no = cursor.lastrowid
                return await self.get_profit_management_by_seq_no(seq_no)

    async def get_profit_management_by_seq_no(self, seq_no: int) -> Optional[ProfitManagementResponse]:
        """SeqNoで粗利按分管理レコードを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM profit_management WHERE seq_no = %s"
                await cursor.execute(query, (seq_no,))
                result = await cursor.fetchone()
                
                if result:
                    response = self._dict_to_response(result)
                    # 物件担当者情報を取得（seq_noで取得）
                    response.owners = await self.property_owner_service.get_property_owners_by_seq_no(seq_no)
                    return response
                return None

    async def get_profit_management_by_property_id(self, property_id: str) -> Optional[ProfitManagementResponse]:
        """物件IDで粗利按分管理レコードを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM profit_management WHERE property_id = %s"
                await cursor.execute(query, (property_id,))
                result = await cursor.fetchone()
                
                if result:
                    response = self._dict_to_response(result)
                    # 物件担当者情報を取得
                    response.owners = await self.property_owner_service.get_property_owners_by_property_id(property_id)
                    return response
                return None

    async def update_profit_management(self, seq_no: int, data: ProfitManagementUpdate) -> Optional[ProfitManagementResponse]:
        """粗利按分管理レコードを更新"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 更新フィールドを動的に構築
                update_fields = []
                values = []
                
                for field, value in data.dict(exclude_unset=True).items():
                    if value is not None:
                        update_fields.append(f"{field} = %s")
                        values.append(value)
                
                if not update_fields:
                    return await self.get_profit_management_by_seq_no(seq_no)
                
                values.append(seq_no)
                
                query = f"""
                UPDATE profit_management 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE seq_no = %s
                """
                
                await cursor.execute(query, values)
                await conn.commit()
                
                return await self.get_profit_management_by_seq_no(seq_no)

    async def delete_profit_management(self, seq_no: int) -> bool:
        """粗利按分管理レコードを削除"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "DELETE FROM profit_management WHERE seq_no = %s"
                result = await cursor.execute(query, (seq_no,))
                await conn.commit()
                return result > 0

    async def search_profit_management(self, search_request: ProfitManagementSearchRequest) -> ProfitManagementListResponse:
        """粗利按分管理レコードを検索"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # WHERE条件を構築
                where_conditions = []
                values = []
                
                if search_request.accounting_year:
                    where_conditions.append("YEAR(accounting_year_month) = %s")
                    values.append(search_request.accounting_year)
                
                if search_request.property_name:
                    where_conditions.append("property_name LIKE %s")
                    values.append(f"%{search_request.property_name}%")
                
                if search_request.profit_confirmed is not None:
                    where_conditions.append("profit_confirmed = %s")
                    values.append(search_request.profit_confirmed)
                
                # 総件数を取得
                count_query = "SELECT COUNT(*) as total FROM profit_management"
                if where_conditions:
                    count_query += " WHERE " + " AND ".join(where_conditions)
                
                await cursor.execute(count_query, values)
                total_result = await cursor.fetchone()
                total = total_result['total'] if total_result else 0
                
                # データを取得
                query = "SELECT * FROM profit_management"
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)
                
                query += " ORDER BY seq_no DESC"
                query += " LIMIT %s OFFSET %s"
                
                values.extend([search_request.limit, search_request.offset])
                
                await cursor.execute(query, values)
                results = await cursor.fetchall()
                
                items = []
                for result in results:
                    response = self._dict_to_response(result)
                    # 物件担当者情報を取得（seq_noで取得）
                    response.owners = await self.property_owner_service.get_property_owners_by_seq_no(result['seq_no'])
                    items.append(response)
                
                return ProfitManagementListResponse(
                    items=items,
                    total=total,
                    limit=search_request.limit,
                    offset=search_request.offset
                )

    def _dict_to_response(self, data: Dict[str, Any]) -> ProfitManagementResponse:
        """辞書データをレスポンスモデルに変換"""
        return ProfitManagementResponse(
            seq_no=data['seq_no'],
            property_id=data['property_id'],
            property_name=data['property_name'],
            property_type=data['property_type'],
            purchase_settlement_date=data.get('purchase_settlement_date'),
            purchase_price=data.get('purchase_price'),
            sales_settlement_date=data.get('sales_settlement_date'),
            sales_price=data.get('sales_price'),
            gross_profit=data['gross_profit'],
            profit_confirmed=data['profit_confirmed'],
            accounting_year_month=data.get('accounting_year_month'),
            created_at=data['created_at'],
            updated_at=data['updated_at']
        )
