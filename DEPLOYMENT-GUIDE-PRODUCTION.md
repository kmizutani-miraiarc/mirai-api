# Mirai API 本番環境デプロイメント手順書

## 概要

Mirai APIの本番環境へのデプロイメント手順書です。販売集計レポートの新機能追加と物件別販売取引レポートの実装を含む最新の変更を本番環境に反映します。

## 主要な変更内容

### 1. HubSpot API の拡張
- 新しい取引プロパティの追加（物件紹介日、資料開示日、調査検討日、買付取得日、見込み確度B/A設定日、見送り日、失注日）
- 取引の関連付け情報（associations）の取得機能追加
- 物件カスタムオブジェクト（bukken）との関連付け機能

### 2. 販売集計レポートの新機能
- 当月物件紹介数
- 当月資料開示数
- 当月調査/検討数
- 当月買付取得数
- 当月見込み確度B数
- 当月見込み確度A数
- 当月見送り数
- 当月失注数

### 3. 物件別販売取引レポートの実装
- 物件別ステージ集計
- 担当者物件別集計
- HubSpot関連付け情報を使用した正確な物件判定
- キャッシュ機能によるパフォーマンス向上

## デプロイメント手順

### 1. 事前準備

#### 1.1 環境変数の確認
```bash
# 必須の環境変数
HUBSPOT_API_KEY=your_hubspot_api_key
DB_HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=your_database_name
```

#### 1.2 依存関係の確認
```bash
# Python 3.9以上が必要
python3 --version

# 必要なパッケージ
pip install -r requirements.txt
```

### 2. コードのデプロイ

#### 2.1 リポジトリの更新
```bash
# 本番サーバーにSSH接続
ssh your_production_server

# アプリケーションディレクトリに移動
cd /path/to/mirai-api

# 最新のコードを取得
git pull origin main

# 依存関係の更新
pip install -r requirements.txt
```

#### 2.2 設定ファイルの確認
```bash
# 環境変数ファイルの確認
cat .env

# 設定の検証
python -c "from config import Config; print('Config validation:', Config.validate_config())"
```

### 3. データベースの更新

#### 3.1 APIキーテーブルの確認
```bash
# データベース接続確認
python -c "
import asyncio
from database.connection import get_connection
async def test():
    conn = await get_connection()
    print('Database connection successful')
    conn.close()
asyncio.run(test())
"
```

#### 3.2 マイグレーション（必要に応じて）
```bash
# データベーススキーマの更新が必要な場合
# 現在の実装では新しいテーブルは不要
```

### 4. アプリケーションの起動

#### 4.1 プロセス管理（PM2使用の場合）
```bash
# 既存のプロセスを停止
pm2 stop mirai-api

# 新しいコードで再起動
pm2 start main.py --name mirai-api --interpreter python3

# プロセス状態の確認
pm2 status mirai-api
pm2 logs mirai-api
```

#### 4.2 直接起動の場合
```bash
# アプリケーションの起動
python main.py

# バックグラウンド実行
nohup python main.py > app.log 2>&1 &
```

### 5. 動作確認

#### 5.1 ヘルスチェック
```bash
# APIの動作確認
curl -X GET "http://localhost:8000/health"

# API情報の確認
curl -X GET "http://localhost:8000/api/info"
```

#### 5.2 HubSpot API接続確認
```bash
# HubSpot API接続テスト
curl -X GET "http://localhost:8000/hubspot/owners" \
  -H "X-API-Key: your_api_key"
```

#### 5.3 新しい機能のテスト
```bash
# 取引検索API（新しいプロパティ含む）
curl -X POST "http://localhost:8000/hubspot/deals/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "pipeline": "682910274",
    "properties": [
      "dealname",
      "dealstage",
      "amount",
      "hubspot_owner_id",
      "createdate",
      "introduction_datetime",
      "deal_disclosure_date",
      "deal_survey_review_date",
      "purchase_date",
      "deal_probability_b_date",
      "deal_probability_a_date",
      "deal_farewell_date",
      "deal_lost_date",
      "contract_date",
      "settlement_date"
    ],
    "limit": 10
  }'
```

