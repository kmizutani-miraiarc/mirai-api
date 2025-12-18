#!/usr/bin/env python3
"""
バッチジョブキューからジョブを順次実行するワーカープロセス
常時起動してキューを監視し、ジョブを順次実行する
"""
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.batch_job_queue import BatchJobQueue

# ログ設定
if os.path.exists('/var/www/mirai-api/logs'):
    log_dir = '/var/www/mirai-api/logs'
else:
    log_dir = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'batch_job_worker.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BatchJobWorker:
    """バッチジョブワーカー"""
    
    def __init__(self, poll_interval: int = 10):
        """
        初期化
        
        Args:
            poll_interval: キューをチェックする間隔（秒）
        """
        self.poll_interval = poll_interval
        self.queue = BatchJobQueue()
        self.running = False
        
        # Python実行パスを取得
        if os.path.exists('/var/www/mirai-api/venv/bin/python3'):
            self.python_path = '/var/www/mirai-api/venv/bin/python3'
        else:
            self.python_path = sys.executable
    
    async def start(self):
        """ワーカーを開始"""
        self.running = True
        logger.info("バッチジョブワーカーを開始しました")
        
        while self.running:
            try:
                job = await self.queue.get_next_job()
                
                if job:
                    await self.process_job(job)
                else:
                    # ジョブがない場合は待機
                    await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"ワーカーの実行中にエラーが発生しました: {str(e)}", exc_info=True)
                await asyncio.sleep(self.poll_interval)
    
    def stop(self):
        """ワーカーを停止"""
        self.running = False
        logger.info("バッチジョブワーカーを停止しました")
    
    async def process_job(self, job: Dict[str, Any]):
        """
        ジョブを処理
        
        Args:
            job: ジョブ情報の辞書
        """
        job_id = job['id']
        job_name = job['job_name']
        script_path = job['script_path']
        
        logger.info(f"ジョブを開始します: {job_name} (ID: {job_id})")
        
        # 注意: get_next_job()で既にrunningステータスに更新されている
        
        try:
            # スクリプトを実行（停止チェック付き）
            result = await self.run_script_with_stop_check(script_path, job_id)
            
            # ジョブが停止されたかチェック
            is_stopped = await self.queue.is_job_stopped(job_id)
            if is_stopped:
                logger.info(f"ジョブが停止されました: {job_name} (ID: {job_id})")
                return
            
            if result['success']:
                logger.info(f"ジョブが正常に完了しました: {job_name} (ID: {job_id})")
                await self.queue.update_job_status(job_id, 'completed')
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"ジョブの実行に失敗しました: {job_name} (ID: {job_id}) - {error_msg}")
                
                # リトライ可能かチェック
                if job['retry_count'] < job['max_retries']:
                    await self.queue.increment_retry_count(job_id)
                    logger.info(f"ジョブをリトライキューに戻しました: {job_name} (ID: {job_id})")
                else:
                    await self.queue.update_job_status(job_id, 'failed', error_msg)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"ジョブの処理中にエラーが発生しました: {job_name} (ID: {job_id}) - {error_msg}", exc_info=True)
            
            # リトライ可能かチェック
            if job['retry_count'] < job['max_retries']:
                await self.queue.increment_retry_count(job_id)
                logger.info(f"ジョブをリトライキューに戻しました: {job_name} (ID: {job_id})")
            else:
                await self.queue.update_job_status(job_id, 'failed', error_msg)
    
    async def run_script(self, script_path: str) -> Dict[str, Any]:
        """
        スクリプトを実行
        
        Args:
            script_path: 実行するスクリプトのパス
            
        Returns:
            実行結果の辞書 {'success': bool, 'error': str}
        """
        try:
            # スクリプトが存在するか確認
            if not os.path.exists(script_path):
                return {
                    'success': False,
                    'error': f'Script not found: {script_path}'
                }
            
            # 作業ディレクトリを決定
            if os.path.exists('/var/www/mirai-api'):
                working_dir = '/var/www/mirai-api'
            else:
                working_dir = str(PROJECT_ROOT)
            
            # 非同期でスクリプトを実行
            process = await asyncio.create_subprocess_exec(
                self.python_path,
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {'success': True}
            else:
                error_output = stderr.decode('utf-8') if stderr else 'Unknown error'
                return {
                    'success': False,
                    'error': error_output
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run_script_with_stop_check(self, script_path: str, job_id: int) -> Dict[str, Any]:
        """
        スクリプトを実行（停止チェック付き）
        
        Args:
            script_path: 実行するスクリプトのパス
            job_id: ジョブID（停止チェック用）
            
        Returns:
            実行結果の辞書 {'success': bool, 'error': str}
        """
        try:
            # スクリプトが存在するか確認
            if not os.path.exists(script_path):
                return {
                    'success': False,
                    'error': f'Script not found: {script_path}'
                }
            
            # 作業ディレクトリを決定
            if os.path.exists('/var/www/mirai-api'):
                working_dir = '/var/www/mirai-api'
            else:
                working_dir = str(PROJECT_ROOT)
            
            # 非同期でスクリプトを実行
            process = await asyncio.create_subprocess_exec(
                self.python_path,
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            # プロセス完了を待機（停止チェック付き）
            stopped = False
            while process.returncode is None:
                # ジョブが停止されているかチェック
                is_stopped = await self.queue.is_job_stopped(job_id)
                if is_stopped:
                    logger.info(f"ジョブが停止されました。プロセスを終了します: {job_id}")
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                    stopped = True
                    break
                
                # 少し待機してから再チェック
                await asyncio.sleep(2)
                if process.returncode is None:
                    # プロセスがまだ実行中の場合は継続
                    continue
                else:
                    break
            
            if stopped:
                return {
                    'success': False,
                    'error': '手動で停止されました'
                }
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return {'success': True}
            else:
                error_output = stderr.decode('utf-8') if stderr else 'Unknown error'
                return {
                    'success': False,
                    'error': error_output
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


async def main():
    """メイン処理"""
    worker = BatchJobWorker(poll_interval=10)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("停止シグナルを受信しました")
        worker.stop()
    except Exception as e:
        logger.error(f"ワーカーの実行中にエラーが発生しました: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

