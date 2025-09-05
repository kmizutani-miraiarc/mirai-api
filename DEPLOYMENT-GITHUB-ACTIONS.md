# GitHub Actions 自動デプロイ完全ガイド

このガイドでは、GitHub Actionsを使用してMirai APIを自動デプロイする完全な手順を説明します。

## 📋 目次

1. [前提条件](#前提条件)
2. [サーバー初期設定](#サーバー初期設定)
3. [GitHub Actions設定](#github-actions設定)
4. [初回デプロイ](#初回デプロイ)
5. [自動デプロイのテスト](#自動デプロイのテスト)
6. [監視とメンテナンス](#監視とメンテナンス)
7. [トラブルシューティング](#トラブルシューティング)

## 前提条件

### 必要なもの

- **GitHubリポジトリ**: コードがプッシュされている
- **VPSサーバー**: AlmaLinux 9 または Ubuntu 20.04+
- **ドメイン**: `api.miraiarc.co.jp` (オプション)
- **SSHアクセス**: サーバーへのSSH接続権限

### サーバー要件

- **CPU**: 2コア以上
- **メモリ**: 4GB以上
- **ストレージ**: 20GB以上
- **OS**: AlmaLinux 9 / Ubuntu 20.04+ / CentOS 8+

## サーバー初期設定

### 1. サーバーに接続

```bash
ssh user@your-server-ip
```

### 2. リポジトリをクローン

```bash
# ホームディレクトリに移動
cd ~

# リポジトリをクローン
git clone https://github.com/your-username/mirai-api.git
cd mirai-api
```

### 3. 初期設定スクリプトを実行

```bash
# スクリプトに実行権限を付与
chmod +x scripts/server-setup.sh

# 初期設定を実行
sudo ./scripts/server-setup.sh
```

**注意**: スクリプト内のGitリポジトリURLを実際のリポジトリURLに変更してください。

このスクリプトは以下を自動実行します：

- システムパッケージの更新
- Python 3、MySQL、Nginxのインストール
- データベースとユーザーの作成
- Nginx設定ファイルの作成
- ファイアウォール設定
- 監視スクリプトの設定

### 4. 環境変数の設定

```bash
# 環境変数ファイルを作成
sudo cp /var/www/mirai-api/.env.template /var/www/mirai-api/.env
sudo nano /var/www/mirai-api/.env
```

`.env`ファイルの内容：

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

### 5. SSL証明書の設定

```bash
# Let's Encrypt証明書を取得
sudo certbot --nginx -d api.miraiarc.co.jp --non-interactive --agree-tos --email your-email@example.com
```

## GitHub Actions設定

### 1. SSH鍵の生成

ローカルマシンでSSH鍵を生成：

```bash
# SSH鍵を生成
ssh-keygen -t rsa -b 4096 -C "github-actions@miraiarc.co.jp"

# 公開鍵をサーバーにコピー
ssh-copy-id -i ~/.ssh/id_rsa.pub user@your-server-ip

# 秘密鍵の内容を確認（GitHub Secrets用）
cat ~/.ssh/id_rsa
```

### 2. GitHub Secretsの設定

GitHubリポジトリで以下のシークレットを設定：

1. **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** をクリック
3. 以下のシークレットを追加：

| シークレット名 | 値 | 説明 |
|---------------|-----|------|
| `SERVER_HOST` | `123.456.789.012` | サーバーのIPアドレス |
| `SERVER_USER` | `root` | SSH接続ユーザー名 |
| `SERVER_SSH_KEY` | `-----BEGIN OPENSSH...` | SSH秘密鍵の完全な内容 |
| `SERVER_PORT` | `22` | SSH接続ポート |

### 3. ワークフローファイルの確認

`.github/workflows/deploy.yml` ファイルが正しく配置されていることを確認：

```yaml
name: Deploy to Production Server

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    # ... ワークフローの詳細
```

## 初回デプロイ

### 1. 手動デプロイのテスト

GitHub Actionsで手動実行：

1. GitHubリポジトリの **Actions** タブをクリック
2. **Deploy to Production Server** ワークフローを選択
3. **Run workflow** をクリック
4. **main** ブランチを選択して実行

### 2. デプロイの監視

```bash
# サーバー側でログを監視
sudo journalctl -u mirai-api -f

# デプロイログを確認
sudo tail -f /var/log/mirai-api/deploy.log
```

### 3. ヘルスチェック

```bash
# ローカルヘルスチェック
curl http://localhost:8000/health

# 外部ヘルスチェック
curl https://api.miraiarc.co.jp/health
```

## 自動デプロイのテスト

### 1. テスト用の変更をコミット

```bash
# ローカルで小さな変更を加える
echo "# Test deployment" >> README.md

# 変更をコミット・プッシュ
git add README.md
git commit -m "Test automatic deployment"
git push origin main
```

### 2. GitHub Actionsの実行確認

1. GitHubリポジトリの **Actions** タブを確認
2. 新しいワークフロー実行が開始されることを確認
3. 各ステップが正常に完了することを確認

### 3. デプロイ結果の確認

```bash
# サーバー側でアプリケーションの状態確認
sudo systemctl status mirai-api

# ログの確認
sudo journalctl -u mirai-api --since "5 minutes ago"
```

## 監視とメンテナンス

### 1. ログの監視

```bash
# アプリケーションログ
sudo journalctl -u mirai-api -f

# デプロイログ
sudo tail -f /var/log/mirai-api/deploy.log

# 監視ログ
sudo tail -f /var/log/mirai-api/monitor.log

# Nginxログ
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 2. システムリソースの監視

```bash
# CPU・メモリ使用率
htop

# ディスク使用率
df -h

# プロセス確認
ps aux | grep mirai-api
```

### 3. データベースの監視

```bash
# MySQL接続確認
mysql -u mirai_user -p mirai_base

# データベースサイズ確認
mysql -u mirai_user -p -e "SELECT table_schema AS 'Database', ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)' FROM information_schema.tables WHERE table_schema = 'mirai_base' GROUP BY table_schema;"
```

### 4. バックアップの設定

```bash
# データベースバックアップのcron設定
sudo crontab -e

# 以下を追加（毎日午前2時にバックアップ）
0 2 * * * mysqldump -u mirai_user -p mirai_base > /backup/mirai_base_$(date +\%Y\%m\%d).sql
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. SSH接続エラー

**問題**: GitHub ActionsでSSH接続に失敗

**解決方法**:
```bash
# SSH接続をテスト
ssh -i ~/.ssh/id_rsa user@your-server-ip

# SSH鍵の権限を確認
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
```

#### 2. デプロイ失敗

**問題**: デプロイ中にエラーが発生

**解決方法**:
```bash
# 手動でロールバック
sudo systemctl stop mirai-api
sudo rm -rf /var/www/mirai-api/main.py /var/www/mirai-api/hubspot /var/www/mirai-api/database
LATEST_BACKUP=$(ls -t /var/www/mirai-api/backups/app.backup.*.tar.gz | head -1)
sudo tar -xzf "$LATEST_BACKUP"
sudo systemctl start mirai-api
```

#### 3. データベース接続エラー

**問題**: アプリケーションがデータベースに接続できない

**解決方法**:
```bash
# MySQLサービスの状態確認
sudo systemctl status mysql

# データベース接続テスト
mysql -u mirai_user -p mirai_base

# 環境変数の確認
sudo cat /var/www/mirai-api/.env
```

#### 4. Nginx設定エラー

**問題**: Nginxが正常に動作しない

**解決方法**:
```bash
# Nginx設定のテスト
sudo nginx -t

# Nginxの再起動
sudo systemctl restart nginx

# 設定ファイルの確認
sudo cat /etc/nginx/conf.d/mirai-api.conf
```

#### 5. アプリケーションが起動しない

**問題**: systemdサービスが起動しない

**解決方法**:
```bash
# サービスの状態確認
sudo systemctl status mirai-api

# 詳細なログ確認
sudo journalctl -u mirai-api -n 50

# 手動でアプリケーションを起動
cd /var/www/mirai-api
sudo -u www-data ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

### 緊急時の対応

#### 1. 緊急停止

```bash
# アプリケーションを停止
sudo systemctl stop mirai-api

# Nginxを停止
sudo systemctl stop nginx
```

#### 2. 緊急復旧

```bash
# 最新のバックアップから復旧
sudo systemctl stop mirai-api
sudo rm -rf /var/www/mirai-api/main.py /var/www/mirai-api/hubspot /var/www/mirai-api/database
LATEST_BACKUP=$(ls -t /var/www/mirai-api/backups/app.backup.*.tar.gz | head -1)
sudo tar -xzf "$LATEST_BACKUP"
sudo systemctl start mirai-api
```

#### 3. ログの収集

```bash
# 問題調査用のログを収集
sudo journalctl -u mirai-api --since "1 hour ago" > /tmp/mirai-api-error.log
sudo tail -100 /var/log/nginx/error.log >> /tmp/mirai-api-error.log
sudo systemctl status mirai-api >> /tmp/mirai-api-error.log
```

## セキュリティのベストプラクティス

### 1. 定期的な更新

```bash
# システムパッケージの更新
sudo apt update && sudo apt upgrade -y

# Python依存関係の更新
cd /var/www/mirai-api
sudo venv/bin/pip install --upgrade -r requirements.txt
```

### 2. ログの監視

```bash
# 不正アクセスの監視
sudo tail -f /var/log/nginx/access.log | grep -E "(40[0-9]|50[0-9])"

# エラーログの監視
sudo tail -f /var/log/nginx/error.log
```

### 3. バックアップの確認

```bash
# バックアップファイルの確認
ls -la /backup/

# バックアップの復元テスト
mysql -u mirai_user -p mirai_base < /backup/mirai_base_20240101.sql
```

## まとめ

このガイドに従うことで、GitHub Actionsを使用した自動デプロイシステムが構築できます。

### 主な利点

- **自動化**: mainブランチへのプッシュで自動デプロイ
- **安全性**: ロールバック機能付き
- **監視**: 包括的なログとヘルスチェック
- **スケーラビリティ**: 簡単に新しいサーバーに展開可能

### 次のステップ

1. 本番環境でのテスト
2. 監視アラートの設定
3. パフォーマンスの最適化
4. セキュリティの強化

何か問題が発生した場合は、ログを確認し、このガイドのトラブルシューティングセクションを参照してください。
