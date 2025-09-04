from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Mirai API Server",
    description="AlmaLinuxで動作するPython APIサーバー",
    version="1.0.0"
)

# CORSミドルウェアを追加（外部からのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限してください
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# レスポンス用のモデル
class TestResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {"message": "Mirai API Server is running!"}

@app.get("/test", response_model=TestResponse)
async def test_endpoint():
    """テスト用エンドポイント - JSONを返す"""
    return TestResponse(
        status="success",
        message="テストエンドポイントが正常に動作しています",
        data={
            "server": "Mirai API Server",
            "platform": "AlmaLinux",
            "language": "Python",
            "framework": "FastAPI",
            "timestamp": "2024-01-01T00:00:00Z",
            "version": "1.0.0"
        }
    )

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "service": "mirai-api",
        "uptime": "running"
    }

@app.get("/api/info")
async def api_info():
    """API情報を返すエンドポイント"""
    return {
        "api_name": "Mirai API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "ルートエンドポイント"},
            {"path": "/test", "method": "GET", "description": "テスト用JSONレスポンス"},
            {"path": "/health", "method": "GET", "description": "ヘルスチェック"},
            {"path": "/api/info", "method": "GET", "description": "API情報"}
        ]
    }

if __name__ == "__main__":
    # 開発用サーバーの起動
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # 外部からのアクセスを許可
        port=8000,
        reload=True,  # 開発時は自動リロードを有効
        log_level="info"
    )
