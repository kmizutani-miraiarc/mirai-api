#!/bin/bash

# Mirai API 直接実行デプロイスクリプト（Docker不使用）
# 本番サーバーでの直接Python実行デプロイを自動化

set -e

echo "=== Mirai API 直接実行デプロイスクリプト ==="

# 設定確認
if [ ! -f ".env.prod" ]; then
    echo "エラー: .env.prod ファイルが見つかりません"
    echo "env.prod.example をコピーして .env.prod を作成し、設定してください"
    exit 1
fi

# ユーザーとグループの作成
echo "ユーザーとグループを作成中..."
sudo useradd -r -s /bin/false mirai-api || true

# アプリケーションディレクトリの設定
echo "アプリケーションディレクトリを設定中..."
sudo mkdir -p /opt/mirai-api
sudo mkdir -p /opt/mirai-api/logs
sudo chown -R mirai-api:mirai-api /opt/mirai-api

# 必要なディレクトリの作成
mkdir -p logs
mkdir -p ssl

# Python仮想環境の作成
echo "Python仮想環境を作成中..."
cd /opt/mirai-api
sudo -u mirai-api python3 -m venv venv

# 依存関係のインストール
echo "Python依存関係をインストール中..."
sudo -u mirai-api /opt/mirai-api/venv/bin/pip install --upgrade pip
sudo -u mirai-api /opt/mirai-api/venv/bin/pip install -r requirements.txt

# アプリケーションファイルのコピー
echo "アプリケーションファイルをコピー中..."
sudo cp -r /path/to/your/mirai-api/* /opt/mirai-api/
sudo chown -R mirai-api:mirai-api /opt/mirai-api

# systemdサービスの設定
echo "systemdサービスを設定中..."
sudo cp mirai-api-direct.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mirai-api

# Nginxのインストールと設定
echo "Nginxを設定中..."
sudo dnf install -y nginx
sudo cp nginx/nginx-direct.conf /etc/nginx/nginx.conf
sudo systemctl enable nginx

# サービスの起動
echo "サービスを起動中..."
sudo systemctl start mirai-api
sudo systemctl start nginx

# ヘルスチェック
echo "ヘルスチェックを実行中..."
sleep 10

# APIのヘルスチェック
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ APIサーバーが正常に起動しました"
else
    echo "❌ APIサーバーの起動に失敗しました"
    sudo journalctl -u mirai-api --no-pager -l
    exit 1
fi

# Nginxのヘルスチェック
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ Nginxリバースプロキシが正常に動作しています"
else
    echo "❌ Nginxリバースプロキシの動作に問題があります"
    sudo journalctl -u nginx --no-pager -l
    exit 1
fi

echo ""
echo "=== デプロイ完了 ==="
echo "API URL: http://localhost:8000"
echo "Swagger UI: http://localhost:8000/docs"
echo "Nginx URL: http://localhost"
echo ""
echo "ログ確認:"
echo "  API: sudo journalctl -u mirai-api -f"
echo "  Nginx: sudo journalctl -u nginx -f"
echo ""
echo "サービス管理:"
echo "  停止: sudo systemctl stop mirai-api"
echo "  再起動: sudo systemctl restart mirai-api"
echo "  状態確認: sudo systemctl status mirai-api"
