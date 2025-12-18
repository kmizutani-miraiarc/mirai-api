# バッチジョブのトラブルシューティングガイド

## 手動実行では正常だが、ジョブワーカー経由で止まる場合

### 1. プロセスの状態を確認

```bash
# 実行中のバッチ処理プロセスを確認
ps aux | grep sync_profit_management
ps aux | grep batch_job_worker

# プロセスの詳細情報を確認（PIDを指定）
ps -fp <PID>

# プロセスのリソース使用状況を確認
top -p <PID>
htop -p <PID>

# プロセスのファイルディスクリプタ数を確認
ls -l /proc/<PID>/fd | wc -l

# プロセスのメモリ使用量を確認
cat /proc/<PID>/status | grep -E "VmSize|VmRSS|VmPeak"
```

### 2. システムリソースを確認

```bash
# メモリ使用量を確認
free -h

# ファイルディスクリプタの制限を確認
ulimit -n

# システム全体のファイルディスクリプタ使用状況を確認
lsof | wc -l

# CPU使用率を確認
top
htop

# ディスクI/Oを確認
iostat -x 1

# ネットワーク接続数を確認
netstat -an | wc -l
ss -s
```

### 3. ログを確認

```bash
# ワーカーのログを確認
tail -f /var/www/mirai-api/logs/batch_job_worker.log

# スクリプトのログを確認
tail -f /var/www/mirai-api/logs/profit_management_sync.log

# systemdのログを確認
sudo journalctl -u batch-job-queue-worker -f

# 特定のジョブIDのログを検索
grep "ジョブID: <job_id>" /var/www/mirai-api/logs/batch_job_worker.log

# エラーログを検索
grep -i error /var/www/mirai-api/logs/batch_job_worker.log | tail -20
grep -i error /var/www/mirai-api/logs/profit_management_sync.log | tail -20
```

### 4. プロセスのトレース（strace）

```bash
# 実行中のプロセスをトレース（PIDを指定）
sudo strace -p <PID> -f -e trace=all -o /tmp/strace_output.txt

# 新しいプロセスをトレース（ジョブをキューに追加してから実行）
sudo strace -f -e trace=network,file,process -o /tmp/strace_batch.txt \
  /var/www/mirai-api/venv/bin/python3 /var/www/mirai-api/scripts/sync_profit_management.py
```

### 5. データベース接続の状態を確認

```bash
# MySQLに接続
mysql -u root -p mirai_base

# 実行中のクエリを確認
SHOW PROCESSLIST;

# 接続数を確認
SHOW STATUS LIKE 'Threads_connected';
SHOW STATUS LIKE 'Max_used_connections';

# ロックを確認
SHOW ENGINE INNODB STATUS\G

# 特定のテーブルのロックを確認
SELECT * FROM information_schema.INNODB_LOCKS;
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
```

### 6. 環境変数の違いを確認

```bash
# ワーカープロセスの環境変数を確認
sudo cat /proc/$(pgrep -f batch_job_worker)/environ | tr '\0' '\n'

# 手動実行時の環境変数を確認
env | sort

# 環境変数の違いを比較
diff <(sudo cat /proc/$(pgrep -f batch_job_worker)/environ | tr '\0' '\n' | sort) \
     <(env | sort)
```

### 7. ファイルシステムの状態を確認

```bash
# ディスク使用量を確認
df -h

# inode使用量を確認
df -i

# ログディレクトリの状態を確認
ls -lh /var/www/mirai-api/logs/
du -sh /var/www/mirai-api/logs/

# ファイルの権限を確認
ls -la /var/www/mirai-api/scripts/sync_profit_management.py
```

### 8. ネットワーク接続を確認

```bash
# プロセスのネットワーク接続を確認
sudo netstat -anp | grep <PID>
sudo ss -anp | grep <PID>

# HubSpot APIへの接続を確認
sudo tcpdump -i any -n host api.hubapi.com -w /tmp/hubspot_traffic.pcap
```

### 9. メモリダンプを取得（デバッグ用）

```bash
# プロセスのメモリマップを確認
cat /proc/<PID>/maps

# コアダンプを有効化（必要に応じて）
ulimit -c unlimited
echo '/tmp/core.%e.%p' | sudo tee /proc/sys/kernel/core_pattern
```

### 10. ジョブキューの状態を確認

