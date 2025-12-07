import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import aiomysql
from models.property_owner import (
    PropertyOwnerCreate,
    PropertyOwnerUpdate,
    PropertyOwnerResponse,
    PropertyOwnerSearchRequest,
    PropertyOwnerListResponse,
    OwnerType
)

logger = logging.getLogger(__name__)


class PropertyOwnerService:
    """物件担当者サービス"""
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool

    async def create_property_owner(self, data: PropertyOwnerCreate) -> PropertyOwnerResponse:
        """物件担当者レコードを作成"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                INSERT INTO property_owners (
                    property_id, profit_management_seq_no, owner_type, owner_id, owner_name,
                    settlement_date, price, profit_rate, profit_amount
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """
                
                # profit_management_seq_noを取得（オプショナルフィールド）
                profit_management_seq_no = None
                if hasattr(data, 'profit_management_seq_no'):
                    profit_management_seq_no = data.profit_management_seq_no
                elif hasattr(data, 'dict'):
                    data_dict = data.dict()
                    profit_management_seq_no = data_dict.get('profit_management_seq_no')
                elif hasattr(data, 'model_dump'):
                    data_dict = data.model_dump()
                    profit_management_seq_no = data_dict.get('profit_management_seq_no')
                
                values = (
                    data.property_id,
                    profit_management_seq_no,
                    data.owner_type.value,
                    data.owner_id,
                    data.owner_name,
                    data.settlement_date,
                    data.price,
                    data.profit_rate,
                    data.profit_amount
                )
                
                await cursor.execute(query, values)
                await conn.commit()
                
                # 作成されたレコードを取得
                owner_id = cursor.lastrowid
                return await self.get_property_owner_by_id(owner_id)

    async def get_property_owner_by_id(self, owner_id: int) -> Optional[PropertyOwnerResponse]:
        """IDで物件担当者レコードを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM property_owners WHERE id = %s"
                await cursor.execute(query, (owner_id,))
                result = await cursor.fetchone()
                
                if result:
                    return self._dict_to_response(result)
                return None

    async def get_property_owners_by_property_id(self, property_id: str) -> List[PropertyOwnerResponse]:
        """物件IDで物件担当者レコード一覧を取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM property_owners WHERE property_id = %s ORDER BY owner_type, id"
                await cursor.execute(query, (property_id,))
                results = await cursor.fetchall()
                
                return [self._dict_to_response(result) for result in results]

    async def get_property_owners_by_seq_no(self, seq_no: int) -> List[PropertyOwnerResponse]:
        """粗利按分管理seq_noで物件担当者レコード一覧を取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM property_owners WHERE profit_management_seq_no = %s ORDER BY owner_type, id"
                await cursor.execute(query, (seq_no,))
                results = await cursor.fetchall()
                
                return [self._dict_to_response(result) for result in results]

    async def update_property_owner(self, owner_id: int, data: PropertyOwnerUpdate) -> Optional[PropertyOwnerResponse]:
        """物件担当者レコードを更新"""
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
                    return await self.get_property_owner_by_id(owner_id)
                
                values.append(owner_id)
                
                query = f"""
                UPDATE property_owners 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """
                
                await cursor.execute(query, values)
                await conn.commit()
                
                return await self.get_property_owner_by_id(owner_id)

    async def delete_property_owner(self, owner_id: int) -> bool:
        """物件担当者レコードを削除"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "DELETE FROM property_owners WHERE id = %s"
                result = await cursor.execute(query, (owner_id,))
                await conn.commit()
                return result > 0

    async def search_property_owners(self, search_request: PropertyOwnerSearchRequest) -> PropertyOwnerListResponse:
        """物件担当者レコードを検索"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # デバッグ: データベース名とテーブル存在確認
                try:
                    await cursor.execute("SELECT DATABASE() as current_db")
                    db_result = await cursor.fetchone()
                    current_db = db_result.get('current_db') if db_result else 'unknown'
                    logger.info(f"[property_owners] 現在のデータベース: {current_db}")
                except Exception as e:
                    logger.error(f"[property_owners] データベース名取得エラー: {str(e)}")
                
                # WHERE条件を構築
                where_conditions = []
                values = []
                
                if search_request.property_id:
                    where_conditions.append("property_id LIKE %s")
                    values.append(f"%{search_request.property_id}%")
                
                if search_request.owner_type:
                    where_conditions.append("owner_type = %s")
                    values.append(search_request.owner_type.value)
                
                if search_request.owner_id:
                    where_conditions.append("owner_id LIKE %s")
                    values.append(f"%{search_request.owner_id}%")
                
                if search_request.owner_name:
                    where_conditions.append("owner_name LIKE %s")
                    values.append(f"%{search_request.owner_name}%")
                
                if search_request.settlement_date_from:
                    where_conditions.append("settlement_date >= %s")
                    values.append(search_request.settlement_date_from)
                
                if search_request.settlement_date_to:
                    where_conditions.append("settlement_date <= %s")
                    values.append(search_request.settlement_date_to)
                
                # 総件数を取得
                count_query = "SELECT COUNT(*) as total FROM property_owners"
                if where_conditions:
                    count_query += " WHERE " + " AND ".join(where_conditions)
                
                await cursor.execute(count_query, values)
                total_result = await cursor.fetchone()
                total = total_result['total'] if total_result else 0
                
                # データを取得
                query = "SELECT * FROM property_owners"
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)
                
                query += " ORDER BY property_id, owner_type, id"
                query += " LIMIT %s OFFSET %s"
                
                values.extend([search_request.limit, search_request.offset])
                
                await cursor.execute(query, values)
                results = await cursor.fetchall()
                
                items = [self._dict_to_response(result) for result in results]
                
                return PropertyOwnerListResponse(
                    items=items,
                    total=total,
                    limit=search_request.limit,
                    offset=search_request.offset
                )

    def _dict_to_response(self, data: Dict[str, Any]) -> PropertyOwnerResponse:
        """辞書データをレスポンスモデルに変換"""
        return PropertyOwnerResponse(
            id=data['id'],
            property_id=data['property_id'],
            owner_type=OwnerType(data['owner_type']),
            owner_id=data['owner_id'],
            owner_name=data['owner_name'],
            settlement_date=data['settlement_date'],
            price=data['price'],
            profit_rate=data['profit_rate'],
            profit_amount=data['profit_amount'],
            created_at=data['created_at'],
            updated_at=data['updated_at']
        )






