"""
バッチジョブ管理API
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import logging
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.batch_job_queue import BatchJobQueue
from database.api_keys import api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch-jobs", tags=["batch-jobs"])


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


@router.post("/queue", summary="バッチジョブをキューに追加")
async def add_batch_job_to_queue(
    request: Dict[str, Any],
    api_key_info=Depends(verify_api_key)
):
    """
    バッチジョブをキューに追加
    
    Args:
        request: リクエストボディ（job_keyを含む）
        api_key_info: APIキー情報
        
    Returns:
        追加結果
    """
    try:
        job_key = request.get('job_key')
        
        if not job_key:
            raise HTTPException(
                status_code=400,
                detail="job_key is required"
            )
        
        # バッチジョブキューに追加
        queue = BatchJobQueue()
        job_id = await queue.add_job(job_key, max_retries=0)
        
        if job_id:
            logger.info(f"バッチジョブをキューに追加しました: {job_key} (ID: {job_id})")
            return {
                "status": "success",
                "message": "バッチジョブをキューに追加しました",
                "data": {
                    "job_id": job_id,
                    "job_key": job_key
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="バッチジョブの追加に失敗しました"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"バッチジョブの追加中にエラーが発生しました: {str(e)}"
        logger.error(error_detail, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )


@router.post("/progress", summary="バッチジョブの進捗を更新")
async def update_batch_job_progress(
    request: Dict[str, Any],
    api_key_info=Depends(verify_api_key)
):
    """
    バッチジョブの進捗を更新
    
    Args:
        request: リクエストボディ（job_id, progress_message, progress_percentageを含む）
        api_key_info: APIキー情報
        
    Returns:
        更新結果
    """
    try:
        job_id = request.get('job_id')
        progress_message = request.get('progress_message')
        progress_percentage = request.get('progress_percentage')
        
        if not job_id:
            raise HTTPException(
                status_code=400,
                detail="job_id is required"
            )
        
        # 進捗パーセンテージの範囲チェック
        if progress_percentage is not None:
            if not isinstance(progress_percentage, int) or progress_percentage < 0 or progress_percentage > 100:
                raise HTTPException(
                    status_code=400,
                    detail="progress_percentage must be an integer between 0 and 100"
                )
        
        # バッチジョブキューで進捗を更新
        queue = BatchJobQueue()
        success = await queue.update_job_progress(job_id, progress_message, progress_percentage)
        
        if success:
            logger.info(f"バッチジョブの進捗を更新しました: job_id={job_id}, progress={progress_percentage}%")
            return {
                "status": "success",
                "message": "バッチジョブの進捗を更新しました",
                "data": {
                    "job_id": job_id,
                    "progress_message": progress_message,
                    "progress_percentage": progress_percentage
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="バッチジョブの進捗更新に失敗しました"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"バッチジョブの進捗更新中にエラーが発生しました: {str(e)}"
        logger.error(error_detail, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

