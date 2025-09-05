# Mirai API 本番デプロイ手順書

## 概要

このドキュメントでは、Mirai APIサーバーをAlmaLinux 9環境の本番サーバーに直接Pythonで実行する手順を説明します。

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

### 1.2 Python3のインストール

```bash
# Python3とpipのインストール
sudo dnf install -y python3 python3-pip python3-devel gcc

# 仮想環境用パッケージのインストール
sudo dnf install -y python3-venv
```

### 1.3 Nginxのインストール

```bash
# Nginxのインストール
sudo dnf install -y nginx

# Nginxサービスの有効化
sudo systemctl enable nginx
```

## 2. アプリケーションのデプロイ

### 2.1 アプリケーションディレクトリの作成

```bash
# アプリケーションディレクトリの作成
sudo mkdir -p /var/www/mirai-api
sudo mkdir -p /var/www/mirai-api/logs

# 専用ユーザーの作成
sudo useradd -r -s /bin/false mirai-api

# ディレクトリの所有権設定
sudo chown -R mirai-api:mirai-api /var/www/mirai-api
```

### 2.2 アプリケーションファイルの配置

```bash
# アプリケーションディレクトリに移動
cd /var/www/mirai-api

# Gitリポジトリからクローン（またはファイルをアップロード）
sudo -u mirai-api git clone <your-repository-url> .

# または、ローカルからファイルをコピー
# sudo cp -r /path/to/mirai-api/* /var/www/mirai-api/
# sudo chown -R mirai-api:mirai-api /var/www/mirai-api
```

### 2.3 Python仮想環境の作成

```bash
# Python仮想環境の作成
sudo -u mirai-api python3 -m venv venv

# 仮想環境の有効化と依存関係のインストール
sudo -u mirai-api /var/www/mirai-api/venv/bin/pip install --upgrade pip
sudo -u mirai-api /var/www/mirai-api/venv/bin/pip install -r requirements.txt
```

### 2.4 環境変数の設定

```bash
# 環境変数ファイルの作成
sudo -u mirai-api cp env.prod.example .env.prod

# 環境変数を編集
sudo -u mirai-api nano .env.prod
```

`.env.prod`ファイルの内容例：
```bash
HUBSPOT_API_KEY=your_actual_hubspot_api_key
HUBSPOT_ID=your_actual_hubspot_id
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## 3. SSL証明書の設定

### 3.1 Let's Encrypt証明書の取得

```bash
# Certbotのインストール
sudo dnf install -y epel-release
sudo dnf install -y certbot

# SSL証明書の取得
sudo certbot certonly --standalone -d your-domain.com

# 証明書ディレクトリの作成
sudo mkdir -p /etc/nginx/ssl

# 証明書のコピー
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /etc/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem /etc/nginx/ssl/key.pem
sudo chmod 600 /etc/nginx/ssl/key.pem
```

### 3.2 自動更新の設定

```bash
# 自動更新のcron設定
sudo crontab -e
```

以下の行を追加：
```bash
0 12 * * * /usr/bin/certbot renew --quiet && sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /etc/nginx/ssl/cert.pem && sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem /etc/nginx/ssl/key.pem && sudo systemctl reload nginx
```

## 4. Nginx設定

### 4.1 設定方法の選択

Nginx設定には3つの方法があります：

#### 方法0: 自動設定スクリプト（既存Nginx環境推奨）

```bash
# 既存Nginx環境用の自動設定スクリプトを実行
./nginx-setup-existing.sh
```

スクリプトが自動的に以下を実行します：
- 既存設定のバックアップ
- conf.dディレクトリの確認・作成
- nginx.confへのinclude追加
- mirai-api.confの配置
- SSL証明書の設定（オプション）
- ドメイン名の設定

#### 方法A: 完全なnginx.conf置き換え（新規インストール推奨）

```bash
# Nginx設定ファイルのコピー
sudo cp nginx/nginx-direct.conf /etc/nginx/nginx.conf

# ドメイン名の設定
sudo nano /etc/nginx/nginx.conf
```

`server_name _;` を `server_name your-domain.com;` に変更

#### 方法B: conf.dディレクトリに追加（既存Nginx環境推奨）

```bash
# conf.dディレクトリの確認
ls -la /etc/nginx/conf.d/

# mirai-api.confをコピー
sudo cp nginx/conf.d/mirai-api.conf /etc/nginx/conf.d/

