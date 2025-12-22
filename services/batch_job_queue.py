"""
バッチジョブキュー管理サービス
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import db_connection
import aiomysql

logger = logging.getLogger(__name__)


class BatchJobQueue:
    """バッチジョブキュー管理クラス"""
    
    # バッチ処理の定義
    BATCH_JOBS = {
        'contact-phase-summary': {
            'name': '週次フェーズ集計',
            'script': 'scripts/sync_contact_phase_summary.py',
            'priority': 5
        },
        'contact-phase-summary-monthly': {
            'name': '月次フェーズ集計',
            'script': 'scripts/sync_contact_phase_summary_monthly.py',
            'priority': 4
        },
        'contact-scoring-summary': {
            'name': 'コンタクトスコアリング集計',
            'script': 'scripts/sync_contact_scoring_summary.py',
            'priority': 5
        },
        'purchase-achievements': {
            'name': '物件買取実績同期',
            'script': 'scripts/sync_purchase_achievements.py',
            'priority': 3
        },
        'contact-sales-badge': {
            'name': 'HubSpotコンタクトセールスバッジ更新',
            'script': 'scripts/update_contact_sales_badge.py',
            'priority': 2
        },
        'profit-management': {
            'name': '粗利按分管理データ同期',
            'script': 'scripts/sync_profit_management.py',
            'priority': 4
        }
    }
    
    async def add_job(self, job_key: str) -> Optional[int]:
        """
        キューにジョブを追加
        
        Args:
            job_key: ジョブキー（BATCH_JOBSのキー）
            
        Returns:
            追加されたジョブのID、失敗時はNone
        """
        if job_key not in self.BATCH_JOBS:
            logger.error(f"不明なジョブキー: {job_key}")
            return None
        
        job_info = self.BATCH_JOBS[job_key]
        script_path = job_info['script']
        
        # スクリプトのフルパスを取得
        if os.path.exists('/var/www/mirai-api'):
            full_script_path = f'/var/www/mirai-api/{script_path}'
        else:
            full_script_path = str(PROJECT_ROOT / script_path)
        
        try:
            await db_connection.create_pool()
            if not db_connection.pool:
                logger.error("データベース接続プールが作成されていません")
                return None
            
            async with db_connection.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO batch_job_queue 
                        (job_name, script_path, status, priority)
                        VALUES (%s, %s, 'pending', %s)
                    """, (job_info['name'], full_script_path, job_info['priority']))
                    
                    job_id = cursor.lastrowid
                    await conn.commit()
                    
                    logger.info(f"ジョブをキューに追加しました: {job_info['name']} (ID: {job_id})")
                    return job_id
        except Exception as e:
            logger.error(f"ジョブの追加に失敗しました: {str(e)}", exc_info=True)
            return None
    
    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """
        次の実行待ちジョブを取得してロック（優先度順）
        取得したジョブは自動的にrunningステータスに更新される
        
        Returns:
            ジョブ情報の辞書、ジョブがない場合はNone
        """
        try:
            await db_connection.create_pool()
            if not db_connection.pool:
                logger.error("データベース接続プールが作成されていません")
                return None
            
            async with db_connection.pool.acquire() as conn:
                # トランザクション開始
                await conn.begin()
                try:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        # ジョブを取得してロック（FOR UPDATE）
                        await cursor.execute("""
                            SELECT * FROM batch_job_queue
                            WHERE status = 'pending'
                            ORDER BY priority DESC, created_at ASC
                            LIMIT 1
                            FOR UPDATE
                        """)
                        
                        job = await cursor.fetchone()
                        
                        if job:
                            # 取得したジョブのステータスをrunningに更新
                            await cursor.execute("""
                                UPDATE batch_job_queue
                                SET status = 'running', started_at = NOW()
                                WHERE id = %s
                            """, (job['id'],))
                            await conn.commit()
                        else:
                            await conn.commit()
                        
                        return job
                except Exception as e:
                    await conn.rollback()
                    raise
        except Exception as e:
            logger.error(f"ジョブの取得に失敗しました: {str(e)}", exc_info=True)
            return None
    
    async def is_job_stopped(self, job_id: int) -> bool:
        """
        ジョブが停止されているかチェック
        
        Args:
            job_id: ジョブID
            
        Returns:
            停止されている場合True、実行中の場合False
        """
        try:
            await db_connection.create_pool()
            if not db_connection.pool:
                return False
            
            async with db_connection.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT status, stop_requested FROM batch_job_queue
                        WHERE id = %s
                    """, (job_id,))
                    
                    job = await cursor.fetchone()
                    if job:
                        # stop_requestedフラグがTrueの場合、またはstatusがrunning以外の場合
                        if job.get('stop_requested', False) or job.get('status') != 'running':
                            return True
                    return False
        except Exception as e:
            logger.error(f"ジョブ停止チェックに失敗しました: {str(e)}", exc_info=True)
            return False
    
    async def request_stop(self, job_id: int) -> bool:
        """
        ジョブの停止を要求
        
        Args:
            job_id: ジョブID
            
        Returns:
            成功時True、失敗時False
        """
        try:
            await db_connection.create_pool()
            if not db_connection.pool:
                logger.error("データベース接続プールが作成されていません")
                return False
            
            async with db_connection.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        UPDATE batch_job_queue
                        SET stop_requested = TRUE
                        WHERE id = %s
                    """, (job_id,))
                    
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"ジョブ停止要求の設定に失敗しました: {str(e)}", exc_info=True)
            return False
    
    async def update_job_status(
        self, 
        job_id: int, 
        status: str, 
        error_message: Optional[str] = None
    ) -> bool:
        """
        ジョブのステータスを更新
        
        Args:
            job_id: ジョブID
            status: 新しいステータス
            error_message: エラーメッセージ（エラー時）
            
        Returns:
            成功時True、失敗時False
        """
        try:
            await db_connection.create_pool()
            if not db_connection.pool:
                logger.error("データベース接続プールが作成されていません")
                return False
            
            async with db_connection.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    if status == 'running':
                        await cursor.execute("""
                            UPDATE batch_job_queue
                            SET status = %s, started_at = NOW()
                            WHERE id = %s
                        """, (status, job_id))
                    elif status in ('completed', 'failed'):
                        await cursor.execute("""
                            UPDATE batch_job_queue
                            SET status = %s, completed_at = NOW(), error_message = %s
                            WHERE id = %s
                        """, (status, error_message, job_id))
                    else:
                        await cursor.execute("""
                            UPDATE batch_job_queue
                            SET status = %s
                            WHERE id = %s
                        """, (status, job_id))
                    
                    await conn.commit()
                    return True
        except Exception as e:
            logger.error(f"ジョブステータスの更新に失敗しました: {str(e)}", exc_info=True)
            return False
    

