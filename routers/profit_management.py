from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import List, Optional
from datetime import date
from decimal import Decimal
import logging

from models.profit_management import (
    ProfitManagementCreate,
    ProfitManagementUpdate,
    ProfitManagementResponse,
    ProfitManagementSearchRequest,
    ProfitManagementListResponse
)
from services.profit_management_service import ProfitManagementService
from database.connection import get_db_pool
from database.api_keys import api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profit-management", tags=["profit-management"])


def get_profit_management_service(db_pool=Depends(get_db_pool)) -> ProfitManagementService:
    """粗利按分管理サービスの依存性注入"""
    return ProfitManagementService(db_pool)


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


@router.post("/", response_model=ProfitManagementResponse, summary="粗利按分管理レコード作成")
async def create_profit_management(
    data: ProfitManagementCreate,
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利按分管理レコードを作成します"""
    try:
        return await service.create_profit_management(data)
    except Exception as e:
        logger.error(f"粗利按分管理レコード作成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利按分管理レコードの作成に失敗しました: {str(e)}")


@router.get("/{seq_no}", response_model=ProfitManagementResponse, summary="粗利按分管理レコード取得")
async def get_profit_management(
    seq_no: int,
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """SeqNoで粗利按分管理レコードを取得します"""
    try:
        result = await service.get_profit_management_by_seq_no(seq_no)
        if not result:
            raise HTTPException(status_code=404, detail="粗利按分管理レコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"粗利按分管理レコード取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利按分管理レコードの取得に失敗しました: {str(e)}")


@router.get("/property/{property_id}", response_model=ProfitManagementResponse, summary="物件IDで粗利按分管理レコード取得")
async def get_profit_management_by_property_id(
    property_id: str,
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """物件IDで粗利按分管理レコードを取得します"""
    try:
        result = await service.get_profit_management_by_property_id(property_id)
        if not result:
            raise HTTPException(status_code=404, detail="粗利按分管理レコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件IDでの粗利按分管理レコード取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件IDでの粗利按分管理レコードの取得に失敗しました: {str(e)}")


@router.put("/{seq_no}", response_model=ProfitManagementResponse, summary="粗利按分管理レコード更新")
async def update_profit_management(
    seq_no: int,
    data: ProfitManagementUpdate,
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利按分管理レコードを更新します"""
    try:
        result = await service.update_profit_management(seq_no, data)
        if not result:
            raise HTTPException(status_code=404, detail="粗利按分管理レコードが見つかりません")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"粗利按分管理レコード更新エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利按分管理レコードの更新に失敗しました: {str(e)}")


@router.delete("/{seq_no}", summary="粗利按分管理レコード削除")
async def delete_profit_management(
    seq_no: int,
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利按分管理レコードを削除します"""
    try:
        success = await service.delete_profit_management(seq_no)
        if not success:
            raise HTTPException(status_code=404, detail="粗利按分管理レコードが見つかりません")
        return {"message": "粗利按分管理レコードが削除されました"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"粗利按分管理レコード削除エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利按分管理レコードの削除に失敗しました: {str(e)}")


@router.post("/search", response_model=ProfitManagementListResponse, summary="粗利按分管理レコード検索")
async def search_profit_management(
    search_request: ProfitManagementSearchRequest,
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利按分管理レコードを検索します"""
    try:
        return await service.search_profit_management(search_request)
    except Exception as e:
        logger.error(f"粗利按分管理レコード検索エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利按分管理レコードの検索に失敗しました: {str(e)}")


@router.get("/", response_model=ProfitManagementListResponse, summary="粗利按分管理レコード一覧取得")
async def list_profit_management(
    property_id: Optional[str] = Query(None, description="物件番号で検索"),
    property_name: Optional[str] = Query(None, description="物件名で検索"),
    profit_confirmed: Optional[bool] = Query(None, description="粗利確定で検索"),
    limit: int = Query(100, description="取得件数制限"),
    offset: int = Query(0, description="オフセット"),
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利按分管理レコードの一覧を取得します（クエリパラメータ版）"""
    try:
        search_request = ProfitManagementSearchRequest(
            property_id=property_id,
            property_name=property_name,
            profit_confirmed=profit_confirmed,
            limit=limit,
            offset=offset
        )
        return await service.search_profit_management(search_request)
    except Exception as e:
        logger.error(f"粗利按分管理レコード一覧取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利按分管理レコードの一覧取得に失敗しました: {str(e)}")


@router.post("/calculate-profit/{seq_no}", response_model=ProfitManagementResponse, summary="粗利計算")
async def calculate_profit(
    seq_no: int,
    purchase_owner_profit_rate: Optional[Decimal] = Query(None, description="仕入担当粗利率(%)"),
    sales_owner_profit_rate: Optional[Decimal] = Query(None, description="販売担当粗利率(%)"),
    service: ProfitManagementService = Depends(get_profit_management_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利を計算して按分します"""
    try:
        # 現在のレコードを取得
        current = await service.get_profit_management_by_seq_no(seq_no)
        if not current:
            raise HTTPException(status_code=404, detail="粗利按分管理レコードが見つかりません")
        
        if not current.gross_profit:
            raise HTTPException(status_code=400, detail="粗利が計算できません。仕入価格と販売価格を確認してください。")
        
        # 粗利率の合計が100%になることを確認
        if purchase_owner_profit_rate is not None and sales_owner_profit_rate is not None:
            total_rate = purchase_owner_profit_rate + sales_owner_profit_rate
            if abs(total_rate - 100) > 0.01:  # 小数点以下の誤差を考慮
                raise HTTPException(status_code=400, detail="仕入担当と販売担当の粗利率の合計が100%になる必要があります")
        
        # 粗利按分を計算
        purchase_owner_profit = None
        sales_owner_profit = None
        
        if purchase_owner_profit_rate is not None:
            purchase_owner_profit = current.gross_profit * (purchase_owner_profit_rate / 100)
        
        if sales_owner_profit_rate is not None:
            sales_owner_profit = current.gross_profit * (sales_owner_profit_rate / 100)
        
        # レコードを更新
        update_data = ProfitManagementUpdate(
            purchase_owner_profit_rate=purchase_owner_profit_rate,
            purchase_owner_profit=purchase_owner_profit,
            sales_owner_profit_rate=sales_owner_profit_rate,
            sales_owner_profit=sales_owner_profit
        )
        
        return await service.update_profit_management(seq_no, update_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"粗利計算エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利の計算に失敗しました: {str(e)}")
