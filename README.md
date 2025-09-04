# Mirai API Server

AlmaLinuxで動作するPython APIサーバーです。FastAPIを使用して構築されています。Dockerコンテナとしても実行可能です。

## 機能

- 外部からのAPIアクセスに対応
- JSONレスポンスを返すテストエンドポイント
- ヘルスチェック機能
- CORS対応
- Dockerコンテナ対応

## セットアップ

### 方法1: Dockerを使用（推奨）

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

### 方法2: 直接実行

#### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

#### 2. サーバーの起動

```bash
python main.py
```

または

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## エンドポイント

### ルートエンドポイント
- **URL**: `GET /`
- **説明**: サーバーの動作確認

### テストエンドポイント
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

### ヘルスチェック
- **URL**: `GET /health`
- **説明**: サーバーの状態確認

### API情報
- **URL**: `GET /api/info`
- **説明**: 利用可能なエンドポイントの一覧

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
