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
                # 進捗を100%に更新してからステータスを完了に更新
                await self.queue.update_job_progress(job_id, "完了", 100)
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
    
    async def run_script_with_stop_check(self, script_path: str, job_id: int, timeout: int = 3600) -> Dict[str, Any]:
        """
        スクリプトを実行（停止チェック付き、タイムアウト付き）
        
        Args:
            script_path: 実行するスクリプトのパス
            job_id: ジョブID（停止チェック用）
            timeout: タイムアウト時間（秒、デフォルト1時間）
            
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
            
            # 非同期でスクリプトを実行（環境変数にジョブIDを設定、バッファリングを無効化）
            env = os.environ.copy()
            env['BATCH_JOB_ID'] = str(job_id)
            env['PYTHONUNBUFFERED'] = '1'  # Pythonの出力バッファリングを無効化
            
            # 出力を一時ファイルにリダイレクト（バッファ溢れを防ぐ）
            stdout_file = os.path.join(log_dir, f'batch_job_{job_id}_stdout.log')
            stderr_file = os.path.join(log_dir, f'batch_job_{job_id}_stderr.log')
            
            # ファイルを開く
            stdout_fd = os.open(stdout_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
            stderr_fd = os.open(stderr_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
            
            process = await asyncio.create_subprocess_exec(
                self.python_path,
                '-u',  # バッファリングを無効化
                script_path,
                stdout=stdout_fd,
                stderr=stderr_fd,
                cwd=working_dir,
                env=env,
                pass_fds=[]  # ファイルディスクリプタを継承
            )
            
            # ファイルディスクリプタを閉じる（プロセスが継承するため）
            os.close(stdout_fd)
            os.close(stderr_fd)
            
            logger.info(f"プロセスを開始しました: PID {process.pid} (ジョブID: {job_id})")
            
            # プロセス完了を待機（停止チェック付き、タイムアウト付き）
            stopped = False
            start_time = asyncio.get_event_loop().time()
            
            try:
                # プロセスの完了を待機しながら、定期的に停止チェックとタイムアウトチェックを行う
                # process.communicate()を使用し、別タスクで停止チェックとタイムアウトチェックを実行
                stop_requested = False
                timeout_reached = False
                
                # プロセスの終了を待機するタスク（先に定義）
                wait_task = asyncio.create_task(process.wait())
                
                async def check_stop_and_timeout():
                    """停止チェックとタイムアウトチェックを行うタスク"""
                    nonlocal stop_requested, timeout_reached
                    while True:
                        await asyncio.sleep(2)  # 2秒ごとにチェック
                        
                        # プロセスが既に終了している場合は終了
                        if wait_task.done():
                            return
                        
                        # タイムアウトチェック
                        elapsed_time = asyncio.get_event_loop().time() - start_time
                        if elapsed_time > timeout:
                            logger.warning(f"ジョブがタイムアウトしました (ジョブID: {job_id}, 経過時間: {elapsed_time:.1f}秒)")
                            timeout_reached = True
                            process.terminate()
                            return
                        
                        # ジョブが停止されているかチェック
                        is_stopped = await self.queue.is_job_stopped(job_id)
                        if is_stopped:
                            logger.info(f"ジョブが停止されました。プロセスを終了します: {job_id}")
                            stop_requested = True
                            process.terminate()
                            return
                
                # 停止チェック・タイムアウトチェックのタスクを開始
                check_task = asyncio.create_task(check_stop_and_timeout())
                
                # どちらかが完了するまで待機（プロセス終了または停止/タイムアウト）
                done, pending = await asyncio.wait(
                    [wait_task, check_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 未完了のタスクをキャンセル
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # 停止またはタイムアウトが発生した場合
                if check_task in done:
                    # wait_taskがまだ実行中の場合はキャンセル
                    if wait_task in pending:
                        wait_task.cancel()
                        try:
                            await wait_task
                        except asyncio.CancelledError:
                            pass
                    
                    # プロセスの終了を待機
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"プロセスの終了待ちがタイムアウトしました。強制終了します (ジョブID: {job_id})")
                        process.kill()
                        await process.wait()
                    
                    # ファイルから出力を読み取る
                    stdout = b''
                    stderr = b''
                    try:
                        if os.path.exists(stdout_file):
                            with open(stdout_file, 'rb') as f:
                                stdout = f.read()
                        if os.path.exists(stderr_file):
                            with open(stderr_file, 'rb') as f:
                                stderr = f.read()
                    except Exception as e:
                        logger.warning(f"出力ファイルの読み取りに失敗しました: {str(e)}")
                    
                    if stop_requested:
                        return {
                            'success': False,
                            'error': '手動で停止されました'
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'ジョブがタイムアウトしました (制限時間: {timeout}秒)'
                        }
                
                # プロセスが完了した場合
                returncode = await wait_task
                
                # ファイルから出力を読み取る（少し待機してファイルが完全に書き込まれるのを待つ）
                await asyncio.sleep(0.2)  # 200ms待機してファイルが完全に書き込まれるのを待つ
                stdout = b''
                stderr = b''
                try:
                    if os.path.exists(stdout_file):
                        with open(stdout_file, 'rb') as f:
                            stdout = f.read()
                    if os.path.exists(stderr_file):
                        with open(stderr_file, 'rb') as f:
                            stderr = f.read()
                except Exception as e:
                    logger.warning(f"出力ファイルの読み取りに失敗しました: {str(e)}")
                
                # 一時ファイルを削除（オプション）
                try:
                    if os.path.exists(stdout_file):
                        os.remove(stdout_file)
                    if os.path.exists(stderr_file):
                        os.remove(stderr_file)
                except Exception:
                    pass  # 削除に失敗しても問題ない
                
                elapsed_time = asyncio.get_event_loop().time() - start_time
                
                # 停止が要求された場合
                if stop_requested:
                    return {
                        'success': False,
                        'error': '手動で停止されました'
                    }
                
                # タイムアウトが発生した場合
                if timeout_reached:
                    return {
                        'success': False,
                        'error': f'ジョブがタイムアウトしました (制限時間: {timeout}秒)'
                    }
                
                # 出力をログに記録（デバッグ用）
                if stdout:
                    stdout_text = stdout.decode('utf-8', errors='replace')
                    if stdout_text.strip():
                        logger.info(f"ジョブの標準出力 (ジョブID: {job_id}):\n{stdout_text}")
                
                if stderr:
                    stderr_text = stderr.decode('utf-8', errors='replace')
                    if stderr_text.strip():
                        logger.warning(f"ジョブの標準エラー出力 (ジョブID: {job_id}):\n{stderr_text}")
                
                if returncode == 0:
                    logger.info(f"ジョブが正常に完了しました (ジョブID: {job_id}, 経過時間: {elapsed_time:.1f}秒)")
                    return {'success': True}
                else:
                    error_output = stderr.decode('utf-8', errors='replace') if stderr else 'Unknown error'
                    logger.error(f"ジョブの実行に失敗しました (ジョブID: {job_id}, 終了コード: {returncode}): {error_output}")
                    # stdoutにもエラー情報がある可能性がある
                    if stdout:
                        stdout_text = stdout.decode('utf-8', errors='replace')
                        if stdout_text.strip():
                            error_output += f"\n標準出力: {stdout_text}"
                    return {
                        'success': False,
                        'error': error_output
                    }
            except asyncio.CancelledError:
                logger.warning(f"ジョブの実行がキャンセルされました (ジョブID: {job_id})")
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                return {
                    'success': False,
                    'error': 'ジョブがキャンセルされました'
                }
        except Exception as e:
            logger.error(f"ジョブの実行中にエラーが発生しました (ジョブID: {job_id}): {str(e)}", exc_info=True)
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

