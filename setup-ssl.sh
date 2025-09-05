#!/bin/bash

# SSL証明書設定スクリプト
# Let's Encryptを使用してSSL証明書を取得・設定

set -e

DOMAIN_NAME=${1:-"your-domain.com"}
EMAIL=${2:-"admin@your-domain.com"}

echo "SSL証明書設定を開始します..."
echo "ドメイン名: $DOMAIN_NAME"
echo "メールアドレス: $EMAIL"

# 必要なディレクトリを作成
mkdir -p ssl
mkdir -p logs/nginx

# Certbotのインストール（AlmaLinux 9）
echo "Certbotをインストール中..."
sudo dnf install -y epel-release
sudo dnf install -y certbot

# 一時的なHTTPサーバーでドメイン認証
echo "SSL証明書を取得中..."
sudo certbot certonly --standalone \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN_NAME

# 証明書をプロジェクトディレクトリにコピー
echo "証明書をコピー中..."
sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem ssl/key.pem
sudo chown -R $(whoami):$(whoami) ssl/

# 自動更新の設定
echo "自動更新を設定中..."
sudo crontab -l 2>/dev/null | { cat; echo "0 12 * * * /usr/bin/certbot renew --quiet && cd /var/www/mirai-api && sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem ssl/cert.pem && sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem ssl/key.pem && sudo chown -R $(whoami):$(whoami) ssl/ && sudo systemctl reload nginx"; } | sudo crontab -

echo "SSL証明書設定が完了しました！"
echo "証明書の有効期限:"
sudo certbot certificates

echo ""
echo "次のステップ:"
echo "1. nginx/nginx-direct.confでserver_nameを更新"
echo "2. サービスを起動: sudo systemctl start mirai-api"
