# Docker MySQLコンテナへの接続方法

## 接続情報

### mirai-mysqlコンテナ
- **コンテナ名**: `mirai-mysql`
- **ホストポート**: `3306`
- **データベース名**: `mirai_base`
- **ユーザー**: `mirai_user`
- **パスワード**: `mirai_password`
- **rootパスワード**: `rootpassword`

## 接続方法

### 方法1: Dockerコンテナ内から接続（推奨）

```bash
# コンテナ内でMySQLに接続
docker exec -it mirai-mysql mysql -umirai_user -pmirai_password mirai_base

# またはrootユーザーで接続
docker exec -it mirai-mysql mysql -uroot -prootpassword mirai_base
```

### 方法2: ホストマシンから接続

```bash
# ホストの3306ポート経由で接続
mysql -h 127.0.0.1 -P 3306 -umirai_user -pmirai_password mirai_base

# またはrootユーザーで接続
mysql -h 127.0.0.1 -P 3306 -uroot -prootpassword mirai_base
```

### 方法3: SQLファイルを実行

```bash
# コンテナ内でSQLファイルを実行
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base < /path/to/your/file.sql

# 例: フェーズ集計テーブルを作成
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base < mirai-api/database/create_contact_phase_summary_table.sql
```

### 方法4: クエリを直接実行

```bash
# 単一のクエリを実行
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "SHOW TABLES;"

# データを確認
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "SELECT * FROM contact_phase_summary LIMIT 10;"
```

## よく使うコマンド

### テーブル一覧を確認

```bash
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "SHOW TABLES;"
```

### テーブル構造を確認

```bash
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "DESCRIBE contact_phase_summary;"
```

### データを確認

```bash
# 最新の集計データを確認
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "SELECT * FROM contact_phase_summary ORDER BY aggregation_date DESC LIMIT 20;"

# 集計日ごとの件数を確認
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "SELECT aggregation_date, COUNT(*) as count FROM contact_phase_summary GROUP BY aggregation_date ORDER BY aggregation_date DESC;"
```

### データを削除

```bash
# 特定の集計日のデータを削除
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "DELETE FROM contact_phase_summary WHERE aggregation_date = '2024-01-15';"

# すべてのデータを削除（注意！）
docker exec -i mirai-mysql mysql -uroot -prootpassword mirai_base -e "DELETE FROM contact_phase_summary;"
```

## 接続確認

### コンテナの状態確認

```bash
docker ps | grep mysql
```

### コンテナのログ確認

```bash
docker logs mirai-mysql
```

### コンテナ内でシェルにアクセス

```bash
docker exec -it mirai-mysql bash
```

## トラブルシューティング

### 接続できない場合

1. **コンテナが起動しているか確認**
   ```bash
   docker ps | grep mirai-mysql
   ```

2. **コンテナを再起動**
   ```bash
   docker restart mirai-mysql
   ```

3. **ポートが使用されているか確認**
   ```bash
   lsof -i :3306
   ```

### パスワードエラーの場合

docker-compose.ymlで設定されているパスワードを確認してください：
- `MYSQL_ROOT_PASSWORD: rootpassword`
- `MYSQL_PASSWORD: mirai_password`

## 注意事項

- 本番環境では、パスワードを環境変数で管理することを推奨します
- データベースのバックアップを定期的に取得してください
- 本番環境のデータを削除する際は十分注意してください


