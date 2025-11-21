# 物件買取実績機能

## 概要

物件買取実績機能は、買取物件の情報を管理し、API経由で取得できるようにする機能です。

## 機能

- **一覧表示**: 物件買取実績の一覧を取得
- **詳細表示**: 物件買取実績の詳細を取得
- **作成**: 新しい物件買取実績を作成
- **更新**: 既存の物件買取実績を更新
- **削除**: 物件買取実績を削除（未実装）

## データベーステーブル

テーブル名: `purchase_achievements`

### カラム

- **一覧表示項目**
  - `property_image_url`: 物件写真URL
  - `purchase_date`: 買取日
  - `title`: タイトル（例：◯県◯市一棟アパート）

- **詳細表示項目**
  - `property_name`: 物件名
  - `building_age`: 築年数
  - `structure`: 構造
  - `nearest_station`: 最寄り

- **その他管理項目**
  - `hubspot_bukken_id`: HubSpotの物件ID（オプショナル）
  - `hubspot_bukken_created_date`: HubSpotの物件登録日（オプショナル）
  - `hubspot_deal_id`: HubSpotの取引ID（オプショナル）
  - `is_public`: 公開フラグ（デフォルト: false）
  - `created_at`: レコード作成日
  - `updated_at`: レコード更新日

## APIエンドポイント

### 1. 一覧取得

```
GET /purchase-achievements
```

**パラメータ**:
- `is_public` (optional): 公開フラグでフィルタリング（true/false）
- `limit` (optional): 取得件数上限（デフォルト: 100）
- `offset` (optional): オフセット（デフォルト: 0）

**レスポンス**:
```json
{
  "status": "success",
  "message": "物件買取実績一覧を正常に取得しました（10件）",
  "data": [
    {
      "id": 1,
      "property_image_url": "https://example.com/image.jpg",
      "purchase_date": "2024-01-01",
      "title": "千葉県柏市一棟アパート",
      "property_name": "柏市一棟アパート",
      "building_age": 10,
      "structure": "RC造",
      "nearest_station": "柏駅",
      "hubspot_bukken_id": null,
      "hubspot_bukken_created_date": null,
      "hubspot_deal_id": null,
      "is_public": false,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ],
  "count": 10
}
```

### 2. 詳細取得

```
GET /purchase-achievements/{achievement_id}
```

**レスポンス**:
```json
{
  "status": "success",
  "message": "物件買取実績詳細を正常に取得しました",
  "data": {
    "id": 1,
    "property_image_url": "https://example.com/image.jpg",
    "purchase_date": "2024-01-01",
    "title": "千葉県柏市一棟アパート",
    "property_name": "柏市一棟アパート",
    "building_age": 10,
    "structure": "RC造",
    "nearest_station": "柏駅",
    "hubspot_bukken_id": null,
    "hubspot_bukken_created_date": null,
    "hubspot_deal_id": null,
    "is_public": false,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
}
```

### 3. 作成

```
POST /purchase-achievements
```

**リクエストボディ**:
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

**レスポンス**:
```json
{
  "status": "success",
  "message": "物件買取実績を正常に作成しました",
  "data": {
    "id": 1,
    ...
  }
}
```

### 4. 更新

```
PATCH /purchase-achievements/{achievement_id}
```

**リクエストボディ**:
```json
{
  "title": "千葉県柏市一棟アパート（更新）",
  "is_public": true
}
```

**レスポンス**:
```json
{
  "status": "success",
  "message": "物件買取実績を正常に更新しました",
  "data": {
    "id": 1,
    ...
  }
}
```

### 5. 削除

```
DELETE /purchase-achievements/{achievement_id}
```

**注意**: 削除機能は現在未実装です。501エラーが返されます。

## セットアップ

### 1. データベーステーブルの作成

```bash
# 方法1: SQLスクリプトを使用
mysql -u your_username -p mirai_base < database/create_purchase_achievements_table.sql

# 方法2: Pythonスクリプトを使用
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/create_purchase_achievements_table.py
```

### 2. APIサーバーの起動

```bash
# APIサーバーを起動
sudo systemctl start mirai-api

# または、開発モードで起動
cd /var/www/mirai-api
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. APIエンドポイントのテスト

```bash
# 一覧取得
curl -X GET "http://localhost:8000/purchase-achievements?limit=10" \
  -H "X-API-Key: your-api-key"

# 作成
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

## 注意事項

1. **HubSpot関連項目**: HubSpot関連の項目（`hubspot_bukken_id`, `hubspot_deal_id`など）はオプショナルです。HubSpotと連携しない場合は、これらの項目を `null` のままにしておくことができます。

2. **日付形式**: 
   - 日付は `YYYY-MM-DD` 形式で指定してください
   - 日時は `YYYY-MM-DD HH:MM:SS` 形式で指定してください

3. **API認証**: すべてのエンドポイントで `X-API-Key` ヘッダーが必要です。

4. **公開フラグ**: `is_public` フラグを使用して、公開する物件を管理できます。デフォルトは `false`（非公開）です。

## トラブルシューティング

詳細なトラブルシューティング手順は、`docs/PURCHASE_ACHIEVEMENTS_SETUP.md` を参照してください。

## 関連ファイル

- `database/create_purchase_achievements_table.sql`: テーブル作成SQLスクリプト
- `database/init.sql`: データベース初期化スクリプト（テーブル定義を含む）
- `scripts/create_purchase_achievements_table.py`: テーブル作成Pythonスクリプト
- `models/purchase_achievement.py`: データモデル
- `services/purchase_achievement_service.py`: ビジネスロジック
- `routers/purchase_achievement.py`: APIエンドポイント
- `docs/PURCHASE_ACHIEVEMENTS_SETUP.md`: セットアップガイド




