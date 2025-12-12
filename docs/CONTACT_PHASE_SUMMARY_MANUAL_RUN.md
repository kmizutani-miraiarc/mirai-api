# フェーズ集計バッチスクリプト 手動実行ガイド

## 概要

フェーズ集計バッチスクリプトを手動で単体実行する方法を説明します。

## 前提条件

- Python 3.8以上がインストールされている
- mirai-apiの仮想環境がセットアップされている
- 環境変数（.envファイル）が正しく設定されている
- MySQLデータベースが起動している
- HubSpot APIキーが設定されている

## 実行方法

### 方法1: 実行用シェルスクリプトを使用（推奨）

```bash
cd /path/to/mirai-arc/mirai-api
./scripts/run_contact_phase_summary.sh
```

### 方法2: 直接Pythonスクリプトを実行

```bash
cd /path/to/mirai-arc/mirai-api

# 仮想環境を有効化
source venv/bin/activate

# スクリプトを実行
python3 scripts/sync_contact_phase_summary.py
```

### 方法3: Docker環境で実行

```bash
# Dockerコンテナ内で実行
docker exec -it mirai-api-server bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/sync_contact_phase_summary.py
```

## 環境変数の確認

実行前に、以下の環境変数が設定されているか確認してください：

```bash
# .envファイルを確認
cat .env | grep -E "HUBSPOT_|MYSQL_"
```

必要な環境変数：
- `HUBSPOT_API_KEY`: HubSpot APIキー
- `HUBSPOT_ID`: HubSpot ID
- `MYSQL_HOST`: MySQLホスト（例: localhost または mysql）
- `MYSQL_PORT`: MySQLポート（デフォルト: 3306）
- `MYSQL_USER`: MySQLユーザー名
- `MYSQL_PASSWORD`: MySQLパスワード
- `MYSQL_DATABASE`: データベース名（通常: mirai_base）

## 実行結果の確認

### ログファイルの確認

```bash
# 本番環境の場合
tail -f /var/www/mirai-api/logs/contact_phase_summary.log

# ローカル環境の場合
tail -f logs/contact_phase_summary.log
```

### データベースの確認

```bash
# MySQLに接続
mysql -u root -p mirai_base

# 集計データを確認
SELECT * FROM contact_phase_summary ORDER BY aggregation_date DESC, owner_name LIMIT 20;

# 最新の集計日を確認
SELECT MAX(aggregation_date) as latest_date FROM contact_phase_summary;
```

## トラブルシューティング

### エラー: 仮想環境が見つからない

```bash
# 仮想環境を作成
cd /path/to/mirai-arc/mirai-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### エラー: データベース接続に失敗

```bash
# データベース接続を確認
mysql -u $MYSQL_USER -p$MYSQL_PASSWORD -h $MYSQL_HOST $MYSQL_DATABASE -e "SELECT 1;"
```

### エラー: HubSpot API認証エラー

```bash
# 環境変数を確認
echo $HUBSPOT_API_KEY
echo $HUBSPOT_ID

# .envファイルを確認
cat .env | grep HUBSPOT
```

### エラー: テーブルが存在しない

```bash
# テーブルを作成
mysql -u root -p mirai_base < database/create_contact_phase_summary_table.sql
```

## 実行例

```bash
$ cd /path/to/mirai-arc/mirai-api
$ source venv/bin/activate
$ python3 scripts/sync_contact_phase_summary.py

2024-01-15 10:30:00 - contact_phase_summary - INFO - コンタクトフェーズ集計を開始します。
2024-01-15 10:30:01 - contact_phase_summary - INFO - 担当者キャッシュを読み込みました。件数: 15
2024-01-15 10:30:01 - contact_phase_summary - INFO - 集計日: 2024-01-15
2024-01-15 10:30:05 - contact_phase_summary - INFO - 100件のコンタクトを取得しました。 (page=1)
2024-01-15 10:30:10 - contact_phase_summary - INFO - 200件のコンタクトを取得しました。 (page=2)
...
2024-01-15 10:30:45 - contact_phase_summary - INFO - コンタクトの集計が完了しました。総件数: 1250, 処理件数: 1250
2024-01-15 10:30:46 - contact_phase_summary - INFO - 既存データを削除しました。件数: 0
2024-01-15 10:30:46 - contact_phase_summary - INFO - データベースに保存しました。件数: 180
2024-01-15 10:30:46 - contact_phase_summary - INFO - コンタクトフェーズ集計が完了しました。
```

## 注意事項

- このスクリプトはHubSpot APIを呼び出すため、レート制限に注意してください
- 大量のコンタクトがある場合、実行に時間がかかる可能性があります
- 本番環境では、systemdタイマーを使用して自動実行することを推奨します



