# 物件買取実績機能 次のステップ

## 実装完了

物件買取実績機能の実装が完了しました。以下の手順でセットアップを進めてください。

## セットアップ手順

### 1. データベーステーブルの作成

#### 方法1: 検証スクリプトを使用（推奨）

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/verify_purchase_achievements_setup.py
```

このスクリプトは以下を自動的に実行します：
- ✅ データベース接続の確認
- ✅ テーブルの存在確認
- ✅ テーブルが存在しない場合、自動的に作成
- ✅ サービスの動作確認

#### 方法2: 自動セットアップスクリプトを使用

```bash
cd /var/www/mirai-api
./scripts/setup_purchase_achievements.sh
```

#### 方法3: SQLスクリプトを直接実行

```bash
mysql -u root -p mirai_base < database/create_purchase_achievements_table.sql
```

### 2. APIサーバーの再起動

```bash
# APIサーバーを再起動
sudo systemctl restart mirai-api

# ステータス確認
sudo systemctl status mirai-api

# ログ確認
sudo journalctl -u mirai-api -f
```

### 3. APIエンドポイントの確認

```bash
# API情報を確認（物件買取実績エンドポイントが含まれているか確認）
curl http://localhost:8000/api/info | grep purchase-achievements

# ヘルスチェック
curl http://localhost:8000/health
```

### 4. APIエンドポイントのテスト

#### 方法1: テストスクリプトを使用

```bash
cd /var/www/mirai-api
source venv/bin/activate
API_KEY=your-api-key API_BASE_URL=http://localhost:8000 \
  python3 scripts/test_purchase_achievements_api.py
```

#### 方法2: 手動テスト

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

# 3. 詳細取得（作成したIDを使用）
curl -X GET "http://localhost:8000/purchase-achievements/1" \
  -H "X-API-Key: your-api-key"

# 4. 更新
curl -X PATCH "http://localhost:8000/purchase-achievements/1" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "千葉県柏市一棟アパート（更新）",
    "is_public": true
  }'
```

## バッチ処理の設定（オプション）

HubSpotからデータを自動取得する場合は、systemdタイマーを設定します：

```bash
# 1. サービスファイルをコピー
sudo cp purchase-achievements-sync.service /etc/systemd/system/
sudo cp purchase-achievements-sync.timer /etc/systemd/system/

# 2. systemdをリロード
sudo systemctl daemon-reload

# 3. タイマーを有効化
sudo systemctl enable purchase-achievements-sync.timer

# 4. タイマーを起動
sudo systemctl start purchase-achievements-sync.timer

# 5. ステータス確認
sudo systemctl status purchase-achievements-sync.timer

# 6. 次の実行時刻を確認
sudo systemctl list-timers purchase-achievements-sync.timer

# 7. 手動実行のテスト
sudo systemctl start purchase-achievements-sync.service

# 8. ログ確認
sudo journalctl -u purchase-achievements-sync.service -f
```

## トラブルシューティング

### データベース接続エラー

```bash
# 環境変数を確認
cat .env | grep MYSQL

# データベース接続をテスト
mysql -u $MYSQL_USER -p$MYSQL_PASSWORD -h $MYSQL_HOST $MYSQL_DATABASE -e "SELECT 1;"
```

### テーブルが存在しない

```bash
# 検証スクリプトを実行
python3 scripts/verify_purchase_achievements_setup.py

# または、SQLスクリプトを直接実行
mysql -u root -p mirai_base < database/create_purchase_achievements_table.sql
```

### APIエンドポイントが404を返す

```bash
# main.pyにルーターが追加されているか確認
grep -r "purchase_achievement_router" main.py

# APIサーバーが再起動されているか確認
sudo systemctl status mirai-api

# ログを確認
sudo journalctl -u mirai-api -f
```

## 実装ファイル一覧

### データベース
- ✅ `database/create_purchase_achievements_table.sql`: テーブル作成SQL
- ✅ `database/init.sql`: データベース初期化スクリプト（テーブル定義を含む）

### モデル
- ✅ `models/purchase_achievement.py`: データモデル

### サービス
- ✅ `services/purchase_achievement_service.py`: ビジネスロジック

### ルーター
- ✅ `routers/purchase_achievement.py`: APIエンドポイント

### スクリプト
- ✅ `scripts/sync_purchase_achievements.py`: HubSpot同期バッチ
- ✅ `scripts/create_purchase_achievements_table.py`: テーブル作成スクリプト
- ✅ `scripts/verify_purchase_achievements_setup.py`: セットアップ検証スクリプト
- ✅ `scripts/test_purchase_achievements_api.py`: APIテストスクリプト
- ✅ `scripts/setup_purchase_achievements.sh`: セットアップスクリプト

### systemd設定
- ✅ `purchase-achievements-sync.service`: systemdサービスファイル
- ✅ `purchase-achievements-sync.timer`: systemdタイマーファイル

### ドキュメント
- ✅ `docs/PURCHASE_ACHIEVEMENTS.md`: 機能説明
- ✅ `docs/PURCHASE_ACHIEVEMENTS_SETUP.md`: セットアップガイド
- ✅ `docs/PURCHASE_ACHIEVEMENTS_QUICKSTART.md`: クイックスタートガイド
- ✅ `README_PURCHASE_ACHIEVEMENTS.md`: 概要とAPI仕様
- ✅ `IMPLEMENTATION_SUMMARY.md`: 実装完了まとめ
- ✅ `CHANGELOG_PURCHASE_ACHIEVEMENTS.md`: 変更履歴
- ✅ `DEPLOYMENT_PURCHASE_ACHIEVEMENTS.md`: デプロイガイド
- ✅ `NEXT_STEPS.md`: 次のステップ（このファイル）

## APIエンドポイント一覧

- `GET /purchase-achievements`: 一覧取得
- `GET /purchase-achievements/{id}`: 詳細取得
- `POST /purchase-achievements`: 作成
- `PATCH /purchase-achievements/{id}`: 更新
- `DELETE /purchase-achievements/{id}`: 削除（未実装、501エラー）

## 次のステップ

1. **データベーステーブルの作成**: 上記のセットアップ手順を実行
2. **APIサーバーの再起動**: `sudo systemctl restart mirai-api`
3. **APIエンドポイントのテスト**: テストスクリプトまたは手動でテスト
4. **バッチ処理の設定**（オプション）: HubSpotからデータを自動取得する場合
5. **フロントエンドの実装**: APIエンドポイントを使用してフロントエンドを実装

## 関連ドキュメント

- `docs/PURCHASE_ACHIEVEMENTS_QUICKSTART.md`: クイックスタートガイド
- `docs/PURCHASE_ACHIEVEMENTS_SETUP.md`: 詳細なセットアップガイド
- `README_PURCHASE_ACHIEVEMENTS.md`: 概要とAPI仕様
- `DEPLOYMENT_PURCHASE_ACHIEVEMENTS.md`: デプロイガイド

## サポート

問題が発生した場合は、以下のドキュメントを参照してください：

- `docs/PURCHASE_ACHIEVEMENTS_SETUP.md`: トラブルシューティング
- `DEPLOYMENT_PURCHASE_ACHIEVEMENTS.md`: デプロイ時のトラブルシューティング



