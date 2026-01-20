from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import Optional
import logging

from services.profit_report_service import ProfitReportService
from services.purchase_summary_service import PurchaseSummaryService
from services.sales_summary_service import SalesSummaryService
from database.connection import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profit-report", tags=["profit-report"])


def get_profit_report_service(db_pool=Depends(get_db_pool)) -> ProfitReportService:
    """粗利集計レポートサービスの依存性注入"""
    return ProfitReportService(db_pool)


def get_purchase_summary_service(db_pool=Depends(get_db_pool)) -> PurchaseSummaryService:
    """仕入集計レポートサービスの依存性注入"""
    return PurchaseSummaryService(db_pool)


def get_sales_summary_service(db_pool=Depends(get_db_pool)) -> SalesSummaryService:
    """販売集計レポートサービスの依存性注入"""
    return SalesSummaryService(db_pool)


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


@router.get("/purchase-summary", summary="仕入集計レポート取得（バッチ処理版）")
async def get_purchase_summary_report(
    year: int = Query(..., description="集計年"),
    is_appraisal_only: bool = Query(False, description="査定物件のみフラグ"),
    service: PurchaseSummaryService = Depends(get_purchase_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """仕入集計レポートを取得します（バッチ処理で集計されたデータを取得）"""
    try:
        return await service.get_latest_summary(year, is_appraisal_only)
    except Exception as e:
        logger.error(f"仕入集計レポート取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"仕入集計レポートの取得に失敗しました: {str(e)}")


@router.get("/sales-summary", summary="販売集計レポート取得（バッチ処理版）")
async def get_sales_summary_report(
    year: int = Query(..., description="集計年"),
    service: SalesSummaryService = Depends(get_sales_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """販売集計レポートを取得します（バッチ処理で集計されたデータを取得）"""
    try:
        return await service.get_latest_summary(year)
    except Exception as e:
        logger.error(f"販売集計レポート取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"販売集計レポートの取得に失敗しました: {str(e)}")


@router.get("/purchase-summary/deal-ids", summary="仕入集計レポート取引IDリスト取得")
async def get_purchase_summary_deal_ids(
    year: int = Query(..., description="集計年"),
    owner_id: str = Query(..., description="担当者ID（totalの場合は全担当者）"),
    year_month: str = Query(..., description="年月（YYYY-MM形式）"),
    stage_name: str = Query(..., description="ステージ名または当月系項目名"),
    service: PurchaseSummaryService = Depends(get_purchase_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """仕入集計レポートの取引IDリストを取得します（バッチ処理で集計されたデータから）"""
    try:
        return await service.get_deal_ids(year, owner_id, year_month, stage_name)
    except Exception as e:
        logger.error(f"仕入集計レポート取引IDリスト取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引IDリストの取得に失敗しました: {str(e)}")


@router.get("/purchase-summary/deal-details", summary="仕入集計レポート取引詳細取得")
async def get_purchase_summary_deal_details(
    year: int = Query(..., description="集計年"),
    owner_id: str = Query(..., description="担当者ID（totalの場合は全担当者）"),
    year_month: str = Query(..., description="年月（YYYY-MM形式）"),
    stage_name: str = Query(..., description="ステージ名または当月系項目名"),
    is_appraisal_only: bool = Query(False, description="査定物件のみフラグ"),
    service: PurchaseSummaryService = Depends(get_purchase_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """仕入集計レポートの取引詳細を取得します（バッチ処理で集計されたデータから、会社名・コンタクト名を含む）"""
    try:
        return await service.get_deal_details(year, owner_id, year_month, stage_name, is_appraisal_only)
    except Exception as e:
        logger.error(f"仕入集計レポート取引詳細取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引詳細の取得に失敗しました: {str(e)}")


@router.get("/sales-summary/deal-details", summary="販売集計レポート取引詳細取得")
async def get_sales_summary_deal_details(
    year: int = Query(..., description="集計年"),
    owner_id: str = Query(..., description="担当者ID（totalの場合は全担当者）"),
    year_month: str = Query(..., description="年月（YYYY-MM形式）"),
    stage_name: str = Query(..., description="ステージ名または当月系項目名"),
    service: SalesSummaryService = Depends(get_sales_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """販売集計レポートの取引詳細を取得します（バッチ処理で集計されたデータから、会社名・コンタクト名を含む）"""
    try:
        return await service.get_deal_details(year, owner_id, year_month, stage_name)
    except Exception as e:
        logger.error(f"販売集計レポート取引詳細取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引詳細の取得に失敗しました: {str(e)}")






