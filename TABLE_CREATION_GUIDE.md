# 物件買取実績テーブル作成ガイド

## 問題

エラー: `Table 'mirai_base.purchase_achievements' doesn't exist`

このエラーは、データベースに `purchase_achievements` テーブルが存在しないことを示しています。

## 解決方法

### 方法1: APIサーバーを再起動（自動的にテーブル作成）

**推奨**: `main.py` にテーブル自動作成処理を追加しました。APIサーバーを再起動すると、テーブルが存在しない場合に自動的に作成されます。

```bash
# APIサーバーを再起動
sudo systemctl restart mirai-api

# ログを確認してテーブル作成を確認
sudo journalctl -u mirai-api -f
```

ログに以下のメッセージが表示されれば成功です：
```
物件買取実績テーブルが存在しないため、作成します...
物件買取実績テーブルを作成しました
物件買取実績テーブルの初期化が完了しました
```

### 方法2: SQLスクリプトを直接実行

本番環境でデータベースに直接接続してテーブルを作成します：

```bash
# SQLスクリプトを実行
mysql -u root -p mirai_base < database/create_purchase_achievements_table.sql

# または、スタンドアロン版を使用
mysql -u root -p mirai_base < database/create_purchase_achievements_table_standalone.sql
```

### 方法3: シェルスクリプトを使用

```bash
cd /var/www/mirai-api
./scripts/create_table_direct.sh
```

### 方法4: Pythonスクリプトを使用

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/create_purchase_achievements_table.py
```

### 方法5: 検証スクリプトを使用（推奨）

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/verify_purchase_achievements_setup.py
```

このスクリプトは以下を自動的に実行します：
- データベース接続の確認
- テーブルの存在確認
- テーブルが存在しない場合、自動的に作成
- サービスの動作確認

## テーブル作成の確認

### SQLで確認

```sql
-- MySQLに接続
mysql -u root -p mirai_base

-- テーブルの存在確認
SHOW TABLES LIKE 'purchase_achievements';

-- テーブル構造の確認
DESCRIBE purchase_achievements;

-- インデックスの確認
SHOW INDEX FROM purchase_achievements;
```

### Pythonスクリプトで確認

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 -c "
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from database.connection import db_connection

async def check():
    await db_connection.create_pool()
    result = await db_connection.execute_query(\"\"\"
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = 'purchase_achievements'
    \"\"\")
    if result and result[0]['count'] > 0:
        print('✅ テーブルが存在します')
        # テーブル構造を確認
        columns = await db_connection.execute_query('DESCRIBE purchase_achievements')
        print(f'カラム数: {len(columns)}')
        for col in columns:
            print(f\"  - {col.get('Field') or col.get('field')}: {col.get('Type') or col.get('type')}\")
    else:
        print('❌ テーブルが存在しません')
    await db_connection.close_pool()

asyncio.run(check())
"
```

## トラブルシューティング

### データベース接続エラー

**症状**: `Access denied for user 'mirai_user'@'...'`

**解決方法**:
1. 環境変数を確認: `cat /var/www/mirai-api/.env | grep MYSQL`
2. データベースユーザーの権限を確認
3. データベースが起動しているか確認: `sudo systemctl status mysql`

### テーブル作成エラー

**症状**: `Table 'mirai_base.purchase_achievements' already exists`

**解決方法**:
- このエラーは無視しても問題ありません。テーブルは既に存在しています。

### 権限エラー

**症状**: `Access denied for user '...'@'...' to database 'mirai_base'`

**解決方法**:
1. データベースユーザーに適切な権限を付与:
   ```sql
   GRANT ALL PRIVILEGES ON mirai_base.* TO 'mirai_user'@'%';
   FLUSH PRIVILEGES;
   ```

2. rootユーザーで実行:
   ```bash
   sudo mysql -u root -p mirai_base < database/create_purchase_achievements_table.sql
   ```

## 確認手順

### 1. テーブルの存在確認

```bash
mysql -u root -p mirai_base -e "SHOW TABLES LIKE 'purchase_achievements';"
```

### 2. テーブル構造の確認

```bash
mysql -u root -p mirai_base -e "DESCRIBE purchase_achievements;"
```

### 3. APIエンドポイントの確認

```bash
# APIサーバーを再起動
sudo systemctl restart mirai-api

# ログを確認
sudo journalctl -u mirai-api -f | grep purchase_achievements

# APIエンドポイントをテスト
curl -X GET "http://localhost:8000/purchase-achievements?limit=10" \
  -H "X-API-Key: your-api-key"
```

## 次のステップ

テーブルが作成されたら：

1. **APIサーバーを再起動**: `sudo systemctl restart mirai-api`
2. **APIエンドポイントをテスト**: テストスクリプトまたは手動でテスト
3. **データの作成**: APIエンドポイントを使用してデータを作成

## 関連ファイル

- `database/create_purchase_achievements_table.sql`: テーブル作成SQL
- `database/create_purchase_achievements_table_standalone.sql`: スタンドアロン版SQL
- `scripts/create_purchase_achievements_table.py`: Pythonスクリプト
- `scripts/create_table_direct.sh`: シェルスクリプト
- `scripts/verify_purchase_achievements_setup.py`: 検証スクリプト
- `main.py`: アプリケーション起動時にテーブルを自動作成

