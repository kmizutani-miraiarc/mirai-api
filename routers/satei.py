from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response, Body, Header
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
import uuid
import os
import re
import requests
import traceback
from datetime import datetime, date
from decimal import Decimal
from urllib.parse import unquote
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from database.connection import db_connection
from database.api_keys import api_key_manager
from database.gmail_credentials import gmail_credentials_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# API認証の依存関数
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """API認証キーを検証（データベースベース）"""
    if not x_api_key:
        raise HTTPException(
            status_code=401, 
            detail="API key is required. Please provide X-API-Key header."
        )
    
    # データベースからAPIキーを検証
    api_key_info = await api_key_manager.validate_api_key(x_api_key)
    if not api_key_info:
        raise HTTPException(
            status_code=401, 
            detail="Invalid API key. Please check your X-API-Key header."
        )
    
    return api_key_info

@router.post("/satei/upload")
async def upload_satei_property(
    email: str = Form(...),
    files: List[UploadFile] = File(...),
    propertyName: Optional[str] = Form(None),
    companyName: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    firstName: Optional[str] = Form(None),
    lastName: Optional[str] = Form(None),
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
                contact_id = contact.get("id")
                
                # Noneを空文字列に変換してから結合
                lastname = properties.get("lastname") or ""
                firstname = properties.get("firstname") or ""
                full_name = (lastname + " " + firstname).strip() or None
                
                contact_info = {
                    "contact_id": contact_id,
                    "name": full_name,
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
                    contact_id = contact.get("id")
                    # Noneを空文字列に変換してから結合
                    lastname = properties.get("lastname") or ""
                    firstname = properties.get("firstname") or ""
                    full_name = (lastname + " " + firstname).strip() or None
                    
                    contact_info = {
                        "contact_id": contact_id,
                        "name": full_name,
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
        
        # HubSpotコンタクトに関連付けられた会社名を取得
        hubspot_company_name = None
        if contact_info and contact_info.get("contact_id"):
            try:
                from hubspot.client import HubSpotBaseClient
                base_client = HubSpotBaseClient()
                
                # 認証情報を確認
                if base_client.api_key and base_client.api_key != "your-hubspot-api-key-here":
                    contact_id = contact_info.get("contact_id")
                    logger.info(f"コンタクトIDから会社名を取得: contact_id={contact_id}")
                    
                    # v4 APIを使用して関連会社を取得
                    associations_response = await base_client._make_request(
                        "GET", 
                        f"/crm/v4/objects/contacts/{contact_id}/associations/companies",
                        params={"limit": 100},
                        timeout=60.0
                    )
                    
                    if associations_response and associations_response.get('results'):
                        # 最初の関連会社のIDを取得
                        first_result = associations_response.get('results', [{}])[0]
                        if isinstance(first_result, dict):
                            company_id = first_result.get('toObjectId')
                            if not company_id:
                                company_id = first_result.get('id')
                        else:
                            company_id = first_result
                        
                        if company_id:
                            # 会社情報を取得
                            company_info = await base_client._make_request(
                                "GET",
                                f"/crm/v3/objects/companies/{company_id}",
                                params={"properties": "name"},
                                timeout=60.0
                            )
                            if company_info and company_info.get('properties'):
                                hubspot_company_name = company_info.get('properties', {}).get('name')
                                if hubspot_company_name:
                                    logger.info(f"HubSpot会社名を取得: {hubspot_company_name}")
                                else:
                                    logger.warning(f"会社情報は取得できたが、会社名が空です: contact_id={contact_id}")
                            else:
                                logger.warning(f"会社情報の取得に失敗: contact_id={contact_id}, company_id={company_id}")
                        else:
                            logger.info(f"関連会社が見つかりませんでした: contact_id={contact_id}")
                    else:
                        logger.info(f"コンタクトに関連付けられた会社がありません: contact_id={contact_id}")
                else:
                    logger.warning("HubSpot API key not configured, skipping company name")
            except Exception as e:
                logger.error(f"HubSpot会社名取得エラー: {str(e)}", exc_info=True)
                # エラーが発生しても処理は継続
        
        # ユーザー情報を保存
        logger.info("データベース接続を開始します")
        conn = None
        try:
            async with db_connection.get_connection() as conn:
                logger.info("データベース接続が確立されました")
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
                        
                        # 既存ユーザーの場合、HubSpot会社名を更新（コンタクトIDがある場合のみ）
                        if hubspot_company_name and contact_info and contact_info.get("contact_id"):
                            await cursor.execute("""
                                UPDATE satei_users 
                                SET hubspot_company_name = %s 
                                WHERE id = %s
                            """, (hubspot_company_name, user_id))
                            logger.info(f"既存ユーザーのHubSpot会社名を更新: user_id={user_id}, company_name={hubspot_company_name}")
                    else:
                        # 新規ユーザーの場合はユニークIDを生成して登録
                        unique_id = str(uuid.uuid4())
                        await cursor.execute("""
                            INSERT INTO satei_users (unique_id, email, contact_id, name, owner_id, owner_name, hubspot_company_name)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            unique_id,
                            email,
                            contact_info.get("contact_id") if contact_info else None,
                            contact_info.get("name") if contact_info else None,
                            contact_info.get("owner_id") if contact_info else None,
                            contact_info.get("owner_name") if contact_info else None,
                            hubspot_company_name
                        ))
                        
                        user_id = cursor.lastrowid
                        logger.info(f"新規ユーザーを作成: user_id={user_id}, unique_id={unique_id}, email={email}, hubspot_company_name={hubspot_company_name}")
                    
                    # 査定物件を作成（担当者とフォーム入力の氏名、会社名を含む）
                    await cursor.execute("""
                        INSERT INTO satei_properties (user_id, owner_user_id, property_name, company_name, first_name, last_name, comment, request_date, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURDATE(), 'parsing')
                    """, (user_id, owner_user_id, propertyName or "未設定", companyName or None, firstName or None, lastName or None, comment))
                    
                    satei_property_id = cursor.lastrowid
                    
                    # ファイルを保存
                    saved_files = []
                    # アップロードディレクトリを環境変数から取得（フォールバック付き）
                    upload_dir = os.getenv('SATEI_UPLOAD_DIR', '/tmp/satei_uploads')
                    
                    # ディレクトリの作成と書き込み権限の確認
                    try:
                        os.makedirs(upload_dir, exist_ok=True)
                        logger.info(f"アップロードディレクトリを作成/確認しました: {upload_dir}")
                        
                        # ディレクトリの書き込み権限を確認
                        test_file = os.path.join(upload_dir, '.write_test')
                        try:
                            with open(test_file, 'w') as f:
                                f.write('test')
                            os.remove(test_file)
                            logger.info(f"アップロードディレクトリの書き込み権限を確認しました: {upload_dir}")
                        except Exception as write_test_error:
                            logger.error(f"アップロードディレクトリに書き込み権限がありません: {upload_dir}, エラー: {str(write_test_error)}")
                            await conn.rollback()
                            raise HTTPException(
                                status_code=500,
                                detail=f"アップロードディレクトリに書き込み権限がありません: {upload_dir}。環境変数SATEI_UPLOAD_DIRを書き込み可能なディレクトリに設定してください。"
                            )
                    except PermissionError as perm_error:
                        logger.error(f"アップロードディレクトリの作成に失敗しました（権限エラー）: {upload_dir}, エラー: {str(perm_error)}")
                        await conn.rollback()
                        raise HTTPException(
                            status_code=500,
                            detail=f"アップロードディレクトリの作成に失敗しました（権限エラー）: {upload_dir}。環境変数SATEI_UPLOAD_DIRを書き込み可能なディレクトリに設定してください。"
                        )
                    except OSError as os_error:
                        logger.error(f"アップロードディレクトリの作成に失敗しました: {upload_dir}, エラー: {str(os_error)}")
                        await conn.rollback()
                        raise HTTPException(
                            status_code=500,
                            detail=f"アップロードディレクトリの作成に失敗しました: {upload_dir}。環境変数SATEI_UPLOAD_DIRを書き込み可能なディレクトリに設定してください。"
                        )
                    
                    # ファイルサイズ制限（各ファイル最大50MB、合計最大200MB）
                    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
                    MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200MB
                    total_size = 0
                    
                    for file in files:
                        # ファイルサイズをチェック（先に読み込んでサイズを確認）
                        file_content = await file.read()
                        file_size = len(file_content)
                        total_size += file_size
                        
                        # 各ファイルのサイズチェック
                        if file_size > MAX_FILE_SIZE:
                            await conn.rollback()
                            raise HTTPException(
                                status_code=413,
                                detail=f"ファイル '{file.filename}' のサイズが大きすぎます（最大50MB）。現在のサイズ: {file_size / (1024 * 1024):.2f}MB"
                            )
                        
                        # 合計サイズのチェック
                        if total_size > MAX_TOTAL_SIZE:
                            await conn.rollback()
                            raise HTTPException(
                                status_code=413,
                                detail=f"アップロードファイルの合計サイズが大きすぎます（最大200MB）。現在の合計サイズ: {total_size / (1024 * 1024):.2f}MB"
                            )
                        
                        # ファイル名を適切にデコード（文字化け対策）
                        original_filename = file.filename
                        
                        # ファイルポインタを先頭に戻す（後で保存するため）
                        await file.seek(0)
                        
                        # Content-Dispositionヘッダーからファイル名を取得（より確実）
                        if not original_filename:
                            # Content-Dispositionヘッダーから直接取得を試みる
                            content_disposition = file.headers.get("content-disposition", "")
                            if content_disposition:
                                # filename*=UTF-8''形式またはfilename="..."形式を検索
                                filename_match = re.search(r'filename\*=UTF-8\'\'([^;]+)', content_disposition)
                                if not filename_match:
                                    filename_match = re.search(r'filename="([^"]+)"', content_disposition)
                                if not filename_match:
                                    filename_match = re.search(r'filename=([^;]+)', content_disposition)
                                if filename_match:
                                    original_filename = filename_match.group(1)
                        
                        if original_filename:
                            # 文字化け修復を試みる
                            decoded_filename = original_filename
                            try:
                                # まず、RFC 2231形式（UTF-8''）でエンコードされている場合のデコード
                                decoded_filename = unquote(original_filename, encoding='utf-8')
                            except Exception:
                                try:
                                    # 通常のURLエンコードの場合
                                    decoded_filename = unquote(original_filename)
                                except Exception:
                                    pass
                            
                            # 文字化けしたファイル名を修復（Latin-1として解釈されたUTF-8を修復）
                            try:
                                # Latin-1/Windows-1252として解釈されたUTF-8バイト列を修復
                                if decoded_filename and any(ord(c) > 127 for c in decoded_filename):
                                    # 文字化けしている可能性がある場合、Latin-1でエンコードしてUTF-8でデコード
                                    try:
                                        repaired = decoded_filename.encode('latin-1').decode('utf-8')
                                        if repaired != decoded_filename:
                                            logger.info(f"ファイル名を修復: {decoded_filename} -> {repaired}")
                                            decoded_filename = repaired
                                    except (UnicodeEncodeError, UnicodeDecodeError):
                                        # 修復に失敗した場合は元のファイル名を使用
                                        pass
                            except Exception as e:
                                logger.warning(f"ファイル名修復エラー: {str(e)}, 元のファイル名を使用: {original_filename}")
                        else:
                            decoded_filename = "unknown_file"
                        
                        # ファイル名を生成（ファイルシステム用に安全なファイル名に変換）
                        # ファイル名から危険な文字を除去
                        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', decoded_filename)
                        new_filename = f"{unique_id}_{safe_filename}"
                        file_path = os.path.join(upload_dir, new_filename)
                        
                        # ファイルを保存（既に読み込んだ内容を使用）
                        try:
                            # ディレクトリが存在することを再確認（念のため）
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            
                            with open(file_path, "wb") as f:
                                f.write(file_content)
                            logger.info(f"ファイルを保存しました: {file_path} ({len(file_content)} bytes)")
                        except PermissionError as perm_error:
                            logger.error(f"ファイル保存権限エラー: {file_path}, エラー: {str(perm_error)}")
                            await conn.rollback()
                            raise HTTPException(
                                status_code=500,
                                detail=f"ファイルの保存に失敗しました（権限エラー）: {str(perm_error)}。ディレクトリ '{upload_dir}' に書き込み権限があるか確認してください。"
                            )
                        except OSError as os_error:
                            logger.error(f"ファイル保存エラー: {file_path}, エラー: {str(os_error)}")
                            await conn.rollback()
                            raise HTTPException(
                                status_code=500,
                                detail=f"ファイルの保存に失敗しました: {str(os_error)}。ディレクトリ '{upload_dir}' が存在し、書き込み可能であることを確認してください。"
                            )
                        except Exception as file_error:
                            logger.error(f"ファイル保存予期しないエラー: {file_path}, エラー: {str(file_error)}")
                            await conn.rollback()
                            raise HTTPException(
                                status_code=500,
                                detail=f"ファイルの保存中に予期しないエラーが発生しました: {str(file_error)}"
                            )
                        
                        # アップロードファイルテーブルに保存（デコードされたファイル名を使用）
                        await cursor.execute("""
                            INSERT INTO upload_files (entity_type, entity_id, file_name, file_path, file_size, mime_type)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            'satei_property',
                            satei_property_id,
                            decoded_filename,
                            file_path,
                            os.path.getsize(file_path),
                            file.content_type
                        ))
                        
                        saved_files.append({
                            "original_name": decoded_filename,
                            "saved_path": file_path
                        })
                    
                    logger.info(f"データベースにコミットします: saved_files数={len(saved_files)}")
                    await conn.commit()
                    logger.info("データベースへのコミットが完了しました")
        except HTTPException:
            # HTTPExceptionはそのまま再スロー（ロールバックは既に処理済み）
            raise
        except Exception as db_error:
            logger.error(f"データベース処理中にエラーが発生しました: {str(db_error)}", exc_info=True)
            # トランザクションをロールバック（接続が存在する場合のみ）
            if conn:
                try:
                    await conn.rollback()
                    logger.info("エラー発生のため、トランザクションをロールバックしました")
                except Exception as rollback_error:
                    logger.error(f"ロールバック中にエラーが発生しました: {str(rollback_error)}")
            raise
        
        # 査定依頼受信時にSlack通知を送信（物件査定依頼チャンネルに統一）
        try:
            # 統一されたWebhookURLを環境変数から取得
            slack_webhook_url = os.getenv('SLACK_WEBHOOK_SATEI', '')
            
            if not slack_webhook_url:
                logger.warning("SLACK_WEBHOOK_SATEI環境変数が設定されていません。Slack通知をスキップします。")
            else:
                # 会社名を決定（フォーム入力値を使用、空文字列の場合は「未入力」）
                company_name_display = "未入力"
                if companyName and companyName.strip():
                    company_name_display = companyName.strip()
                    logger.info(f"フォームから会社名を取得: {company_name_display}")
                else:
                    logger.info(f"フォームから会社名が取得できませんでした: companyName={companyName}")
                
                # 担当者のメンションを取得（コンタクト担当者）
                owner_mention = ""
                if hubspot_owner_email:
                    try:
                        from config.slack import get_slack_config
                        slack_config = get_slack_config(hubspot_owner_email)
                        if slack_config['mention'] == 'here':
                            owner_mention = '<!here>'
                        else:
                            owner_mention = f"<@{slack_config['mention']}>"
                        logger.info(f"担当者のメンションを取得: {owner_mention}")
                    except Exception as mention_error:
                        logger.warning(f"担当者のメンション取得エラー: {str(mention_error)}")
                        owner_mention = ""
                else:
                    logger.info("hubspot_owner_emailが取得できませんでした。担当者のメンションはスキップします。")
                
                # 必要な情報を取得
                hubspot_id = os.getenv('HUBSPOT_ID', '')
                mirai_base_url = os.getenv('MIRAI_BASE_URL', 'http://localhost:3000')
                
                # メンションを構築（3名）
                mentions = []
                
                # 1. 担当者（コンタクト担当者）
                if owner_mention:
                    mentions.append(owner_mention)
                
                # 2. 赤瀬さん（akase@miraiarc.jpのmention）
#                mentions.append('<@U05FNC60W2V>')
                
                # 3. 営業事務（User Groupの場合は<!subteam^ID>形式を使用）
#                mentions.append('<!subteam^S09B4NN6TTJ>')
                
                # 通知内容を構築
                contact_id = contact_info.get("contact_id") if contact_info else None
                contact_name = contact_info.get("name") if contact_info else "不明"
                
                # HubSpotページURL
                hubspot_url = ""
                if hubspot_id and contact_id:
                    hubspot_url = f"https://app.hubspot.com/contacts/{hubspot_id}/contact/{contact_id}"
                else:
                    hubspot_url = "取得できませんでした"
                
                # 査定物件URL
                satei_url = f"{mirai_base_url}/admin/satei/detail/{satei_property_id}"
                
                # メッセージを構築
                message_text = f"{' '.join(mentions)} 査定依頼がありました\n\n"
                message_text += f"Hubspotページ：{hubspot_url}\n"
                message_text += f"会社名：{company_name_display}\n"
                message_text += f"コンタクト名：{contact_name}\n"
                message_text += f"査定物件URL：{satei_url}"
                
                message = {'text': message_text}
                
                logger.info(f"Slackメッセージ送信中: webhook_url={slack_webhook_url[:50]}..., message={message}")
                # Slackに送信（統一されたWebhookURLを使用）
                response = requests.post(
                    slack_webhook_url,
                    json=message,
                    timeout=10
                )
                
                logger.info(f"Slackレスポンス: status_code={response.status_code}, response_text={response.text[:200]}")
                
                if response.status_code == 200:
                    logger.info("物件査定依頼チャンネルにSlack通知を送信しました")
                else:
                    logger.error(f"Slack通知送信失敗: status_code={response.status_code}, response_text={response.text}")
        except Exception as slack_error:
            logger.error(f"Slack通知エラー: {str(slack_error)}", exc_info=True)
        
        # 査定依頼者へ自動返信メールを送信
        email_sent_successfully = False
        is_email_invalid = False
        try:
            # noreply@miraiarc.jpのユーザーIDを取得（送信元アカウントとして使用）
            noreply_user_id = None
            async with db_connection.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT id FROM users WHERE email = %s
                    """, ('noreply@miraiarc.jp',))
                    result = await cursor.fetchone()
                    if result:
                        noreply_user_id = result[0]
                        logger.info(f"noreply@miraiarc.jpのユーザーIDを取得: {noreply_user_id}")
                    else:
                        logger.warning("noreply@miraiarc.jpのユーザーが見つかりません。自動返信メールをスキップします。")
            
            if noreply_user_id:
                # Gmail APIサービスを取得（noreply@miraiarc.jpの認証情報を使用）
                try:
                    service, from_email = await get_gmail_service(noreply_user_id)
                    logger.info(f"Gmail APIサービスを取得: from_email={from_email}")
                    
                    # マイページURLを環境変数から取得（ローカル/本番の判定）
                    satei_mypage_base_url = os.getenv('SATEI_MYPAGE_BASE_URL', '')
                    if not satei_mypage_base_url:
                        # 環境変数が設定されていない場合は、MIRAI_BASE_URLから判定
                        mirai_base_url = os.getenv('MIRAI_BASE_URL', 'http://localhost:3000')
                        if 'localhost' in mirai_base_url or '127.0.0.1' in mirai_base_url:
                            satei_mypage_base_url = 'http://localhost:8081'
                        else:
                            satei_mypage_base_url = 'https://miraiarc.co.jp'
                    
                    # マイページURLを構築
                    mypage_url = f"{satei_mypage_base_url}/satei-mypage/?user={unique_id}"
                    
                    # WordPressのお問い合わせページURL
                    contact_url = f"{satei_mypage_base_url}/contact/"
                    
                    # フォーム入力値を取得（表示用）
                    company_name_display = companyName if companyName and companyName.strip() else "未入力"
                    first_name_display = firstName if firstName and firstName.strip() else "未入力"
                    last_name_display = lastName if lastName and lastName.strip() else "未入力"
                    full_name_display = f"{last_name_display} {first_name_display}".strip() if (lastName or firstName) else "未入力"
                    comment_display = comment if comment and comment.strip() else "未入力"
                    
                    # メール件名
                    subject = "【MiraiArc】買取査定依頼を受け付けました"
                    
                    # テキスト形式のメール本文
                    text_body = f"""買取査定依頼ありがとうございます。
以下内容にて買取査定依頼を承りました。
・会社名：{company_name_display}
・氏名：{full_name_display}
・メールアドレス：{email}
・内容：{comment_display}

これより、頂戴した内容を参考に査定を開始させていただきます。

＜査定について＞
査定につきましては、最短即日にて対応させていただきます。
なお、ご提供いただきました情報によっては、査定にお時間を要する場合や、
査定そのものが難しい場合もございますので、予めご了承いただけますと幸いです。

査定結果につきましてはメール、ならびに専用マイページよりお知らせ致します。

＜専用マイページについて＞
お客様専用のマイページを発行させていただきました。
{mypage_url}
マイページでは、
・査定結果の確認
・査定結果から実際の売却依頼
・追加の査定依頼
などを行っていただくことが可能です。
上記のURLよりいつでもご確認いただけますので、ブックマーク等をお願い致します。
なお、こちらのURLは外部の方には共有しないよう、ご注意くださいませ。


それでは、査定結果まで今しばらくお待ち下さいませ。

※本メールアドレスは送信専用のため、ご返信いただけません。
※ご意見・ご要望は、{contact_url} よりお問い合わせください。"""
                    
                    # HTML形式のメール本文（リンクをHTMLタグで表示）
                    html_body = f"""買取査定依頼ありがとうございます。<br>
以下内容にて買取査定依頼を承りました。<br>
・会社名：{company_name_display}<br>
・氏名：{full_name_display}<br>
・メールアドレス：{email}<br>
・内容：{comment_display}<br>
<br>
これより、頂戴した内容を参考に査定を開始させていただきます。<br>
<br>
＜査定について＞<br>
査定につきましては、最短即日にて対応させていただきます。<br>
なお、ご提供いただきました情報によっては、査定にお時間を要する場合や、<br>
査定そのものが難しい場合もございますので、予めご了承いただけますと幸いです。<br>
<br>
査定結果につきましてはメール、ならびに専用マイページよりお知らせ致します。<br>
<br>
＜専用マイページについて＞<br>
お客様専用のマイページを発行させていただきました。<br>
<a href="{mypage_url}">{mypage_url}</a><br>
マイページでは、<br>
・査定結果の確認<br>
・査定結果から実際の売却依頼<br>
・追加の査定依頼<br>
などを行っていただくことが可能です。<br>
上記のURLよりいつでもご確認いただけますので、ブックマーク等をお願い致します。<br>
なお、こちらのURLは外部の方には共有しないよう、ご注意くださいませ。<br>
<br>
<br>
それでは、査定結果まで今しばらくお待ち下さいませ。<br>
<br>
※本メールアドレスは送信専用のため、ご返信いただけません。<br>
※ご意見・ご要望は、<a href="{contact_url}">こちら</a>よりお問い合わせください。"""
                    
                    # メールメッセージを作成
                    msg = MIMEMultipart('alternative')
                    # 送信者をinfo@miraiarc.jpに設定（受信者に表示される送信者）
                    # 実際の送信元アカウントはnoreply@miraiarc.jpだが、Fromヘッダーでinfo@miraiarc.jpとして表示
                    msg['From'] = 'noreply@miraiarc.jp'
                    # 返信先をinfo@miraiarc.jpに設定（返信はinfo@miraiarc.jpに届くように）
                    msg['Reply-To'] = 'noreply@miraiarc.jp'
                    msg['To'] = email
                    msg['Subject'] = subject
                    
                    # BCCを追加（環境変数から取得）
                    bcc_address = os.getenv('GMAIL_BCC_ADDRESS', '').strip()
                    if bcc_address:
                        msg['Bcc'] = bcc_address
                        logger.info(f"BCCアドレスを追加しました: {bcc_address}")
                    
                    # テキスト形式のメール本文を追加
                    text_part = MIMEText(text_body, 'plain', 'utf-8')
                    msg.attach(text_part)
                    
                    # HTML形式のメール本文を追加
                    html_part = MIMEText(html_body, 'html', 'utf-8')
                    msg.attach(html_part)
                    
                    # Base64エンコード
                    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
                    
                    # Gmail APIでメールを送信
                    try:
                        message = {'raw': raw_message}
                        send_result = service.users().messages().send(
                            userId='me',
                            body=message
                        ).execute()
                        
                        email_sent_successfully = True
                        logger.info(f"査定依頼自動返信メールを送信しました: {email}, 件名: {subject}, message_id: {send_result.get('id')}")
                    except HttpError as e:
                        error_detail = e.error_details[0] if e.error_details else {}
                        error_message = error_detail.get('message', str(e))
                        error_code = e.resp.status if hasattr(e, 'resp') else None
                        
                        # メール未達エラーを判定（一般的なメール未達エラーコード）
                        # Gmail APIのエラーメッセージに含まれる可能性のあるキーワード
                        invalid_email_keywords = [
                            'invalid', 'not found', 'does not exist', 'unavailable',
                            'bounce', 'rejected', 'undeliverable', 'delivery failed',
                            '550', '551', '552', '553', '554', 'mailbox', 'address'
                        ]
                        
                        error_message_lower = error_message.lower()
                        if any(keyword in error_message_lower for keyword in invalid_email_keywords):
                            is_email_invalid = True
                            logger.warning(f"メールアドレスが無効の可能性: {email}, エラー: {error_message}")
                        else:
                            logger.error(f"査定依頼自動返信メール送信エラー（Gmail API）: {error_message}")
                    except Exception as e:
                        error_message = str(e).lower()
                        # メール未達エラーを判定
                        invalid_email_keywords = [
                            'invalid', 'not found', 'does not exist', 'unavailable',
                            'bounce', 'rejected', 'undeliverable', 'delivery failed'
                        ]
                        if any(keyword in error_message for keyword in invalid_email_keywords):
                            is_email_invalid = True
                            logger.warning(f"メールアドレスが無効の可能性: {email}, エラー: {str(e)}")
                        else:
                            logger.error(f"査定依頼自動返信メール送信エラー: {str(e)}", exc_info=True)
                    
                    # メール送信結果に基づいてフラグを更新（user_idを使用）
                    try:
                        async with db_connection.get_connection() as conn:
                            async with conn.cursor() as cursor:
                                if email_sent_successfully:
                                    # 送信成功時はフラグをfalseに設定
                                    await cursor.execute("""
                                        UPDATE satei_users 
                                        SET is_email_invalid = FALSE 
                                        WHERE id = %s
                                    """, (user_id,))
                                    logger.info(f"メール送信成功: user_id={user_id}, email={email} のis_email_invalidフラグをFALSEに設定しました")
                                elif is_email_invalid:
                                    # メール未達エラーの場合はフラグをtrueに設定
                                    await cursor.execute("""
                                        UPDATE satei_users 
                                        SET is_email_invalid = TRUE 
                                        WHERE id = %s
                                    """, (user_id,))
                                    logger.warning(f"メール未達エラー: user_id={user_id}, email={email} のis_email_invalidフラグをTRUEに設定しました")
                                await conn.commit()
                    except Exception as flag_error:
                        logger.error(f"メール無効フラグ更新エラー: {str(flag_error)}", exc_info=True)
                        # フラグ更新エラーはメール送信処理を失敗させない
                except ValueError as e:
                    logger.warning(f"Gmail APIサービス取得エラー: {str(e)}。自動返信メールをスキップします。")
                except Exception as e:
                    logger.error(f"査定依頼自動返信メール処理エラー: {str(e)}", exc_info=True)
            else:
                logger.warning("noreply@miraiarc.jpのユーザーIDが取得できませんでした。自動返信メールをスキップします。")
        except Exception as email_error:
            logger.error(f"査定依頼自動返信メール処理エラー: {str(email_error)}", exc_info=True)
            # メール送信エラーは査定依頼処理を失敗させない
        
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
        
    except HTTPException:
        # HTTPExceptionはそのまま再スロー
        raise
    except Exception as e:
        # 詳細なエラー情報をログに出力（exc_info=Trueでスタックトレースも含める）
        logger.error(f"査定物件アップロードエラー: {str(e)}", exc_info=True)
        
        # エラーの種類と詳細情報を取得
        error_type = type(e).__name__
        error_message = str(e) if str(e) else repr(e)
        
        # エラーオブジェクトの属性を確認
        error_attrs = {}
        if hasattr(e, '__dict__'):
            error_attrs = e.__dict__
        
        logger.error(f"エラー種類: {error_type}")
        logger.error(f"エラーメッセージ: {error_message}")
        logger.error(f"エラー属性: {error_attrs}")
        
        # エラーの引数を確認
        if hasattr(e, 'args') and e.args:
            logger.error(f"エラー引数: {e.args}")
        
        # データベース関連のエラーの場合
        error_msg_lower = error_message.lower()
        if "database" in error_msg_lower or "connection" in error_msg_lower or "mysql" in error_msg_lower or "pymysql" in error_type.lower():
            logger.error("データベース関連のエラーが発生しました")
            detail_message = "データベース接続エラーが発生しました。管理者にお問い合わせください。"
        
        # ファイル関連のエラーの場合
        elif "file" in error_msg_lower or "permission" in error_msg_lower or "oserror" in error_type.lower() or "ioerror" in error_type.lower():
            logger.error("ファイル関連のエラーが発生しました")
            detail_message = f"ファイル処理エラー: {error_message}"
        
        # HubSpot API関連のエラーの場合
        elif "hubspot" in error_msg_lower or "api" in error_msg_lower:
            logger.error("HubSpot API関連のエラーが発生しました")
            detail_message = f"HubSpot APIエラー: {error_message}"
        
        # その他のエラー
        else:
            detail_message = error_message if error_message else f"{error_type}エラーが発生しました"
        
        # ユーザー向けのエラーメッセージを構築
        user_message = f"査定物件のアップロードに失敗しました: {detail_message}"
        
        logger.error(f"ユーザー向けエラーメッセージ: {user_message}")
        
        raise HTTPException(
            status_code=500,
            detail=user_message
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


@router.get("/satei/users/{unique_id}/properties")
async def get_user_properties_by_unique_id(
    unique_id: str,
    limit: int = 100,
    offset: int = 0,
    api_key: dict = Depends(verify_api_key)
):
    """指定ユーザーの査定物件一覧を取得（ページネーション対応）"""
    try:
        async with db_connection.get_connection() as conn:
            async with conn.cursor() as cursor:
                # ユーザーIDを取得
                await cursor.execute("""
                    SELECT id, name, email FROM satei_users WHERE unique_id = %s
                """, (unique_id,))
                
                user_result = await cursor.fetchone()
                if not user_result:
                    raise HTTPException(status_code=404, detail="指定されたユーザーが見つかりません")
                
                user_id = user_result[0]
                user_name = user_result[1] if user_result[1] else ""
                user_email = user_result[2] if user_result[2] else ""
                
                # 総件数を取得
                await cursor.execute("""
                    SELECT COUNT(*) as total
                    FROM satei_properties sp
                    WHERE sp.user_id = %s
                """, (user_id,))
                
                total_result = await cursor.fetchone()
                total = total_result[0] if total_result else 0
                
                # 査定物件を取得（フォーム入力の氏名はsatei_propertiesから取得）
                await cursor.execute("""
                    SELECT sp.*, su.email, su.name as user_name, sp.first_name, sp.last_name, su.unique_id, su.is_email_invalid
                    FROM satei_properties sp
                    JOIN satei_users su ON sp.user_id = su.id
                    WHERE sp.user_id = %s
                    ORDER BY sp.created_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, limit, offset))
                
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
                    # Boolean型をboolに変換
                    if prop.get('for_sale') is not None:
                        prop['for_sale'] = bool(prop['for_sale'])
                    # evaluation_resultは文字列（ENUM）なのでそのまま使用
                    
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
                "total": total,
                "limit": limit,
                "offset": offset,
                "user": {
                    "id": user_id,
                    "name": user_name,
                    "email": user_email,
                    "unique_id": unique_id
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"査定物件ユーザー別取得エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"査定物件の取得に失敗しました: {str(e)}"
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
    for_sale: Optional[bool] = None,
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
                
                if for_sale is not None:
                    where_conditions.append("sp.for_sale = %s")
                    params.append(1 if for_sale else 0)
                
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
                    SELECT sp.*, su.email, su.name as user_name, sp.first_name, sp.last_name, su.unique_id, su.is_email_invalid, su.hubspot_company_name
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
                    # Boolean型をboolに変換
                    if prop.get('for_sale') is not None:
                        prop['for_sale'] = bool(prop['for_sale'])
                    # evaluation_resultは文字列（ENUM）なのでそのまま使用
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
                    SELECT sp.*, su.email, su.name as user_name, sp.first_name, sp.last_name, su.unique_id, 
                           su.contact_id, su.owner_id, su.owner_name, su.is_email_invalid, su.hubspot_company_name
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
                
                # Boolean型をboolに変換
                if property_dict.get('for_sale') is not None:
                    property_dict['for_sale'] = bool(property_dict['for_sale'])
                # evaluation_resultは文字列（ENUM）なのでそのまま使用
                
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
    company_name: Optional[str] = None
    status: Optional[str] = None
    estimated_price_from: Optional[float] = None
    estimated_price_to: Optional[float] = None
    comment: Optional[str] = None
    owner_comment: Optional[str] = None
    evaluation_date: Optional[str] = None
    for_sale: Optional[bool] = None
    evaluation_result: Optional[str] = None


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
                
                # ファイル名をRFC 2231形式でエンコード（日本語対応）
                from urllib.parse import quote
                encoded_filename = quote(file_name, safe='')
                content_disposition = f"inline; filename*=UTF-8''{encoded_filename}"
                
                return Response(
                    content=file_content,
                    media_type=mime_type or 'application/octet-stream',
                    headers={
                        "Content-Disposition": content_disposition
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
                # 更新前のfor_saleの値を取得（販売希望通知用）
                old_for_sale = False
                try:
                    await cursor.execute("""
                        SELECT for_sale FROM satei_properties WHERE id = %s
                    """, (property_id,))
                    old_for_sale_result = await cursor.fetchone()
                    if old_for_sale_result and old_for_sale_result[0] is not None:
                        old_for_sale_value = old_for_sale_result[0]
                        # Boolean型やTINYINT(1)の場合、0/1やTrue/Falseとして返される可能性がある
                        old_for_sale = bool(old_for_sale_value)
                    logger.info(f"更新前のfor_sale値: {old_for_sale} (raw: {old_for_sale_result[0] if old_for_sale_result else None})")
                except Exception as old_value_error:
                    logger.warning(f"更新前のfor_sale値取得エラー: {str(old_value_error)}", exc_info=True)
                    old_for_sale = False
                
                # 更新可能なフィールドを構築
                update_fields = []
                update_values = []
                
                allowed_fields = ['property_name', 'company_name', 'status', 'estimated_price_from', 
                                'estimated_price_to', 'comment', 'owner_comment', 'evaluation_date',
                                'for_sale', 'evaluation_result']
                
                request_dict = request.dict(exclude_unset=True, exclude_none=False)
                for_sale_updated = False
                new_for_sale = None
                
                for field in allowed_fields:
                    if field in request_dict:
                        update_fields.append(f"{field} = %s")
                        update_values.append(request_dict[field])
                        if field == 'for_sale':
                            for_sale_updated = True
                            new_for_sale = bool(request_dict[field]) if request_dict[field] is not None else False
                            logger.info(f"for_sale更新: {old_for_sale} -> {new_for_sale}")
                
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
                
                # 販売希望がFalseからTrueに変更された場合、Slack通知を送信
                logger.info(f"販売希望通知チェック: for_sale_updated={for_sale_updated}, new_for_sale={new_for_sale}, old_for_sale={old_for_sale}")
                if for_sale_updated and new_for_sale is True and old_for_sale is False:
                    logger.info(f"販売希望通知を送信します: property_id={property_id}")
                    try:
                        # 査定物件の情報を取得
                        await cursor.execute("""
                            SELECT sp.*, su.email, su.name as user_name, su.contact_id, su.owner_id, su.owner_name,
                                   sp.company_name, sp.first_name, sp.last_name, sp.owner_user_id
                            FROM satei_properties sp
                            JOIN satei_users su ON sp.user_id = su.id
                            WHERE sp.id = %s
                        """, (property_id,))
                        
                        property_result = await cursor.fetchone()
                        if not property_result:
                            logger.warning(f"査定物件情報が見つかりません: property_id={property_id}")
                        else:
                            columns = [desc[0] for desc in cursor.description]
                            property_dict = dict(zip(columns, property_result))
                            logger.info(f"査定物件情報を取得しました: property_id={property_id}, company_name={property_dict.get('company_name')}, contact_id={property_dict.get('contact_id')}")
                            
                            # 統一されたWebhookURLを環境変数から取得
                            slack_webhook_url = os.getenv('SLACK_WEBHOOK_SATEI', '')
                            
                            if not slack_webhook_url:
                                logger.warning("SLACK_WEBHOOK_SATEI環境変数が設定されていません。販売希望のSlack通知をスキップします。")
                            else:
                                # 会社名を取得
                                company_name_display = "未入力"
                                company_name = property_dict.get('company_name')
                                if company_name and str(company_name).strip():
                                    company_name_display = str(company_name).strip()
                                
                                # 担当者のメンションを取得（コンタクト担当者）
                                owner_mention = ""
                                hubspot_owner_email = None
                                
                                # owner_user_idから担当者のメールアドレスを取得（usersテーブルのid）
                                owner_user_id = property_dict.get('owner_user_id')
                                if owner_user_id:
                                    try:
                                        await cursor.execute("""
                                            SELECT email FROM users WHERE id = %s
                                        """, (owner_user_id,))
                                        owner_result = await cursor.fetchone()
                                        if owner_result:
                                            hubspot_owner_email = owner_result[0]
                                            logger.info(f"担当者のメールアドレスを取得: {hubspot_owner_email}")
                                    except Exception as owner_email_error:
                                        logger.warning(f"担当者のメールアドレス取得エラー: {str(owner_email_error)}")
                                
                                if hubspot_owner_email:
                                    try:
                                        from config.slack import get_slack_config
                                        slack_config = get_slack_config(hubspot_owner_email)
                                        if slack_config['mention'] == 'here':
                                            owner_mention = '<!here>'
                                        else:
                                            owner_mention = f"<@{slack_config['mention']}>"
                                        logger.info(f"担当者のメンションを取得: {owner_mention}")
                                    except Exception as mention_error:
                                        logger.warning(f"担当者のメンション取得エラー: {str(mention_error)}")
                                        owner_mention = ""
                                
                                # 必要な情報を取得
                                hubspot_id = os.getenv('HUBSPOT_ID', '')
                                mirai_base_url = os.getenv('MIRAI_BASE_URL', 'http://localhost:3000')
                                
                                # メンションを構築（3名）
                                mentions = []
                                
                                # 1. 担当者（コンタクト担当者）
                                if owner_mention:
                                    mentions.append(owner_mention)
                                
                                # 2. 赤瀬さん（akase@miraiarc.jpのmention）
#                                mentions.append('<@U05FNC60W2V>')
                                
                                # 3. 営業事務（User Groupの場合は<!subteam^ID>形式を使用）
#                                mentions.append('<!subteam^S09B4NN6TTJ>')
                                
                                # 通知内容を構築
                                contact_id = property_dict.get('contact_id')
                                contact_name = property_dict.get('user_name') or "不明"
                                
                                # HubSpotページURL
                                hubspot_url = ""
                                if hubspot_id and contact_id:
                                    hubspot_url = f"https://app.hubspot.com/contacts/{hubspot_id}/contact/{contact_id}"
                                else:
                                    hubspot_url = "取得できませんでした"
                                
                                # 査定物件URL
                                satei_url = f"{mirai_base_url}/admin/satei/detail/{property_id}"
                                
                                # メッセージを構築
                                message_text = f"{' '.join(mentions)} 販売希望がありました\n\n"
                                message_text += f"Hubspotページ：{hubspot_url}\n"
                                message_text += f"会社名：{company_name_display}\n"
                                message_text += f"コンタクト名：{contact_name}\n"
                                message_text += f"査定物件URL：{satei_url}"
                                
                                message = {'text': message_text}
                                
                                # Slackに通知を送信（査定依頼時と同じ方法で実行）
                                try:
                                    logger.info(f"Slack通知を送信します: webhook_url={slack_webhook_url[:50]}..., message={message_text[:100]}...")
                                    # Slackに送信（統一されたWebhookURLを使用）
                                    slack_response = requests.post(
                                        slack_webhook_url,
                                        json=message,
                                        timeout=10
                                    )
                                    
                                    logger.info(f"Slackレスポンス: status_code={slack_response.status_code}, response_text={slack_response.text[:200]}")
                                    
                                    if slack_response.status_code == 200:
                                        logger.info(f"販売希望のSlack通知を送信しました: property_id={property_id}")
                                    else:
                                        logger.warning(f"販売希望のSlack通知送信エラー: status_code={slack_response.status_code}, response={slack_response.text}")
                                except Exception as request_error:
                                    logger.error(f"販売希望のSlack通知送信リクエストエラー: {str(request_error)}", exc_info=True)
                    except Exception as slack_error:
                        logger.error(f"販売希望のSlack通知処理エラー: {str(slack_error)}", exc_info=True)
                        # Slack通知のエラーは更新処理を失敗させない
        
        return {
            "status": "success",
            "message": "査定物件を正常に更新しました",
            "data": {"property_id": property_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"査定物件更新エラー: {str(e)}", exc_info=True)
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


async def get_gmail_service(user_id: int):
    """
    Gmail APIサービスを取得（ユーザーIDから認証情報を取得）
    
    Args:
        user_id: ユーザーID
    
    Returns:
        Gmail API service object, user_email
    """
    # データベースからユーザーのGmail認証情報を取得
    credentials = await gmail_credentials_manager.get_credentials_by_user_id(user_id)
    
    if not credentials:
        raise ValueError(
            f"ユーザーID {user_id} のGmail認証情報が見つかりません。"
            "Gmail認証情報を登録してください。"
        )
    
    # OAuth2認証情報を作成
    creds = Credentials(
        token=None,
        refresh_token=credentials['gmail_refresh_token'],
        token_uri='https://oauth2.googleapis.com/token',
        client_id=credentials['gmail_client_id'],
        client_secret=credentials['gmail_client_secret']
    )
    
    # トークンをリフレッシュ
    creds.refresh(Request())
    
    # Gmail APIサービスを構築
    service = build('gmail', 'v1', credentials=creds)
    return service, credentials['email']


@router.post("/satei/send-email")
async def send_satei_email(
    request: dict = Body(...),
    api_key: dict = Depends(verify_api_key)
):
    """
    査定物件完了通知メールを送信（Gmail API使用）
    
    Args:
        request: メール送信リクエスト（email, subject, body, user_id）
            - email: 送信先メールアドレス
            - subject: メールタイトル
            - body: メール本文
            - user_id: ログインユーザーID（送信元メールアドレスを決定）
        api_key: APIキー認証
    
    Returns:
        送信結果
    """
    try:
        email = request.get('email')
        subject = request.get('subject')
        body = request.get('body')
        user_id = request.get('user_id')
        
        if not email:
            raise HTTPException(status_code=400, detail="メールアドレスは必須です")
        if not subject:
            raise HTTPException(status_code=400, detail="メールタイトルは必須です")
        if not body:
            raise HTTPException(status_code=400, detail="メール本文は必須です")
        if not user_id:
            raise HTTPException(status_code=400, detail="ユーザーIDは必須です")
        
        # Gmail APIサービスを取得（ログインユーザーの認証情報を使用）
        try:
            service, from_email = await get_gmail_service(user_id)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        
        # BCCを追加（環境変数から取得）
        bcc_address = os.getenv('GMAIL_BCC_ADDRESS', '').strip()
        logger.info(f"BCC環境変数チェック: GMAIL_BCC_ADDRESS='{bcc_address}' (length: {len(bcc_address)})")
        
        # メールメッセージを作成
        msg = MIMEMultipart('alternative')
        msg['From'] = from_email
        msg['To'] = email
        msg['Subject'] = subject
        
        # BCCが設定されている場合は追加
        if bcc_address:
            # Gmail APIでは、BCCはToやCcと同様にヘッダーに追加する必要がある
            # BCCヘッダーは実際の送信先には表示されないが、Gmail APIが処理する
            msg['Bcc'] = bcc_address
            logger.info(f"BCCアドレスを追加しました: {bcc_address}")
        
        # 本文を追加（HTML形式）
        html_body = body.replace('\n', '<br>')
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # テキスト形式も追加
        text_part = MIMEText(body, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # Base64エンコード
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        
        # Gmail APIでメールを送信
        try:
            message = {'raw': raw_message}
            send_result = service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            logger.info(f"Gmail APIでメール送信成功: {email}, 件名: {subject}, message_id: {send_result.get('id')}")
            
            return {
                "status": "success",
                "message": "メールを送信しました"
            }
        except HttpError as e:
            error_detail = e.error_details[0] if e.error_details else {}
            error_message = error_detail.get('message', str(e))
            logger.error(f"Gmail APIエラー: {error_message}")
            raise HTTPException(
                status_code=500,
                detail=f"メール送信に失敗しました: {error_message}"
            )
        except Exception as e:
            logger.error(f"メール送信エラー: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"メール送信中にエラーが発生しました: {str(e)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"メール送信処理エラー: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"予期しないエラーが発生しました: {str(e)}"
        )


@router.post("/gmail/credentials")
async def save_gmail_credentials(
    request: dict = Body(...),
    api_key: dict = Depends(verify_api_key)
):
    """
    Gmail認証情報を保存
    
    Args:
        request: Gmail認証情報リクエスト
            - user_id: ユーザーID
            - email: メールアドレス
            - gmail_client_id: Gmail Client ID
            - gmail_client_secret: Gmail Client Secret
            - gmail_refresh_token: Gmail Refresh Token
        api_key: APIキー認証
    
    Returns:
        保存結果
    """
    try:
        user_id = request.get('user_id')
        email = request.get('email')
        gmail_client_id = request.get('gmail_client_id')
        gmail_client_secret = request.get('gmail_client_secret')
        gmail_refresh_token = request.get('gmail_refresh_token')
        
        if not user_id:
            raise HTTPException(status_code=400, detail="ユーザーIDは必須です")
        if not email:
            raise HTTPException(status_code=400, detail="メールアドレスは必須です")
        if not gmail_client_id:
            raise HTTPException(status_code=400, detail="Gmail Client IDは必須です")
        if not gmail_client_secret:
            raise HTTPException(status_code=400, detail="Gmail Client Secretは必須です")
        if not gmail_refresh_token:
            raise HTTPException(status_code=400, detail="Gmail Refresh Tokenは必須です")
        
        # Gmail認証情報を保存
        success = await gmail_credentials_manager.save_credentials(
            user_id=user_id,
            email=email,
            gmail_client_id=gmail_client_id,
            gmail_client_secret=gmail_client_secret,
            gmail_refresh_token=gmail_refresh_token
        )
        
        if success:
            return {
                "status": "success",
                "message": "Gmail認証情報を保存しました"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Gmail認証情報の保存に失敗しました"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail認証情報保存エラー: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"予期しないエラーが発生しました: {str(e)}"
        )


@router.get("/gmail/credentials/{user_id}")
async def get_gmail_credentials(
    user_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """
    Gmail認証情報を取得
    
    Args:
        user_id: ユーザーID
        api_key: APIキー認証
    
    Returns:
        Gmail認証情報（パスワード情報は含まない）
    """
    try:
        credentials = await gmail_credentials_manager.get_credentials_by_user_id(user_id)
        
        if not credentials:
            raise HTTPException(
                status_code=404,
                detail=f"ユーザーID {user_id} のGmail認証情報が見つかりません"
            )
        
        # セキュリティのため、機密情報は返さない
        # データベースからcreated_atも取得
        select_query_with_date = """
        SELECT user_id, email, created_at
        FROM user_gmail_credentials
        WHERE user_id = %s
        """
        result = await db_connection.execute_query(select_query_with_date, (user_id,))
        
        return {
            "status": "success",
            "data": {
                "user_id": credentials["user_id"],
                "email": credentials["email"],
                "created_at": result[0]["created_at"] if result and len(result) > 0 else None,
                "has_credentials": True
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail認証情報取得エラー: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"予期しないエラーが発生しました: {str(e)}"
        )
