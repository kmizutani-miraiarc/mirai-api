#!/usr/bin/env python3
"""
すべてのバッチジョブをキューに追加するスクリプト
systemdタイマーから毎日午前2時に呼び出される
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.batch_job_queue import BatchJobQueue

async def main():
    """メイン処理"""
    queue = BatchJobQueue()
    today = datetime.now()
    
    # 毎日実行するジョブ
    daily_jobs = [
        'purchase-achievements',
        'contact-sales-badge',
        'profit-management',
        'property-sales-stage-summary',
        'purchase-summary',
        'sales-summary'
    ]
    
    # 毎週月曜日に実行するジョブ
    weekly_jobs = [
        'contact-phase-summary',
        'contact-scoring-summary'
    ]
    
    # 毎月1日に実行するジョブ
    monthly_jobs = [
        'contact-phase-summary-monthly'
    ]
    
    added_jobs = []
    
    # 毎日実行するジョブを追加
    for job_key in daily_jobs:
        job_id = await queue.add_job(job_key)
        if job_id:
            added_jobs.append(job_key)
            print(f"ジョブをキューに追加しました: {job_key} (ID: {job_id})")
    
    # 毎週月曜日に実行するジョブを追加
    if today.weekday() == 0:  # 月曜日は0
        for job_key in weekly_jobs:
            job_id = await queue.add_job(job_key)
            if job_id:
                added_jobs.append(job_key)
                print(f"ジョブをキューに追加しました: {job_key} (ID: {job_id})")
    
    # 毎月1日に実行するジョブを追加
    if today.day == 1:
        for job_key in monthly_jobs:
            job_id = await queue.add_job(job_key)
            if job_id:
                added_jobs.append(job_key)
                print(f"ジョブをキューに追加しました: {job_key} (ID: {job_id})")
    
    print(f"合計 {len(added_jobs)} 個のジョブをキューに追加しました")
    
    if len(added_jobs) > 0:
        sys.exit(0)
    else:
        print("追加するジョブがありませんでした")
        sys.exit(0)

if __name__ == '__main__':
    asyncio.run(main())

