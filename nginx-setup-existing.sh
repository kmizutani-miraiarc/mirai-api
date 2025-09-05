#!/bin/bash

# 既存のNginx環境でのMirai API設定スクリプト

set -e

echo "=== 既存Nginx環境でのMirai API設定 ==="

# 既存のNginx設定を確認
echo "既存のNginx設定を確認中..."
if [ ! -f "/etc/nginx/nginx.conf" ]; then
    echo "エラー: Nginxがインストールされていません"
    exit 1
fi

# Nginxのバージョン確認
echo "Nginxバージョン:"
nginx -v

# 既存のconf.dディレクトリの確認
if [ ! -d "/etc/nginx/conf.d" ]; then
    echo "conf.dディレクトリが存在しません。作成中..."
    sudo mkdir -p /etc/nginx/conf.d
fi

# 既存の設定ファイルをバックアップ
echo "既存の設定をバックアップ中..."
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)

# nginx.confにconf.dのincludeが含まれているか確認
if ! grep -q "include /etc/nginx/conf.d/\*.conf;" /etc/nginx/nginx.conf; then
    echo "nginx.confにconf.dのincludeを追加中..."
    sudo sed -i '/http {/a\    include /etc/nginx/conf.d/*.conf;' /etc/nginx/nginx.conf
fi

# Mirai API設定ファイルをコピー
echo "Mirai API設定ファイルをコピー中..."
sudo cp nginx/conf.d/mirai-api.conf /etc/nginx/conf.d/

# ドメイン名の設定
read -p "ドメイン名を入力してください (例: api.example.com): " DOMAIN_NAME
if [ -n "$DOMAIN_NAME" ]; then
    echo "ドメイン名を設定中: $DOMAIN_NAME"
    sudo sed -i "s/your-domain.com/$DOMAIN_NAME/g" /etc/nginx/conf.d/mirai-api.conf
    sudo sed -i "s/www.your-domain.com/www.$DOMAIN_NAME/g" /etc/nginx/conf.d/mirai-api.conf
fi

# SSL証明書ディレクトリの作成
echo "SSL証明書ディレクトリを作成中..."
sudo mkdir -p /etc/nginx/ssl

# SSL証明書の設定
read -p "SSL証明書を設定しますか？ (y/n): " SETUP_SSL
if [ "$SETUP_SSL" = "y" ] || [ "$SETUP_SSL" = "Y" ]; then
    if [ -n "$DOMAIN_NAME" ]; then
        echo "Let's Encrypt証明書を取得中..."
        sudo dnf install -y epel-release
        sudo dnf install -y certbot
        
        # 一時的にNginxを停止して証明書を取得
        sudo systemctl stop nginx
        sudo certbot certonly --standalone -d $DOMAIN_NAME
        
        # 証明書をコピー
        sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem /etc/nginx/ssl/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem /etc/nginx/ssl/key.pem
        sudo chmod 600 /etc/nginx/ssl/key.pem
        
        echo "SSL証明書の自動更新を設定中..."
        sudo crontab -l 2>/dev/null | { cat; echo "0 12 * * * /usr/bin/certbot renew --quiet && sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem /etc/nginx/ssl/cert.pem && sudo cp /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem /etc/nginx/ssl/key.pem && sudo systemctl reload nginx"; } | sudo crontab -
    else
        echo "ドメイン名が設定されていないため、SSL証明書の設定をスキップします"
    fi
fi

# Nginx設定のテスト
echo "Nginx設定をテスト中..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx設定は正常です"
    
    # Nginxの再起動
    echo "Nginxを再起動中..."
    sudo systemctl restart nginx
    
    # ステータス確認
    sudo systemctl status nginx --no-pager -l
    
    echo ""
    echo "=== 設定完了 ==="
    echo "Mirai API設定が正常に追加されました"
    echo ""
    echo "設定ファイル: /etc/nginx/conf.d/mirai-api.conf"
    echo "SSL証明書: /etc/nginx/ssl/"
    echo ""
    echo "次のステップ:"
    echo "1. Mirai APIサーバーを起動してください"
    echo "2. ファイアウォールでポート80,443を開放してください"
    echo "3. ドメインのDNS設定を確認してください"
    echo ""
    echo "テスト:"
    echo "  curl -f http://$DOMAIN_NAME/health"
    echo "  curl -f https://$DOMAIN_NAME/health"
else
    echo "❌ Nginx設定にエラーがあります"
    echo "設定を確認してください:"
    echo "  sudo nginx -t"
    echo "  sudo nano /etc/nginx/conf.d/mirai-api.conf"
    exit 1
fi
