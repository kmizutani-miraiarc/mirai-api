# 既存Nginx環境でのMirai API設定手順

## 概要

既にNginxが動作しているサーバーにMirai APIの設定を追加する手順を説明します。`nginx.conf`を変更せずに、`conf.d`ディレクトリに設定ファイルを追加する方法を使用します。

## 前提条件

- Nginxが既にインストール・動作している
- root権限またはsudo権限
- ドメイン名（SSL証明書用）
- Mirai APIサーバーが動作している（ポート8000）

## 1. 既存Nginx設定の確認

### 1.1 Nginxの状態確認

```bash
# Nginxの状態確認
sudo systemctl status nginx

# Nginxのバージョン確認
nginx -v

# 設定ファイルの場所確認
nginx -T | grep "configuration file"
```

### 1.2 既存設定の確認

```bash
# 現在の設定ファイルを確認
sudo nginx -t

# 既存のconf.dディレクトリの確認
ls -la /etc/nginx/conf.d/

# nginx.confの内容確認
sudo cat /etc/nginx/nginx.conf
```

## 2. 自動設定スクリプトの使用（推奨）

### 2.1 スクリプトの実行

```bash
# 自動設定スクリプトの実行
./nginx-setup-existing.sh
```

このスクリプトは`nginx/conf.d/mirai-api.conf`を使用して自動設定を行います。

スクリプトは以下の処理を自動実行します：
- 既存設定のバックアップ
- conf.dディレクトリの確認・作成
- nginx.confへのinclude追加
- Mirai API設定ファイルの配置
- SSL証明書の設定（オプション）

## 3. 手動設定手順（mirai-api.conf使用）

### 3.1 nginx.confの確認・修正

```bash
# nginx.confを編集
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

### 3.2 Mirai API設定ファイルの配置

```bash
# conf.dディレクトリに設定ファイルをコピー
sudo cp nginx/conf.d/mirai-api.conf /etc/nginx/conf.d/

# ドメイン名の設定
sudo nano /etc/nginx/conf.d/mirai-api.conf
```

`mirai-api.conf`ファイルの内容：
- レート制限設定
- アップストリーム設定（127.0.0.1:8000）
- HTTPからHTTPSへのリダイレクト
- SSL設定
- プロキシ設定
- セキュリティヘッダー

`your-domain.com`を実際のドメイン名に変更：
```nginx
server_name your-domain.com www.your-domain.com;
```

### 3.3 SSL証明書の設定

```bash
# SSL証明書ディレクトリの作成
sudo mkdir -p /etc/nginx/ssl

# Let's Encrypt証明書の取得
sudo dnf install -y epel-release
sudo dnf install -y certbot

# 証明書の取得（Nginxを一時停止）
sudo systemctl stop nginx
sudo certbot certonly --standalone -d your-domain.com

# 証明書のコピー
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /etc/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem /etc/nginx/ssl/key.pem
sudo chmod 600 /etc/nginx/ssl/key.pem
```

## 4. 設定のテストと適用

### 4.1 設定ファイルのテスト

```bash
# 設定ファイルの構文チェック
sudo nginx -t
```

### 4.2 Nginxの再起動

```bash
# Nginxの再起動
sudo systemctl restart nginx

# 状態確認
sudo systemctl status nginx
```

## 5. ファイアウォールの設定

### 5.1 必要なポートの開放

```bash
# HTTP (80) と HTTPS (443) の開放
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 6. 動作確認

### 6.1 ヘルスチェック

```bash
# 直接APIアクセス
curl -f http://localhost:8000/health

# Nginx経由でのアクセス
curl -f http://your-domain.com/health
curl -f https://your-domain.com/health
```

### 6.2 Swagger UIの確認

```bash
# Swagger UIの確認
curl -f https://your-domain.com/docs
```

## 7. 既存サイトとの共存

### 7.1 複数サイトの設定例

既存のWebサイトがある場合の設定例：

```nginx
# /etc/nginx/conf.d/mirai-api.conf
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;  # サブドメインを使用
    
    # SSL設定...
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        # プロキシ設定...
    }
}

# 既存サイトの設定（例）
server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # 既存サイトの設定...
    root /var/www/html;
    index index.html;
}
```

### 7.2 パスベースの設定例

同じドメインでパスベースで分ける場合：

```nginx
# 既存サイトの設定
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # 既存サイト
    location / {
        root /var/www/html;
        index index.html;
    }
    
    # Mirai API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 8. トラブルシューティング

### 8.1 よくある問題

#### 設定ファイルの構文エラー
```bash
# エラーの詳細確認
sudo nginx -t

# 設定ファイルの確認
sudo nano /etc/nginx/conf.d/mirai-api.conf
```

#### ポートの競合
```bash
# 使用中のポートを確認
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443
```

#### SSL証明書エラー
```bash
# 証明書の確認
openssl x509 -in /etc/nginx/ssl/cert.pem -text -noout

# 証明書の更新
sudo certbot renew
```

### 8.2 ログの確認

```bash
# Nginxエラーログ
sudo tail -f /var/log/nginx/error.log

# Nginxアクセスログ
sudo tail -f /var/log/nginx/access.log

# システムログ
sudo journalctl -u nginx -f
```

## 9. メンテナンス

### 9.1 設定のバックアップ

```bash
# 設定ファイルのバックアップ
sudo cp /etc/nginx/conf.d/mirai-api.conf /etc/nginx/conf.d/mirai-api.conf.backup
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
```

### 9.2 SSL証明書の自動更新

```bash
# 自動更新の確認
sudo crontab -l

# 手動更新
sudo certbot renew
sudo systemctl reload nginx
```

## 10. パフォーマンスチューニング

### 10.1 既存設定との調整

```bash
# 既存のworker設定を確認
grep worker_processes /etc/nginx/nginx.conf
grep worker_connections /etc/nginx/nginx.conf

# 必要に応じて調整
sudo nano /etc/nginx/nginx.conf
```

### 10.2 キャッシュ設定の追加

```nginx
# /etc/nginx/conf.d/mirai-api.conf に追加
location /static/ {
    alias /var/www/mirai-api/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

**注意**: 既存のNginx設定を変更する前に、必ずバックアップを取ってください。
