# バウンスメール監視機能 本番環境デプロイ手順

## 概要

バウンスメール監視機能を本番環境にデプロイする手順を説明します。

## 前提条件

- 本番環境へのアクセス権限
- データベースへのアクセス権限
- サーバーへのSSHアクセス権限
- Google Cloud Consoleへのアクセス権限

## デプロイ手順

### 1. データベーススキーマの変更

#### 1.1 バックアップの取得

```bash
# データベースのバックアップを取得
mysqldump -u mirai_user -p mirai_base > backup_before_bounce_email_$(date +%Y%m%d_%H%M%S).sql
```

#### 1.2 スキーマ変更の実行

```bash
# 本番サーバーに接続
ssh user@production-server

# プロジェクトディレクトリに移動
cd /var/www/mirai-api

# SQLファイルを実行
mysql -u mirai_user -p mirai_base < database/change_is_email_invalid_to_enum.sql
```

または、Docker環境の場合：

```bash
docker exec -i mirai-mysql mysql -u mirai_user -pmirai_password mirai_base < mirai-api/database/change_is_email_invalid_to_enum.sql
```

#### 1.3 スキーマ変更の確認

```sql
-- データベースに接続
mysql -u mirai_user -p mirai_base

-- カラムの定義を確認
DESCRIBE satei_users;

-- 期待される結果:
-- is_email_invalid | enum('pending','valid','invalid') | YES | | pending | メールアドレス有効性: pending=確認中, valid=有効, invalid=無効
```

### 2. Gmail APIスコープの設定

#### 2.1 Google Cloud Consoleでの設定

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを選択
3. 「APIとサービス」→「OAuth同意画面」に移動
4. 「スコープ」セクションで以下のスコープを追加：
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`（既に存在する場合はスキップ）

#### 2.2 既存ユーザーの再認証

既存のGmail認証情報には`gmail.readonly`スコープが含まれていないため、再認証が必要です。

**手順**:
1. マイページにログイン
2. Gmail認証設定ページにアクセス
3. 「Gmail認証を再設定」をクリック
4. Google認証画面で、新しいスコープ（`gmail.readonly`）へのアクセスを許可

**対象ユーザー**:
- `noreply@miraiarc.jp`（バウンスメール監視に使用）

### 3. アプリケーションコードのデプロイ

#### 3.1 コードのデプロイ

```bash
# 本番サーバーに接続
ssh user@production-server

# プロジェクトディレクトリに移動
cd /var/www/mirai-api

# Gitから最新のコードを取得
git pull origin main

# または、特定のブランチから取得
git pull origin feature/bounce-email-monitoring
```

#### 3.2 アプリケーションの再起動

```bash
# mirai-apiを再起動
sudo systemctl restart mirai-api-server
# または
pm2 restart mirai-api

# mirai-baseを再起動
sudo systemctl restart mirai-base-server
# または
pm2 restart mirai-base
```

### 4. バウンスメール監視スクリプトのデプロイ

#### 4.1 スクリプトの配置確認

```bash
# スクリプトが存在することを確認
ls -la /var/www/mirai-api/scripts/check_bounce_emails.py

# 実行権限を確認・設定
chmod +x /var/www/mirai-api/scripts/check_bounce_emails.py
```

#### 4.2 systemd timerの設定

```bash
# サービスファイルとタイマーファイルをコピー
sudo cp /var/www/mirai-api/bounce-email-check.service /etc/systemd/system/
sudo cp /var/www/mirai-api/bounce-email-check.timer /etc/systemd/system/

# サービスファイルのパスを確認・修正（必要に応じて）
sudo vi /etc/systemd/system/bounce-email-check.service
# WorkingDirectory=/var/www/mirai-api
# ExecStart=/usr/bin/python3 /var/www/mirai-api/scripts/check_bounce_emails.py

# タイマーを有効化
sudo systemctl daemon-reload
sudo systemctl enable bounce-email-check.timer
sudo systemctl start bounce-email-check.timer
```

#### 4.3 タイマーの状態確認

```bash
# タイマーの状態を確認
sudo systemctl status bounce-email-check.timer

# タイマーの一覧を確認
sudo systemctl list-timers bounce-email-check.timer

# 次の実行時刻を確認
sudo systemctl list-timers | grep bounce-email-check
```

### 5. 動作確認

#### 5.1 手動実行によるテスト

```bash
# スクリプトを手動で実行
cd /var/www/mirai-api
python3 scripts/check_bounce_emails.py

# ログを確認
tail -f /var/www/mirai-api/logs/bounce_email_check.log
```

#### 5.2 ログの確認

```bash
# ログファイルを確認
tail -f /var/www/mirai-api/logs/bounce_email_check.log

