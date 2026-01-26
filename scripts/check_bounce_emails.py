#!/usr/bin/env python3
"""
バウンスメール検知スクリプト
Gmailの受信トレイをチェックしてバウンスメールを検知し、
satei_usersテーブルのis_email_invalidフラグを更新する

実行頻度: 10分ごと（推奨）
"""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from email import message_from_string
from email.header import decode_header

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import db_connection
from database.gmail_credentials import gmail_credentials_manager
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import aiomysql

# ログ設定
if os.path.exists("/var/www/mirai-api/logs"):
    log_dir = "/var/www/mirai-api/logs"
else:
    log_dir = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,  # デバッグ情報も出力するためにDEBUGレベルに変更
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "bounce_email_check.log"))
    ]
)

logger = logging.getLogger(__name__)

# バウンスメールの検知パターン
BOUNCE_SUBJECT_PATTERNS = [
    r'Delivery Status Notification',
    r'Undelivered Mail Returned to Sender',
    r'Mail Delivery Failed',
    r'Delivery Failure',
    r'Message not delivered',
    r'Returned mail',
    r'Mail delivery failed',
    r'Delivery has failed',
    r'Mail System Error',
    r'Delivery Notification',
    r'Failure Notice',
    r'Mail Delivery Subsystem',
    r'Mailer-Daemon',
    r'Postmaster',
    r'Mail Administrator',
    r'自動送信',
    r'配信エラー',
    r'配信失敗',
    r'メール配信エラー',
    r'メール配信失敗',
    r'未達',
    r'返送',
]

# バウンスメール本文からメールアドレスを抽出するパターン
EMAIL_PATTERN = r'[\w\.-]+@[\w\.-]+\.\w+'

# チェック対象の時間範囲（過去72時間）
# バウンスメールは送信後すぐに返ってくるとは限らないため、72時間に設定
CHECK_TIME_RANGE_HOURS = 72


def decode_mime_header(header_value: str) -> str:
    """MIMEエンコードされたヘッダーをデコード"""
    if not header_value:
        return ""
    
    decoded_parts = decode_header(header_value)
    decoded_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            if encoding:
                decoded_str += part.decode(encoding)
            else:
                decoded_str += part.decode('utf-8', errors='ignore')
        else:
            decoded_str += part
    return decoded_str


def extract_email_from_bounce_body(body: str) -> Optional[str]:
    """バウンスメール本文から元の送信先メールアドレスを抽出"""
    if not body:
        return None
    
    # 本文を小文字に変換
    body_lower = body.lower()
    
    # 一般的なバウンスメールのパターンからメールアドレスを抽出
    # パターン1: "To: email@example.com" または "To: <email@example.com>"
    to_patterns = [
        r'to:\s*<?([\w\.-]+@[\w\.-]+\.\w+)>?',
        r'^to\s*:\s*<?([\w\.-]+@[\w\.-]+\.\w+)>?',
    ]
    for pattern in to_patterns:
        match = re.search(pattern, body_lower, re.IGNORECASE | re.MULTILINE)
        if match:
            email = match.group(1)
            if 'miraiarc' not in email.lower() and 'noreply' not in email.lower():
                return email
    
    # パターン2: "Original-Recipient: email@example.com" または "Original-Recipient: rfc822;email@example.com"
    original_recipient_patterns = [
        r'original-recipient:\s*rfc822;\s*([\w\.-]+@[\w\.-]+\.\w+)',
        r'original-recipient:\s*<?([\w\.-]+@[\w\.-]+\.\w+)>?',
    ]
    for pattern in original_recipient_patterns:
        match = re.search(pattern, body_lower, re.IGNORECASE)
        if match:
            email = match.group(1)
            if 'miraiarc' not in email.lower() and 'noreply' not in email.lower():
                return email
    
    # パターン3: "Final-Recipient: email@example.com" または "Final-Recipient: rfc822;email@example.com"
    final_recipient_patterns = [
        r'final-recipient:\s*rfc822;\s*([\w\.-]+@[\w\.-]+\.\w+)',
        r'final-recipient:\s*<?([\w\.-]+@[\w\.-]+\.\w+)>?',
    ]
    for pattern in final_recipient_patterns:
        match = re.search(pattern, body_lower, re.IGNORECASE)
        if match:
            email = match.group(1)
            if 'miraiarc' not in email.lower() and 'noreply' not in email.lower():
                return email
    
    # パターン4: "The following address(es) failed: email@example.com"
    failed_patterns = [
        r'failed[:\s]+([\w\.-]+@[\w\.-]+\.\w+)',
        r'address\(es\)\s+failed[:\s]+([\w\.-]+@[\w\.-]+\.\w+)',
        r'failed\s+to\s+deliver\s+to[:\s]+([\w\.-]+@[\w\.-]+\.\w+)',
    ]
    for pattern in failed_patterns:
        match = re.search(pattern, body_lower, re.IGNORECASE)
        if match:
            email = match.group(1)
            if 'miraiarc' not in email.lower() and 'noreply' not in email.lower():
                return email
    
    # パターン5: "配信できませんでした" の後にメールアドレス
    japanese_failed_patterns = [
        r'配信できませんでした[。\s]*([\w\.-]+@[\w\.-]+\.\w+)',
        r'([\w\.-]+@[\w\.-]+\.\w+)\s+にメールを配信できませんでした',
        r'([\w\.-]+@[\w\.-]+\.\w+)\s+への配信に失敗',
    ]
    for pattern in japanese_failed_patterns:
        match = re.search(pattern, body_lower, re.IGNORECASE)
        if match:
            email = match.group(1)
            if 'miraiarc' not in email.lower() and 'noreply' not in email.lower():
                return email
    
    # パターン6: 本文内の最初のメールアドレス（最後の手段）
    # ただし、送信元アドレス（miraiarc、noreply、mailer-daemon、postmasterなど）を除外
    emails = re.findall(EMAIL_PATTERN, body)
    if emails:
        exclude_patterns = ['miraiarc', 'noreply', 'mailer-daemon', 'postmaster', 'mailer', 'daemon', 'googlemail.com', 'gmail.com']
        for email in emails:
            email_lower = email.lower()
            # 送信元アドレスを除外
            if not any(exclude in email_lower for exclude in exclude_patterns):
                return email
    
    return None


