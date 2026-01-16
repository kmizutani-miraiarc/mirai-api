from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import Optional
from datetime import date
import logging

from services.property_sales_stage_summary_service import PropertySalesStageSummaryService
from database.connection import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/property-sales-stage-summary", tags=["property-sales-stage-summary"])


def get_property_sales_stage_summary_service(db_pool=Depends(get_db_pool)) -> PropertySalesStageSummaryService:
    """物件別販売取引レポート集計サービスの依存性注入"""
    return PropertySalesStageSummaryService(db_pool)


# API認証の依存関数
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """API認証キーを検証（データベースベース）"""
    if not x_api_key:
        raise HTTPException(
            status_code=401, 
            detail="API key is required. Please provide X-API-Key header."
        )
    
    # データベースからAPIキーを検証
    from database.api_keys import api_key_manager
    api_key_info = await api_key_manager.validate_api_key(x_api_key)
    if not api_key_info:
        raise HTTPException(
            status_code=401, 
            detail="Invalid API key. Please check your X-API-Key header."
        )
    
    return api_key_info


@router.get("/latest", summary="最新の物件別販売取引レポート集計データ取得")
async def get_latest_summary(
    service: PropertySalesStageSummaryService = Depends(get_property_sales_stage_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """最新の物件別販売取引レポート集計データを取得します"""
    try:
        return await service.get_latest_summary()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件別販売取引レポート集計データ取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件別販売取引レポート集計データの取得に失敗しました: {str(e)}")


@router.get("/summary", summary="指定した集計日のデータ取得")
async def get_summary_by_date(
    aggregation_date: str = Query(..., description="集計日 (YYYY-MM-DD形式)"),
    service: PropertySalesStageSummaryService = Depends(get_property_sales_stage_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """指定した集計日のデータを取得します"""
    try:
        try:
            date_obj = date.fromisoformat(aggregation_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効な日付形式です。YYYY-MM-DD形式で指定してください。")
        
        return await service.get_summary_by_date(date_obj)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件別販売取引レポート集計データ取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件別販売取引レポート集計データの取得に失敗しました: {str(e)}")


@router.get("/deal-ids", summary="取引IDリスト取得（物件別）")
async def get_deal_ids(
    aggregation_date: str = Query(..., description="集計日 (YYYY-MM-DD形式)"),
    property_id: str = Query(..., description="物件ID"),
    stage_id: str = Query(..., description="ステージID"),
    service: PropertySalesStageSummaryService = Depends(get_property_sales_stage_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """指定した条件の取引IDリストとHubSpotリンクを取得します（物件別）"""
    try:
        try:
            date_obj = date.fromisoformat(aggregation_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効な日付形式です。YYYY-MM-DD形式で指定してください。")
        
        return await service.get_deal_ids(date_obj, property_id, stage_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取引IDリスト取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引IDリストの取得に失敗しました: {str(e)}")


@router.get("/owner-property-deal-ids", summary="取引IDリスト取得（担当者物件別）")
async def get_owner_property_deal_ids(
    aggregation_date: str = Query(..., description="集計日 (YYYY-MM-DD形式)"),
    owner_id: str = Query(..., description="担当者ID"),
    property_id: str = Query(..., description="物件ID"),
    stage_id: str = Query(..., description="ステージID"),
    service: PropertySalesStageSummaryService = Depends(get_property_sales_stage_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """指定した条件の取引IDリストとHubSpotリンクを取得します（担当者物件別）"""
    try:
        try:
            date_obj = date.fromisoformat(aggregation_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効な日付形式です。YYYY-MM-DD形式で指定してください。")
        
        return await service.get_owner_property_deal_ids(date_obj, owner_id, property_id, stage_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取引IDリスト取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引IDリストの取得に失敗しました: {str(e)}")


@router.get("/deal-details", summary="取引詳細取得（物件別、会社名・コンタクト名を含む）")
async def get_deal_details(
    aggregation_date: str = Query(..., description="集計日 (YYYY-MM-DD形式)"),
    property_id: str = Query(..., description="物件ID"),
    stage_id: str = Query(..., description="ステージID"),
    service: PropertySalesStageSummaryService = Depends(get_property_sales_stage_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """指定した条件の取引詳細を取得します（物件別、会社名・コンタクト名を含む）"""
    try:
        try:
            date_obj = date.fromisoformat(aggregation_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効な日付形式です。YYYY-MM-DD形式で指定してください。")
        
        return await service.get_deal_details_with_company_and_contact(date_obj, property_id, stage_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取引詳細取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引詳細の取得に失敗しました: {str(e)}")


@router.get("/owner-property-deal-details", summary="取引詳細取得（担当者物件別、会社名・コンタクト名を含む）")
async def get_owner_property_deal_details(
    aggregation_date: str = Query(..., description="集計日 (YYYY-MM-DD形式)"),
    owner_id: str = Query(..., description="担当者ID"),
    property_id: str = Query(..., description="物件ID"),
    stage_id: str = Query(..., description="ステージID"),
    service: PropertySalesStageSummaryService = Depends(get_property_sales_stage_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """指定した条件の取引詳細を取得します（担当者物件別、会社名・コンタクト名を含む）"""
    try:
        try:
            date_obj = date.fromisoformat(aggregation_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効な日付形式です。YYYY-MM-DD形式で指定してください。")
        
        return await service.get_owner_property_deal_details_with_company_and_contact(date_obj, owner_id, property_id, stage_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取引詳細取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引詳細の取得に失敗しました: {str(e)}")