# systemd journalを確認
sudo journalctl -u bounce-email-check.service -f
```

#### 5.3 データベースの確認

```sql
-- メールアドレスの状態を確認
SELECT email, is_email_invalid, created_at 
FROM satei_users 
ORDER BY created_at DESC 
LIMIT 10;

-- 期待される結果:
-- email | is_email_invalid | created_at
-- test@example.com | pending | 2026-01-26 ...
-- test2@example.com | valid | 2026-01-26 ...
-- test3@example.com | invalid | 2026-01-26 ...
```

### 6. フロントエンドの確認

#### 6.1 画面表示の確認

以下の画面で「確認中」「有効」「無効」のバッジが正しく表示されることを確認：

1. **査定依頼ユーザー一覧** (`/admin/satei/users`)
   - メールアドレスの下にバッジが表示される
   - 「確認中」（黄）、「有効」（緑）、「無効」（赤）

2. **査定物件依頼一覧** (`/admin/satei/list`)
   - メールアドレスの下にバッジが表示される

3. **査定依頼詳細** (`/admin/satei/detail/:id`)
   - メールアドレスの横にバッジが表示される

### 7. トラブルシューティング

#### 7.1 よくある問題と解決方法

**問題1: タイマーが起動しない**

```bash
# タイマーの状態を確認
sudo systemctl status bounce-email-check.timer

# タイマーを再起動
sudo systemctl restart bounce-email-check.timer

# ログを確認
sudo journalctl -u bounce-email-check.timer -n 50
```

**問題2: Gmail APIスコープエラー**

```
エラー: invalid_scope: Bad Request
```

**解決方法**:
- Google Cloud Consoleで`gmail.readonly`スコープが追加されているか確認
- ユーザーが再認証を行っているか確認

**問題3: バウンスメールが検知されない**

```bash
# ログを確認
tail -f /var/www/mirai-api/logs/bounce_email_check.log

# 手動で実行してエラーを確認
python3 scripts/check_bounce_emails.py
```

**問題4: メールアドレスが抽出できない**

- ログに「バウンスメールから送信先メールアドレスを抽出できませんでした」と表示される場合
- バウンスメールの本文構造が想定と異なる可能性
- ログのデバッグ情報を確認し、必要に応じて抽出ロジックを改善

### 8. ロールバック手順（問題が発生した場合）

#### 8.1 データベースのロールバック

```bash
# バックアップから復元
mysql -u mirai_user -p mirai_base < backup_before_bounce_email_YYYYMMDD_HHMMSS.sql
```

#### 8.2 タイマーの無効化

```bash
# タイマーを停止
sudo systemctl stop bounce-email-check.timer
sudo systemctl disable bounce-email-check.timer

# サービスファイルを削除（オプション）
sudo rm /etc/systemd/system/bounce-email-check.service
sudo rm /etc/systemd/system/bounce-email-check.timer
sudo systemctl daemon-reload
```

#### 8.3 コードのロールバック

```bash
# 前のバージョンに戻す
git checkout <previous-commit-hash>

# アプリケーションを再起動
sudo systemctl restart mirai-api-server
sudo systemctl restart mirai-base-server
```

## チェックリスト

デプロイ前の確認事項：

- [ ] データベースのバックアップを取得
- [ ] Google Cloud Consoleで`gmail.readonly`スコープを追加
- [ ] `noreply@miraiarc.jp`のGmail認証を再設定
- [ ] データベーススキーマの変更を実行
- [ ] アプリケーションコードをデプロイ
- [ ] アプリケーションを再起動
- [ ] バウンスメール監視スクリプトを配置
- [ ] systemd timerを設定・有効化
- [ ] 手動実行で動作確認
- [ ] フロントエンドの表示を確認

## 関連ファイル

- `mirai-api/database/change_is_email_invalid_to_enum.sql` - データベーススキーマ変更SQL
- `mirai-api/scripts/check_bounce_emails.py` - バウンスメール監視スクリプト
- `mirai-api/bounce-email-check.service` - systemdサービスファイル
- `mirai-api/bounce-email-check.timer` - systemdタイマーファイル
- `mirai-api/docs/BOUNCE_EMAIL_MONITORING.md` - 機能詳細ドキュメント

## 注意事項

1. **データベースバックアップ**: スキーマ変更前に必ずバックアップを取得してください
2. **再認証**: 既存のGmail認証情報には`gmail.readonly`スコープが含まれていないため、再認証が必要です
3. **実行頻度**: デフォルトでは10分ごとに実行されます。Gmail APIのレート制限に注意してください
4. **ログ管理**: ログファイルが大きくなりすぎないよう、定期的にローテーションを設定してください

## サポート

問題が発生した場合は、以下の情報を含めて報告してください：

- エラーメッセージ
- ログファイルの内容
- 実行したコマンド
- 環境情報（OS、Pythonバージョンなど）
