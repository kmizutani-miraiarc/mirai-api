# バッチジョブキュー処理フロー

## ジョブキュー経由の処理フロー

### 1. ジョブの追加
- **systemdタイマー経由**: 各バッチ処理のsystemdタイマーが午前2時に`queue_batch_job.py`を実行
- **API経由**: `/batch-jobs/queue`エンドポイントを呼び出し
- **管理画面経由**: 開発メニューの「バッチ処理」画面から手動でキューに追加

ジョブは`batch_job_queue`テーブルに`pending`ステータスで登録されます。

### 2. ワーカープロセスの動作
- **常時起動**: `batch-job-queue-worker.service`が常時起動している
- **キュー監視**: 10秒ごとに`batch_job_queue`テーブルをチェック
- **ジョブ取得**: `get_next_job()`で`pending`ステータスのジョブを優先度順に取得
  - 取得時にステータスを`running`に更新（`FOR UPDATE`で排他制御）

### 3. ジョブの実行
ワーカーは以下の手順でジョブを実行します：

1. **環境変数の設定**
   - `BATCH_JOB_ID`: ジョブID（進捗更新用）
   - `PYTHONUNBUFFERED=1`: Pythonの出力バッファリングを無効化

2. **スクリプトの実行**
   - サブプロセスとして実行（`asyncio.create_subprocess_exec`）
   - `-u`フラグでPythonのバッファリングを無効化
   - 標準出力・標準エラー出力をキャプチャ

3. **監視機能**
   - **タイムアウト**: デフォルト1時間（3600秒）
   - **停止チェック**: 2秒ごとに`stop_requested`フラグをチェック
   - **プロセス管理**: `process.communicate()`でプロセスの完了を待機

4. **完了処理**
   - 成功時: ステータスを`completed`に更新
   - 失敗時: リトライ可能なら`pending`に戻し、不可能なら`failed`に更新

### 4. 進捗更新（オプション）
バッチ処理スクリプト内で`update_job_progress()`を呼び出すことで、進捗を更新できます：
- `progress_message`: 進捗メッセージ
- `progress_percentage`: 進捗パーセンテージ（0-100）

## 手動実行との違い

### ジョブキュー経由の場合

| 項目 | 詳細 |
|------|------|
| **実行方法** | ワーカープロセスがサブプロセスとして実行 |
| **環境変数** | `BATCH_JOB_ID`が自動設定される |
| **進捗更新** | `BATCH_JOB_ID`を使用して進捗を更新可能 |
| **タイムアウト** | デフォルト1時間（設定可能） |
| **停止機能** | 管理画面から実行中のジョブを停止可能 |
| **リトライ機能** | 失敗時に自動リトライ（設定可能） |
| **ログ** | ワーカーのログ（`batch_job_worker.log`）とスクリプトのログに分かれる |
| **並行実行** | 1つのワーカーが1つのジョブを順次実行（キュー管理） |
| **ステータス管理** | データベースでステータスを管理（pending/running/completed/failed/stopped） |
| **出力バッファリング** | 無効化（`-u`フラグ + `PYTHONUNBUFFERED=1`） |

### 手動実行の場合

| 項目 | 詳細 |
|------|------|
| **実行方法** | 直接スクリプトを実行（`python3 scripts/sync_profit_management.py`） |
| **環境変数** | `BATCH_JOB_ID`は設定されない |
| **進捗更新** | 進捗更新機能は使用できない（`BATCH_JOB_ID`がないため） |
| **タイムアウト** | なし（プロセスが終了するまで実行） |
| **停止機能** | `Ctrl+C`で手動停止 |
| **リトライ機能** | なし（手動で再実行が必要） |
| **ログ** | スクリプトのログのみ（例: `profit_management_sync.log`） |
| **並行実行** | 複数のスクリプトを同時実行可能（制御なし） |
| **ステータス管理** | なし |
| **出力バッファリング** | 通常のバッファリング（`-u`フラグを指定しない限り） |

## 処理フロー図

```
[systemdタイマー] または [API/管理画面]
        ↓
[queue_batch_job.py]
        ↓
[batch_job_queue テーブル]
  ステータス: pending
        ↓
[ワーカープロセス] (10秒ごとにチェック)
        ↓
[get_next_job()] → ステータス: running
        ↓
[process_job()]
        ↓
[run_script_with_stop_check()]
  環境変数設定:
  - BATCH_JOB_ID
  - PYTHONUNBUFFERED=1
        ↓
[サブプロセス実行]
  python3 -u scripts/sync_profit_management.py
        ↓
[監視]
  - タイムアウトチェック（1時間）
  - 停止チェック（2秒ごと）
        ↓
[完了]
  成功 → ステータス: completed
  失敗 → ステータス: failed または pending（リトライ）
```

