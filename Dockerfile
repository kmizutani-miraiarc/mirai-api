# AlmaLinux 9をベースイメージとして使用
FROM almalinux:9

# メタデータを設定
LABEL maintainer="Mirai API Team"
LABEL description="Mirai API Server on AlmaLinux"

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージを更新し、Python3とpipをインストール
RUN dnf update -y && \
    dnf install -y python3 python3-pip python3-devel gcc curl \
    tesseract tesseract-langpack-jpn \
    poppler-utils --allowerasing && \
    dnf clean all

# Pythonのシンボリックリンクを作成（pythonコマンドでpython3を実行）
RUN ln -sf /usr/bin/python3 /usr/bin/python

# pipを最新版にアップグレード
RUN python -m pip install --upgrade pip

# アプリケーションの依存関係をコピー
COPY requirements.txt .

# Pythonの依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . .

# ポート8000を公開
EXPOSE 8000

# ヘルスチェックを追加
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# アプリケーションを起動
CMD ["python", "main.py"]