def is_bounce_email(subject: str, body: str) -> bool:
    """メールがバウンスメールかどうかを判定"""
    if not subject:
        return False
    
    subject_lower = subject.lower()
    
    # 件名パターンマッチング
    for pattern in BOUNCE_SUBJECT_PATTERNS:
        if re.search(pattern, subject_lower, re.IGNORECASE):
            return True
    
    # 本文にバウンスを示すキーワードがあるか確認
    if body:
        body_lower = body.lower()
        bounce_keywords = [
            'delivery failure',
            'undelivered',
            'returned mail',
            'mail delivery failed',
            'message not delivered',
            'recipient address rejected',
            'user unknown',
            'no such user',
            'mailbox full',
            'quota exceeded',
            'address not found',
            'host unknown',
            'domain not found',
            '550',
            '551',
            '552',
            '553',
            '554',
            '配信エラー',
            '配信失敗',
            '未達',
        ]
        
        for keyword in bounce_keywords:
            if keyword in body_lower:
                return True
    
    return False


async def get_gmail_service(user_id: int):
    """Gmail APIサービスを取得"""
    try:
        credentials = await gmail_credentials_manager.get_credentials_by_user_id(user_id)
        if not credentials:
            raise ValueError(f"Gmail認証情報が見つかりません: user_id={user_id}")
        
        # 認証情報を構築
        # バウンスメール監視には gmail.readonly スコープが必要
        creds = Credentials(
            token=None,
            refresh_token=credentials['gmail_refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=credentials['gmail_client_id'],
            client_secret=credentials['gmail_client_secret'],
            scopes=['https://www.googleapis.com/auth/gmail.readonly']
        )
        
        # トークンをリフレッシュ
        creds.refresh(Request())
        
        # Gmail APIサービスを構築
        service = build('gmail', 'v1', credentials=creds)
        return service, credentials['email']
        
    except Exception as e:
        error_message = str(e)
        if 'invalid_scope' in error_message or 'Bad Request' in error_message:
            logger.error(
                f"Gmail APIスコープエラー: user_id={user_id}, email={credentials.get('email', 'unknown')}\n"
                f"既存のGmail認証情報に 'gmail.readonly' スコープが含まれていません。\n"
                f"バウンスメール監視機能を使用するには、マイページでGmail認証を再設定してください。"
            )
        else:
            logger.error(f"Gmail APIサービス取得エラー: user_id={user_id}, error={error_message}", exc_info=True)
        raise


async def check_bounce_emails_for_user(user_id: int) -> int:
    """指定ユーザーのGmail受信トレイをチェックしてバウンスメールを検知"""
    try:
        service, email = await get_gmail_service(user_id)
        logger.info(f"バウンスメールチェック開始: user_id={user_id}, email={email}")
        
        # チェック対象の時間範囲を計算
        since_date = datetime.now() - timedelta(hours=CHECK_TIME_RANGE_HOURS)
        since_timestamp = int(since_date.timestamp())
        
        # 受信トレイのメールを検索（過去24時間）
        query = f'in:inbox after:{since_timestamp}'
        
        try:
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=100
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"チェック対象メール数: {len(messages)} (過去{CHECK_TIME_RANGE_HOURS}時間)")
            logger.info(f"チェック対象時間範囲: {since_date.strftime('%Y-%m-%d %H:%M:%S')} ～ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            bounce_count = 0
            processed_message_ids = set()  # 処理済みメッセージIDを記録（重複チェック防止）
            
            for msg in messages:
                try:
                    message_id = msg['id']
                    
                    # 既に処理済みのメッセージはスキップ
                    if message_id in processed_message_ids:
                        logger.debug(f"メッセージID {message_id} は既に処理済みのためスキップ")
                        continue
                    
                    # メールの詳細を取得
                    message = service.users().messages().get(
                        userId='me',
                        id=message_id,
                        format='full'
                    ).execute()
                    
                    # メールの受信日時を取得
                    internal_date = message.get('internalDate')
                    received_date = None
                    if internal_date:
                        received_date = datetime.fromtimestamp(int(internal_date) / 1000)
                        logger.debug(f"メッセージID {message_id} の受信日時: {received_date.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # ヘッダーを取得
                    headers = message['payload'].get('headers', [])
                    subject = ""
                    from_email = ""
                    date_header = ""
                    
                    for header in headers:
                        if header['name'].lower() == 'subject':
                            subject = decode_mime_header(header['value'])
                        elif header['name'].lower() == 'from':
                            from_email = decode_mime_header(header['value'])
                        elif header['name'].lower() == 'date':
                            date_header = decode_mime_header(header['value'])
                    
                    logger.debug(f"メッセージID {message_id}: subject={subject[:50] if subject else 'N/A'}, from={from_email[:50] if from_email else 'N/A'}, date={date_header}")
                    
                    # 本文を取得（再帰的にマルチパートメッセージを処理）
                    def get_body_from_payload(payload):
                        """ペイロードから本文を再帰的に取得"""
                        body = ""
                        
                        # シンプルなメッセージの場合
                        if 'body' in payload and payload['body'].get('data'):
                            body_data = payload['body']['data']
                            try:
                                import base64
                                body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                            except Exception as e:
                                logger.debug(f"本文のデコードエラー: {str(e)}")
                        
                        # マルチパートメッセージの場合
                        if 'parts' in payload:
                            for part in payload['parts']:
                                # 再帰的に処理
                                if 'parts' in part:
                                    body += get_body_from_payload(part)
                                # text/plainパートを優先
                                elif part.get('mimeType') == 'text/plain':
                                    if part.get('body', {}).get('data'):
                                        body_data = part['body']['data']
                                        try:
                                            import base64
                                            decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                                            if decoded:
                                                body = decoded  # text/plainを優先
                                        except Exception as e:
                                            logger.debug(f"本文のデコードエラー: {str(e)}")
                                # text/htmlパートも取得（text/plainがない場合）
                                elif part.get('mimeType') == 'text/html' and not body:
                                    if part.get('body', {}).get('data'):
                                        body_data = part['body']['data']
                                        try:
                                            import base64
                                            decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                                            # HTMLタグを除去（簡易的）
                                            import re
                                            decoded = re.sub(r'<[^>]+>', '', decoded)
                                            if decoded:
                                                body = decoded
                                        except Exception as e:
                                            logger.debug(f"本文のデコードエラー: {str(e)}")
                        
                        return body
                    
                    body = get_body_from_payload(message['payload'])
                    
                    # バウンスメールかどうかを判定
                    is_bounce = is_bounce_email(subject, body)
                    logger.debug(f"メッセージID {message_id}: バウンス判定結果={is_bounce}, subject={subject[:100] if subject else 'N/A'}")
                    
                    if is_bounce:
                        logger.info(f"バウンスメールを検知: subject={subject}, from={from_email}, message_id={message_id}")
                        
                        # デバッグ用: バウンスメールの本文の一部をログに出力（最初の500文字）
                        logger.debug(f"バウンスメール本文（最初の500文字）: {body[:500] if body else 'N/A'}")
                        
                        # 元の送信先メールアドレスを抽出
                        recipient_email = extract_email_from_bounce_body(body)
                        
                        if recipient_email:
                            logger.info(f"抽出されたメールアドレス: {recipient_email}, message_id={message_id}")
                        else:
                            logger.warning(f"バウンスメールからメールアドレスを抽出できませんでした: subject={subject}, message_id={message_id}")
                            # デバッグ用: 本文の一部をログに出力（抽出失敗時）
                            if body:
                                logger.debug(f"バウンスメール本文（抽出失敗時、最初の1000文字）: {body[:1000]}")
                    else:
                        # バウンスメールではない場合もログに記録（デバッグ用）
                        logger.debug(f"バウンスメールではない: subject={subject[:100] if subject else 'N/A'}, from={from_email[:50] if from_email else 'N/A'}, message_id={message_id}")
                            
                            # 抽出されたメールアドレスが実際に送信したメールアドレスか確認
                            # satei_usersテーブルに存在するメールアドレスのみを更新
                            async with db_connection.get_connection() as conn:
                                async with conn.cursor(aiomysql.DictCursor) as cursor:
                                    # まず、該当するメールアドレスが存在するか確認
                                    await cursor.execute("""
                                        SELECT id, email 
                                        FROM satei_users 
                                        WHERE email = %s
                                    """, (recipient_email,))
                                    user_result = await cursor.fetchone()
                                    
                                    if user_result:
                                        # メールアドレスが存在する場合のみフラグを更新（invalidに設定）
                                        await cursor.execute("""
                                            UPDATE satei_users 
                                            SET is_email_invalid = 'invalid' 
                                            WHERE email = %s
                                        """, (recipient_email,))
                                        await conn.commit()
                                        
                                        logger.info(f"メールアドレスを無効に設定: {recipient_email} (user_id={user_result['id']}), user_id={user_id}, message_id={message_id}")
                                        bounce_count += 1
                                        processed_message_ids.add(message_id)  # 処理済みとして記録
                                    else:
                                        logger.warning(f"抽出されたメールアドレスがsatei_usersテーブルに存在しません: {recipient_email}")
                        else:
                            logger.warning(f"バウンスメールから送信先メールアドレスを抽出できませんでした: subject={subject}")
                            # デバッグ用: 本文の一部をログに出力
                            if body:
                                logger.debug(f"バウンスメール本文（抽出失敗時、最初の1000文字）: {body[:1000]}")
                    
                except Exception as e:
                    logger.error(f"メール処理エラー: message_id={msg.get('id')}, error={str(e)}", exc_info=True)
                    continue
            
            logger.info(f"バウンスメールチェック完了: user_id={user_id}, 検知数={bounce_count}")
            return bounce_count
            
        except HttpError as e:
            logger.error(f"Gmail APIエラー: {str(e)}", exc_info=True)
            return 0
            
    except Exception as e:
        logger.error(f"バウンスメールチェックエラー: user_id={user_id}, error={str(e)}", exc_info=True)
        return 0


async def check_all_users_bounce_emails():
    """noreply@miraiarc.jpのバウンスメールをチェック"""
    try:
        # noreply@miraiarc.jpのGmail認証情報を取得
        async with db_connection.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT DISTINCT user_id 
                    FROM user_gmail_credentials
                    WHERE email = 'noreply@miraiarc.jp'
                """)
                results = await cursor.fetchall()
                
                user_ids = [row['user_id'] for row in results]
                
                if not user_ids:
                    logger.warning("noreply@miraiarc.jpのGmail認証情報が見つかりませんでした")
                    return 0
                
                logger.info(f"チェック対象ユーザー数: {len(user_ids)} (noreply@miraiarc.jpのみ)")
                
                total_bounce_count = 0
                for user_id in user_ids:
                    try:
                        bounce_count = await check_bounce_emails_for_user(user_id)
                        total_bounce_count += bounce_count
                    except Exception as e:
                        error_message = str(e)
                        if 'invalid_scope' in error_message or 'Bad Request' in error_message:
                            logger.warning(
                                f"ユーザーのバウンスメールチェックをスキップ: user_id={user_id}\n"
                                f"理由: Gmail認証情報に 'gmail.readonly' スコープが含まれていません。\n"
                                f"再認証が必要です。"
                            )
                        else:
                            logger.error(f"ユーザーのバウンスメールチェックエラー: user_id={user_id}, error={error_message}", exc_info=True)
                        continue
                
                logger.info(f"noreply@miraiarc.jpのバウンスメールチェック完了: 総検知数={total_bounce_count}")
                return total_bounce_count
                
    except Exception as e:
        logger.error(f"バウンスメールチェックエラー: {str(e)}", exc_info=True)
        return 0


async def main():
    """メイン処理"""
    try:
        logger.info("バウンスメールチェック処理を開始します")
        
        # すべてのユーザーのバウンスメールをチェック
        bounce_count = await check_all_users_bounce_emails()
        
        logger.info(f"バウンスメールチェック処理が完了しました: 検知数={bounce_count}")
        
    except Exception as e:
        logger.error(f"バウンスメールチェック処理エラー: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # データベース接続プールを明示的に閉じる
        try:
            await db_connection.close_pool()
        except Exception as e:
            logger.warning(f"データベース接続プールのクローズ中にエラーが発生しました: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
