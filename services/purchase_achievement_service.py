import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from database.connection import db_connection
from models.purchase_achievement import PurchaseAchievementCreate, PurchaseAchievementUpdate

logger = logging.getLogger(__name__)

# 日付型を適切に処理するためのヘルパー関数
def format_date_for_db(d: Optional[date]) -> Optional[str]:
    """dateをMySQL用の文字列に変換"""
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")

def format_datetime_for_db(dt: Optional[datetime]) -> Optional[str]:
    """datetimeをMySQL用の文字列に変換"""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")

class PurchaseAchievementService:
    """物件買取実績サービスクラス"""
    
    def _convert_date_types(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """データベースから取得した日付型を適切に変換"""
        # date型をdateオブジェクトに変換（aiomysqlは文字列として返す可能性がある）
        if result.get("purchase_date") and isinstance(result["purchase_date"], str):
            try:
                from datetime import datetime as dt
                result["purchase_date"] = dt.strptime(result["purchase_date"], "%Y-%m-%d").date()
            except:
                pass
        # datetime型をdatetimeオブジェクトに変換
        for datetime_field in ["hubspot_bukken_created_date", "created_at", "updated_at"]:
            if result.get(datetime_field) and isinstance(result[datetime_field], str):
                try:
                    from datetime import datetime as dt
                    result[datetime_field] = dt.strptime(result[datetime_field], "%Y-%m-%d %H:%M:%S")
                except:
                    try:
                        from datetime import datetime as dt
                        result[datetime_field] = dt.fromisoformat(result[datetime_field].replace("Z", "+00:00"))
                    except:
                        pass
        return result
    
    async def create(self, achievement: PurchaseAchievementCreate) -> int:
        """物件買取実績を作成"""
        try:
            query = """
                INSERT INTO purchase_achievements (
                    property_image_url,
                    purchase_date,
                    title,
                    property_name,
                    building_age,
                    structure,
                    nearest_station,
                    hubspot_bukken_id,
                    hubspot_bukken_created_date,
                    hubspot_deal_id,
                    is_public
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            params = (
                achievement.property_image_url,
                format_date_for_db(achievement.purchase_date),
                achievement.title,
                achievement.property_name,
                achievement.building_age,
                achievement.structure,
                achievement.nearest_station,
                achievement.hubspot_bukken_id,
                format_datetime_for_db(achievement.hubspot_bukken_created_date),
                achievement.hubspot_deal_id,
                achievement.is_public
            )
            
            achievement_id = await db_connection.execute_insert(query, params)
            logger.info(f"物件買取実績を作成しました: id={achievement_id}, bukken_id={achievement.hubspot_bukken_id}, deal_id={achievement.hubspot_deal_id}")
            return achievement_id
            
        except Exception as e:
            logger.error(f"物件買取実績の作成に失敗しました: bukken_id={achievement.hubspot_bukken_id}, deal_id={achievement.hubspot_deal_id}, error={str(e)}")
            # 重複エラーの場合は既存レコードを返す（hubspot_bukken_idとhubspot_deal_idの両方が存在する場合のみ）
            if ("Duplicate entry" in str(e) or "UNIQUE constraint" in str(e)) and achievement.hubspot_bukken_id and achievement.hubspot_deal_id:
                logger.warning(f"重複エラーが発生しました。既存レコードを取得します: bukken_id={achievement.hubspot_bukken_id}, deal_id={achievement.hubspot_deal_id}")
                existing = await self.get_by_bukken_and_deal(
                    achievement.hubspot_bukken_id,
                    achievement.hubspot_deal_id
                )
                if existing:
                    return existing["id"]
            raise
    
    async def get_by_id(self, achievement_id: int) -> Optional[Dict[str, Any]]:
        """物件買取実績をIDで取得"""
        try:
            query = """
                SELECT 
                    id,
                    property_image_url,
                    purchase_date,
                    title,
                    property_name,
                    building_age,
                    structure,
                    nearest_station,
                    hubspot_bukken_id,
                    hubspot_bukken_created_date,
                    hubspot_deal_id,
                    is_public,
                    created_at,
                    updated_at
                FROM purchase_achievements
                WHERE id = %s
            """
            
            results = await db_connection.execute_query(query, (achievement_id,))
            if results:
                result = results[0]
                # date型とdatetime型を適切に変換
                result = self._convert_date_types(result)
                return result
            return None
            
        except Exception as e:
            logger.error(f"物件買取実績の取得に失敗しました: {str(e)}")
            raise
    
    async def get_by_bukken_and_deal(self, bukken_id: Optional[str], deal_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """物件IDと取引IDで物件買取実績を取得"""
        try:
            if not bukken_id or not deal_id:
                return None
                
            query = """
                SELECT 
                    id,
                    property_image_url,
                    purchase_date,
                    title,
                    property_name,
                    building_age,
                    structure,
                    nearest_station,
                    hubspot_bukken_id,
                    hubspot_bukken_created_date,
                    hubspot_deal_id,
                    is_public,
                    created_at,
                    updated_at
                FROM purchase_achievements
                WHERE hubspot_bukken_id = %s AND hubspot_deal_id = %s
            """
            
            results = await db_connection.execute_query(query, (bukken_id, deal_id))
            if results:
                result = results[0]
                # date型とdatetime型を適切に変換
                result = self._convert_date_types(result)
                return result
            return None
            
        except Exception as e:
            logger.error(f"物件買取実績の取得に失敗しました: {str(e)}")
            raise
    
    async def get_by_bukken_id(self, bukken_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """物件IDで物件買取実績を取得（hubspot_bukken_idのみで照合）"""
        try:
            if not bukken_id:
                return None
                
            query = """
                SELECT 
                    id,
                    property_image_url,
                    purchase_date,
                    title,
                    property_name,
                    building_age,
                    structure,
                    nearest_station,
                    hubspot_bukken_id,
                    hubspot_bukken_created_date,
                    hubspot_deal_id,
                    is_public,
                    created_at,
                    updated_at
                FROM purchase_achievements
                WHERE hubspot_bukken_id = %s
                LIMIT 1
            """
            
            results = await db_connection.execute_query(query, (bukken_id,))
            if results:
                result = results[0]
                # date型とdatetime型を適切に変換
                result = self._convert_date_types(result)
                return result
            return None
            
        except Exception as e:
            logger.error(f"物件買取実績の取得に失敗しました: {str(e)}")
            raise
    
    async def get_list(
        self,
        is_public: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """物件買取実績一覧を取得"""
        try:
            conditions = []
            params = []
            
            if is_public is not None:
                conditions.append("is_public = %s")
                params.append(is_public)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT 
                    id,
                    property_image_url,
                    purchase_date,
                    title,
                    property_name,
                    building_age,
                    structure,
                    nearest_station,
                    hubspot_bukken_id,
                    hubspot_bukken_created_date,
                    hubspot_deal_id,
                    is_public,
                    created_at,
                    updated_at
                FROM purchase_achievements
                {where_clause}
                ORDER BY purchase_date DESC, created_at DESC
                LIMIT %s OFFSET %s
            """
            
            params.extend([limit, offset])
            results = await db_connection.execute_query(query, tuple(params))
            
            # date型とdatetime型を適切に変換
            converted_results = []
            for result in results:
                converted_result = self._convert_date_types(result)
                converted_results.append(converted_result)
            
            return converted_results
            
        except Exception as e:
            logger.error(f"物件買取実績一覧の取得に失敗しました: {str(e)}")
            raise
    
    async def get_count(
        self,
        is_public: Optional[bool] = None
    ) -> int:
        """物件買取実績の総件数を取得"""
        try:
            conditions = []
            params = []
            
            if is_public is not None:
                conditions.append("is_public = %s")
                params.append(is_public)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT COUNT(*) as total
                FROM purchase_achievements
                {where_clause}
            """
            
            results = await db_connection.execute_query(query, tuple(params) if params else None)
            if results and len(results) > 0:
                return results[0].get("total", 0)
            return 0
            
        except Exception as e:
            logger.error(f"物件買取実績の総件数取得に失敗しました: {str(e)}")
            raise
    
    async def update(self, achievement_id: int, achievement: PurchaseAchievementUpdate) -> bool:
        """物件買取実績を更新"""
        try:
            updates = []
            params = []
            
            if achievement.property_image_url is not None:
                updates.append("property_image_url = %s")
                params.append(achievement.property_image_url)
            
            if achievement.purchase_date is not None:
                updates.append("purchase_date = %s")
                params.append(format_date_for_db(achievement.purchase_date))
            
            if achievement.title is not None:
                updates.append("title = %s")
                params.append(achievement.title)
            
            if achievement.property_name is not None:
                updates.append("property_name = %s")
                params.append(achievement.property_name)
            
            if achievement.building_age is not None:
                updates.append("building_age = %s")
                params.append(achievement.building_age)
            
            if achievement.structure is not None:
                updates.append("structure = %s")
                params.append(achievement.structure)
            
            if achievement.nearest_station is not None:
                updates.append("nearest_station = %s")
                params.append(achievement.nearest_station)
            
            if achievement.hubspot_bukken_created_date is not None:
                updates.append("hubspot_bukken_created_date = %s")
                params.append(format_datetime_for_db(achievement.hubspot_bukken_created_date))
            
            if achievement.hubspot_deal_id is not None:
                updates.append("hubspot_deal_id = %s")
                params.append(achievement.hubspot_deal_id)
            
            if achievement.is_public is not None:
                updates.append("is_public = %s")
                params.append(achievement.is_public)
            
            if not updates:
                return False
            
            params.append(achievement_id)
            query = f"UPDATE purchase_achievements SET {', '.join(updates)} WHERE id = %s"
            
            rowcount = await db_connection.execute_update(query, tuple(params))
            logger.info(f"物件買取実績を更新しました: id={achievement_id}, rowcount={rowcount}")
            return rowcount > 0
            
        except Exception as e:
            logger.error(f"物件買取実績の更新に失敗しました: {str(e)}")
            raise
    
    async def upsert(self, achievement: PurchaseAchievementCreate) -> int:
        """物件買取実績を作成または更新（upsert）"""
        try:
            # 既存のレコードを確認（hubspot_bukken_idとhubspot_deal_idの両方が存在する場合のみ）
            if achievement.hubspot_bukken_id and achievement.hubspot_deal_id:
                existing = await self.get_by_bukken_and_deal(
                    achievement.hubspot_bukken_id,
                    achievement.hubspot_deal_id
                )
                
                if existing:
                    # 更新
                    update_data = PurchaseAchievementUpdate(
                        property_image_url=achievement.property_image_url,
                        purchase_date=achievement.purchase_date,
                        title=achievement.title,
                        property_name=achievement.property_name,
                        building_age=achievement.building_age,
                        structure=achievement.structure,
                        nearest_station=achievement.nearest_station,
                        hubspot_bukken_created_date=achievement.hubspot_bukken_created_date,
                        hubspot_deal_id=achievement.hubspot_deal_id,
                        is_public=achievement.is_public
                    )
                    success = await self.update(existing["id"], update_data)
                    if success:
                        return existing["id"]
            
            # 作成
            return await self.create(achievement)
            
        except Exception as e:
            logger.error(f"物件買取実績のupsertに失敗しました: {str(e)}")
            raise
    
    async def delete(self, achievement_id: int) -> bool:
        """物件買取実績を削除（HubSpotのデータは削除しない）"""
        try:
            query = "DELETE FROM purchase_achievements WHERE id = %s"
            rowcount = await db_connection.execute_update(query, (achievement_id,))
            logger.info(f"物件買取実績を削除しました: id={achievement_id}, rowcount={rowcount}")
            return rowcount > 0
            
        except Exception as e:
            logger.error(f"物件買取実績の削除に失敗しました: id={achievement_id}, error={str(e)}")
            raise

