# バウンスメール監視機能

## 概要

バウンスメール監視機能は、Gmailの受信トレイを定期的にチェックしてバウンスメール（配信失敗メール）を検知し、`satei_users`テーブルの`is_email_invalid`フラグを自動的に更新します。

## 機能

- Gmailの受信トレイを定期的にチェック
- バウンスメールを自動検知
- 元の送信先メールアドレスを抽出
- `satei_users`テーブルの`is_email_invalid`フラグを`TRUE`に更新

## 必要なGmail APIスコープ

バウンスメール監視には、以下のGmail APIスコープが必要です：

### 必須スコープ

1. **`https://www.googleapis.com/auth/gmail.readonly`**
   - Gmailの受信トレイを読み取るために必要
   - バウンスメールを検知するために必須

2. **`https://www.googleapis.com/auth/gmail.send`**
   - メール送信のために必要（既存機能）

### スコープの設定方法

#### 1. Google Cloud Consoleでの設定

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを選択
3. 「APIとサービス」→「認証情報」に移動
4. OAuth 2.0 クライアント IDを選択（または新規作成）
5. 「承認済みのリダイレクト URI」に以下を追加：
   - `http://localhost:3000/admin/gmail/callback`（ローカル環境）
   - `https://miraiarc.co.jp/admin/gmail/callback`（本番環境）

#### 2. OAuth同意画面でのスコープ設定

1. 「APIとサービス」→「OAuth同意画面」に移動
2. 「スコープ」セクションで以下のスコープを追加：
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`

#### 3. 既存の認証情報の再認証

既にGmail認証情報を登録しているユーザーは、以下の手順で再認証が必要です：

1. マイページにログイン
2. Gmail認証設定ページにアクセス
3. 「Gmail認証を再設定」をクリック
4. Google認証画面で、新しいスコープ（`gmail.readonly`）へのアクセスを許可

**注意**: 既存の認証情報では`gmail.readonly`スコープが含まれていないため、バウンスメール監視機能を使用するには再認証が必要です。

## インストールと設定

### 1. スクリプトの実行権限を設定

```bash
chmod +x mirai-api/scripts/check_bounce_emails.py
```

### 2. 定期実行の設定

#### systemd timerを使用する場合（推奨）

##### サービスファイルの作成

`/etc/systemd/system/bounce-email-check.service`:

```ini
[Unit]
Description=Check bounce emails for MiraiArc
After=network.target

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/var/www/mirai-api
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /var/www/mirai-api/scripts/check_bounce_emails.py
StandardOutput=journal
StandardError=journal
```

##### タイマーファイルの作成

`/etc/systemd/system/bounce-email-check.timer`:

```ini
[Unit]
Description=Check bounce emails every 10 minutes
Requires=bounce-email-check.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=10min
Unit=bounce-email-check.service

[Install]
WantedBy=timers.target
```

##### タイマーの有効化と起動

```bash
sudo systemctl daemon-reload
sudo systemctl enable bounce-email-check.timer
sudo systemctl start bounce-email-check.timer
```

##### タイマーの状態確認

```bash
sudo systemctl status bounce-email-check.timer
sudo systemctl list-timers bounce-email-check.timer
```

#### cronを使用する場合

```bash
# 10分ごとに実行
*/10 * * * * /usr/bin/python3 /var/www/mirai-api/scripts/check_bounce_emails.py >> /var/www/mirai-api/logs/bounce_email_check_cron.log 2>&1
```

### 3. 手動実行

```bash
cd /var/www/mirai-api
python3 scripts/check_bounce_emails.py
```

## 動作確認

### ログの確認

```bash
# ログファイルを確認
tail -f /var/www/mirai-api/logs/bounce_email_check.log

# systemd journalを確認
sudo journalctl -u bounce-email-check.service -f
```

### テスト実行

```bash
# 手動で実行して動作確認
python3 scripts/check_bounce_emails.py
```

## バウンスメールの検知パターン

以下のパターンでバウンスメールを検知します：

### 件名パターン

- `Delivery Status Notification`
- `Undelivered Mail Returned to Sender`
- `Mail Delivery Failed`
- `Delivery Failure`
- `Message not delivered`
- `Returned mail`
- `Mail delivery failed`
- `Delivery has failed`
- `Mail System Error`
- `Delivery Notification`
- `Failure Notice`
- `Mail Delivery Subsystem`
- `Mailer-Daemon`
- `Postmaster`
- `Mail Administrator`
- `自動送信`
- `配信エラー`
- `配信失敗`
- `メール配信エラー`
- `メール配信失敗`
- `未達`
- `返送`

### 本文パターン

- `delivery failure`
- `undelivered`
- `returned mail`
- `mail delivery failed`
- `message not delivered`
- `recipient address rejected`
- `user unknown`
- `no such user`
- `mailbox full`
- `quota exceeded`
- `address not found`
- `host unknown`
- `domain not found`
- `550`, `551`, `552`, `553`, `554`（SMTPエラーコード）
- `配信エラー`
- `配信失敗`
- `未達`

## メールアドレスの抽出方法

バウンスメール本文から、以下のパターンで元の送信先メールアドレスを抽出します：

1. `To: email@example.com`
2. `Original-Recipient: email@example.com`
3. `Final-Recipient: email@example.com`
4. `The following address(es) failed: email@example.com`
5. 本文内の最初のメールアドレス（送信元アドレスを除外）

## チェック対象の時間範囲

デフォルトでは、過去24時間のメールをチェックします。

`CHECK_TIME_RANGE_HOURS`変数で変更可能です（`check_bounce_emails.py`内）。

## トラブルシューティング

### エラー: "Insufficient Permission"

**原因**: Gmail APIの認証スコープが不足しています。

**解決方法**:
1. Google Cloud Consoleで`gmail.readonly`スコープを追加
2. ユーザーに再認証を依頼

### エラー: "Gmail認証情報が見つかりません"

**原因**: ユーザーのGmail認証情報がデータベースに登録されていません。

**解決方法**:
1. マイページでGmail認証を実行
2. 認証情報が正しく保存されているか確認

### バウンスメールが検知されない

**原因**: 
- バウンスメールの件名や本文が検知パターンに一致しない
- メールアドレスの抽出に失敗している

**解決方法**:
1. ログを確認して、バウンスメールが検知されているか確認
2. 必要に応じて検知パターンを追加（`check_bounce_emails.py`の`BOUNCE_SUBJECT_PATTERNS`を編集）

## 関連ファイル

- `mirai-api/scripts/check_bounce_emails.py` - バウンスメール検知スクリプト
- `mirai-api/routers/satei.py` - メール送信処理（`is_email_invalid`フラグの更新）
- `mirai-api/database/gmail_credentials.py` - Gmail認証情報管理

## 注意事項

1. **プライバシー**: バウンスメール監視は、送信元メールアドレス（noreply@miraiarc.jpなど）の受信トレイを読み取ります。適切な権限管理を行ってください。

2. **実行頻度**: 10分ごとの実行を推奨しますが、Gmail APIのレート制限に注意してください。

3. **再認証**: 既存のGmail認証情報には`gmail.readonly`スコープが含まれていないため、バウンスメール監視機能を使用するには再認証が必要です。

4. **ログ管理**: ログファイルが大きくなりすぎないよう、定期的にローテーションを設定してください。
