# 物件買取実績機能 デプロイガイド

## 概要

このガイドでは、物件買取実績機能を本番環境にデプロイする手順を説明します。

## デプロイ前の確認事項

### 1. 環境変数の確認

本番環境の `.env` ファイルに以下の設定が含まれているか確認してください：

```bash
MYSQL_HOST=your-production-db-host
MYSQL_PORT=3306
MYSQL_USER=your-db-user
MYSQL_PASSWORD=your-db-password
MYSQL_DATABASE=mirai_base
MYSQL_CHARSET=utf8mb4
```

### 2. データベースバックアップ

デプロイ前にデータベースのバックアップを取得してください：

```bash
# バックアップを取得
mysqldump -u root -p mirai_base > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 3. コードのデプロイ

```bash
# リポジトリから最新のコードを取得
cd /var/www/mirai-api
git pull origin main

# 依存関係の更新
source venv/bin/activate
pip install -r requirements.txt
```

## デプロイ手順

### ステップ1: データベーステーブルの作成

#### 方法1: 検証スクリプトを使用（推奨）

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/verify_purchase_achievements_setup.py
```

#### 方法2: SQLスクリプトを使用

```bash
mysql -u your-user -p mirai_base < database/create_purchase_achievements_table.sql
```

#### 方法3: 自動セットアップスクリプトを使用

```bash
cd /var/www/mirai-api
./scripts/setup_purchase_achievements.sh
```

### ステップ2: テーブルの確認

```bash
# MySQLに接続
mysql -u your-user -p mirai_base

# テーブルの存在確認
SHOW TABLES LIKE 'purchase_achievements';

# テーブル構造の確認
DESCRIBE purchase_achievements;
```

### ステップ3: APIサーバーの再起動

```bash
# APIサーバーを再起動
sudo systemctl restart mirai-api

# ステータス確認
sudo systemctl status mirai-api

# ログ確認
sudo journalctl -u mirai-api -f
```

### ステップ4: APIエンドポイントの確認

```bash
# ヘルスチェック
curl http://localhost:8000/health

# API情報の確認
curl http://localhost:8000/api/info | grep purchase-achievements
```

### ステップ5: 動作確認

```bash
# テストスクリプトの実行
cd /var/www/mirai-api
source venv/bin/activate
API_KEY=your-api-key API_BASE_URL=http://localhost:8000 \
  python3 scripts/test_purchase_achievements_api.py
```

## バッチ処理の設定（オプション）

HubSpotからデータを自動取得する場合は、systemdタイマーを設定します：

### 1. サービスファイルのコピー

```bash
sudo cp purchase-achievements-sync.service /etc/systemd/system/
sudo cp purchase-achievements-sync.timer /etc/systemd/system/
```

### 2. サービスの有効化

```bash
# systemdのリロード
sudo systemctl daemon-reload

# タイマーの有効化
sudo systemctl enable purchase-achievements-sync.timer

# タイマーの起動
sudo systemctl start purchase-achievements-sync.timer

# ステータス確認
sudo systemctl status purchase-achievements-sync.timer

# 次の実行時刻を確認
sudo systemctl list-timers purchase-achievements-sync.timer
```

### 3. 手動実行のテスト

```bash
# サービスを手動で実行
sudo systemctl start purchase-achievements-sync.service

# ログを確認
sudo journalctl -u purchase-achievements-sync.service -f
```

## ロールバック手順

問題が発生した場合のロールバック手順：

### 1. APIサーバーのロールバック

```bash
# 前のバージョンに戻す
cd /var/www/mirai-api
git checkout <previous-commit-hash>

# APIサーバーを再起動
sudo systemctl restart mirai-api
```

### 2. データベースのロールバック

```bash
# バックアップから復元
mysql -u root -p mirai_base < backup_YYYYMMDD_HHMMSS.sql
```

### 3. テーブルの削除（必要に応じて）

```bash
# テーブルを削除
mysql -u root -p mirai_base -e "DROP TABLE IF EXISTS purchase_achievements;"
```

## トラブルシューティング

### データベース接続エラー

**症状**: `データベース接続に失敗しました`

**解決方法**:
1. 環境変数を確認: `sudo cat /var/www/mirai-api/.env | grep MYSQL`
2. データベースが起動しているか確認: `sudo systemctl status mysql`
3. ファイアウォール設定を確認
4. データベースユーザーの権限を確認

### テーブルが作成されない

**症状**: `purchase_achievements テーブルが存在しません`

**解決方法**:
1. データベースユーザーに適切な権限があるか確認
2. SQLスクリプトを直接実行してエラーメッセージを確認
3. ログを確認: `sudo journalctl -u mirai-api -f`

### APIエンドポイントが404を返す

**症状**: `404 Not Found`

**解決方法**:
1. `main.py` にルーターが追加されているか確認
2. APIサーバーが再起動されているか確認
3. ルートパスが正しいか確認: `/purchase-achievements`

### パフォーマンスの問題

**症状**: APIレスポンスが遅い

**解決方法**:
1. データベースインデックスを確認
2. クエリの最適化
3. キャッシュの導入を検討

## 監視とメンテナンス

### ログの確認

```bash
# APIサーバーのログ
sudo journalctl -u mirai-api -f

# バッチ処理のログ
sudo journalctl -u purchase-achievements-sync.service -f
tail -f /var/www/mirai-api/logs/purchase_achievements_sync.log
```

### データベースのメンテナンス

```bash
# テーブルの状態確認
mysql -u root -p mirai_base -e "SHOW TABLE STATUS LIKE 'purchase_achievements';"

# インデックスの確認
mysql -u root -p mirai_base -e "SHOW INDEX FROM purchase_achievements;"

# テーブルの最適化
mysql -u root -p mirai_base -e "OPTIMIZE TABLE purchase_achievements;"
```

### パフォーマンスの監視

```bash
# テーブルサイズの確認
mysql -u root -p mirai_base -e "
  SELECT 
    table_name AS 'Table',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
  FROM information_schema.TABLES
  WHERE table_schema = 'mirai_base'
  AND table_name = 'purchase_achievements';"
```

## セキュリティ

### APIキーの管理

- APIキーは安全に管理してください
- 定期的にAPIキーをローテーションしてください
- 不要なAPIキーは削除してください

### データベースのセキュリティ

- データベースユーザーに最小限の権限のみを付与してください
- パスワードを強力に設定してください
- 定期的にバックアップを取得してください

## 関連ドキュメント

- `docs/PURCHASE_ACHIEVEMENTS.md`: 機能説明
- `docs/PURCHASE_ACHIEVEMENTS_SETUP.md`: セットアップガイド
- `docs/PURCHASE_ACHIEVEMENTS_QUICKSTART.md`: クイックスタートガイド
- `README_PURCHASE_ACHIEVEMENTS.md`: 概要とAPI仕様




