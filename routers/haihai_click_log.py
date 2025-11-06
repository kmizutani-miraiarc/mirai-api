from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import List, Optional
from datetime import datetime
import logging

from models.haihai_click_log import (
    HaihaiClickLogCreate,
    HaihaiClickLogUpdate,
    HaihaiClickLogResponse,
    HaihaiClickLogSearchRequest,
    HaihaiClickLogListResponse
)
from services.haihai_click_log_service import HaihaiClickLogService
from database.connection import get_db_pool
from database.api_keys import api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/haihai-click-logs", tags=["haihai-click-logs"])


def get_haihai_click_log_service(db_pool=Depends(get_db_pool)) -> HaihaiClickLogService:
    """配配メールログサービスの依存性注入"""
    return HaihaiClickLogService(db_pool)


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


@router.post("/", response_model=HaihaiClickLogResponse, summary="配配メールログレコード作成")
async def create_haihai_click_log(
    data: HaihaiClickLogCreate,
    service: HaihaiClickLogService = Depends(get_haihai_click_log_service),
    api_key_info=Depends(verify_api_key)
):
    """配配メールログレコードを作成します"""
    try:
        return await service.create_haihai_click_log(data)
    except Exception as e:
        logger.error(f"配配メールログレコード作成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"配配メールログレコードの作成に失敗しました: {str(e)}")


@router.get("/{log_id}", response_model=HaihaiClickLogResponse, summary="配配メールログレコード取得")
async def get_haihai_click_log(
    log_id: int,
    service: HaihaiClickLogService = Depends(get_haihai_click_log_service),
    api_key_info=Depends(verify_api_key)
):
    """IDで配配メールログレコードを取得します"""
    try:
        result = await service.get_haihai_click_log_by_id(log_id)
        if not result:
            raise HTTPException(status_code=404, detail="配配メールログレコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配配メールログレコード取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"配配メールログレコードの取得に失敗しました: {str(e)}")


@router.put("/{log_id}", response_model=HaihaiClickLogResponse, summary="配配メールログレコード更新")
async def update_haihai_click_log(
    log_id: int,
    data: HaihaiClickLogUpdate,
    service: HaihaiClickLogService = Depends(get_haihai_click_log_service),
    api_key_info=Depends(verify_api_key)
):
    """配配メールログレコードを更新します"""
    try:
        result = await service.update_haihai_click_log(log_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="配配メールログレコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配配メールログレコード更新エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"配配メールログレコードの更新に失敗しました: {str(e)}")


@router.delete("/{log_id}", summary="配配メールログレコード削除")
async def delete_haihai_click_log(
    log_id: int,
    service: HaihaiClickLogService = Depends(get_haihai_click_log_service),
    api_key_info=Depends(verify_api_key)
):
    """配配メールログレコードを削除します"""
    try:
        success = await service.delete_haihai_click_log(log_id)
        if not success:
            raise HTTPException(status_code=404, detail="配配メールログレコードが見つかりません")
        return {"message": "配配メールログレコードが削除されました"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配配メールログレコード削除エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"配配メールログレコードの削除に失敗しました: {str(e)}")


@router.post("/search", response_model=HaihaiClickLogListResponse, summary="配配メールログレコード検索")
async def search_haihai_click_logs(
    search_request: HaihaiClickLogSearchRequest,
    service: HaihaiClickLogService = Depends(get_haihai_click_log_service),
    api_key_info=Depends(verify_api_key)
):
    """配配メールログレコードを検索します"""
    try:
        return await service.search_haihai_click_logs(search_request)
    except Exception as e:
        logger.error(f"配配メールログレコード検索エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"配配メールログレコードの検索に失敗しました: {str(e)}")


@router.get("/", response_model=HaihaiClickLogListResponse, summary="配配メールログレコード一覧取得")
async def list_haihai_click_logs(
    email: Optional[str] = Query(None, description="メールアドレスで検索（部分一致）"),
    mail_type: Optional[str] = Query(None, description="メール種別で検索"),
    mail_id: Optional[str] = Query(None, description="メールIDで検索（部分一致）"),
    start_date: Optional[datetime] = Query(None, description="クリック日時（開始）"),
    end_date: Optional[datetime] = Query(None, description="クリック日時（終了）"),
    limit: int = Query(100, description="取得件数制限"),
    offset: int = Query(0, description="オフセット"),
    service: HaihaiClickLogService = Depends(get_haihai_click_log_service),
    api_key_info=Depends(verify_api_key)
):
    """配配メールログレコード一覧を取得します"""
    try:
        search_request = HaihaiClickLogSearchRequest(
            email=email,
            mail_type=mail_type,
            mail_id=mail_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        return await service.search_haihai_click_logs(search_request)
    except Exception as e:
        logger.error(f"配配メールログレコード一覧取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"配配メールログレコード一覧の取得に失敗しました: {str(e)}")

