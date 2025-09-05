#!/bin/bash

# Mirai API デプロイスクリプト
# 本番サーバーでのデプロイを自動化

set -e

echo "=== Mirai API デプロイスクリプト ==="

# 設定確認
if [ ! -f ".env.prod" ]; then
    echo "エラー: .env.prod ファイルが見つかりません"
    echo "env.prod.example をコピーして .env.prod を作成し、設定してください"
    exit 1
fi

# バックアップ作成
echo "既存のコンテナをバックアップ中..."
if [ -f "docker-compose.prod.yml" ]; then
    docker-compose -f docker-compose.prod.yml down || true
fi

# イメージのビルド
echo "Dockerイメージをビルド中..."
docker-compose -f docker-compose.prod.yml build --no-cache

# 古いイメージの削除
echo "未使用のDockerイメージを削除中..."
docker image prune -f

# サービスの起動
echo "サービスを起動中..."
docker-compose -f docker-compose.prod.yml up -d

# ヘルスチェック
echo "ヘルスチェックを実行中..."
sleep 30

# APIのヘルスチェック
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ APIサーバーが正常に起動しました"
else
    echo "❌ APIサーバーの起動に失敗しました"
    docker-compose -f docker-compose.prod.yml logs mirai-api-server
    exit 1
fi

# Nginxのヘルスチェック
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ Nginxリバースプロキシが正常に動作しています"
else
    echo "❌ Nginxリバースプロキシの動作に問題があります"
    docker-compose -f docker-compose.prod.yml logs nginx
    exit 1
fi

echo ""
echo "=== デプロイ完了 ==="
echo "API URL: http://localhost:8000"
echo "Swagger UI: http://localhost:8000/docs"
echo "Nginx URL: http://localhost"
echo ""
echo "ログ確認: docker-compose -f docker-compose.prod.yml logs -f"
echo "サービス停止: docker-compose -f docker-compose.prod.yml down"
echo "サービス再起動: docker-compose -f docker-compose.prod.yml restart"
