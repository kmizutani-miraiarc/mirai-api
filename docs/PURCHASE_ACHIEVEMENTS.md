# 物件買取実績機能

## 概要

物件買取実績機能は、HubSpotの仕入パイプラインで「決済」または「契約」ステージに到達した取引の物件情報を自動的にMySQLデータベースに保存し、API経由で取得できるようにする機能です。

## 機能

### 1. バッチ処理

- **実行スケジュール**: 1日1回、午前3時に自動実行
- **処理内容**:
  - HubSpotの仕入パイプライン（ID: `675713658`）から「決済」または「契約」ステージの取引を取得
  - 各取引に関連する物件情報を取得
  - 物件買取実績テーブルに保存（既存レコードは更新）

### 2. データベーステーブル

テーブル名: `purchase_achievements`

#### カラム

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
  - `hubspot_bukken_id`: HubSpotの物件ID（必須）
  - `hubspot_bukken_created_date`: HubSpotの物件登録日
  - `hubspot_deal_id`: HubSpotの取引ID
  - `is_public`: 公開フラグ（デフォルト: false）
  - `created_at`: レコード作成日
  - `updated_at`: レコード更新日

### 3. APIエンドポイント

#### 物件買取実績一覧取得

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
      "hubspot_bukken_id": "123456789",
      "hubspot_bukken_created_date": "2024-01-01T00:00:00",
      "hubspot_deal_id": "987654321",
      "is_public": false,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ],
  "count": 10
}
```

#### 物件買取実績詳細取得

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
    "hubspot_bukken_id": "123456789",
    "hubspot_bukken_created_date": "2024-01-01T00:00:00",
    "hubspot_deal_id": "987654321",
    "is_public": false,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
}
```

## セットアップ

### 1. データベーステーブルの作成

```bash
mysql -u your_username -p mirai_base < database/create_purchase_achievements_table.sql
```

### 2. systemdサービスの設定

```bash
# サービスファイルをコピー
sudo cp purchase-achievements-sync.service /etc/systemd/system/
sudo cp purchase-achievements-sync.timer /etc/systemd/system/

# タイマーを有効化
sudo systemctl daemon-reload
sudo systemctl enable purchase-achievements-sync.timer
sudo systemctl start purchase-achievements-sync.timer

# タイマーの状態を確認
sudo systemctl status purchase-achievements-sync.timer

# 次の実行時刻を確認
sudo systemctl list-timers purchase-achievements-sync.timer
```

### 3. 手動実行

バッチ処理を手動で実行する場合:

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/sync_purchase_achievements.py
```

### 4. ログ確認

```bash
# ログファイルを確認
tail -f /var/www/mirai-api/logs/purchase_achievements_sync.log

# systemdログを確認
sudo journalctl -u purchase-achievements-sync.service -f
```

## 注意事項

1. **ステージ名の判定**: バッチ処理はステージラベルに「決済」または「settlement」、「契約」または「contract」が含まれるかどうかで判定します。HubSpotのステージ名が異なる場合は、バッチ処理スクリプトを修正してください。

2. **物件画像URL**: 物件画像URLはHubSpotの物件プロパティから取得します。プロパティ名が異なる場合は、バッチ処理スクリプトを修正してください。

3. **最寄り駅**: 最寄り駅情報はHubSpotの物件プロパティから取得します。プロパティ名が異なる場合は、バッチ処理スクリプトを修正してください。

4. **買取日の優先順位**:
   - 決済日（settlement_date）
   - 契約日（contract_date）
   - 買取日（purchase_date）
   - 取引の作成日（createdate）

5. **重複防止**: 同じ物件IDと取引IDの組み合わせは1つのレコードのみが保存されます（UNIQUE制約）。

## トラブルシューティング

### バッチ処理が実行されない

1. タイマーの状態を確認:
   ```bash
   sudo systemctl status purchase-achievements-sync.timer
   ```

2. タイマーを再起動:
   ```bash
   sudo systemctl restart purchase-achievements-sync.timer
   ```

### データが取得されない

1. HubSpot API設定を確認:
   - 環境変数 `HUBSPOT_API_KEY` と `HUBSPOT_ID` が正しく設定されているか確認

2. ログを確認:
   ```bash
   tail -f /var/www/mirai-api/logs/purchase_achievements_sync.log
   ```

3. ステージIDを確認:
   - バッチ処理スクリプトのログで「決済」や「契約」ステージが検出されているか確認

### APIがエラーを返す

1. データベース接続を確認:
   - 環境変数 `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` が正しく設定されているか確認

2. APIキーを確認:
   - `X-API-Key` ヘッダーが正しく設定されているか確認