### 6. Nginx設定の更新（必要に応じて）

#### 6.1 プロキシ設定の確認
```nginx
# /etc/nginx/sites-available/mirai-api
server {
    listen 80;
    server_name your-api-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 6.2 Nginx設定の再読み込み
```bash
# 設定ファイルの構文チェック
nginx -t

# Nginxの再読み込み
systemctl reload nginx
```

### 7. ログ監視

#### 7.1 アプリケーションログの確認
```bash
# PM2使用の場合
pm2 logs mirai-api

# 直接起動の場合
tail -f app.log

# システムログの確認
journalctl -u mirai-api -f
```

#### 7.2 エラーログの監視
```bash
# エラーログの確認
grep -i error /var/log/mirai-api/error.log

# リアルタイム監視
tail -f /var/log/mirai-api/error.log
```

## トラブルシューティング

### 1. よくある問題と解決方法

#### 1.1 HubSpot API接続エラー
```bash
# エラー: 401 Unauthorized
# 解決方法: APIキーの確認
echo $HUBSPOT_API_KEY

# エラー: 429 Too Many Requests
# 解決方法: レート制限の確認と待機
```

#### 1.2 データベース接続エラー
```bash
# エラー: データベース接続失敗
# 解決方法: 接続情報の確認
python -c "
from config import Config
print('DB_HOST:', Config.DB_HOST)
print('DB_USER:', Config.DB_USER)
print('DB_NAME:', Config.DB_NAME)
"
```

#### 1.3 新しいプロパティが取得できない
```bash
# エラー: プロパティが存在しない
# 解決方法: HubSpotでプロパティが作成されているか確認
# HubSpot管理画面で以下のプロパティが存在することを確認:
# - introduction_datetime
# - deal_disclosure_date
# - deal_survey_review_date
# - purchase_date
# - deal_probability_b_date
# - deal_probability_a_date
# - deal_farewell_date
# - deal_lost_date
```

### 2. ロールバック手順

#### 2.1 緊急時のロールバック
```bash
# 前のバージョンに戻す
git checkout HEAD~1

# 依存関係の再インストール
pip install -r requirements.txt

# アプリケーションの再起動
pm2 restart mirai-api
```

#### 2.2 データベースのロールバック
```bash
# データベースのバックアップから復元（必要に応じて）
# 現在の実装では新しいテーブルは追加していないため、通常は不要
```

## パフォーマンス最適化

### 1. メモリ使用量の監視
```bash
# メモリ使用量の確認
ps aux | grep python
free -h

# PM2使用の場合
pm2 monit
```

### 2. API応答時間の監視
```bash
# 応答時間の測定
time curl -X GET "http://localhost:8000/health"

# 負荷テスト（必要に応じて）
# ab -n 100 -c 10 http://localhost:8000/health
```

## セキュリティ考慮事項

### 1. APIキーの管理
- 環境変数での管理
- ログファイルへの出力禁止
- 定期的なキーのローテーション

### 2. アクセス制御
- 適切なCORS設定
- APIキーによる認証
- レート制限の実装

### 3. ログの管理
- 機密情報のログ出力禁止
- ログファイルの適切な権限設定
- 定期的なログローテーション

## 監視とアラート

### 1. ヘルスチェック
```bash
# 定期的なヘルスチェック（cron設定例）
*/5 * * * * curl -f http://localhost:8000/health || echo "API is down" | mail -s "Mirai API Alert" admin@example.com
```

### 2. ログ監視
```bash
# エラーログの監視
tail -f /var/log/mirai-api/error.log | grep -i "error\|exception\|failed"
```

## 今後の改善点

### 1. キャッシュ機能の追加
- Redisを使用したAPIレスポンスキャッシュ
- データベースクエリの最適化

### 2. 監視機能の強化
- Prometheus + Grafanaによるメトリクス監視
- アラート機能の実装

### 3. セキュリティの強化
- APIレート制限の実装
- より詳細なアクセスログ

## 連絡先

デプロイメントに関する問題や質問がある場合は、開発チームまでご連絡ください。

---

**最終更新日**: 2025年10月24日  
**バージョン**: 1.0.0  
**作成者**: Mirai Development Team

