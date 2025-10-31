from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import uuid
import os
import requests
from datetime import datetime, date
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
        
        # ユニークIDを生成
        unique_id = str(uuid.uuid4())
        
        # ユーザー情報を保存
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
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
                await cursor.execute("""
                    SELECT * FROM satei_users
                    ORDER BY created_at DESC
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
                    where_conditions.append("sp.owner_user_id = %s")
                    params.append(owner_user_id)
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
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
                "total": len(properties_dict)
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
                
                # ファイルを取得
                await cursor.execute("""
                    SELECT * FROM upload_files
                    WHERE entity_type = 'satei_property' AND entity_id = %s
                    ORDER BY created_at ASC
                """, (property_id,))
                
                files = await cursor.fetchall()
                files_columns = [desc[0] for desc in cursor.description]
                property_dict['files'] = [dict(zip(files_columns, f)) for f in files]
        
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


@router.put("/satei/properties/{property_id}")
async def update_satei_property(
    property_id: int,
    request: dict,
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
                
                for field in allowed_fields:
                    if field in request:
                        update_fields.append(f"{field} = %s")
                        update_values.append(request[field])
                
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
