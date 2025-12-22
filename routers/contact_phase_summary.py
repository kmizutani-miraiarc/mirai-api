from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import Optional
from datetime import date
import logging

from services.contact_phase_summary_service import ContactPhaseSummaryService
from database.connection import get_db_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contact-phase-summary", tags=["contact-phase-summary"])


def get_contact_phase_summary_service(db_pool=Depends(get_db_pool)) -> ContactPhaseSummaryService:
    """コンタクトフェーズ集計サービスの依存性注入"""
    return ContactPhaseSummaryService(db_pool)


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


@router.get("/dates", summary="利用可能な集計日リスト取得")
async def get_available_dates(
    service: ContactPhaseSummaryService = Depends(get_contact_phase_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """利用可能な集計日のリストを取得します"""
    try:
        dates = await service.get_available_dates()
        return {"dates": dates}
    except Exception as e:
        logger.error(f"集計日リスト取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"集計日リストの取得に失敗しました: {str(e)}")


@router.get("/summary", summary="指定した集計日のデータ取得")
async def get_summary_by_date(
    aggregation_date: str = Query(..., description="集計日 (YYYY-MM-DD形式)"),
    service: ContactPhaseSummaryService = Depends(get_contact_phase_summary_service),
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
        logger.error(f"フェーズ集計データ取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"フェーズ集計データの取得に失敗しました: {str(e)}")


@router.get("/latest", summary="最新のフェーズ集計データ取得")
async def get_latest_summary(
    service: ContactPhaseSummaryService = Depends(get_contact_phase_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """最新のフェーズ集計データを取得します"""
    try:
        return await service.get_latest_summary()
    except Exception as e:
        logger.error(f"フェーズ集計データ取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"フェーズ集計データの取得に失敗しました: {str(e)}")


@router.get("/comparison", summary="フェーズ集計データと前週比取得")
async def get_comparison(
    current_date: Optional[str] = Query(None, description="現在の集計日 (YYYY-MM-DD形式)"),
    previous_date: Optional[str] = Query(None, description="比較対象の集計日 (YYYY-MM-DD形式)"),
    service: ContactPhaseSummaryService = Depends(get_contact_phase_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """指定した2つの集計日を比較します。日付が指定されない場合は最新と前週を比較します"""
    try:
        if current_date and previous_date:
            try:
                current_date_obj = date.fromisoformat(current_date)
                previous_date_obj = date.fromisoformat(previous_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="無効な日付形式です。YYYY-MM-DD形式で指定してください。")
            
            return await service.get_comparison(current_date_obj, previous_date_obj)
        else:
            # 日付が指定されない場合は最新と前週を比較
            return await service.get_summary_with_comparison()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"フェーズ集計データ（前週比）取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"フェーズ集計データ（前週比）の取得に失敗しました: {str(e)}")


@router.get("/contact-ids", summary="コンタクトIDリスト取得")
async def get_contact_ids(
    aggregation_date: str = Query(..., description="集計日 (YYYY-MM-DD形式)"),
    owner_id: str = Query(..., description="担当者ID"),
    phase_type: str = Query(..., description="フェーズ区分 (buy または sell)"),
    phase_value: str = Query(..., description="フェーズ値 (S, A, B, C, D, Z)"),
    service: ContactPhaseSummaryService = Depends(get_contact_phase_summary_service),
    api_key_info=Depends(verify_api_key)
):
    """指定した条件のコンタクトIDリストとHubSpotリンクを取得します"""
    try:
        try:
            date_obj = date.fromisoformat(aggregation_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="無効な日付形式です。YYYY-MM-DD形式で指定してください。")
        
        if phase_type not in ['buy', 'sell']:
            raise HTTPException(status_code=400, detail="phase_typeは 'buy' または 'sell' である必要があります。")
        
        if phase_value not in ['S', 'A', 'B', 'C', 'D', 'Z']:
            raise HTTPException(status_code=400, detail="phase_valueは 'S', 'A', 'B', 'C', 'D', 'Z' のいずれかである必要があります。")
        
        return await service.get_contact_ids(date_obj, owner_id, phase_type, phase_value)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"コンタクトIDリスト取得エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"コンタクトIDリストの取得に失敗しました: {str(e)}")

