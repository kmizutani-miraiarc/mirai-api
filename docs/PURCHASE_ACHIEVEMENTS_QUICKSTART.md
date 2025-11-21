# 物件買取実績機能 クイックスタートガイド

## 概要

このガイドでは、物件買取実績機能を素早くセットアップして使用する方法を説明します。

## 前提条件

- MySQLデータベースが起動している
- mirai-apiサーバーがインストールされている
- 環境変数が正しく設定されている

## セットアップ手順

### 1. 環境変数の確認

`.env`ファイルまたは環境変数に以下の設定が含まれているか確認してください：

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=mirai_base
MYSQL_CHARSET=utf8mb4
```

### 2. データベーステーブルの作成

#### 方法1: 検証スクリプトを使用（推奨）

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/verify_purchase_achievements_setup.py
```

このスクリプトは以下を実行します：
- データベース接続の確認
- テーブルの存在確認
- テーブルが存在しない場合、自動的に作成
- サービスの動作確認

#### 方法2: SQLスクリプトを使用

```bash
mysql -u root -p mirai_base < database/create_purchase_achievements_table.sql
```

#### 方法3: Pythonスクリプトを使用

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/create_purchase_achievements_table.py
```

### 3. APIサーバーの再起動

```bash
sudo systemctl restart mirai-api
```

または、開発モードで起動：

```bash
cd /var/www/mirai-api
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. APIエンドポイントのテスト

#### 4.1 APIキーの取得

まず、APIキーを取得または作成する必要があります：

```bash
# APIキー一覧を取得（APIキー管理エンドポイントを使用）
curl -X GET "http://localhost:8000/api-keys"
```

#### 4.2 テストスクリプトの実行

```bash
cd /var/www/mirai-api
source venv/bin/activate
API_KEY=your-api-key python3 scripts/test_purchase_achievements_api.py
```

#### 4.3 手動テスト

```bash
# 1. 一覧取得
curl -X GET "http://localhost:8000/purchase-achievements?limit=10" \
  -H "X-API-Key: your-api-key"

# 2. 作成
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

# 3. 詳細取得（ID=1の場合）
curl -X GET "http://localhost:8000/purchase-achievements/1" \
  -H "X-API-Key: your-api-key"

# 4. 更新（ID=1の場合）
curl -X PATCH "http://localhost:8000/purchase-achievements/1" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "千葉県柏市一棟アパート（更新）",
    "is_public": true
  }'
```

## 使用方法

### データの作成

物件買取実績データを作成するには、`POST /purchase-achievements` エンドポイントを使用します：

```json
{
  "title": "千葉県柏市一棟アパート",
  "property_name": "柏市一棟アパート",
  "purchase_date": "2024-01-01",
  "building_age": 10,
  "structure": "RC造",
  "nearest_station": "柏駅",
  "property_image_url": "https://example.com/image.jpg",
  "is_public": false
}
```

### データの取得

#### 一覧取得

```bash
curl -X GET "http://localhost:8000/purchase-achievements?limit=10&offset=0" \
  -H "X-API-Key: your-api-key"
```

#### 公開物件のみ取得

```bash
curl -X GET "http://localhost:8000/purchase-achievements?is_public=true&limit=10" \
  -H "X-API-Key: your-api-key"
```

#### 詳細取得

```bash
curl -X GET "http://localhost:8000/purchase-achievements/{id}" \
  -H "X-API-Key: your-api-key"
```

### データの更新

```bash
curl -X PATCH "http://localhost:8000/purchase-achievements/{id}" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "更新されたタイトル",
    "is_public": true
  }'
```

## トラブルシューティング

### データベース接続エラー

**症状**: `データベース接続に失敗しました`

**解決方法**:
1. 環境変数を確認: `echo $MYSQL_HOST $MYSQL_USER $MYSQL_DATABASE`
2. データベースが起動しているか確認: `sudo systemctl status mysql`
3. 接続情報を確認: `mysql -u $MYSQL_USER -p $MYSQL_DATABASE`

### テーブルが存在しない

**症状**: `purchase_achievements テーブルが存在しません`

**解決方法**:
1. 検証スクリプトを実行: `python3 scripts/verify_purchase_achievements_setup.py`
2. または、SQLスクリプトを実行: `mysql -u root -p mirai_base < database/create_purchase_achievements_table.sql`

### API認証エラー

**症状**: `401 Unauthorized` または `Invalid API key`

**解決方法**:
1. APIキーが正しく設定されているか確認
2. `X-API-Key` ヘッダーが含まれているか確認
3. APIキーが有効か確認: `curl -X GET "http://localhost:8000/api-keys"`

### 日付形式エラー

**症状**: `日付の形式が正しくありません`

**解決方法**:
- 日付は `YYYY-MM-DD` 形式で指定してください
- 例: `2024-01-01`

## 次のステップ

1. **バッチ処理の設定**（オプション）:
   - HubSpotからデータを自動取得する場合は、systemdタイマーを設定
   - 詳細は `docs/PURCHASE_ACHIEVEMENTS.md` を参照

2. **フロントエンドの実装**:
   - APIエンドポイントを使用してフロントエンドを実装
   - 一覧表示、詳細表示、作成、更新機能を実装

3. **画像アップロード機能**:
   - 物件画像をアップロードする機能を実装
   - アップロードした画像のURLを `property_image_url` に設定

## 関連ドキュメント

- `docs/PURCHASE_ACHIEVEMENTS.md`: 機能説明
- `docs/PURCHASE_ACHIEVEMENTS_SETUP.md`: 詳細なセットアップガイド
- `README_PURCHASE_ACHIEVEMENTS.md`: 概要とAPI仕様




