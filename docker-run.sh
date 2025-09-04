#!/bin/bash

# Mirai API Server Docker起動スクリプト

echo "=========================================="
echo "Mirai API Server (Docker版) を起動しています..."
echo "=========================================="

# Dockerがインストールされているかチェック
if ! command -v docker &> /dev/null; then
    echo "エラー: Dockerがインストールされていません。"
    echo "Dockerをインストールしてから再実行してください。"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "エラー: Docker Composeがインストールされていません。"
    echo "Docker Composeをインストールしてから再実行してください。"
    exit 1
fi

# ログディレクトリを作成
mkdir -p logs

echo "Dockerイメージをビルドしています..."
docker-compose build

echo ""
echo "コンテナを起動しています..."
docker-compose up -d

echo ""
echo "=========================================="
echo "起動完了！"
echo "=========================================="
echo "アクセスURL: http://localhost:8000"
echo "APIドキュメント: http://localhost:8000/docs"
echo "テストエンドポイント: http://localhost:8000/test"
echo "ヘルスチェック: http://localhost:8000/health"
echo ""
echo "ログを確認するには: docker-compose logs -f"
echo "停止するには: docker-compose down"
echo "=========================================="

# コンテナの状態を表示
echo ""
echo "コンテナの状態:"
docker-compose ps
