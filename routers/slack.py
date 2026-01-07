"""
Slack通知API
"""
import os
import requests
import logging
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional
from database.api_keys import api_key_manager
from config.slack import get_slack_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])


class SlackMessageRequest(BaseModel):
    """Slack通知リクエストモデル"""
    message: dict = Field(..., description="送信するメッセージ（Slackフォーマット）")
    user_email: str = Field(..., description="ユーザーのメールアドレス（Webhook URLを取得するために使用）")


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


@router.post("/send")
async def send_slack_message(
    request: SlackMessageRequest,
    api_key_info = Depends(verify_api_key)
):
    """
    Slackにメッセージを送信
    
    Args:
        request: Slack通知リクエスト（メッセージとユーザーメールアドレス）
        api_key: APIキー認証
    
    Returns:
        送信結果
    """
    try:
        # メールアドレスからSlack設定を取得
        logger.info(f"[Slack通知] リクエスト受信: user_email={request.user_email}")
        try:
            slack_config = get_slack_config(request.user_email)
            webhook_url = slack_config['webhook_url']
            logger.info(
                f"[Slack通知] 設定取得成功: "
                f"webhook_url={webhook_url[:50]}..., "
                f"mention={slack_config.get('mention', 'N/A')}"
            )
        except ValueError as ve:
            # 環境変数未設定やメールアドレス無効などのエラー
            logger.error(f"[Slack通知] 設定取得エラー: {str(ve)}, user_email={request.user_email}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Slack設定の取得に失敗しました: {str(ve)}"
            )
        except Exception as config_error:
            logger.error(f"[Slack通知] 設定取得時の予期しないエラー: {str(config_error)}, user_email={request.user_email}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Slack設定の取得中にエラーが発生しました: {str(config_error)}"
            )
        
        # messageオブジェクトが辞書の場合、そのまま使用
        # text形式の場合、辞書に変換
        if isinstance(request.message, str):
            payload = {"text": request.message}
        else:
            payload = request.message
        
        logger.info(f"[Slack通知] メッセージ送信開始: payload={str(payload)[:200]}")
        
        # Slack Webhookにメッセージを送信
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10
            )
            logger.info(
                f"[Slack通知] レスポンス受信: "
                f"status_code={response.status_code}, "
                f"response_text={response.text[:200]}"
            )
        except requests.exceptions.RequestException as req_e:
            logger.error(f"[Slack通知] リクエスト送信エラー: {str(req_e)}, webhook_url={webhook_url[:50]}...", exc_info=True)
            raise
        
        if response.status_code != 200:
            logger.error(
                f"[Slack通知] 送信失敗: "
                f"status_code={response.status_code}, "
                f"response_text={response.text}, "
                f"webhook_url={webhook_url[:50]}..."
            )
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Slackメッセージの送信に失敗しました: {response.status_code} - {response.text[:200]}"
            )
        
        logger.info(f"[Slack通知] 送信成功: user_email={request.user_email}")
        return {
            "status": "success",
            "message": "Slackメッセージを送信しました"
        }
    except HTTPException:
        # HTTPExceptionはそのまま再スロー
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"[Slack通知] リクエスト例外: {str(e)}, user_email={request.user_email}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Slackメッセージの送信に失敗しました: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[Slack通知] 予期しないエラー: {str(e)}, user_email={request.user_email}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"予期しないエラーが発生しました: {str(e)}"
        )



