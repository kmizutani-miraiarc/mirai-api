#!/bin/bash

# Mirai API Server 起動スクリプト

echo "Mirai API Server を起動しています..."

# 依存関係のインストール（初回のみ）
if [ ! -d "venv" ]; then
    echo "仮想環境を作成しています..."
    python3 -m venv venv
    source venv/bin/activate
    echo "依存関係をインストールしています..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# サーバーの起動
echo "サーバーを起動しています..."
echo "アクセスURL: http://localhost:8000"
echo "APIドキュメント: http://localhost:8000/docs"
echo "テストエンドポイント: http://localhost:8000/test"
echo ""
echo "停止するには Ctrl+C を押してください"
echo ""

python main.py
