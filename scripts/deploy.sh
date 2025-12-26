#!/bin/bash

# Mirai API デプロイスクリプト
# このスクリプトはサーバー側で実行されます

set -e  # エラー時に停止

# 設定
APP_NAME="mirai-api"
APP_DIR="/var/www/mirai-api"
SERVICE_NAME="mirai-api"
NGINX_CONFIG="/etc/nginx/conf.d/mirai-api.conf"
LOG_FILE="/var/log/mirai-api/deploy.log"

# ログディレクトリを作成
sudo mkdir -p /var/log/mirai-api
sudo chown www-data:www-data /var/log/mirai-api

# ログ関数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | sudo tee -a "$LOG_FILE"
}

log "Starting deployment process..."

# アプリケーションディレクトリを作成
sudo mkdir -p "$APP_DIR"
cd "$APP_DIR"

# 既存のアプリケーションを停止
log "Stopping existing application..."
sudo systemctl stop "$SERVICE_NAME" || true

# バックアップを作成（無効化）
# if [ -f "main.py" ]; then
#     BACKUP_FILE="backups/app.backup.$(date +%Y%m%d_%H%M%S).tar.gz"
#     log "Creating backup: $BACKUP_FILE"
#     sudo mkdir -p backups
#     sudo tar -czf "$BACKUP_FILE" --exclude='backups' --exclude='*.tar.gz' --exclude='.git' .
# fi

# Gitから最新のコードを取得
log "Pulling latest code from Git..."
sudo -u www-data git fetch origin
sudo -u www-data git reset --hard origin/main

# 権限を設定
log "Setting permissions..."
sudo chown -R www-data:www-data .
sudo chmod -R 755 .

# 仮想環境を作成・更新
log "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    sudo python3 -m venv venv
fi

# 依存関係をインストール
log "Installing dependencies..."
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install -r requirements.txt

# 環境変数ファイルを確認
if [ ! -f ".env" ]; then
    log "Warning: .env file not found. Please create it manually."
    log "Copy from env.example and configure your settings."
fi

# systemdサービスファイルを作成/更新
log "Creating systemd service..."
sudo tee /etc/systemd/system/"$SERVICE_NAME".service > /dev/null <<EOF
[Unit]
Description=Mirai API Server
After=network.target mysql.service
Requires=mysql.service

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10

# ログ設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# セキュリティ設定
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

# systemdをリロード
sudo systemctl daemon-reload

# アプリケーションを起動
log "Starting application..."
sudo systemctl start "$SERVICE_NAME"
sudo systemctl enable "$SERVICE_NAME"

# ヘルスチェック
log "Performing health check..."
sleep 10

# 複数回ヘルスチェックを試行
for i in {1..5}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log "Health check passed!"
        break
    else
        log "Health check failed (attempt $i/5), retrying in 5 seconds..."
        sleep 5
    fi
    
    if [ $i -eq 5 ]; then
        log "Health check failed after 5 attempts. Rolling back..."
        
        # ロールバック（バックアップが無効化されているため、ロールバックも無効化）
        # sudo systemctl stop "$SERVICE_NAME"
        # if [ -f "backups/app.backup.*.tar.gz" ]; then
        #     LATEST_BACKUP=$(ls -t backups/app.backup.*.tar.gz | head -1)
        #     sudo tar -xzf "$LATEST_BACKUP"
        #     sudo systemctl start "$SERVICE_NAME"
        #     log "Rollback completed."
        # fi
        exit 1
    fi
done

# Nginx設定を確認
if [ ! -f "$NGINX_CONFIG" ]; then
    log "Warning: Nginx configuration not found at $NGINX_CONFIG"
    log "Please configure Nginx manually."
else
    # Nginx設定をテスト
    if sudo nginx -t; then
        log "Nginx configuration is valid."
        sudo systemctl reload nginx
        log "Nginx reloaded."
    else
        log "Error: Nginx configuration is invalid!"
        exit 1
    fi
fi

# デプロイ完了
log "Deployment completed successfully!"
log "Application is running on http://localhost:8000"

# 古いバックアップを削除（7日以上古いもの）（無効化）
# log "Cleaning up old backups..."
# find "$APP_DIR/backups" -name "app.backup.*.tar.gz" -type f -mtime +7 -exec sudo rm -f {} \; 2>/dev/null || true

log "Deployment process finished."
