# 粗利按分管理データ同期バッチのデバッグ方法

## 問題の確認手順

### 1. APIエンドポイントが正しく呼び出されているか確認

```bash
# APIログを確認
docker-compose logs -f mirai-api | grep -i "profit.*sync\|バッチ処理"

# または、コンテナ内でログを確認
docker-compose exec mirai-api tail -f /app/logs/profit_management_sync.log
```

### 2. バッチスクリプトが存在するか確認

```bash
# コンテナ内で確認
docker-compose exec mirai-api ls -la /app/scripts/sync_profit_management.py

# ファイルの内容を確認
docker-compose exec mirai-api head -20 /app/scripts/sync_profit_management.py
```

### 3. ログディレクトリが存在するか確認

```bash
# コンテナ内で確認
docker-compose exec mirai-api ls -la /app/logs/

# ログファイルが作成されているか確認
docker-compose exec mirai-api ls -la /app/logs/profit_management_sync.log
```

### 4. 手動でバッチスクリプトを実行してテスト

```bash
# コンテナ内で直接実行
docker-compose exec mirai-api python3 /app/scripts/sync_profit_management.py
```

### 5. APIエンドポイントを直接テスト

```bash
# curlでAPIエンドポイントを呼び出し
curl -X POST http://localhost:8000/profit-management/sync \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json"
```

### 6. エラーログを確認

```bash
# すべてのエラーログを確認
docker-compose logs mirai-api | grep -i error

# バッチ処理関連のエラーのみ
docker-compose logs mirai-api | grep -i "profit.*sync\|バッチ処理" | grep -i error
```

## よくある問題と解決方法

### 問題1: ログディレクトリが存在しない

**症状**: ログファイルが作成されない

**解決方法**:
```bash
# コンテナ内でログディレクトリを作成
docker-compose exec mirai-api mkdir -p /app/logs
docker-compose exec mirai-api chmod 755 /app/logs
```

### 問題2: インポートエラー

**症状**: `ImportError` が発生する

**解決方法**:
```bash
# コンテナ内でPythonパスを確認
docker-compose exec mirai-api python3 -c "import sys; print(sys.path)"

# スクリプトのインポートをテスト
docker-compose exec mirai-api python3 -c "from scripts.sync_profit_management import ProfitManagementSync; print('OK')"
```

### 問題3: バックグラウンドタスクが実行されない

**症状**: APIは成功を返すが、バッチ処理が実行されない

**解決方法**:
- APIログでバックグラウンドタスクの作成を確認
- エラーハンドリングが正しく動作しているか確認

### 問題4: HubSpot API接続エラー

**症状**: HubSpot APIへの接続に失敗する

**解決方法**:
```bash
# 環境変数を確認
docker-compose exec mirai-api env | grep HUBSPOT

# HubSpot設定を確認
docker-compose exec mirai-api python3 -c "from hubspot.config import Config; print(Config.validate_config())"
```

## デバッグ用コマンド集

```bash
# 1. コンテナの状態確認
docker-compose ps

# 2. APIログのリアルタイム監視
docker-compose logs -f mirai-api

# 3. バッチ処理のログをリアルタイム監視
docker-compose exec mirai-api tail -f /app/logs/profit_management_sync.log

# 4. コンテナ内でシェルを起動
docker-compose exec mirai-api bash

# 5. Python環境を確認
docker-compose exec mirai-api python3 --version
docker-compose exec mirai-api pip list | grep -i hubspot

# 6. データベース接続を確認
docker-compose exec mirai-api python3 -c "from database.connection import db_connection; import asyncio; asyncio.run(db_connection.test_connection())"
```



