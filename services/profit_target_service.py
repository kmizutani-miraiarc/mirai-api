import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
import aiomysql
from models.profit_target import (
    ProfitTargetCreate,
    ProfitTargetUpdate,
    ProfitTargetResponse,
    ProfitTargetSearchRequest,
    ProfitTargetListResponse
)

logger = logging.getLogger(__name__)


class ProfitTargetService:
    """粗利目標管理サービス"""
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool

    async def create_profit_target(self, data: ProfitTargetCreate) -> ProfitTargetResponse:
        """粗利目標レコードを作成"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                INSERT INTO profit_target (
                    owner_id, owner_name, year,
                    q1_target, q2_target, q3_target, q4_target
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                """
                
                values = (
                    data.owner_id,
                    data.owner_name,
                    data.year,
                    data.q1_target,
                    data.q2_target,
                    data.q3_target,
                    data.q4_target
                )
                
                await cursor.execute(query, values)
                await conn.commit()
                
                # 作成されたレコードを取得
                target_id = cursor.lastrowid
                return await self.get_profit_target_by_id(target_id)

    async def get_profit_target_by_id(self, target_id: int) -> Optional[ProfitTargetResponse]:
        """IDで粗利目標レコードを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM profit_target WHERE id = %s"
                await cursor.execute(query, (target_id,))
                result = await cursor.fetchone()
                
                if result:
                    return self._dict_to_response(result)
                return None

    async def get_profit_target_by_owner_and_year(self, owner_id: str, year: int) -> Optional[ProfitTargetResponse]:
        """担当者IDと年度で粗利目標レコードを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM profit_target WHERE owner_id = %s AND year = %s"
                await cursor.execute(query, (owner_id, year))
                result = await cursor.fetchone()
                
                if result:
                    return self._dict_to_response(result)
                return None

    async def update_profit_target(self, target_id: int, data: ProfitTargetUpdate) -> Optional[ProfitTargetResponse]:
        """粗利目標レコードを更新"""
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
                    return await self.get_profit_target_by_id(target_id)
                
                values.append(target_id)
                
                query = f"""
                UPDATE profit_target 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """
                
                await cursor.execute(query, values)
                await conn.commit()
                
                return await self.get_profit_target_by_id(target_id)

    async def delete_profit_target(self, target_id: int) -> bool:
        """粗利目標レコードを削除"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "DELETE FROM profit_target WHERE id = %s"
                result = await cursor.execute(query, (target_id,))
                await conn.commit()
                return result > 0

    async def search_profit_target(self, search_request: ProfitTargetSearchRequest) -> ProfitTargetListResponse:
        """粗利目標レコードを検索"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # WHERE条件を構築
                where_conditions = []
                values = []
                
                if search_request.owner_id:
                    where_conditions.append("owner_id = %s")
                    values.append(search_request.owner_id)
                
                if search_request.year:
                    where_conditions.append("year = %s")
                    values.append(search_request.year)
                
                # 総件数を取得
                count_query = "SELECT COUNT(*) as total FROM profit_target"
                if where_conditions:
                    count_query += " WHERE " + " AND ".join(where_conditions)
                
                await cursor.execute(count_query, values)
                total_result = await cursor.fetchone()
                total = total_result['total'] if total_result else 0
                
                # データを取得
                query = "SELECT * FROM profit_target"
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)
                
                query += " ORDER BY year DESC, owner_name ASC"
                query += " LIMIT %s OFFSET %s"
                
                values.extend([search_request.limit, search_request.offset])
                
                await cursor.execute(query, values)
                results = await cursor.fetchall()
                
                items = []
                for result in results:
                    items.append(self._dict_to_response(result))
                
                return ProfitTargetListResponse(
                    items=items,
                    total=total,
                    limit=search_request.limit,
                    offset=search_request.offset
                )

    def _dict_to_response(self, data: Dict[str, Any]) -> ProfitTargetResponse:
        """辞書データをレスポンスモデルに変換"""
        return ProfitTargetResponse(
            id=data['id'],
            owner_id=data['owner_id'],
            owner_name=data['owner_name'],
            year=data['year'],
            q1_target=data.get('q1_target'),
            q2_target=data.get('q2_target'),
            q3_target=data.get('q3_target'),
            q4_target=data.get('q4_target'),
            created_at=data['created_at'],
            updated_at=data['updated_at']
        )

