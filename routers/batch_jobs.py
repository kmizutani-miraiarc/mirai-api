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
        job_id = await queue.add_job(job_key)
        
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


@router.get("/{job_id}/status", summary="ジョブのステータスを取得")
async def get_job_status(
    job_id: int,
    api_key_info=Depends(verify_api_key)
):
    """
    ジョブのステータスを取得
    
    Args:
        job_id: ジョブID
        api_key_info: APIキー情報
        
    Returns:
        ジョブのステータス情報
    """
    try:
        from database.connection import db_connection
        import aiomysql
        
        await db_connection.create_pool()
        if not db_connection.pool:
            raise HTTPException(
                status_code=500,
                detail="データベース接続プールが作成されていません"
            )
        
        async with db_connection.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        id,
                        job_name,
                        script_path,
                        status,
                        priority,
                        created_at,
                        started_at,
                        completed_at,
                        error_message
                    FROM batch_job_queue
                    WHERE id = %s
                """, (job_id,))
                
                job = await cursor.fetchone()
                
                if not job:
                    raise HTTPException(
                        status_code=404,
                        detail=f"ジョブID {job_id} が見つかりません"
                    )
                
                return {
                    "status": "success",
                    "data": {
                        "id": job['id'],
                        "job_name": job['job_name'],
                        "status": job['status'],
                        "created_at": job['created_at'].isoformat() if job['created_at'] else None,
                        "started_at": job['started_at'].isoformat() if job['started_at'] else None,
                        "completed_at": job['completed_at'].isoformat() if job['completed_at'] else None,
                        "error_message": job.get('error_message')
                    }
                }
                
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"ジョブステータスの取得中にエラーが発生しました: {str(e)}"
        logger.error(error_detail, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )



