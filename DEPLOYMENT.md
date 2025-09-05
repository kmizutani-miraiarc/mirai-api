# Mirai API 本番デプロイ手順書

## 概要

このドキュメントでは、Mirai APIサーバーをAlmaLinux 9環境の本番サーバーにデプロイする手順を説明します。

## 前提条件

- AlmaLinux 9 サーバー
- root権限またはsudo権限
- ドメイン名（SSL証明書用）
- HubSpot APIキー

## 1. サーバー環境の準備

### 1.1 システムの更新

```bash
sudo dnf update -y
sudo dnf install -y curl wget git
```

### 1.2 Dockerのインストール

```bash
# Dockerリポジトリの追加
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Dockerのインストール
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Dockerサービスの開始と有効化
sudo systemctl start docker
sudo systemctl enable docker

# ユーザーをdockerグループに追加
sudo usermod -aG docker $USER
```

### 1.3 Docker Composeのインストール

```bash
# Docker Composeのインストール
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## 2. アプリケーションのデプロイ

### 2.1 アプリケーションディレクトリの作成

```bash
sudo mkdir -p /opt/mirai-api
sudo chown $USER:$USER /opt/mirai-api
cd /opt/mirai-api
```

### 2.2 アプリケーションファイルの配置

```bash
# Gitリポジトリからクローン（またはファイルをアップロード）
git clone <your-repository-url> .

# または、ローカルからファイルをコピー
# scp -r /path/to/mirai-api/* user@server:/opt/mirai-api/
```

### 2.3 環境変数の設定

```bash
# 環境変数ファイルの作成
cp env.prod.example .env.prod

# 環境変数を編集
nano .env.prod
```

`.env.prod`ファイルの内容例：
```bash
HUBSPOT_API_KEY=your_actual_hubspot_api_key
HUBSPOT_ID=your_actual_hubspot_id
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 2.4 必要なディレクトリの作成

```bash
mkdir -p logs/nginx
mkdir -p ssl
```

## 3. SSL証明書の設定

### 3.1 Let's Encrypt証明書の取得

```bash
# SSL設定スクリプトの実行
./setup-ssl.sh your-domain.com admin@your-domain.com
```

### 3.2 手動でのSSL証明書設定（オプション）

```bash
# Certbotのインストール
sudo dnf install -y epel-release
sudo dnf install -y certbot

# 証明書の取得
sudo certbot certonly --standalone -d your-domain.com

# 証明書のコピー
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown -R $USER:$USER ssl/
```

## 4. Nginx設定の更新

### 4.1 ドメイン名の設定

```bash
# nginx/nginx.confを編集
nano nginx/nginx.conf
```

`server_name _;` を `server_name your-domain.com;` に変更

### 4.2 docker-compose.prod.ymlの更新

```bash
# docker-compose.prod.ymlを編集
nano docker-compose.prod.yml
```

必要に応じてドメイン名やポート設定を調整

## 5. サービスの起動

### 5.1 自動デプロイスクリプトの使用

```bash
# デプロイスクリプトの実行
./deploy.sh
```

### 5.2 手動での起動

```bash
# Dockerイメージのビルド
docker-compose -f docker-compose.prod.yml build

# サービスの起動
docker-compose -f docker-compose.prod.yml up -d

# ヘルスチェック
curl http://localhost:8000/health
curl http://localhost/health
```

## 6. systemdサービスの設定

### 6.1 サービスファイルの配置

```bash
# systemdサービスファイルをコピー
sudo cp mirai-api.service /etc/systemd/system/

# systemdの再読み込み
sudo systemctl daemon-reload

# サービスの有効化
sudo systemctl enable mirai-api
```

### 6.2 サービスの管理

```bash
# サービスの開始
sudo systemctl start mirai-api

# サービスの状態確認
sudo systemctl status mirai-api

# サービスの停止
sudo systemctl stop mirai-api

# サービスの再起動
sudo systemctl restart mirai-api
```

## 7. ファイアウォールの設定

### 7.1 必要なポートの開放

```bash
# HTTP (80) と HTTPS (443) の開放
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# または特定のポートを開放
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
```

## 8. 監視とログ

### 8.1 ログの確認

```bash
# アプリケーションログ
docker-compose -f docker-compose.prod.yml logs -f mirai-api-server

# Nginxログ
docker-compose -f docker-compose.prod.yml logs -f nginx

# システムログ
sudo journalctl -u mirai-api -f
```

### 8.2 ヘルスチェック

```bash
# APIヘルスチェック
curl -f https://your-domain.com/health

# Swagger UIの確認
curl -f https://your-domain.com/docs
```

## 9. メンテナンス

### 9.1 アプリケーションの更新

```bash
# 新しいバージョンのデプロイ
git pull origin main
./deploy.sh
```

### 9.2 SSL証明書の更新

```bash
# 手動更新
sudo certbot renew

# 証明書の再コピー
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown -R $USER:$USER ssl/

# Nginxの再起動
docker-compose -f docker-compose.prod.yml restart nginx
```

### 9.3 バックアップ

```bash
# 設定ファイルのバックアップ
tar -czf backup-$(date +%Y%m%d).tar.gz .env.prod nginx/ ssl/ docker-compose.prod.yml
```

## 10. トラブルシューティング

### 10.1 よくある問題

#### ポートが使用中
```bash
# 使用中のポートを確認
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443

# プロセスの停止
sudo systemctl stop httpd  # Apacheの場合
sudo systemctl stop nginx  # 既存のNginxの場合
```

#### SSL証明書エラー
```bash
# 証明書の確認
openssl x509 -in ssl/cert.pem -text -noout

# 証明書の更新
./setup-ssl.sh your-domain.com admin@your-domain.com
```

#### Dockerコンテナが起動しない
```bash
# ログの確認
docker-compose -f docker-compose.prod.yml logs

# コンテナの状態確認
docker-compose -f docker-compose.prod.yml ps

# 強制再ビルド
docker-compose -f docker-compose.prod.yml build --no-cache
```

### 10.2 パフォーマンスチューニング

#### Nginxの設定調整
```bash
# nginx/nginx.confで以下を調整
worker_processes auto;  # CPUコア数に合わせる
worker_connections 1024;  # 必要に応じて増加
```

#### Dockerリソース制限
```bash
# docker-compose.prod.ymlに追加
services:
  mirai-api-server:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
```

## 11. セキュリティ考慮事項

### 11.1 ファイアウォール設定
- 必要最小限のポートのみ開放
- SSHポートの変更（22以外）
- 不要なサービスの停止

### 11.2 定期的な更新
- システムパッケージの更新
- Dockerイメージの更新
- SSL証明書の自動更新

### 11.3 ログ監視
- アクセスログの監視
- エラーログの監視
- 異常なアクセスの検出

## 12. 連絡先・サポート

問題が発生した場合は、以下の情報と共にサポートに連絡してください：

- エラーメッセージ
- ログファイル
- システム情報（OS、Dockerバージョンなど）
- 実行したコマンド

---

**注意**: 本番環境でのデプロイ前に、必ずステージング環境でテストを実施してください。
