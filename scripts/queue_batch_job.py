#!/usr/bin/env python3
"""
バッチジョブをキューに追加するスクリプト
systemdタイマーから呼び出される
"""
import asyncio
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.batch_job_queue import BatchJobQueue

async def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("Usage: python queue_batch_job.py <job_key>")
        print("Available job keys:")
        for key, info in BatchJobQueue.BATCH_JOBS.items():
            print(f"  {key}: {info['name']}")
        sys.exit(1)
    
    job_key = sys.argv[1]
    queue = BatchJobQueue()
    
    job_id = await queue.add_job(job_key, max_retries=0)
    
    if job_id:
        print(f"ジョブをキューに追加しました: {job_key} (ID: {job_id})")
        sys.exit(0)
    else:
        print(f"ジョブの追加に失敗しました: {job_key}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())

