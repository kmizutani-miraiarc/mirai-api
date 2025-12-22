#!/usr/bin/env python3
"""
バッチジョブの進捗を更新するヘルパーモジュール
バッチ処理スクリプトから使用する
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.batch_job_queue import BatchJobQueue

logger = logging.getLogger(__name__)
# ログレベルをINFOに設定（デバッグ用）
logger.setLevel(logging.INFO)

# ログハンドラーが設定されていない場合は、デフォルトのハンドラーを追加
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


async def update_progress(
    job_id: Optional[int],
    progress_message: Optional[str] = None,
    progress_percentage: Optional[int] = None
):
    """
    バッチジョブの進捗を更新
    
    Args:
        job_id: ジョブID（環境変数BATCH_JOB_IDから取得可能）
        progress_message: 進捗メッセージ
        progress_percentage: 進捗パーセンテージ（0-100）
    """
    if job_id is None:
        # 環境変数から取得を試みる
        job_id_str = os.environ.get('BATCH_JOB_ID')
        if job_id_str:
            try:
                job_id = int(job_id_str)
                logger.info(f"環境変数からBATCH_JOB_IDを取得: {job_id}")
            except (ValueError, TypeError):
                logger.warning(f"無効なBATCH_JOB_ID: {job_id_str}")
                return
        else:
            # 環境変数が設定されていない場合は警告を出さずに静かに終了
            # （手動実行時など、BATCH_JOB_IDが設定されていない場合があるため）
            logger.info("BATCH_JOB_IDが設定されていません（手動実行の可能性）")
            return
    
    try:
        logger.info(f"進捗更新を開始: job_id={job_id}, progress={progress_percentage}%, message={progress_message}")
        queue = BatchJobQueue()
        success = await queue.update_job_progress(job_id, progress_message, progress_percentage)
        if success:
            logger.info(f"進捗を更新しました: job_id={job_id}, progress={progress_percentage}%, message={progress_message}")
        else:
            logger.error(f"進捗の更新に失敗しました: job_id={job_id}")
    except Exception as e:
        logger.error(f"進捗の更新中にエラーが発生しました: {str(e)}", exc_info=True)


def update_progress_sync(
    job_id: Optional[int],
    progress_message: Optional[str] = None,
    progress_percentage: Optional[int] = None
):
    """
    バッチジョブの進捗を更新（同期版）
    
    Args:
        job_id: ジョブID（環境変数BATCH_JOB_IDから取得可能）
        progress_message: 進捗メッセージ
        progress_percentage: 進捗パーセンテージ（0-100）
    """
    asyncio.run(update_progress(job_id, progress_message, progress_percentage))

