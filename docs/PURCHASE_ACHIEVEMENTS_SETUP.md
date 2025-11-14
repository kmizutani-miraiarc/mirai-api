# 物件買取実績機能 セットアップガイド

## 概要

物件買取実績機能のセットアップ手順を説明します。

## 1. データベーステーブルの作成

### 方法1: SQLスクリプトを使用

```bash
# MySQLに接続してSQLスクリプトを実行
mysql -u your_username -p mirai_base < database/create_purchase_achievements_table.sql
```

### 方法2: Pythonスクリプトを使用

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/create_purchase_achievements_table.py
```

### 方法3: init.sqlに含まれている場合

`database/init.sql`にテーブル定義が含まれている場合は、データベース初期化時に自動的に作成されます。

## 2. テーブル構造の確認

```sql
-- テーブルが作成されているか確認
SHOW TABLES LIKE 'purchase_achievements';

-- テーブル構造を確認
DESCRIBE purchase_achievements;

-- インデックスを確認
SHOW INDEX FROM purchase_achievements;
```

## 3. APIエンドポイントの確認

APIサーバーを起動して、以下のエンドポイントが利用可能か確認します。

### 一覧取得

```bash
curl -X GET "http://localhost:8000/purchase-achievements?limit=10&offset=0" \
  -H "X-API-Key: your-api-key"
```

### 詳細取得

```bash
curl -X GET "http://localhost:8000/purchase-achievements/1" \
  -H "X-API-Key: your-api-key"
```

### 作成

```bash
curl -X POST "http://localhost:8000/purchase-achievements" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "千葉県柏市一棟アパート",
    "property_name": "柏市一棟アパート",
    "purchase_date": "2024-01-01",
    "building_age": 10,
    "structure": "RC造",
    "nearest_station": "柏駅",
    "is_public": false
  }'
```

### 更新

```bash
curl -X PATCH "http://localhost:8000/purchase-achievements/1" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "千葉県柏市一棟アパート（更新）",
    "is_public": true
  }'
```

## 4. テストデータの投入

### SQLで直接投入

```sql
INSERT INTO purchase_achievements (
    title,
    property_name,
    purchase_date,
    building_age,
    structure,
    nearest_station,
    is_public
) VALUES (
    '千葉県柏市一棟アパート',
    '柏市一棟アパート',
    '2024-01-01',
    10,
    'RC造',
    '柏駅',
    false
);
```

### API経由で投入

上記の「作成」エンドポイントを使用してデータを投入します。

## 5. トラブルシューティング

### テーブルが作成されない

1. データベース接続情報を確認:
   - 環境変数 `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` が正しく設定されているか確認

2. データベースへの接続を確認:
   ```bash
   mysql -u your_username -p -h your_host mirai_base
   ```

3. ログを確認:
   ```bash
   tail -f /var/www/mirai-api/logs/purchase_achievements_sync.log
   ```

### APIがエラーを返す

1. データベース接続を確認:
   - APIサーバーのログを確認
   - データベースが起動しているか確認

2. APIキーを確認:
   - `X-API-Key` ヘッダーが正しく設定されているか確認
   - APIキーが有効か確認

3. エラーログを確認:
   ```bash
   sudo journalctl -u mirai-api -f
   ```

### 日付形式のエラー

- 日付は `YYYY-MM-DD` 形式で指定してください
- 日時は `YYYY-MM-DD HH:MM:SS` 形式で指定してください

## 6. 次のステップ

1. **バッチ処理の設定**（オプション）:
   - HubSpotからデータを自動取得する場合は、`scripts/sync_purchase_achievements.py` を設定
   - systemdタイマーを設定して1日1回実行

2. **公開フラグの管理**:
   - `is_public` フラグを使用して、公開する物件を管理
   - APIの `is_public` パラメータでフィルタリング

3. **画像のアップロード**:
   - `property_image_url` に画像URLを設定
   - 画像は別途アップロードして、URLを保存

## 7. 注意事項

- HubSpot関連の項目（`hubspot_bukken_id`, `hubspot_deal_id`など）はオプショナルです
- HubSpotと連携しない場合は、これらの項目を `null` のままにしておくことができます
- 同じ `hubspot_bukken_id` と `hubspot_deal_id` の組み合わせは1つのレコードのみが保存されます（重複防止）


