from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import List, Optional
from decimal import Decimal
import logging

from models.profit_target import (
    ProfitTargetCreate,
    ProfitTargetUpdate,
    ProfitTargetResponse,
    ProfitTargetSearchRequest,
    ProfitTargetListResponse
)
from services.profit_target_service import ProfitTargetService
from database.connection import get_db_pool
from database.api_keys import api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profit-target", tags=["profit-target"])


def get_profit_target_service(db_pool=Depends(get_db_pool)) -> ProfitTargetService:
    """粗利目標管理サービスの依存性注入"""
    return ProfitTargetService(db_pool)


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


@router.post("/", response_model=ProfitTargetResponse, summary="粗利目標レコード作成")
async def create_profit_target(
    data: ProfitTargetCreate,
    service: ProfitTargetService = Depends(get_profit_target_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利目標レコードを作成します"""
    try:
        return await service.create_profit_target(data)
    except Exception as e:
        logger.error(f"粗利目標レコード作成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利目標レコードの作成に失敗しました: {str(e)}")


@router.get("/{target_id}", response_model=ProfitTargetResponse, summary="粗利目標レコード取得")
async def get_profit_target(
    target_id: int,
    service: ProfitTargetService = Depends(get_profit_target_service),
    api_key_info=Depends(verify_api_key)
):
    """IDで粗利目標レコードを取得します"""
    try:
        result = await service.get_profit_target_by_id(target_id)
        if not result:
            raise HTTPException(status_code=404, detail="粗利目標レコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"粗利目標レコード取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利目標レコードの取得に失敗しました: {str(e)}")


@router.put("/{target_id}", response_model=ProfitTargetResponse, summary="粗利目標レコード更新")
async def update_profit_target(
    target_id: int,
    data: ProfitTargetUpdate,
    service: ProfitTargetService = Depends(get_profit_target_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利目標レコードを更新します"""
    try:
        result = await service.update_profit_target(target_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="粗利目標レコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"粗利目標レコード更新エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利目標レコードの更新に失敗しました: {str(e)}")


@router.delete("/{target_id}", summary="粗利目標レコード削除")
async def delete_profit_target(
    target_id: int,
    service: ProfitTargetService = Depends(get_profit_target_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利目標レコードを削除します"""
    try:
        success = await service.delete_profit_target(target_id)
        if not success:
            raise HTTPException(status_code=404, detail="粗利目標レコードが見つかりません")
        return {"message": "粗利目標レコードが削除されました"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"粗利目標レコード削除エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利目標レコードの削除に失敗しました: {str(e)}")


@router.post("/search", response_model=ProfitTargetListResponse, summary="粗利目標レコード検索")
async def search_profit_target(
    search_request: ProfitTargetSearchRequest,
    service: ProfitTargetService = Depends(get_profit_target_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利目標レコードを検索します"""
    try:
        return await service.search_profit_target(search_request)
    except Exception as e:
        logger.error(f"粗利目標レコード検索エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利目標レコードの検索に失敗しました: {str(e)}")


@router.get("/", response_model=ProfitTargetListResponse, summary="粗利目標レコード一覧取得")
async def list_profit_target(
    owner_id: Optional[str] = Query(None, description="担当者IDで検索"),
    year: Optional[int] = Query(None, description="年度で検索"),
    limit: int = Query(100, description="取得件数制限"),
    offset: int = Query(0, description="オフセット"),
    service: ProfitTargetService = Depends(get_profit_target_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利目標レコードの一覧を取得します（クエリパラメータ版）"""
    try:
        search_request = ProfitTargetSearchRequest(
            owner_id=owner_id,
            year=year,
            limit=limit,
            offset=offset
        )
        return await service.search_profit_target(search_request)
    except Exception as e:
        logger.error(f"粗利目標レコード一覧取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利目標レコードの一覧取得に失敗しました: {str(e)}")