## ログの確認方法

### 1. ワーカーのログファイル
ワーカープロセスのログは以下のファイルに出力されます：

```bash
# ログファイルの場所
/var/www/mirai-api/logs/batch_job_worker.log

# リアルタイムでログを確認
tail -f /var/www/mirai-api/logs/batch_job_worker.log

# 最新の100行を表示
tail -n 100 /var/www/mirai-api/logs/batch_job_worker.log

# エラーのみを検索
grep -i error /var/www/mirai-api/logs/batch_job_worker.log
```

### 2. systemdのjournalログ
systemdサービスとして実行されているため、journalctlでも確認できます：

```bash
# リアルタイムでログを確認
sudo journalctl -u batch-job-queue-worker -f

# 最新の100行を表示
sudo journalctl -u batch-job-queue-worker -n 100

# 今日のログを表示
sudo journalctl -u batch-job-queue-worker --since today

# 特定の時間範囲のログを表示
sudo journalctl -u batch-job-queue-worker --since "2025-12-18 22:00:00" --until "2025-12-18 23:00:00"

# エラーのみを表示
sudo journalctl -u batch-job-queue-worker -p err
```

### 3. 各バッチ処理スクリプトのログ
各バッチ処理スクリプトは独自のログファイルに出力します：

| バッチ処理 | ログファイル |
|-----------|------------|
| 粗利按分管理データ同期 | `/var/www/mirai-api/logs/profit_management_sync.log` |
| 物件買取実績同期 | `/var/www/mirai-api/logs/purchase_achievements_sync.log` |
| 週次フェーズ集計 | `/var/www/mirai-api/logs/contact_phase_summary.log` |
| 月次フェーズ集計 | `/var/www/mirai-api/logs/contact_phase_summary_monthly.log` |
| コンタクトスコアリング集計 | `/var/www/mirai-api/logs/contact_scoring_summary.log` |
| HubSpotコンタクトセールスバッジ更新 | `/var/www/mirai-api/logs/contact_sales_badge.log` |

```bash
# 例: 粗利按分管理データ同期のログを確認
tail -f /var/www/mirai-api/logs/profit_management_sync.log

# 最新の100行を表示
tail -n 100 /var/www/mirai-api/logs/profit_management_sync.log
```

### 4. ワーカーがキャプチャしたスクリプトの出力
ワーカーは実行したスクリプトの標準出力・標準エラー出力をキャプチャし、ワーカーのログに記録します：

```bash
# 特定のジョブIDの出力を確認
grep "ジョブID: 123" /var/www/mirai-api/logs/batch_job_worker.log

# 標準出力を確認
grep "ジョブの標準出力" /var/www/mirai-api/logs/batch_job_worker.log

# 標準エラー出力を確認
grep "ジョブの標準エラー出力" /var/www/mirai-api/logs/batch_job_worker.log
```

### 5. ログの確認コマンド例

```bash
# ワーカーの状態を確認
sudo systemctl status batch-job-queue-worker

# ワーカーのログをリアルタイムで確認
sudo journalctl -u batch-job-queue-worker -f

# 特定のジョブの実行ログを確認（ジョブID: 123の場合）
grep -A 50 "ジョブID: 123" /var/www/mirai-api/logs/batch_job_worker.log

# エラーが発生したジョブを確認
grep -B 5 -A 20 "ジョブの実行に失敗しました" /var/www/mirai-api/logs/batch_job_worker.log

# タイムアウトしたジョブを確認
grep "タイムアウト" /var/www/mirai-api/logs/batch_job_worker.log
```

## トラブルシューティング

### ジョブが途中で止まる場合
1. **ログを確認**
   - ワーカーのログ: `/var/www/mirai-api/logs/batch_job_worker.log`
   - スクリプトのログ: `/var/www/mirai-api/logs/profit_management_sync.log`など
   - systemdのログ: `sudo journalctl -u batch-job-queue-worker -f`

2. **プロセス状態を確認**
   ```bash
   sudo systemctl status batch-job-queue-worker
   sudo journalctl -u batch-job-queue-worker -f
   ```

3. **データベースの状態を確認**
   ```sql
   SELECT * FROM batch_job_queue WHERE status = 'running' ORDER BY started_at DESC;
   SELECT * FROM batch_job_queue WHERE status = 'failed' ORDER BY completed_at DESC LIMIT 10;
   ```

4. **実行中のプロセスを確認**
   ```bash
   ps aux | grep batch_job_worker
   ps aux | grep sync_profit_management
   ```

### 手動実行で動作するが、キュー経由で動作しない場合
- 環境変数`BATCH_JOB_ID`の有無による動作の違いを確認
- ワーカーのログでエラーメッセージを確認
- プロセスの権限を確認（ワーカーは`root`ユーザーで実行）

