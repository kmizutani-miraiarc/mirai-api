from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import List, Optional
from datetime import date
from decimal import Decimal
import logging

from models.property_owner import (
    PropertyOwnerCreate,
    PropertyOwnerUpdate,
    PropertyOwnerResponse,
    PropertyOwnerSearchRequest,
    PropertyOwnerListResponse,
    OwnerType
)
from services.property_owner_service import PropertyOwnerService
from database.connection import get_db_pool
from database.api_keys import api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/property-owners", tags=["property-owners"])


def get_property_owner_service(db_pool=Depends(get_db_pool)) -> PropertyOwnerService:
    """物件担当者サービスの依存性注入"""
    return PropertyOwnerService(db_pool)


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


@router.post("/", response_model=PropertyOwnerResponse, summary="物件担当者レコード作成")
async def create_property_owner(
    data: PropertyOwnerCreate,
    service: PropertyOwnerService = Depends(get_property_owner_service),
    api_key_info=Depends(verify_api_key)
):
    """物件担当者レコードを作成します"""
    try:
        return await service.create_property_owner(data)
    except Exception as e:
        logger.error(f"物件担当者レコード作成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件担当者レコードの作成に失敗しました: {str(e)}")


@router.get("/{owner_id}", response_model=PropertyOwnerResponse, summary="物件担当者レコード取得")
async def get_property_owner(
    owner_id: int,
    service: PropertyOwnerService = Depends(get_property_owner_service),
    api_key_info=Depends(verify_api_key)
):
    """IDで物件担当者レコードを取得します"""
    try:
        result = await service.get_property_owner_by_id(owner_id)
        if not result:
            raise HTTPException(status_code=404, detail="物件担当者レコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件担当者レコード取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件担当者レコードの取得に失敗しました: {str(e)}")


@router.get("/property/{property_id}", response_model=List[PropertyOwnerResponse], summary="物件IDで物件担当者レコード一覧取得")
async def get_property_owners_by_property_id(
    property_id: str,
    service: PropertyOwnerService = Depends(get_property_owner_service),
    api_key_info=Depends(verify_api_key)
):
    """物件IDで物件担当者レコード一覧を取得します"""
    try:
        return await service.get_property_owners_by_property_id(property_id)
    except Exception as e:
        logger.error(f"物件IDでの物件担当者レコード一覧取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件IDでの物件担当者レコード一覧の取得に失敗しました: {str(e)}")


@router.put("/{owner_id}", response_model=PropertyOwnerResponse, summary="物件担当者レコード更新")
async def update_property_owner(
    owner_id: int,
    data: PropertyOwnerUpdate,
    service: PropertyOwnerService = Depends(get_property_owner_service),
    api_key_info=Depends(verify_api_key)
):
    """物件担当者レコードを更新します"""
    try:
        result = await service.update_property_owner(owner_id, data)
        if not result:
            raise HTTPException(status_code=404, detail="物件担当者レコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件担当者レコード更新エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件担当者レコードの更新に失敗しました: {str(e)}")


@router.delete("/{owner_id}", summary="物件担当者レコード削除")
async def delete_property_owner(
    owner_id: int,
    service: PropertyOwnerService = Depends(get_property_owner_service),
    api_key_info=Depends(verify_api_key)
):
    """物件担当者レコードを削除します"""
    try:
        success = await service.delete_property_owner(owner_id)
        if not success:
            raise HTTPException(status_code=404, detail="物件担当者レコードが見つかりません")
        return {"message": "物件担当者レコードが削除されました"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件担当者レコード削除エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件担当者レコードの削除に失敗しました: {str(e)}")


@router.post("/search", response_model=PropertyOwnerListResponse, summary="物件担当者レコード検索")
async def search_property_owners(
    search_request: PropertyOwnerSearchRequest,
    service: PropertyOwnerService = Depends(get_property_owner_service),
    api_key_info=Depends(verify_api_key)
):
    """物件担当者レコードを検索します"""
    try:
        return await service.search_property_owners(search_request)
    except Exception as e:
        logger.error(f"物件担当者レコード検索エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件担当者レコードの検索に失敗しました: {str(e)}")


@router.get("/", response_model=PropertyOwnerListResponse, summary="物件担当者レコード一覧取得")
async def list_property_owners(
    property_id: Optional[str] = Query(None, description="物件番号で検索"),
    owner_type: Optional[OwnerType] = Query(None, description="担当者種別で検索"),
    owner_id: Optional[str] = Query(None, description="担当者IDで検索"),
    owner_name: Optional[str] = Query(None, description="担当者名で検索"),
    settlement_date_from: Optional[date] = Query(None, description="決済日（開始）"),
    settlement_date_to: Optional[date] = Query(None, description="決済日（終了）"),
    limit: int = Query(100, description="取得件数制限"),
    offset: int = Query(0, description="オフセット"),
    service: PropertyOwnerService = Depends(get_property_owner_service),
    api_key_info=Depends(verify_api_key)
):
    """物件担当者レコードの一覧を取得します（クエリパラメータ版）"""
    try:
        search_request = PropertyOwnerSearchRequest(
            property_id=property_id,
            owner_type=owner_type,
            owner_id=owner_id,
            owner_name=owner_name,
            settlement_date_from=settlement_date_from,
            settlement_date_to=settlement_date_to,
            limit=limit,
            offset=offset
        )
        return await service.search_property_owners(search_request)
    except Exception as e:
        logger.error(f"物件担当者レコード一覧取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件担当者レコードの一覧取得に失敗しました: {str(e)}")
