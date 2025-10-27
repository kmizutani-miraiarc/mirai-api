#!/bin/bash

# Mirai API サーバー初期設定スクリプト
# このスクリプトはサーバー側で一度だけ実行します

set -e  # エラー時に停止

# 設定
APP_NAME="mirai-api"
APP_DIR="/var/www/mirai-api"
SERVICE_NAME="mirai-api"
NGINX_CONFIG="/etc/nginx/conf.d/mirai-api.conf"

echo "Setting up Mirai API server..."

# システムの更新
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 必要なパッケージをインストール
echo "Installing required packages..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    mysql-server \
    nginx \
    curl \
    git \
    htop \
    unzip

# MySQLの設定
echo "Configuring MySQL..."
sudo mysql_secure_installation

# データベースとユーザーを作成
echo "Creating database and user..."
sudo mysql -e "
CREATE DATABASE IF NOT EXISTS mirai_base CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'mirai_user'@'localhost' IDENTIFIED BY 'mirai_password_2024';
GRANT ALL PRIVILEGES ON mirai_base.* TO 'mirai_user'@'localhost';
FLUSH PRIVILEGES;
"

# アプリケーションディレクトリを作成
echo "Creating application directory..."
sudo mkdir -p "$APP_DIR"
sudo chown www-data:www-data "$APP_DIR"

# Gitリポジトリをクローン（初回のみ）
if [ ! -d "$APP_DIR/.git" ]; then
    echo "Cloning Git repository..."
    sudo -u www-data git clone https://github.com/your-username/mirai-api.git "$APP_DIR"
else
    echo "Git repository already exists, skipping clone."
fi

# ログディレクトリを作成
echo "Creating log directory..."
sudo mkdir -p /var/log/mirai-api
sudo chown www-data:www-data /var/log/mirai-api

# Nginx設定を作成
echo "Creating Nginx configuration..."
sudo tee "$NGINX_CONFIG" > /dev/null <<EOF
# Mirai API Nginx Configuration
upstream mirai_api {
    server 127.0.0.1:8000;
}

# Rate limiting
limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;

server {
    listen 80;
    server_name api.miraiarc.co.jp;
    
    # Redirect HTTP to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.miraiarc.co.jp;
    
    # SSL configuration (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/api.miraiarc.co.jp/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.miraiarc.co.jp/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Rate limiting
    limit_req zone=api burst=20 nodelay;
    
    # API endpoints
    location / {
        proxy_pass http://mirai_api;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeout settings
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://mirai_api/health;
        access_log off;
    }
    
    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        try_files \$uri =404;
    }
}
EOF

# Nginx設定をテスト
echo "Testing Nginx configuration..."
sudo nginx -t

# ファイアウォール設定
echo "Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Let's Encrypt証明書の取得
echo "Setting up SSL certificate..."
sudo apt install -y certbot python3-certbot-nginx

# 証明書を取得（ドメインが設定されている場合）
if [ ! -z "$DOMAIN" ]; then
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@miraiarc.co.jp
else
    echo "Please run the following command to get SSL certificate:"
    echo "sudo certbot --nginx -d api.miraiarc.co.jp --non-interactive --agree-tos --email your-email@example.com"
fi

# デプロイスクリプトをコピー
echo "Setting up deploy script..."
sudo cp scripts/deploy.sh /var/www/mirai-api/deploy.sh
sudo chmod +x /var/www/mirai-api/deploy.sh

# 環境変数ファイルのテンプレートを作成
echo "Creating environment file template..."
sudo tee "$APP_DIR/.env.template" > /dev/null <<EOF
# Mirai API Environment Variables
# Copy this file to .env and configure your settings

# HubSpot API設定
HUBSPOT_API_KEY=your-hubspot-api-key-here
HUBSPOT_ID=your-hubspot-id-here

# MySQLデータベース設定
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=mirai_user
MYSQL_PASSWORD=mirai_password_2024
MYSQL_DATABASE=mirai_base
MYSQL_CHARSET=utf8mb4

# サーバー設定
HOST=0.0.0.0
PORT=8000
DEBUG=false
EOF

# データベースを初期化
echo "Initializing database..."
sudo mysql -u mirai_user -pmirai_password_2024 mirai_base < "$APP_DIR/database/init.sql"

# ログローテーション設定
echo "Setting up log rotation..."
sudo tee /etc/logrotate.d/mirai-api > /dev/null <<EOF
/var/log/mirai-api/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload mirai-api
    endscript
}
EOF

# 監視スクリプトを作成
echo "Creating monitoring script..."
sudo tee /var/www/mirai-api/monitor.sh > /dev/null <<EOF
#!/bin/bash
# Mirai API 監視スクリプト

SERVICE_NAME="mirai-api"
LOG_FILE="/var/log/mirai-api/monitor.log"

check_service() {
    if ! systemctl is-active --quiet \$SERVICE_NAME; then
        echo "\$(date): Service \$SERVICE_NAME is not running. Restarting..." >> \$LOG_FILE
        systemctl restart \$SERVICE_NAME
    fi
}

check_health() {
    if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "\$(date): Health check failed. Restarting service..." >> \$LOG_FILE
        systemctl restart \$SERVICE_NAME
    fi
}

check_service
check_health
EOF

sudo chmod +x /var/www/mirai-api/monitor.sh

# cronジョブを設定（5分ごとに監視）
echo "Setting up monitoring cron job..."
(crontab -l 2>/dev/null; echo "*/5 * * * * /var/www/mirai-api/monitor.sh") | crontab -

echo "Server setup completed!"
echo ""
echo "Next steps:"
echo "1. Update the Git repository URL in this script if needed"
echo "2. Configure your .env file: sudo nano $APP_DIR/.env"
echo "3. Set up GitHub Actions secrets"
echo "4. Push to main branch to trigger deployment"
echo ""
echo "Important files:"
echo "- Application directory: $APP_DIR"
echo "- Nginx config: $NGINX_CONFIG"
echo "- Deploy script: $APP_DIR/deploy.sh"
echo "- Environment template: $APP_DIR/.env.template"