# ドメイン名の設定
sudo nano /etc/nginx/conf.d/mirai-api.conf
```

`your-domain.com`を実際のドメイン名に変更

```bash
# nginx.confにconf.dのincludeが含まれているか確認
sudo nano /etc/nginx/nginx.conf
```

`http`ブロック内に以下が含まれていることを確認：
```nginx
http {
    # 既存の設定...
    
    # conf.dディレクトリのinclude（追加が必要な場合）
    include /etc/nginx/conf.d/*.conf;
    
    # 既存の設定...
}
```

### 4.2 Nginx設定のテスト

```bash
# 設定ファイルの構文チェック
sudo nginx -t

# Nginxの起動
sudo systemctl start nginx
```

## 5. systemdサービスの設定

### 5.1 サービスファイルの配置

```bash
# systemdサービスファイルをコピー
sudo cp mirai-api-direct.service /etc/systemd/system/

# systemdの再読み込み
sudo systemctl daemon-reload

# サービスの有効化
sudo systemctl enable mirai-api
```

### 5.2 サービスの起動

```bash
# サービスの開始
sudo systemctl start mirai-api

# サービスの状態確認
sudo systemctl status mirai-api
```

## 6. ファイアウォールの設定

### 6.1 必要なポートの開放

```bash
# HTTP (80) と HTTPS (443) の開放
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 7. 監視とログ

### 7.1 ログの確認

```bash
# アプリケーションログ
sudo journalctl -u mirai-api -f

# Nginxログ
sudo journalctl -u nginx -f

# システムログ
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 7.2 ヘルスチェック

```bash
# APIヘルスチェック
curl -f http://localhost:8000/health

# Nginx経由でのヘルスチェック
curl -f http://localhost/health

# Swagger UIの確認
curl -f http://localhost/docs
```

## 8. メンテナンス

### 8.1 アプリケーションの更新

```bash
# 新しいバージョンのデプロイ
cd /var/www/mirai-api
sudo -u mirai-api git pull origin main

# 依存関係の更新
sudo -u mirai-api /var/www/mirai-api/venv/bin/pip install -r requirements.txt

# サービスの再起動
sudo systemctl restart mirai-api
```

### 8.2 ログローテーションの設定

```bash
# logrotate設定の作成
sudo nano /etc/logrotate.d/mirai-api
```

以下の内容を追加：
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

## 9. パフォーマンスチューニング

### 9.1 Pythonアプリケーションの最適化

```bash
# ワーカー数の調整（CPUコア数に応じて）
sudo nano /etc/systemd/system/mirai-api-direct.service
```

`--workers 4` を適切な数に変更

### 9.2 Nginxの最適化

```bash
# Nginx設定の調整
sudo nano /etc/nginx/nginx.conf
```

以下の設定を調整：
```nginx
worker_processes auto;  # CPUコア数に合わせる
worker_connections 1024;  # 必要に応じて増加
```

## 10. セキュリティ強化

### 10.1 ファイル権限の設定

```bash
# アプリケーションファイルの権限設定
sudo chmod 755 /var/www/mirai-api
sudo chmod 644 /var/www/mirai-api/*.py
sudo chmod 600 /var/www/mirai-api/.env.prod
```

### 10.2 SELinuxの設定

```bash
# SELinuxコンテキストの設定
sudo setsebool -P httpd_can_network_connect 1
sudo setsebool -P httpd_can_network_relay 1
```

## 11. トラブルシューティング

### 11.1 よくある問題

#### サービスが起動しない
```bash
# ログの確認
sudo journalctl -u mirai-api --no-pager -l

# 設定ファイルの確認
sudo systemctl cat mirai-api
```

#### ポートが使用中
```bash
# 使用中のポートを確認
sudo netstat -tlnp | grep :8000
sudo netstat -tlnp | grep :80
```

#### 権限エラー
```bash
# ファイルの所有権確認
ls -la /var/www/mirai-api/

# 所有権の修正
sudo chown -R mirai-api:mirai-api /var/www/mirai-api
```

### 11.2 パフォーマンス問題

#### メモリ使用量の確認
```bash
# プロセスのメモリ使用量
ps aux | grep uvicorn

# システムリソース
free -h
top
```

#### ログファイルのサイズ確認
```bash
# ログファイルのサイズ
du -sh /var/www/mirai-api/logs/
du -sh /var/log/nginx/
```

## 12. アーキテクチャの特徴

### 直接実行のメリット
- **軽量**: コンテナオーバーヘッドなし
- **直接的なデバッグ**: システムログとの統合
- **リソース効率**: システムリソースの最適利用
- **シンプルな構成**: 管理が容易
- **高速起動**: 起動時間が短い

### セキュリティ機能
- **非root実行**: 専用ユーザーでの実行
- **systemd統合**: システムサービスとして管理
- **ファイル権限制御**: 適切な権限設定
- **SELinux対応**: セキュリティポリシー適用

---

**注意**: 本番環境でのデプロイ前に、必ずステージング環境でテストを実施してください。
