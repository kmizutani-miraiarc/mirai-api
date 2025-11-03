from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import uuid
import os
import requests
from datetime import datetime, date
from decimal import Decimal
from database.connection import db_connection

logger = logging.getLogger(__name__)

router = APIRouter()

# リクエストモデル
class SateiUploadRequest(BaseModel):
    """査定物件アップロードリクエスト"""
    email: str = Field(..., description="メールアドレス")
    property_name: Optional[str] = Field(None, description="物件名")
    files: List[str] = Field(..., description="アップロードされたファイル名のリスト")


# API認証の依存関数
async def verify_api_key(x_api_key: Optional[str] = Depends(lambda: None)):
    """API認証キーを検証"""
    # 簡易的な認証（必要に応じて実装）
    if not x_api_key:
        # 認証なしでもOK
        pass
    return {"site_name": "mirai-base"}


@router.post("/satei/upload")
async def upload_satei_property(
    email: str = Form(...),
    files: List[UploadFile] = File(...),
    property_name: Optional[str] = Form(None),
    api_key: dict = Depends(verify_api_key)
):
    """
    査定物件をアップロード
    - メールアドレスでHubSpotコンタクトを検索
    - ユニークIDを生成してユーザー情報を保存
    - 査定物件として登録
    - ファイルは別途アップロードファイルテーブルに保存
    """
    try:
        # メールアドレスでHubSpotコンタクトを検索
        from hubspot.contacts import HubSpotContactsClient
        contacts_client = HubSpotContactsClient()
        
        # メールアドレスでコンタクトを検索（プロパティにhubspot_owner_idを含める）
        contacts_data = await contacts_client.get_contacts(limit=100)
        contacts = contacts_data.get("results", [])
        
        contact_info = None
        hubspot_owner_email = None
        
        logger.info(f"コンタクト検索: email={email}, contacts数={len(contacts)}")
        
        # 直接HubSpot APIでコンタクトを検索する（より確実に担当者情報を取得）
        try:
            # Search APIを使って直接検索
            from hubspot.client import HubSpotBaseClient
            client = HubSpotBaseClient()
            
            search_request = {
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email
                    }]
                }],
                "properties": ["email", "firstname", "lastname", "hubspot_owner_id"],
                "limit": 1
            }
            
            search_result = await client._make_request("POST", "/crm/v3/objects/contacts/search", json=search_request)
            search_contacts = search_result.get("results", [])
            
            if search_contacts:
                contact = search_contacts[0]
                properties = contact.get("properties", {})
                
                contact_info = {
                    "contact_id": contact.get("id"),
                    "name": (properties.get("lastname", "") + " " + properties.get("firstname", "")).strip() or None,
                    "owner_id": properties.get("hubspot_owner_id"),
                    "owner_name": None
                }
                logger.info(f"Search APIでコンタクト情報: {contact_info}")
            else:
                logger.warning(f"Search APIでコンタクトが見つかりません: {email}")
                
        except Exception as e:
            logger.error(f"Search API呼び出しエラー: {str(e)}")
            # Fallback: 従来の方法で検索
            for contact in contacts:
                properties = contact.get("properties", {})
                contact_email = properties.get("email")
                logger.info(f"コンタクト確認: {contact_email}")
                
                if contact_email == email:
                    contact_info = {
                        "contact_id": contact.get("id"),
                        "name": (properties.get("lastname", "") + " " + properties.get("firstname", "")).strip() or None,
                        "owner_id": properties.get("hubspot_owner_id"),
                        "owner_name": properties.get("hs_analytics_first_visit_url")
                    }
                    logger.info(f"従来方法でコンタクト情報: {contact_info}")
                    break
        
        # HubSpot担当者のメールアドレスを取得
        if contact_info and contact_info.get("owner_id"):
            from hubspot.owners import HubSpotOwnersClient
            owners_client = HubSpotOwnersClient()
            owners = await owners_client.get_owners()
            
            logger.info(f"HubSpot担当者取得: owner_id={contact_info.get('owner_id')}, owners数={len(owners)}")
            
            for owner in owners:
                if str(owner.get("id")) == str(contact_info.get("owner_id")):
                    hubspot_owner_email = owner.get("email")
                    logger.info(f"HubSpot担当者メールアドレス: {hubspot_owner_email}")
                    break
        
        # usersテーブルから担当者を検索
        owner_user_id = None
        if hubspot_owner_email:
            try:
                async with db_connection.get_connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT id FROM users WHERE email = %s
                        """, (hubspot_owner_email,))
                        
                        result = await cursor.fetchone()
                        if result:
                            owner_user_id = result[0]
                            logger.info(f"担当者ユーザーID: {owner_user_id}")
                        else:
                            logger.warning(f"usersテーブルに該当する担当者が見つかりません: {hubspot_owner_email}")
            except Exception as e:
                logger.error(f"担当者検索エラー: {str(e)}")
        
        logger.info(f"最終的な担当者ID: {owner_user_id}")
        
        # ユーザー情報を保存
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                # メールアドレスで既存ユーザーを検索
                await cursor.execute("""
                    SELECT id, unique_id FROM satei_users WHERE email = %s
                """, (email,))
                
                existing_user = await cursor.fetchone()
                
                if existing_user:
                    # 既存ユーザーが見つかった場合はそのユーザーを使用
                    user_id = existing_user[0]
                    unique_id = existing_user[1]
                    logger.info(f"既存ユーザーを使用: user_id={user_id}, unique_id={unique_id}, email={email}")
                else:
                    # 新規ユーザーの場合はユニークIDを生成して登録
                    unique_id = str(uuid.uuid4())
                    await cursor.execute("""
                        INSERT INTO satei_users (unique_id, email, contact_id, name, owner_id, owner_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        unique_id,
                        email,
                        contact_info.get("contact_id") if contact_info else None,
                        contact_info.get("name") if contact_info else None,
                        contact_info.get("owner_id") if contact_info else None,
                        contact_info.get("owner_name") if contact_info else None
                    ))
                    
                    user_id = cursor.lastrowid
                    logger.info(f"新規ユーザーを作成: user_id={user_id}, unique_id={unique_id}, email={email}")
                
                # 査定物件を作成（担当者を含む）
                await cursor.execute("""
                    INSERT INTO satei_properties (user_id, owner_user_id, property_name, request_date, status)
                    VALUES (%s, %s, %s, CURDATE(), 'parsing')
                """, (user_id, owner_user_id, property_name or "未設定"))
                
                satei_property_id = cursor.lastrowid
                
                # ファイルを保存
                saved_files = []
                upload_dir = "data/satei_uploads"
                os.makedirs(upload_dir, exist_ok=True)
                
                for file in files:
                    # ファイル名を生成
                    new_filename = f"{unique_id}_{file.filename}"
                    file_path = os.path.join(upload_dir, new_filename)
                    
                    # ファイルを保存
                    with open(file_path, "wb") as f:
                        file_content = await file.read()
                        f.write(file_content)
                    
                    # アップロードファイルテーブルに保存
                    await cursor.execute("""
                        INSERT INTO upload_files (entity_type, entity_id, file_name, file_path, file_size, mime_type)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        'satei_property',
                        satei_property_id,
                        file.filename,
                        file_path,
                        len(file_content),
                        file.content_type
                    ))
                    
                    saved_files.append({
                        "original_name": file.filename,
                        "saved_path": file_path
                    })
                
                await conn.commit()
        
        # コンタクト担当者にSlack通知を送信
        if hubspot_owner_email:
            try:
                from config.slack import get_slack_config
                slack_config = get_slack_config(hubspot_owner_email)
                
                # メンション付きメッセージを構築
                if slack_config['mention'] == 'here':
                    message = {'text': '<!here> 査定依頼がありました'}
                else:
                    message = {'text': f"<@{slack_config['mention']}> 査定依頼がありました"}
                
                # Slackに送信
                response = requests.post(
                    slack_config['webhook_url'],
                    json=message,
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"担当者({hubspot_owner_email})にSlack通知を送信しました")
                else:
                    logger.error(f"Slack通知送信失敗: status_code={response.status_code}")
            except Exception as slack_error:
                logger.error(f"Slack通知エラー: {str(slack_error)}")
        
        return {
            "status": "success",
            "message": "査定物件を正常に登録しました",
            "data": {
                "unique_id": unique_id,
                "user_id": user_id,
                "satei_property_id": satei_property_id,
                "email": email,
                "contact_info": contact_info,
                "files": saved_files
            }
        }
        
    except Exception as e:
        logger.error(f"査定物件アップロードエラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件のアップロードに失敗しました: {str(e)}"
        )


@router.get("/satei/users")
async def get_satei_users(
    limit: int = 100,
    offset: int = 0,
    api_key: dict = Depends(verify_api_key)
):
    """査定物件ユーザー一覧を取得"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                # ユーザー一覧と各ユーザーの査定物件数を取得
                await cursor.execute("""
                    SELECT su.*, COUNT(DISTINCT sp.id) as property_count
                    FROM satei_users su
                    LEFT JOIN satei_properties sp ON su.id = sp.user_id
                    GROUP BY su.id
                    ORDER BY su.created_at DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                
                users = await cursor.fetchall()
                
                # カラム名を取得
                columns = [desc[0] for desc in cursor.description]
                users_dict = [dict(zip(columns, user)) for user in users]
        
        return {
            "status": "success",
            "data": {
                "users": users_dict,
                "total": len(users_dict)
            }
        }
    except Exception as e:
        logger.error(f"査定物件ユーザー取得エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件ユーザーの取得に失敗しました: {str(e)}"
        )


@router.delete("/satei/users/{user_id}")
async def delete_satei_user(
    user_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """査定物件ユーザーを削除"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                # ユーザーが存在するか確認
                await cursor.execute("""
                    SELECT id FROM satei_users WHERE id = %s
                """, (user_id,))
                
                user_result = await cursor.fetchone()
                if not user_result:
                    raise HTTPException(status_code=404, detail="指定されたユーザーが見つかりません")
                
                # 削除前に関連ファイルを取得して物理削除
                await cursor.execute("""
                    SELECT uf.file_path 
                    FROM upload_files uf
                    JOIN satei_properties sp ON uf.entity_id = sp.id AND uf.entity_type = 'satei_property'
                    WHERE sp.user_id = %s
                """, (user_id,))
                
                files_to_delete = await cursor.fetchall()
                
                # ユーザーを削除（CASCADE により関連データも自動削除）
                await cursor.execute("""
                    DELETE FROM satei_users WHERE id = %s
                """, (user_id,))
                
                await conn.commit()
                
                # 物理ファイルを削除
                deleted_files = 0
                for file_info in files_to_delete:
                    file_path = file_info[0]
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_files += 1
                            logger.info(f"ファイルを削除しました: {file_path}")
                    except Exception as file_error:
                        logger.error(f"ファイル削除エラー: {file_path}, {str(file_error)}")
                
                logger.info(f"ユーザー {user_id} を削除しました（物理ファイル削除数: {deleted_files}）")
        
        return {
            "status": "success",
            "message": "査定物件ユーザーを正常に削除しました",
            "data": {
                "user_id": user_id,
                "deleted_files_count": deleted_files
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"査定物件ユーザー削除エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件ユーザーの削除に失敗しました: {str(e)}"
        )


@router.get("/satei/properties")
async def get_satei_properties(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    owner_user_id: Optional[int] = None,
    api_key: dict = Depends(verify_api_key)
):
    """査定物件一覧を取得"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                # WHERE句を構築
                where_conditions = []
                params = []
                
                if status:
                    where_conditions.append("sp.status = %s")
                    params.append(status)
                
                if owner_user_id is not None:
                    if owner_user_id == -1:
                        where_conditions.append("sp.owner_user_id IS NULL")
                    else:
                        where_conditions.append("sp.owner_user_id = %s")
                        params.append(owner_user_id)
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # 総件数を取得
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM satei_properties sp
                    JOIN satei_users su ON sp.user_id = su.id
                    {where_clause}
                """
                await cursor.execute(count_query, tuple(params))
                total_result = await cursor.fetchone()
                total = total_result[0] if total_result else 0
                
                query = f"""
                    SELECT sp.*, su.email, su.name as user_name, su.unique_id
                    FROM satei_properties sp
                    JOIN satei_users su ON sp.user_id = su.id
                    {where_clause}
                    ORDER BY sp.created_at DESC
                    LIMIT %s OFFSET %s
                """
                
                params.extend([limit, offset])
                
                await cursor.execute(query, tuple(params))
                properties = await cursor.fetchall()
                
                # カラム名を取得
                columns = [desc[0] for desc in cursor.description]
                properties_dict = [dict(zip(columns, prop)) for prop in properties]
                
                # 各物件のファイルと担当者情報を取得
                for prop in properties_dict:
                    # Decimal型をfloatに変換
                    if prop.get('estimated_price_from') is not None and isinstance(prop['estimated_price_from'], Decimal):
                        prop['estimated_price_from'] = float(prop['estimated_price_from'])
                    if prop.get('estimated_price_to') is not None and isinstance(prop['estimated_price_to'], Decimal):
                        prop['estimated_price_to'] = float(prop['estimated_price_to'])
                    # ファイルを取得
                    await cursor.execute("""
                        SELECT * FROM upload_files
                        WHERE entity_type = 'satei_property' AND entity_id = %s
                        ORDER BY created_at ASC
                    """, (prop['id'],))
                    
                    files = await cursor.fetchall()
                    files_columns = [desc[0] for desc in cursor.description]
                    prop['files'] = [dict(zip(files_columns, f)) for f in files]
                    
                    # 担当者情報を取得
                    if prop.get('owner_user_id'):
                        await cursor.execute("""
                            SELECT id, name, email FROM users WHERE id = %s
                        """, (prop['owner_user_id'],))
                        
                        owner_result = await cursor.fetchone()
                        if owner_result:
                            owner_columns = ['id', 'name', 'email']
                            prop['owner'] = dict(zip(owner_columns, owner_result))
        
        return {
            "status": "success",
            "data": {
                "properties": properties_dict,
                "total": total
            }
        }
    except Exception as e:
        logger.error(f"査定物件取得エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件の取得に失敗しました: {str(e)}"
        )


@router.get("/satei/properties/{property_id}")
async def get_satei_property(
    property_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """査定物件詳細を取得"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT sp.*, su.email, su.name as user_name, su.unique_id, 
                           su.contact_id, su.owner_id, su.owner_name
                    FROM satei_properties sp
                    JOIN satei_users su ON sp.user_id = su.id
                    WHERE sp.id = %s
                """, (property_id,))
                
                result = await cursor.fetchone()
                
                if not result:
                    raise HTTPException(status_code=404, detail="指定された査定物件が見つかりません")
                
                # カラム名を取得
                columns = [desc[0] for desc in cursor.description]
                property_dict = dict(zip(columns, result))
                
                # Decimal型をfloatに変換
                if property_dict.get('estimated_price_from') is not None and isinstance(property_dict['estimated_price_from'], Decimal):
                    property_dict['estimated_price_from'] = float(property_dict['estimated_price_from'])
                if property_dict.get('estimated_price_to') is not None and isinstance(property_dict['estimated_price_to'], Decimal):
                    property_dict['estimated_price_to'] = float(property_dict['estimated_price_to'])
                
                # ファイルを取得
                await cursor.execute("""
                    SELECT * FROM upload_files
                    WHERE entity_type = 'satei_property' AND entity_id = %s
                    ORDER BY created_at ASC
                """, (property_id,))
                
                files = await cursor.fetchall()
                files_columns = [desc[0] for desc in cursor.description]
                property_dict['files'] = [dict(zip(files_columns, f)) for f in files]
                
                # 担当者情報を取得
                if property_dict.get('owner_user_id'):
                    await cursor.execute("""
                        SELECT id, name, email FROM users WHERE id = %s
                    """, (property_dict['owner_user_id'],))
                    
                    owner_result = await cursor.fetchone()
                    if owner_result:
                        owner_columns = ['id', 'name', 'email']
                        property_dict['owner'] = dict(zip(owner_columns, owner_result))
        
        return {
            "status": "success",
            "data": {
                "property": property_dict
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"査定物件取得エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件の取得に失敗しました: {str(e)}"
        )


class SateiPropertyUpdateRequest(BaseModel):
    """査定物件更新リクエスト"""
    property_name: Optional[str] = None
    status: Optional[str] = None
    estimated_price_from: Optional[float] = None
    estimated_price_to: Optional[float] = None
    comment: Optional[str] = None
    evaluation_date: Optional[str] = None


@router.get("/satei/files/{file_id}")
async def get_satei_file(
    file_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """査定物件のファイルを取得"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT file_path, file_name, mime_type FROM upload_files WHERE id = %s
                """, (file_id,))
                
                result = await cursor.fetchone()
                
                if not result:
                    raise HTTPException(status_code=404, detail="ファイルが見つかりません")
                
                file_path, file_name, mime_type = result
                
                # ファイルが存在するか確認
                if not os.path.exists(file_path):
                    raise HTTPException(status_code=404, detail="ファイルが見つかりません")
                
                # ファイルを読み込んで返す
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                return Response(
                    content=file_content,
                    media_type=mime_type or 'application/octet-stream',
                    headers={
                        "Content-Disposition": f"inline; filename={file_name}"
                    }
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ファイル取得エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"ファイルの取得に失敗しました: {str(e)}"
        )


@router.put("/satei/properties/{property_id}")
async def update_satei_property(
    property_id: int,
    request: SateiPropertyUpdateRequest,
    api_key: dict = Depends(verify_api_key)
):
    """査定物件を更新"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                # 更新可能なフィールドを構築
                update_fields = []
                update_values = []
                
                allowed_fields = ['property_name', 'status', 'estimated_price_from', 
                                'estimated_price_to', 'comment', 'evaluation_date']
                
                request_dict = request.dict(exclude_unset=True)
                for field in allowed_fields:
                    if field in request_dict:
                        update_fields.append(f"{field} = %s")
                        update_values.append(request_dict[field])
                
                if not update_fields:
                    raise HTTPException(status_code=400, detail="更新する項目がありません")
                
                update_values.append(property_id)
                
                query = f"""
                    UPDATE satei_properties
                    SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """
                
                await cursor.execute(query, tuple(update_values))
                await conn.commit()
        
        return {
            "status": "success",
            "message": "査定物件を正常に更新しました",
            "data": {"property_id": property_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"査定物件更新エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件の更新に失敗しました: {str(e)}"
        )


@router.delete("/satei/properties/{property_id}")
async def delete_satei_property(
    property_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """査定物件を削除"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                # 物件が存在するか確認
                await cursor.execute("""
                    SELECT id FROM satei_properties WHERE id = %s
                """, (property_id,))
                
                property_result = await cursor.fetchone()
                if not property_result:
                    raise HTTPException(status_code=404, detail="指定された査定物件が見つかりません")
                
                # 削除前に関連ファイルを取得して物理削除
                await cursor.execute("""
                    SELECT file_path FROM upload_files
                    WHERE entity_type = 'satei_property' AND entity_id = %s
                """, (property_id,))
                
                files_to_delete = await cursor.fetchall()
                
                # 物件を削除（CASCADE により関連データも自動削除されることはないが、念のため）
                await cursor.execute("""
                    DELETE FROM satei_properties WHERE id = %s
                """, (property_id,))
                
                # 関連ファイルを物理削除
                await cursor.execute("""
                    DELETE FROM upload_files 
                    WHERE entity_type = 'satei_property' AND entity_id = %s
                """, (property_id,))
                
                await conn.commit()
                
                # 物理ファイルを削除
                deleted_files = 0
                for file_info in files_to_delete:
                    file_path = file_info[0]
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_files += 1
                            logger.info(f"ファイルを削除しました: {file_path}")
                    except Exception as file_error:
                        logger.error(f"ファイル削除エラー: {file_path}, {str(file_error)}")
                
                logger.info(f"査定物件 {property_id} を削除しました（物理ファイル削除数: {deleted_files}）")
        
        return {
            "status": "success",
            "message": "査定物件を正常に削除しました",
            "data": {
                "property_id": property_id,
                "deleted_files_count": deleted_files
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"査定物件削除エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件の削除に失敗しました: {str(e)}"
        )
