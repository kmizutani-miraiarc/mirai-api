import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiomysql
from models.haihai_click_log import (
    HaihaiClickLogCreate,
    HaihaiClickLogUpdate,
    HaihaiClickLogResponse,
    HaihaiClickLogSearchRequest,
    HaihaiClickLogListResponse
)

logger = logging.getLogger(__name__)


class HaihaiClickLogService:
    """配配メールログサービス"""
    
    def __init__(self, db_pool: aiomysql.Pool):
        self.db_pool = db_pool

    async def create_haihai_click_log(self, data: HaihaiClickLogCreate) -> HaihaiClickLogResponse:
        """配配メールログレコードを作成"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                INSERT INTO haihai_click_logs (
                    email, mail_type, mail_id, subject, click_date, url
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
                """
                
                values = (
                    data.email,
                    data.mail_type,
                    data.mail_id,
                    data.subject,
                    data.click_date,
                    data.url
                )
                
                await cursor.execute(query, values)
                await conn.commit()
                
                # 作成されたレコードを取得
                log_id = cursor.lastrowid
                return await self.get_haihai_click_log_by_id(log_id)

    async def get_haihai_click_log_by_id(self, log_id: int) -> Optional[HaihaiClickLogResponse]:
        """IDで配配メールログレコードを取得"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM haihai_click_logs WHERE id = %s"
                await cursor.execute(query, (log_id,))
                result = await cursor.fetchone()
                
                if result:
                    return self._dict_to_response(result)
                return None

    async def update_haihai_click_log(self, log_id: int, data: HaihaiClickLogUpdate) -> Optional[HaihaiClickLogResponse]:
        """配配メールログレコードを更新"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 更新フィールドを動的に構築
                update_fields = []
                values = []
                
                for field, value in data.dict(exclude_unset=True).items():
                    if value is not None:
                        # スネークケースに変換
                        db_field = field
                        if field == 'mail_type':
                            db_field = 'mail_type'
                        elif field == 'mail_id':
                            db_field = 'mail_id'
                        elif field == 'click_date':
                            db_field = 'click_date'
                        
                        update_fields.append(f"{db_field} = %s")
                        values.append(value)
                
                if not update_fields:
                    return await self.get_haihai_click_log_by_id(log_id)
                
                values.append(log_id)
                
                query = f"""
                UPDATE haihai_click_logs 
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """
                
                await cursor.execute(query, values)
                await conn.commit()
                
                return await self.get_haihai_click_log_by_id(log_id)

    async def delete_haihai_click_log(self, log_id: int) -> bool:
        """配配メールログレコードを削除"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "DELETE FROM haihai_click_logs WHERE id = %s"
                result = await cursor.execute(query, (log_id,))
                await conn.commit()
                return result > 0

    async def search_haihai_click_logs(self, search_request: HaihaiClickLogSearchRequest) -> HaihaiClickLogListResponse:
        """配配メールログレコードを検索"""
        async with self.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # データベース名とテーブル存在確認（デバッグ用）
                try:
                    await cursor.execute("SELECT DATABASE() as current_db")
                    db_result = await cursor.fetchone()
                    current_db = db_result.get('current_db') if db_result else 'unknown'
                    logger.info(f"現在のデータベース: {current_db}")
                    
                    await cursor.execute("SHOW TABLES LIKE 'haihai_click_logs'")
                    table_exists = await cursor.fetchone()
                    if table_exists:
                        logger.info("テーブル 'haihai_click_logs' は存在します")
                    else:
                        logger.warning(f"テーブル 'haihai_click_logs' がデータベース '{current_db}' に存在しません")
                        # すべてのテーブルをリストアップ
                        await cursor.execute("SHOW TABLES")
                        all_tables = await cursor.fetchall()
                        table_names = [list(table.values())[0] for table in all_tables]
                        logger.info(f"データベース '{current_db}' のテーブル一覧: {table_names}")
                except Exception as debug_error:
                    logger.error(f"デバッグ情報の取得中にエラー: {str(debug_error)}")
                
                # WHERE条件を構築
                where_conditions = []
                values = []
                
                if search_request.email:
                    where_conditions.append("email LIKE %s")
                    values.append(f"%{search_request.email}%")
                
                if search_request.mail_type:
                    where_conditions.append("mail_type = %s")
                    values.append(search_request.mail_type)
                
                if search_request.mail_id:
                    where_conditions.append("mail_id LIKE %s")
                    values.append(f"%{search_request.mail_id}%")
                
                if search_request.start_date:
                    where_conditions.append("click_date >= %s")
                    values.append(search_request.start_date)
                
                if search_request.end_date:
                    where_conditions.append("click_date <= %s")
                    values.append(search_request.end_date)
                
                # 総件数を取得
                count_query = "SELECT COUNT(*) as total FROM haihai_click_logs"
                if where_conditions:
                    count_query += " WHERE " + " AND ".join(where_conditions)
                
                await cursor.execute(count_query, values)
                total_result = await cursor.fetchone()
                total = total_result['total'] if total_result else 0
                
                # データを取得
                query = "SELECT * FROM haihai_click_logs"
                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)
                
                query += " ORDER BY click_date DESC, created_at DESC"
                query += " LIMIT %s OFFSET %s"
                
                values.extend([search_request.limit, search_request.offset])
                
                await cursor.execute(query, values)
                results = await cursor.fetchall()
                
                items = [self._dict_to_response(result) for result in results]
                
                return HaihaiClickLogListResponse(
                    items=items,
                    total=total,
                    limit=search_request.limit,
                    offset=search_request.offset
                )

    def _dict_to_response(self, data: Dict[str, Any]) -> HaihaiClickLogResponse:
        """辞書データをレスポンスモデルに変換"""
        return HaihaiClickLogResponse(
            id=data['id'],
            email=data['email'],
            mail_type=data['mail_type'],
            mail_id=data['mail_id'],
            subject=data['subject'],
            click_date=data['click_date'],
            url=data['url'],
            created_at=data['created_at'],
            updated_at=data['updated_at']
        )

