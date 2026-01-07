#!/bin/bash
# フェーズ集計バッチスクリプトの手動実行用スクリプト

set -e

# カラー出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}フェーズ集計バッチスクリプトを実行します${NC}"

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}プロジェクトディレクトリ: $PROJECT_DIR${NC}"

# 仮想環境の確認
if [ -d "$PROJECT_DIR/venv" ]; then
    echo -e "${GREEN}仮想環境を有効化します${NC}"
    source "$PROJECT_DIR/venv/bin/activate"
else
    echo -e "${RED}エラー: 仮想環境が見つかりません${NC}"
    echo -e "${YELLOW}仮想環境を作成してください:${NC}"
    echo "  cd $PROJECT_DIR"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# 環境変数ファイルの確認
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}警告: .envファイルが見つかりません${NC}"
    if [ -f "$PROJECT_DIR/env.example" ]; then
        echo -e "${YELLOW}env.exampleから.envを作成してください${NC}"
    fi
fi

# ログディレクトリを作成（ローカル環境用）
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}ログディレクトリ: $LOG_DIR${NC}"

# スクリプトを実行
echo -e "${GREEN}バッチスクリプトを実行中...${NC}"
cd "$PROJECT_DIR"
python3 "$SCRIPT_DIR/sync_contact_phase_summary.py"

echo -e "${GREEN}実行が完了しました${NC}"





