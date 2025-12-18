from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import Optional
import logging

from services.profit_report_service import ProfitReportService
from database.connection import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profit-report", tags=["profit-report"])


def get_profit_report_service(db_pool=Depends(get_db_pool)) -> ProfitReportService:
    """粗利集計レポートサービスの依存性注入"""
    return ProfitReportService(db_pool)


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


@router.get("/purchase", summary="仕入集計レポート取得")
async def get_purchase_report(
    year: int = Query(..., description="集計年"),
    service: ProfitReportService = Depends(get_profit_report_service),
    api_key_info=Depends(verify_api_key)
):
    """仕入集計レポートを取得します（仕入決済日を基準に仕入価格を集計）"""
    try:
        return await service.get_purchase_summary(year)
    except Exception as e:
        logger.error(f"仕入集計レポート取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"仕入集計レポートの取得に失敗しました: {str(e)}")


@router.get("/sales", summary="販売集計レポート取得")
async def get_sales_report(
    year: int = Query(..., description="集計年"),
    service: ProfitReportService = Depends(get_profit_report_service),
    api_key_info=Depends(verify_api_key)
):
    """販売集計レポートを取得します（販売決済日を基準に販売価格を集計）"""
    try:
        return await service.get_sales_summary(year)
    except Exception as e:
        logger.error(f"販売集計レポート取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"販売集計レポートの取得に失敗しました: {str(e)}")


@router.get("/profit", summary="粗利集計レポート取得")
async def get_profit_report(
    year: int = Query(..., description="集計年"),
    service: ProfitReportService = Depends(get_profit_report_service),
    api_key_info=Depends(verify_api_key)
):
    """粗利集計レポートを取得します（計上年月を基準に仕入担当者と販売担当者の粗利額の合計を集計）"""
    try:
        return await service.get_profit_summary(year)
    except Exception as e:
        logger.error(f"粗利集計レポート取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"粗利集計レポートの取得に失敗しました: {str(e)}")




