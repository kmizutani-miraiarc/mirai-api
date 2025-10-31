"""
Slack通知API
"""
import os
import requests
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional
from database.api_keys import api_key_manager
from config.slack import get_slack_config

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
        slack_config = get_slack_config(request.user_email)
        webhook_url = slack_config['webhook_url']
        
        # messageオブジェクトが辞書の場合、そのまま使用
        # text形式の場合、辞書に変換
        if isinstance(request.message, str):
            payload = {"text": request.message}
        else:
            payload = request.message
        
        # Slack Webhookにメッセージを送信
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Slackメッセージの送信に失敗しました: {response.status_code}"
            )
        
        return {
            "status": "success",
            "message": "Slackメッセージを送信しました"
        }
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Slackメッセージの送信に失敗しました: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"予期しないエラーが発生しました: {str(e)}"
        )