```bash
# MySQLに接続してジョブキューの状態を確認
mysql -u root -p mirai_base

# 実行中のジョブを確認
SELECT * FROM batch_job_queue WHERE status = 'running' ORDER BY started_at DESC;

# 失敗したジョブを確認
SELECT * FROM batch_job_queue WHERE status = 'failed' ORDER BY completed_at DESC LIMIT 10;

# 特定の物件名で止まっているジョブを確認
SELECT * FROM batch_job_queue WHERE status = 'running' AND progress_message LIKE '%第六竹石%';
```

## 手動実行とジョブワーカー経由の主な違い

### 環境変数

| 項目 | 手動実行 | ジョブワーカー経由 |
|------|----------|-------------------|
| `BATCH_JOB_ID` | 設定されない | 自動設定される |
| `PYTHONUNBUFFERED` | 設定されない（`-u`フラグを使用する場合のみ） | `1`が設定される |
| その他の環境変数 | シェルの環境変数を継承 | ワーカープロセスの環境変数を継承 |

### プロセスの実行方法

| 項目 | 手動実行 | ジョブワーカー経由 |
|------|----------|-------------------|
| 実行方法 | 直接実行 | サブプロセスとして実行 |
| stdout/stderr | 端末に直接出力 | PIPE経由でキャプチャ |
| シグナルハンドリング | シェルが管理 | ワーカープロセスが管理 |

### systemdのセキュリティ設定

ジョブワーカーは以下のsystemdセキュリティ設定の影響を受けます：

- `ProtectSystem=strict`: システムディレクトリへの書き込みを禁止
- `ProtectHome=true`: ホームディレクトリへのアクセスを禁止
- `PrivateTmp=true`: プライベートな/tmpディレクトリを使用
- `ReadWritePaths`: 書き込み可能なパスのみ指定

### データベース接続プール

| 項目 | 手動実行 | ジョブワーカー経由 |
|------|----------|-------------------|
| 接続プール | 新規作成 | 既存のプールを使用する可能性がある |
| 接続の共有 | なし | ワーカープロセスと共有される可能性がある |

## よくある問題と解決方法

### 1. メモリ不足

**症状**: プロセスが突然終了する、またはOOM Killerに殺される

**確認方法**:
```bash
dmesg | grep -i "out of memory"
grep -i "killed process" /var/log/syslog
```

**解決方法**:
- メモリ使用量を減らす（バッチサイズを小さくする）
- サーバーのメモリを増やす
- スワップを有効化する

### 2. ファイルディスクリプタ不足

**症状**: `Too many open files`エラー

**確認方法**:
```bash
ulimit -n
lsof | wc -l
```

**解決方法**:
```bash
# systemdサービスのファイルディスクリプタ制限を増やす
sudo systemctl edit batch-job-queue-worker.service
# 以下を追加:
[Service]
LimitNOFILE=65536
```

### 3. データベース接続のタイムアウト

**症状**: データベース操作でタイムアウトが発生する

**確認方法**:
```bash
mysql -u root -p -e "SHOW VARIABLES LIKE '%timeout%';"
```

**解決方法**:
- MySQLの`wait_timeout`と`interactive_timeout`を増やす
- データベース接続プールの設定を調整する

### 4. ログファイルのサイズが大きすぎる

**症状**: ディスク容量不足、ログ書き込みが遅い

**確認方法**:
```bash
du -sh /var/www/mirai-api/logs/*
ls -lh /var/www/mirai-api/logs/
```

**解決方法**:
- ログローテーションを設定する
- 古いログを削除する
- ログレベルを調整する（DEBUGログを減らす）

## デバッグ用の追加ログ

問題を特定するために、以下のログを追加できます：

```python
# プロセスのリソース使用状況をログに記録
import resource
import psutil
import os

# メモリ使用量
process = psutil.Process(os.getpid())
mem_info = process.memory_info()
logger.info(f"メモリ使用量: RSS={mem_info.rss / 1024 / 1024:.2f}MB, VMS={mem_info.vms / 1024 / 1024:.2f}MB")

# ファイルディスクリプタ数
fd_count = len(os.listdir(f'/proc/{os.getpid()}/fd'))
logger.info(f"ファイルディスクリプタ数: {fd_count}")

# データベース接続数
logger.info(f"データベース接続プールサイズ: {db_connection.pool.size if db_connection.pool else 0}")
```

