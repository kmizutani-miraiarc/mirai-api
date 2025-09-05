# GitHub Actions 自動デプロイ設定ガイド

このガイドでは、GitHub Actionsを使用してmainブランチにPushした際に自動でサーバーにデプロイする設定方法を説明します。

## 前提条件

- GitHubリポジトリが作成済み
- サーバー（VPS）へのSSHアクセス権限
- サーバーにPython 3.11+、MySQL、Nginxがインストール済み

## 1. GitHub Secrets の設定

GitHubリポジトリの設定で以下のシークレットを追加してください：

### 必要なシークレット

| シークレット名 | 説明 | 例 |
|---------------|------|-----|
| `SERVER_HOST` | サーバーのIPアドレスまたはドメイン | `123.456.789.012` または `api.miraiarc.co.jp` |
| `SERVER_USER` | SSH接続用のユーザー名 | `root` または `ubuntu` |
| `SERVER_SSH_KEY` | SSH秘密鍵（完全な内容） | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `SERVER_PORT` | SSH接続ポート | `22` |

### シークレットの設定方法

1. GitHubリポジトリにアクセス
2. **Settings** タブをクリック
3. 左サイドバーの **Secrets and variables** → **Actions** をクリック
4. **New repository secret** をクリック
5. 上記の各シークレットを追加

### SSH鍵の生成と設定

サーバーにSSH鍵が設定されていない場合：

```bash
# ローカルでSSH鍵を生成
ssh-keygen -t rsa -b 4096 -C "github-actions@miraiarc.co.jp"

# 公開鍵をサーバーにコピー
ssh-copy-id -i ~/.ssh/id_rsa.pub user@your-server-ip

# 秘密鍵の内容をコピー（GitHub Secrets用）
cat ~/.ssh/id_rsa
```

## 2. サーバー側の初期設定

### サーバー設定スクリプトの実行

```bash
# サーバーに接続
ssh user@your-server-ip

# リポジトリをクローン
git clone https://github.com/your-username/mirai-api.git
cd mirai-api

# 初期設定スクリプトを実行
sudo chmod +x scripts/server-setup.sh
sudo ./scripts/server-setup.sh
```

**注意**: スクリプト内のGitリポジトリURLを実際のリポジトリURLに変更してください。

### 環境変数の設定

```bash
# 環境変数ファイルを作成
sudo cp /var/www/mirai-api/.env.template /var/www/mirai-api/.env
sudo nano /var/www/mirai-api/.env
```

`.env`ファイルの内容例：

```bash
# HubSpot API設定
HUBSPOT_API_KEY=your-actual-hubspot-api-key
HUBSPOT_ID=your-actual-hubspot-id

# MySQLデータベース設定
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=mirai_user
MYSQL_PASSWORD=your-secure-mysql-password
MYSQL_DATABASE=mirai_base
MYSQL_CHARSET=utf8mb4

# サーバー設定
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

### SSL証明書の設定

```bash
# Let's Encrypt証明書を取得
sudo certbot --nginx -d api.miraiarc.co.jp --non-interactive --agree-tos --email your-email@example.com
```

## 3. デプロイのテスト

### 手動デプロイのテスト

GitHub Actionsのワークフローを手動実行してテスト：

1. GitHubリポジトリの **Actions** タブをクリック
2. **Deploy to Production Server** ワークフローを選択
3. **Run workflow** をクリック
4. **main** ブランチを選択して実行

### 自動デプロイのテスト

```bash
# ローカルで変更をコミット
git add .
git commit -m "Test deployment"
git push origin main
```

## 4. デプロイの監視

### ログの確認

```bash
# アプリケーションログ
sudo journalctl -u mirai-api -f

# デプロイログ
sudo tail -f /var/log/mirai-api/deploy.log

# Nginxログ
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### ヘルスチェック

```bash
# アプリケーションの状態確認
curl http://localhost:8000/health

# 外部からのアクセステスト
curl https://api.miraiarc.co.jp/health
```

## 5. トラブルシューティング

### よくある問題と解決方法

#### SSH接続エラー

```bash
# SSH接続をテスト
ssh -i ~/.ssh/id_rsa user@your-server-ip

# SSH鍵の権限を確認
chmod 600 ~/.ssh/id_rsa
```

#### デプロイ失敗時のロールバック

```bash
# 手動でロールバック
sudo systemctl stop mirai-api
sudo rm -rf /var/www/mirai-api/main.py /var/www/mirai-api/hubspot /var/www/mirai-api/database
LATEST_BACKUP=$(ls -t /var/www/mirai-api/backups/app.backup.*.tar.gz | head -1)
sudo tar -xzf "$LATEST_BACKUP"
sudo systemctl start mirai-api
```

#### データベース接続エラー

```bash
# MySQLサービスの状態確認
sudo systemctl status mysql

# データベース接続テスト
mysql -u mirai_user -p mirai_base
```

#### Nginx設定エラー

```bash
# Nginx設定のテスト
sudo nginx -t

# Nginxの再起動
sudo systemctl restart nginx
```

## 6. セキュリティの考慮事項

### ファイアウォール設定

```bash
# 必要なポートのみ開放
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### SSH鍵の管理

- 定期的にSSH鍵を更新
- 不要なSSH鍵は削除
- 強力なパスフレーズを使用

### 環境変数の保護

- `.env`ファイルの権限を適切に設定
- 機密情報はGitHub Secretsで管理
- 本番環境では`DEBUG=false`に設定

## 7. 監視とアラート

### 監視スクリプト

サーバー側で自動監視が設定されています：

```bash
# 監視ログの確認
sudo tail -f /var/log/mirai-api/monitor.log

# 監視スクリプトの手動実行
sudo /var/www/mirai-api/monitor.sh
```

### アラート設定

必要に応じて、以下のアラートを設定：

- サーバーリソース使用率の監視
- アプリケーションの応答時間監視
- エラーログの監視
- SSL証明書の有効期限監視

## 8. バックアップ戦略

### データベースバックアップ

```bash
# 日次バックアップスクリプト
sudo crontab -e

# 以下を追加
0 2 * * * mysqldump -u mirai_user -p mirai_base > /backup/mirai_base_$(date +\%Y\%m\%d).sql
```

### アプリケーションバックアップ

- デプロイ時に自動でバックアップが作成されます
- 7日以上古いバックアップは自動削除されます

これで、GitHub Actionsを使用した自動デプロイシステムの設定が完了です！
