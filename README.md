# Mirai API Server

AlmaLinuxで動作するPython APIサーバーです。FastAPIを使用して構築されています。HubSpot APIとの統合機能を提供します。

## 機能

- HubSpot API統合（Owners、Contacts、Companies、Deals、Custom Objects）
- 物件情報（bukken）のCRUD操作
- 物件検索機能（物件名、都道府県、市区町村での検索）
- 外部からのAPIアクセスに対応
- JSONレスポンスを返すテストエンドポイント
- ヘルスチェック機能
- CORS対応

## セットアップ

### ローカル開発環境（Docker使用）

#### 前提条件
- Docker
- Docker Compose

#### 起動方法

```bash
# 簡単起動
./docker-run.sh

# または手動で起動
docker-compose up --build
```

#### 停止方法

```bash
docker-compose down
```

### 本番環境（直接実行）

本番環境でのデプロイについては、詳細な手順書を参照してください：

- **📚 ドキュメント一覧**: `DOCUMENTATION-INDEX.md` - 全ドキュメントの用途と選択指針
- **完全統合手順書**: `DEPLOYMENT-GUIDE-COMPLETE.md` （推奨）
- **基本デプロイ**: `DEPLOYMENT-DIRECT.md`
- **既存Nginx環境**: `NGINX-EXISTING-SETUP.md`
- **既存SSL証明書環境**: `SSL-EXISTING-CERT.md`
- **Let's Encrypt認証エラー**: `LETSENCRYPT-TROUBLESHOOTING.md`

#### Nginx設定の選択肢

1. **自動設定（推奨）**: `./nginx-setup-existing.sh` - 既存Nginx環境に自動設定
2. **手動設定**: `nginx/conf.d/mirai-api.conf` - conf.dディレクトリに追加
3. **完全置き換え**: `nginx/nginx-direct.conf` - nginx.confを完全置き換え

#### SSL証明書の設定

既存のSSL証明書がある場合：

1. **自動設定**: `./setup-ssl-existing.sh` - 既存証明書環境に自動設定
2. **手動設定**: `SSL-EXISTING-CERT.md` を参照
3. **新規証明書**: `./setup-ssl.sh` - 新規で証明書を取得

#### クイックスタート

```bash
# 自動デプロイスクリプトの実行
./deploy-direct.sh
```

#### 手動セットアップ

```bash
# 1. 依存関係のインストール
pip install -r requirements.txt

# 2. サーバーの起動
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 環境変数設定

### HubSpot API設定

HubSpot APIを使用する場合は、以下の環境変数を設定してください：

```bash
# 環境変数ファイルを作成
cp env.example .env

