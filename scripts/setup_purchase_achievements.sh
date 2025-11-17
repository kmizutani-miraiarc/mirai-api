#!/bin/bash
# 物件買取実績機能のセットアップスクリプト

set -e

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ログ関数
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

log_info "物件買取実績機能のセットアップを開始します"
log_info "プロジェクトディレクトリ: $PROJECT_DIR"

# 仮想環境の確認
if [ -d "$PROJECT_DIR/venv" ]; then
    log_info "仮想環境が見つかりました"
    source "$PROJECT_DIR/venv/bin/activate"
else
    log_warn "仮想環境が見つかりません。作成しますか？ (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        log_info "仮想環境を作成中..."
        python3 -m venv "$PROJECT_DIR/venv"
        source "$PROJECT_DIR/venv/bin/activate"
        pip install -r "$PROJECT_DIR/requirements.txt"
    else
        log_error "仮想環境が必要です"
        exit 1
    fi
fi

# 環境変数の確認
log_info "環境変数を確認中..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    log_warn ".envファイルが見つかりません"
    if [ -f "$PROJECT_DIR/env.example" ]; then
        log_info "env.exampleから.envを作成しますか？ (y/n)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            cp "$PROJECT_DIR/env.example" "$PROJECT_DIR/.env"
            log_info ".envファイルを作成しました。必要に応じて編集してください"
        fi
    fi
fi

# データベース接続の確認
log_info "データベース接続を確認中..."
if python3 "$SCRIPT_DIR/verify_purchase_achievements_setup.py"; then
    log_info "データベース接続とテーブル作成が正常に完了しました"
else
    log_error "データベース接続またはテーブル作成に失敗しました"
    exit 1
fi

# APIサーバーの状態確認
log_info "APIサーバーの状態を確認中..."
if systemctl is-active --quiet mirai-api; then
    log_info "APIサーバーが起動しています"
    log_info "APIサーバーを再起動しますか？ (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        sudo systemctl restart mirai-api
        log_info "APIサーバーを再起動しました"
    fi
else
    log_warn "APIサーバーが起動していません"
    log_info "APIサーバーを起動しますか？ (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        sudo systemctl start mirai-api
        log_info "APIサーバーを起動しました"
    fi
fi

# セットアップ完了
log_info "=" 
log_info "セットアップが完了しました"
log_info "=" 
log_info "次のステップ:"
log_info "1. APIエンドポイントをテスト:"
log_info "   python3 $SCRIPT_DIR/test_purchase_achievements_api.py"
log_info "2. ドキュメントを確認:"
log_info "   docs/PURCHASE_ACHIEVEMENTS_QUICKSTART.md"
log_info "3. APIエンドポイントの使用方法:"
log_info "   README_PURCHASE_ACHIEVEMENTS.md"



