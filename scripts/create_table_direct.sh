#!/bin/bash
# 物件買取実績テーブルを直接作成するスクリプト
# 本番環境でデータベースに直接接続してテーブルを作成

set -e

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ディレクトリの確認
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SQL_FILE="$PROJECT_DIR/database/create_purchase_achievements_table.sql"

log_info "物件買取実績テーブル作成スクリプトを開始します"
log_info "SQLファイル: $SQL_FILE"

# SQLファイルの存在確認
if [ ! -f "$SQL_FILE" ]; then
    log_error "SQLファイルが見つかりません: $SQL_FILE"
    exit 1
fi

# データベース接続情報の確認
if [ -f "$PROJECT_DIR/.env" ]; then
    log_info ".envファイルからデータベース接続情報を読み込み中..."
    source "$PROJECT_DIR/.env"
fi

# 環境変数の確認
DB_HOST=${MYSQL_HOST:-localhost}
DB_PORT=${MYSQL_PORT:-3306}
DB_USER=${MYSQL_USER:-root}
DB_PASSWORD=${MYSQL_PASSWORD:-}
DB_NAME=${MYSQL_DATABASE:-mirai_base}

log_info "データベース接続情報:"
log_info "  Host: $DB_HOST"
log_info "  Port: $DB_PORT"
log_info "  User: $DB_USER"
log_info "  Database: $DB_NAME"

# パスワードの入力（環境変数にない場合）
if [ -z "$DB_PASSWORD" ]; then
    log_warn "データベースパスワードが環境変数に設定されていません"
    read -sp "データベースパスワードを入力してください: " DB_PASSWORD
    echo
fi

# MySQLコマンドの確認
if ! command -v mysql &> /dev/null; then
    log_error "mysqlコマンドが見つかりません"
    exit 1
fi

# テーブル作成
log_info "テーブルを作成中..."
if [ -z "$DB_PASSWORD" ]; then
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" < "$SQL_FILE"
else
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$SQL_FILE"
fi

if [ $? -eq 0 ]; then
    log_info "✅ テーブルの作成が完了しました"
    
    # テーブルの存在確認
    log_info "テーブルの存在を確認中..."
    if [ -z "$DB_PASSWORD" ]; then
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" -e "SHOW TABLES LIKE 'purchase_achievements';"
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" -e "DESCRIBE purchase_achievements;"
    else
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "SHOW TABLES LIKE 'purchase_achievements';"
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" -e "DESCRIBE purchase_achievements;"
    fi
    
    log_info "✅ テーブルの作成が確認されました"
else
    log_error "❌ テーブルの作成に失敗しました"
    exit 1
fi

log_info "=" 
log_info "テーブル作成が完了しました"
log_info "=" 
log_info "次のステップ:"
log_info "1. APIサーバーを再起動: sudo systemctl restart mirai-api"
log_info "2. APIエンドポイントをテスト:"
log_info "   curl -X GET 'http://localhost:8000/purchase-achievements?limit=10' \\"
log_info "     -H 'X-API-Key: your-api-key'"


