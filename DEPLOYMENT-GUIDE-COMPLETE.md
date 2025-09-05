# Mirai API 完全デプロイ手順書

## 概要

このドキュメントでは、複数のサービスが既に動作しているVPSサーバーにMirai APIサーバーを安全に追加する完全な手順を説明します。既存のサービスに影響を与えることなく、新たなAPIサービスを追加します。

## 前提条件

- AlmaLinux 9 VPSサーバー
- 複数のサービスが既に動作している環境
- root権限またはsudo権限
- ドメイン名またはサブドメイン（SSL証明書用）
- HubSpot APIキー
- 既存サービスへの影響を最小限に抑える必要がある

## 目次

1. [既存環境の確認と安全チェック](#1-既存環境の確認と安全チェック)
2. [必要なソフトウェアのインストール](#2-必要なソフトウェアのインストール)
3. [アプリケーションのデプロイ](#3-アプリケーションのデプロイ)
4. [SSL証明書の設定](#4-ssl証明書の設定)
5. [Nginx設定](#5-nginx設定)
6. [systemdサービスの設定](#6-systemdサービスの設定)
7. [ファイアウォールの設定](#7-ファイアウォールの設定)
8. [監視とログ](#8-監視とログ)
9. [トラブルシューティング](#9-トラブルシューティング)
10. [ベストプラクティス](#10-ベストプラクティス)

---

## 1. 既存環境の確認と安全チェック

### 1.1 既存サービスの確認

```bash
# 動作中のサービスを確認
sudo systemctl list-units --type=service --state=running

# 使用中のポートを確認
sudo netstat -tlnp | grep LISTEN

# 既存のWebサーバーを確認
sudo systemctl status nginx
sudo systemctl status httpd
sudo systemctl status apache2

# 既存のPythonアプリケーションを確認
ps aux | grep python
ps aux | grep uvicorn
```

### 1.2 ポート競合の確認

```bash
# ポート8000が使用中かチェック
sudo netstat -tlnp | grep :8000

# ポート80, 443が使用中かチェック
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443

# 使用中のポート一覧
sudo ss -tlnp
```

**注意**: ポート8000が既に使用されている場合は、別のポート（例：8001）を使用するか、既存サービスを停止してください。

### 1.3 ディスク容量の確認

```bash
# ディスク使用量を確認
df -h

# /var/wwwディレクトリの容量を確認
du -sh /var/www/
```

### 1.4 システムリソースの確認

```bash
# メモリ使用量を確認
free -h

# CPU使用率を確認
top -bn1 | grep "Cpu(s)"

# システム負荷を確認
uptime
```

---

## 2. 必要なソフトウェアのインストール

### 2.1 システムの更新（必要最小限）

```bash
# セキュリティアップデートのみ実行
sudo dnf update --security -y

# 必要なパッケージのみインストール
sudo dnf install -y python3 python3-pip python3-devel gcc curl
```

### 2.2 Nginxの確認・インストール

```bash
# 既存のNginxを確認
sudo systemctl status nginx

# Nginxが未インストールの場合のみインストール
if ! command -v nginx &> /dev/null; then
    echo "Nginxをインストール中..."
    sudo dnf install -y nginx
    sudo systemctl enable nginx
else
    echo "Nginxは既にインストールされています"
fi

# 既存のNginx設定をバックアップ
if [ -f "/etc/nginx/nginx.conf" ]; then
    sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
    echo "既存のNginx設定をバックアップしました"
fi
```

---

## 3. アプリケーションのデプロイ

### 3.1 専用ユーザーの作成

```bash
# 専用ユーザーの作成（既存でない場合のみ）
if ! id "mirai-api" &>/dev/null; then
    sudo useradd -r -s /bin/false mirai-api
    echo "mirai-apiユーザーを作成しました"
else
    echo "mirai-apiユーザーは既に存在します"
fi
```

### 3.2 アプリケーションディレクトリの作成

```bash
# アプリケーションディレクトリの作成
sudo mkdir -p /var/www/mirai-api
sudo mkdir -p /var/www/mirai-api/logs

# ディレクトリの所有権設定
sudo chown -R mirai-api:mirai-api /var/www/mirai-api

# ディレクトリの権限設定
sudo chmod 755 /var/www/mirai-api
sudo chmod 755 /var/www/mirai-api/logs
```

### 3.3 アプリケーションファイルの配置

```bash
# アプリケーションディレクトリに移動
cd /var/www/mirai-api

# Python仮想環境の作成
sudo -u mirai-api python3 -m venv venv

# 仮想環境の有効化
sudo -u mirai-api /var/www/mirai-api/venv/bin/pip install --upgrade pip

# 依存関係のインストール
sudo -u mirai-api /var/www/mirai-api/venv/bin/pip install -r requirements.txt

# アプリケーションファイルのコピー
sudo cp -r /path/to/your/mirai-api/* /var/www/mirai-api/
sudo chown -R mirai-api:mirai-api /var/www/mirai-api
```

### 3.4 環境変数の設定

```bash
# 環境変数ファイルの作成
sudo -u mirai-api cp .env.prod.example .env.prod

# 環境変数の編集
sudo -u mirai-api nano .env.prod
```

`.env.prod`の内容例：
```bash
HUBSPOT_API_KEY=your_hubspot_api_key_here
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

## 4. SSL証明書の設定

### 4.1 既存証明書の確認

```bash
# 既存のLet's Encrypt証明書を確認
sudo certbot certificates

# 既存の証明書ファイルを確認
ls -la /etc/ssl/
ls -la /etc/letsencrypt/live/

# 既存のNginx設定でSSL証明書のパスを確認
sudo grep -r "ssl_certificate" /etc/nginx/
```

### 4.2 証明書の種類を確認

```bash
# 証明書の詳細情報を確認
sudo openssl x509 -in /etc/ssl/cert.pem -text -noout | grep -A 1 "Subject Alternative Name"

# または、Let's Encrypt証明書の場合
sudo openssl x509 -in /etc/letsencrypt/live/your-domain.com/fullchain.pem -text -noout | grep -A 1 "Subject Alternative Name"
```

### 4.3 証明書の取得方法

#### 方法1: サブドメイン専用証明書（推奨）

```bash
# サブドメイン専用の証明書を取得
sudo certbot certonly --webroot \
    -w /var/www/mirai-api \
    -d api.your-domain.com \
    --email admin@your-domain.com \
    --agree-tos \
    --no-eff-email
```

#### 方法2: 既存証明書にサブドメインを追加

```bash
# 既存証明書にサブドメインを追加
sudo certbot certonly --expand \
    -d your-domain.com \
    -d www.your-domain.com \
    -d api.your-domain.com \
    --webroot \
    -w /var/www/mirai-api
```

#### 方法3: ワイルドカード証明書

```bash
# ワイルドカード証明書を取得（DNS認証が必要）
sudo certbot certonly --manual \
    --preferred-challenges dns \
    -d *.your-domain.com \
    --email admin@your-domain.com \
    --agree-tos \
    --no-eff-email
```

### 4.4 Webrootディレクトリの準備

```bash
# Webrootディレクトリの作成
sudo mkdir -p /var/www/mirai-api/.well-known/acme-challenge

# 権限の設定
sudo chown -R www-data:www-data /var/www/mirai-api/
sudo chmod -R 755 /var/www/mirai-api/

# テストファイルの作成
echo "test" | sudo tee /var/www/mirai-api/.well-known/acme-challenge/test

# アクセステスト
curl http://your-domain.com/.well-known/acme-challenge/test
```

---

## 5. Nginx設定

### 5.1 既存Nginx環境での安全な設定

**重要**: 複数サービスが動作しているVPSでは、既存の設定を変更せずに新しいサービスを追加することが重要です。

#### 推奨方法: conf.dディレクトリに追加

```bash
# 既存のconf.dディレクトリを確認
ls -la /etc/nginx/conf.d/

# 既存の設定ファイルをバックアップ
sudo cp -r /etc/nginx/conf.d /etc/nginx/conf.d.backup.$(date +%Y%m%d_%H%M%S)

# mirai-api.confをコピー
sudo cp nginx/conf.d/mirai-api.conf /etc/nginx/conf.d/

# ドメイン名の設定
sudo nano /etc/nginx/conf.d/mirai-api.conf
```

#### ドメイン名の設定

`your-domain.com`を実際のドメイン名またはサブドメインに変更：

```nginx
# サブドメインを使用する場合（推奨）
server_name api.your-domain.com;

# または既存ドメインのパスベースで分ける場合
server_name your-domain.com;
location /api/ {
    proxy_pass http://127.0.0.1:8000/;
}
```

#### nginx.confの確認

```bash
# nginx.confにconf.dのincludeが含まれているか確認
sudo nano /etc/nginx/nginx.conf
```

`http`ブロック内に以下が含まれていることを確認：
```nginx
http {
    # 既存の設定...
    
    # conf.dディレクトリのinclude
    include /etc/nginx/conf.d/*.conf;
    
    # 既存の設定...
}
```

**含まれていない場合**は追加：
```bash
# nginx.confのhttpブロック内に追加
sudo sed -i '/http {/a\    include /etc/nginx/conf.d/*.conf;' /etc/nginx/nginx.conf
```

### 5.2 自動設定スクリプト（推奨）

```bash
# 既存Nginx環境用の自動設定スクリプトを実行
./nginx-setup-existing.sh
```

このスクリプトは以下を安全に実行します：
- 既存設定のバックアップ
- conf.dディレクトリの確認・作成
- nginx.confへのinclude追加（必要時のみ）
- mirai-api.confの配置
- SSL証明書の設定（オプション）
- ドメイン名の設定

### 5.3 Nginx設定のテスト

```bash
# 設定ファイルの構文チェック
sudo nginx -t

# 設定をリロード
sudo systemctl reload nginx

# 設定の確認
sudo nginx -T | grep -A 10 -B 5 "mirai-api"
```

---

## 6. systemdサービスの設定

### 6.1 サービスファイルの配置

```bash
# サービスファイルをコピー
sudo cp mirai-api.service /etc/systemd/system/

# systemdの設定をリロード
sudo systemctl daemon-reload

# サービスの有効化
sudo systemctl enable mirai-api
```

### 6.2 サービスの起動

```bash
# サービスの起動
sudo systemctl start mirai-api

# サービスの状態確認
sudo systemctl status mirai-api

# サービスのログ確認
sudo journalctl -u mirai-api --no-pager -l
```

### 6.3 サービスの自動起動設定

```bash
# サービスの有効化確認
sudo systemctl is-enabled mirai-api

# サービスの起動確認
sudo systemctl is-active mirai-api
```

---

## 7. ファイアウォールの設定

### 7.1 既存ファイアウォール設定の確認

```bash
# 現在のファイアウォール設定を確認
sudo firewall-cmd --list-all

# 既に開放されているポートを確認
sudo firewall-cmd --list-ports
sudo firewall-cmd --list-services
```

### 7.2 必要なポートの開放（必要時のみ）

```bash
# HTTP (80) と HTTPS (443) が既に開放されているかチェック
if ! sudo firewall-cmd --query-service=http; then
    echo "HTTP (80) ポートを開放中..."
    sudo firewall-cmd --permanent --add-service=http
fi

if ! sudo firewall-cmd --query-service=https; then
    echo "HTTPS (443) ポートを開放中..."
    sudo firewall-cmd --permanent --add-service=https
fi

# 変更を適用
sudo firewall-cmd --reload

# 設定を確認
sudo firewall-cmd --list-services
```

**注意**: 既存のサービスでHTTP/HTTPSが既に開放されている場合は、追加の設定は不要です。

---

## 8. 監視とログ

### 8.1 ログの確認

```bash
# アプリケーションログの確認
sudo journalctl -u mirai-api --no-pager -l

# Nginxログの確認
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# システムログの確認
sudo journalctl --no-pager -l
```

### 8.2 ログローテーションの設定

```bash
# ログローテーション設定ファイルの作成
sudo nano /etc/logrotate.d/mirai-api
```

`/etc/logrotate.d/mirai-api`の内容：
```
/var/www/mirai-api/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 mirai-api mirai-api
    postrotate
        systemctl reload mirai-api
    endscript
}
```

### 8.3 ヘルスチェック

```bash
# APIのヘルスチェック
curl -f http://localhost:8000/health

# 外部からのアクセステスト
curl -f https://your-domain.com/health
```

---

## 9. トラブルシューティング

### 9.1 よくある問題

#### サービスが起動しない
```bash
# ログの確認
sudo journalctl -u mirai-api --no-pager -l

# 設定ファイルの確認
sudo systemctl cat mirai-api

# 既存サービスとの競合確認
sudo systemctl list-units --type=service --state=failed
```

#### ポート競合
```bash
# ポート8000の使用状況を確認
sudo netstat -tlnp | grep :8000

# ポート8000を使用しているプロセスを確認
sudo lsof -i :8000

# 別のポートを使用する場合
sudo nano /etc/systemd/system/mirai-api-direct.service
# ExecStartのポート番号を変更（例：8001）
```

#### 既存サービスへの影響
```bash
# 既存のWebサービスの状態確認
sudo systemctl status nginx
sudo systemctl status httpd

# 既存サービスのログ確認
sudo journalctl -u nginx --no-pager -l
sudo journalctl -u httpd --no-pager -l
```

#### 権限エラー
```bash
# ファイルの所有権確認
ls -la /var/www/mirai-api/

# 所有権の修正
sudo chown -R mirai-api:mirai-api /var/www/mirai-api

# SELinuxコンテキストの確認
ls -Z /var/www/mirai-api/
```

#### Nginx設定エラー
```bash
# Nginx設定の構文チェック
sudo nginx -t

# 既存のNginx設定との競合確認
sudo nginx -T | grep -A 10 -B 10 "server_name"

# 設定ファイルのバックアップから復元
sudo cp /etc/nginx/nginx.conf.backup.* /etc/nginx/nginx.conf
```

#### Let's Encrypt認証エラー
```bash
# Webrootディレクトリの確認
ls -la /var/www/mirai-api/.well-known/acme-challenge/

# 権限の確認
sudo chown -R www-data:www-data /var/www/mirai-api/
sudo chmod -R 755 /var/www/mirai-api/

# アクセステスト
curl http://your-domain.com/.well-known/acme-challenge/test

# 証明書の取得（Standalone認証）
sudo systemctl stop nginx
sudo certbot certonly --standalone -d your-domain.com
sudo systemctl start nginx
```

### 9.2 パフォーマンス問題

#### メモリ使用量の確認
```bash
# メモリ使用量の確認
free -h
ps aux --sort=-%mem | head -10

# メモリ使用量の監視
htop
```

#### CPU使用率の確認
```bash
# CPU使用率の確認
top -bn1 | grep "Cpu(s)"
ps aux --sort=-%cpu | head -10

# CPU使用率の監視
htop
```

#### ディスク使用量の確認
```bash
# ディスク使用量の確認
df -h
du -sh /var/www/mirai-api/

# ディスク使用量の監視
iotop
```

---

## 10. ベストプラクティス

### 10.1 リソース管理

```bash
# システムリソースの監視
htop
iotop
nethogs

# メモリ使用量の監視
free -h
cat /proc/meminfo

# ディスク使用量の監視
df -h
du -sh /var/www/*
```

### 10.2 ログ管理

```bash
# ログローテーションの設定
sudo nano /etc/logrotate.d/mirai-api

# 複数サービスのログを統合監視
sudo journalctl -f -u mirai-api -u nginx -u httpd
```

### 10.3 バックアップ戦略

```bash
# 設定ファイルのバックアップ
sudo tar -czf /backup/mirai-api-config-$(date +%Y%m%d).tar.gz \
    /var/www/mirai-api/.env.prod \
    /etc/nginx/conf.d/mirai-api.conf \
    /etc/systemd/system/mirai-api-direct.service

# アプリケーションファイルのバックアップ
sudo tar -czf /backup/mirai-api-app-$(date +%Y%m%d).tar.gz \
    /var/www/mirai-api/ --exclude=/var/www/mirai-api/venv
```

### 10.4 監視とアラート

```bash
# サービス状態の監視スクリプト
cat > /usr/local/bin/check-mirai-api.sh << 'EOF'
#!/bin/bash
if ! systemctl is-active --quiet mirai-api; then
    echo "Mirai API service is down!" | mail -s "Service Alert" admin@your-domain.com
    systemctl restart mirai-api
fi
EOF

chmod +x /usr/local/bin/check-mirai-api.sh

# cronに追加（5分ごとにチェック）
echo "*/5 * * * * /usr/local/bin/check-mirai-api.sh" | sudo crontab -
```

### 10.5 セキュリティ強化

```bash
# ファイアウォールの詳細設定
sudo firewall-cmd --permanent --add-rich-rule="rule family='ipv4' source address='192.168.1.0/24' port protocol='tcp' port='8000' accept"
sudo firewall-cmd --permanent --add-rich-rule="rule family='ipv4' source address='10.0.0.0/8' port protocol='tcp' port='8000' accept"
sudo firewall-cmd --reload

# fail2banの設定（必要に応じて）
sudo dnf install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 10.6 自動更新の設定

```bash
# 証明書の自動更新設定
sudo crontab -e
```

以下の行を追加：
```bash
0 12 * * * /usr/bin/certbot renew --quiet && sudo systemctl reload nginx
```

---

## 自動デプロイスクリプト

### 完全自動デプロイ

```bash
# 自動デプロイスクリプトの実行
./deploy-direct.sh
```

### 段階的デプロイ

```bash
# 1. 既存環境の確認
./deploy-direct.sh

# 2. SSL証明書の設定
./setup-ssl-existing.sh your-domain.com api admin@your-domain.com

# 3. Nginx設定の追加
./nginx-setup-existing.sh
```

---

## まとめ

### デプロイの利点

- **既存サービスへの影響なし**: 既存のWebサービス、データベース、その他のアプリケーションに影響を与えません
- **リソース効率**: 既存のNginx、SSL証明書、ファイアウォール設定を再利用
- **安全な設定**: 既存設定のバックアップと段階的な変更
- **監視とメンテナンス**: 既存の監視システムとの統合が容易

### セキュリティ機能

- **非root実行**: 専用ユーザーでの実行
- **systemd統合**: システムサービスとして管理
- **ファイル権限制御**: 適切な権限設定
- **SELinux対応**: セキュリティポリシー適用

---

**重要**: 複数サービスが動作しているVPSでは、既存サービスへの影響を最小限に抑えることが最優先です。デプロイ前に必ずバックアップを取り、ステージング環境でテストを実施してください。
