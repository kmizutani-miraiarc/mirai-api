from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn
import logging
from hubspot.owners import HubSpotOwnersClient
from hubspot.contacts import HubSpotContactsClient
from hubspot.companies import HubSpotCompaniesClient
from hubspot.config import Config

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class HubSpotResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    count: Optional[int] = None

# リクエスト用のモデル
class OwnerCreateRequest(BaseModel):
    email: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    type: str = "PERSON"

class OwnerUpdateRequest(BaseModel):
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None

class ContactCreateRequest(BaseModel):
    properties: Dict[str, Any]

class ContactUpdateRequest(BaseModel):
    properties: Dict[str, Any]

class CompanyCreateRequest(BaseModel):
    properties: Dict[str, Any]

class CompanyUpdateRequest(BaseModel):
    properties: Dict[str, Any]

# HubSpotクライアントのインスタンス
hubspot_owners_client = HubSpotOwnersClient()
hubspot_contacts_client = HubSpotContactsClient()
hubspot_companies_client = HubSpotCompaniesClient()

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
            {"path": "/api/info", "method": "GET", "description": "API情報"},
            {"path": "/hubspot/owners", "method": "GET", "description": "HubSpot担当者一覧取得"},
            {"path": "/hubspot/owners", "method": "POST", "description": "HubSpot担当者作成"},
            {"path": "/hubspot/owners/{owner_id}", "method": "GET", "description": "HubSpot担当者詳細取得"},
            {"path": "/hubspot/owners/{owner_id}", "method": "PATCH", "description": "HubSpot担当者情報更新"},
            {"path": "/hubspot/owners/{owner_id}", "method": "DELETE", "description": "HubSpot担当者削除"},
            {"path": "/hubspot/contacts", "method": "GET", "description": "HubSpotコンタクト一覧取得"},
            {"path": "/hubspot/contacts", "method": "POST", "description": "HubSpotコンタクト作成"},
            {"path": "/hubspot/contacts/{contact_id}", "method": "GET", "description": "HubSpotコンタクト詳細取得"},
            {"path": "/hubspot/contacts/{contact_id}", "method": "PATCH", "description": "HubSpotコンタクト情報更新"},
            {"path": "/hubspot/contacts/{contact_id}", "method": "DELETE", "description": "HubSpotコンタクト削除"},
            {"path": "/hubspot/companies", "method": "GET", "description": "HubSpot会社一覧取得"},
            {"path": "/hubspot/companies", "method": "POST", "description": "HubSpot会社作成"},
            {"path": "/hubspot/companies/{company_id}", "method": "GET", "description": "HubSpot会社詳細取得"},
            {"path": "/hubspot/companies/{company_id}", "method": "PATCH", "description": "HubSpot会社情報更新"},
            {"path": "/hubspot/companies/{company_id}", "method": "DELETE", "description": "HubSpot会社削除"},
            {"path": "/hubspot/health", "method": "GET", "description": "HubSpot API接続テスト"},
            {"path": "/hubspot/debug", "method": "GET", "description": "HubSpot設定デバッグ情報"}
        ]
    }

# HubSpot API エンドポイント
@app.get("/hubspot/owners", response_model=HubSpotResponse)
async def get_hubspot_owners():
    """HubSpot担当者一覧を取得"""
    try:
        if not Config.validate_config():
            return HubSpotResponse(
                status="error",
                message="HubSpot API設定が正しくありません。環境変数HUBSPOT_API_KEYとHUBSPOT_IDを設定してください。",
                data={"owners": []},
                count=0
            )
        
        owners = await hubspot_owners_client.get_owners()
        if not owners:
            return HubSpotResponse(
                status="warning",
                message="担当者が見つかりませんでした。APIキーが正しいか確認してください。",
                data={"owners": []},
                count=0
            )
        
        return HubSpotResponse(
            status="success",
            message="担当者一覧を正常に取得しました",
            data={"owners": owners},
            count=len(owners)
        )
    except Exception as e:
        logger.error(f"Failed to get HubSpot owners: {str(e)}")
        return HubSpotResponse(
            status="error",
            message=f"担当者一覧の取得に失敗しました: {str(e)}",
            data={"owners": []},
            count=0
        )