# .envファイルを編集して実際の値を設定
HUBSPOT_API_KEY=your-actual-hubspot-api-key
HUBSPOT_ID=your-actual-hubspot-id
```

### MySQLデータベース設定

APIキー管理にMySQLデータベースを使用します：

```bash
# MySQLデータベース設定
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-mysql-password
MYSQL_DATABASE=mirai_base
MYSQL_CHARSET=utf8mb4
```

### データベースの初期化

```bash
# MySQLに接続してデータベースを初期化
mysql -u root -p < database/init.sql
```

## 認証について

このAPIは**データベースベースのAPIキー認証**を使用しています。

### 認証の仕組み

1. **APIキーの生成**: `/api-keys` エンドポイントでサイトごとにAPIキーを作成
2. **データベース保存**: APIキーはハッシュ化されてMySQLデータベースに保存
3. **認証検証**: すべてのリクエストで`X-API-Key`ヘッダーを検証
4. **使用履歴**: 最終使用日時を自動記録

### 認証ヘッダー

すべてのAPIリクエストに以下のヘッダーを含める必要があります：

```bash
X-API-Key: your-actual-api-key-here
```

### 認証エラー

- **401 Unauthorized**: APIキーが未提供または無効
- **エラーメッセージ**: `"API key is required"` または `"Invalid API key"`

## エンドポイント

### 基本エンドポイント

#### ルートエンドポイント
- **URL**: `GET /`
- **説明**: サーバーの動作確認

#### テストエンドポイント
- **URL**: `GET /test`
- **説明**: テスト用のJSONレスポンスを返す
- **レスポンス例**:
```json
{
  "status": "success",
  "message": "テストエンドポイントが正常に動作しています",
  "data": {
    "server": "Mirai API Server",
    "platform": "AlmaLinux",
    "language": "Python",
    "framework": "FastAPI",
    "timestamp": "2024-01-01T00:00:00Z",
    "version": "1.0.0"
  }
}
```

#### ヘルスチェック
- **URL**: `GET /health`
- **説明**: サーバーの状態確認

#### API情報
- **URL**: `GET /api/info`
- **説明**: 利用可能なエンドポイントの一覧

### APIキー管理エンドポイント

#### APIキー作成
- **URL**: `POST /api-keys`
- **説明**: 新しいAPIキーを作成
- **リクエストボディ**:
  ```json
  {
    "site_name": "example-site",
    "description": "テスト用APIキー",
    "expires_days": 365
  }
  ```

#### APIキー一覧取得
- **URL**: `GET /api-keys`
- **説明**: APIキー一覧を取得
- **パラメータ**: `include_inactive` (オプション) - 無効なキーも含める

#### APIキー情報取得
- **URL**: `GET /api-keys/{site_name}`
- **説明**: 指定されたサイトのAPIキー情報を取得

#### APIキー無効化
- **URL**: `PATCH /api-keys/{site_name}/deactivate`
- **説明**: 指定されたサイトのAPIキーを無効化

#### APIキー有効化
- **URL**: `PATCH /api-keys/{site_name}/activate`
- **説明**: 指定されたサイトのAPIキーを有効化

#### APIキー削除
- **URL**: `DELETE /api-keys/{site_name}`
- **説明**: 指定されたサイトのAPIキーを削除

### HubSpot API エンドポイント

#### 担当者関連
- **URL**: `GET /hubspot/owners`
- **説明**: HubSpot担当者一覧を取得
- **パラメータ**: なし

- **URL**: `GET /hubspot/owners/{owner_id}`
- **説明**: 指定されたIDの担当者詳細を取得
- **パラメータ**: `owner_id` (必須)

#### コンタクト関連
- **URL**: `GET /hubspot/contacts`
- **説明**: HubSpotコンタクト一覧を取得
- **パラメータ**: 
  - `limit` (オプション, デフォルト: 100)
  - `after` (オプション, ページネーション用)

- **URL**: `GET /hubspot/contacts/{contact_id}`
- **説明**: 指定されたIDのコンタクト詳細を取得
- **パラメータ**: `contact_id` (必須)

#### 会社関連
- **URL**: `GET /hubspot/companies`
- **説明**: HubSpot会社一覧を取得
- **パラメータ**: 
  - `limit` (オプション, デフォルト: 100)
  - `after` (オプション, ページネーション用)

- **URL**: `GET /hubspot/companies/{company_id}`
- **説明**: 指定されたIDの会社詳細を取得
- **パラメータ**: `company_id` (必須)

#### HubSpot接続テスト
- **URL**: `GET /hubspot/health`
- **説明**: HubSpot API接続テスト

## アクセス方法

サーバー起動後、以下のURLでアクセス可能です：

- ローカル: `http://localhost:8000`
- 外部: `http://[サーバーのIPアドレス]:8000`

## APIドキュメント

FastAPIの自動生成ドキュメントにアクセスできます：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Dockerコマンドリファレンス

### 基本的な操作

```bash
# イメージをビルド
docker-compose build

# コンテナを起動（バックグラウンド）
docker-compose up -d

# コンテナを起動（フォアグラウンド、ログ表示）
docker-compose up

# コンテナを停止
docker-compose down

# ログを確認
docker-compose logs -f

# コンテナの状態確認
docker-compose ps
```

### 開発時の便利なコマンド

```bash
# コンテナ内でシェルを実行
docker-compose exec mirai-api bash

# コンテナを再起動
docker-compose restart

# イメージを再ビルドして起動
docker-compose up --build
```

## 本番環境での注意事項

- `CORS`の設定を適切に制限してください
- `reload=True`を無効にしてください
- 適切なログ設定を行ってください
- セキュリティ設定を確認してください
- Dockerのセキュリティ設定を確認してください
- 本番環境では`docker-compose.yml`の本番用設定を使用してください