@app.get("/hubspot/owners/{owner_id}", response_model=HubSpotResponse)
async def get_hubspot_owner(owner_id: str):
    """HubSpot担当者詳細を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        owner = await hubspot_owners_client.get_owner_by_id(owner_id)
        if not owner:
            raise HTTPException(status_code=404, detail="指定された担当者が見つかりません")
        
        return HubSpotResponse(
            status="success",
            message="担当者詳細を正常に取得しました",
            data={"owner": owner}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot owner {owner_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"担当者詳細の取得に失敗しました: {str(e)}")

@app.post("/hubspot/owners", response_model=HubSpotResponse)
async def create_hubspot_owner(owner_data: OwnerCreateRequest):
    """HubSpot担当者を作成"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        owner = await hubspot_owners_client.create_owner(owner_data.dict())
        if not owner:
            raise HTTPException(status_code=500, detail="担当者の作成に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="担当者を正常に作成しました",
            data={"owner": owner}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create HubSpot owner: {str(e)}")
        raise HTTPException(status_code=500, detail=f"担当者の作成に失敗しました: {str(e)}")

@app.patch("/hubspot/owners/{owner_id}", response_model=HubSpotResponse)
async def update_hubspot_owner(owner_id: str, owner_data: OwnerUpdateRequest):
    """HubSpot担当者情報を更新"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        owner = await hubspot_owners_client.update_owner(owner_id, owner_data.dict())
        if not owner:
            raise HTTPException(status_code=404, detail="指定された担当者が見つからないか、更新に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="担当者情報を正常に更新しました",
            data={"owner": owner}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HubSpot owner {owner_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"担当者情報の更新に失敗しました: {str(e)}")

@app.delete("/hubspot/owners/{owner_id}", response_model=HubSpotResponse)
async def delete_hubspot_owner(owner_id: str):
    """HubSpot担当者を削除"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        success = await hubspot_owners_client.delete_owner(owner_id)
        if not success:
            raise HTTPException(status_code=404, detail="指定された担当者が見つからないか、削除に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="担当者を正常に削除しました",
            data={"owner_id": owner_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HubSpot owner {owner_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"担当者の削除に失敗しました: {str(e)}")

@app.get("/hubspot/contacts", response_model=HubSpotResponse)
async def get_hubspot_contacts(limit: int = 100, after: Optional[str] = None):
    """HubSpotコンタクト一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        contacts_data = await hubspot_contacts_client.get_contacts(limit=limit, after=after)
        return HubSpotResponse(
            status="success",
            message="コンタクト一覧を正常に取得しました",
            data=contacts_data,
            count=len(contacts_data.get("results", []))
        )
    except Exception as e:
        logger.error(f"Failed to get HubSpot contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"コンタクト一覧の取得に失敗しました: {str(e)}")

@app.get("/hubspot/contacts/{contact_id}", response_model=HubSpotResponse)
async def get_hubspot_contact(contact_id: str):
    """HubSpotコンタクト詳細を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        contact = await hubspot_contacts_client.get_contact_by_id(contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="指定されたコンタクトが見つかりません")
        
        return HubSpotResponse(
            status="success",
            message="コンタクト詳細を正常に取得しました",
            data={"contact": contact}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot contact {contact_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"コンタクト詳細の取得に失敗しました: {str(e)}")

@app.post("/hubspot/contacts", response_model=HubSpotResponse)
async def create_hubspot_contact(contact_data: ContactCreateRequest):
    """HubSpotコンタクトを作成"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        contact = await hubspot_contacts_client.create_contact(contact_data.dict())
        if not contact:
            raise HTTPException(status_code=500, detail="コンタクトの作成に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="コンタクトを正常に作成しました",
            data={"contact": contact}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create HubSpot contact: {str(e)}")
        raise HTTPException(status_code=500, detail=f"コンタクトの作成に失敗しました: {str(e)}")

@app.patch("/hubspot/contacts/{contact_id}", response_model=HubSpotResponse)
async def update_hubspot_contact(contact_id: str, contact_data: ContactUpdateRequest):
    """HubSpotコンタクト情報を更新"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        contact = await hubspot_contacts_client.update_contact(contact_id, contact_data.dict())
        if not contact:
            raise HTTPException(status_code=404, detail="指定されたコンタクトが見つからないか、更新に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="コンタクト情報を正常に更新しました",
            data={"contact": contact}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HubSpot contact {contact_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"コンタクト情報の更新に失敗しました: {str(e)}")

@app.delete("/hubspot/contacts/{contact_id}", response_model=HubSpotResponse)
async def delete_hubspot_contact(contact_id: str):
    """HubSpotコンタクトを削除"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        success = await hubspot_contacts_client.delete_contact(contact_id)
        if not success:
            raise HTTPException(status_code=404, detail="指定されたコンタクトが見つからないか、削除に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="コンタクトを正常に削除しました",
            data={"contact_id": contact_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HubSpot contact {contact_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"コンタクトの削除に失敗しました: {str(e)}")

@app.get("/hubspot/companies", response_model=HubSpotResponse)
async def get_hubspot_companies(limit: int = 100, after: Optional[str] = None):
    """HubSpot会社一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        companies_data = await hubspot_companies_client.get_companies(limit=limit, after=after)
        return HubSpotResponse(
            status="success",
            message="会社一覧を正常に取得しました",
            data=companies_data,
            count=len(companies_data.get("results", []))
        )
    except Exception as e:
        logger.error(f"Failed to get HubSpot companies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"会社一覧の取得に失敗しました: {str(e)}")

@app.get("/hubspot/companies/{company_id}", response_model=HubSpotResponse)
async def get_hubspot_company(company_id: str):
    """HubSpot会社詳細を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        company = await hubspot_companies_client.get_company_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="指定された会社が見つかりません")
        
        return HubSpotResponse(
            status="success",
            message="会社詳細を正常に取得しました",
            data={"company": company}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"会社詳細の取得に失敗しました: {str(e)}")

@app.post("/hubspot/companies", response_model=HubSpotResponse)
async def create_hubspot_company(company_data: CompanyCreateRequest):
    """HubSpot会社を作成"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        company = await hubspot_companies_client.create_company(company_data.dict())
        if not company:
            raise HTTPException(status_code=500, detail="会社の作成に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="会社を正常に作成しました",
            data={"company": company}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create HubSpot company: {str(e)}")
        raise HTTPException(status_code=500, detail=f"会社の作成に失敗しました: {str(e)}")

@app.patch("/hubspot/companies/{company_id}", response_model=HubSpotResponse)
async def update_hubspot_company(company_id: str, company_data: CompanyUpdateRequest):
    """HubSpot会社情報を更新"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        company = await hubspot_companies_client.update_company(company_id, company_data.dict())
        if not company:
            raise HTTPException(status_code=404, detail="指定された会社が見つからないか、更新に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="会社情報を正常に更新しました",
            data={"company": company}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HubSpot company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"会社情報の更新に失敗しました: {str(e)}")

@app.delete("/hubspot/companies/{company_id}", response_model=HubSpotResponse)
async def delete_hubspot_company(company_id: str):
    """HubSpot会社を削除"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        success = await hubspot_companies_client.delete_company(company_id)
        if not success:
            raise HTTPException(status_code=404, detail="指定された会社が見つからないか、削除に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="会社を正常に削除しました",
            data={"company_id": company_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HubSpot company {company_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"会社の削除に失敗しました: {str(e)}")

@app.get("/hubspot/health", response_model=HubSpotResponse)
async def hubspot_health_check():
    """HubSpot API接続テスト"""
    try:
        health_data = await hubspot_owners_client.health_check()
        return HubSpotResponse(
            status=health_data["status"],
            message=health_data["message"],
            data={"api_version": health_data["api_version"]}
        )
    except Exception as e:
        logger.error(f"HubSpot health check failed: {str(e)}")
        return HubSpotResponse(
            status="unhealthy",
            message=f"HubSpot API接続テストに失敗しました: {str(e)}"
        )

@app.get("/hubspot/debug")
async def hubspot_debug():
    """HubSpot設定のデバッグ情報"""
    debug_info = Config.debug_config()
    return {
        "status": "debug",
        "message": "HubSpot設定のデバッグ情報",
        "data": debug_info
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
