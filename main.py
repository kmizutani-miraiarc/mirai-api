from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uvicorn
import logging
from hubspot.owners import HubSpotOwnersClient
from hubspot.contacts import HubSpotContactsClient
from hubspot.companies import HubSpotCompaniesClient
from hubspot.deals import HubSpotDealsClient
from hubspot.bukken import HubSpotBukkenClient
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
    status: str = Field(example="success", description="レスポンスステータス")
    message: str = Field(example="物件情報検索を正常に実行しました（100件の物件を取得）", description="レスポンスメッセージ")
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        example={
            "results": [
                {
                    "id": "144611322612",
                    "properties": {
                        "bukken_name": "柏市一棟アパート",
                        "bukken_state": "千葉県",
                        "bukken_city": "柏市",
                        "bukken_address": "中新宿二丁目"
                    },
                    "createdAt": "2025-09-04T05:50:12.453Z",
                    "updatedAt": "2025-09-04T05:50:12.920Z",
                    "archived": False
                }
            ]
        },
        description="検索結果データ"
    )
    count: Optional[int] = Field(example=100, description="取得件数")

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "message": "物件情報検索を正常に実行しました（100件の物件を取得）",
                "data": {
                    "results": [
                        {
                            "id": "144611322612",
                            "properties": {
                                "bukken_name": "柏市一棟アパート",
                                "bukken_state": "千葉県",
                                "bukken_city": "柏市",
                                "bukken_address": "中新宿二丁目"
                            },
                            "createdAt": "2025-09-04T05:50:12.453Z",
                            "updatedAt": "2025-09-04T05:50:12.920Z",
                            "archived": False
                        }
                    ]
                },
                "count": 100
            }
        }

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

class DealCreateRequest(BaseModel):
    properties: Dict[str, Any]

class DealUpdateRequest(BaseModel):
    properties: Dict[str, Any]

class BukkenCreateRequest(BaseModel):
    properties: Dict[str, Any]

class BukkenUpdateRequest(BaseModel):
    properties: Dict[str, Any]

class BukkenSearchRequest(BaseModel):
    """物件情報検索リクエスト"""
    # 検索パラメーター
    bukken_name: Optional[str] = Field(
        default=None,
        example="",
        description="物件名（部分一致検索）"
    )
    bukken_state: Optional[str] = Field(
        default=None,
        example="",
        description="都道府県（完全一致検索）"
    )
    bukken_city: Optional[str] = Field(
        default=None,
        example="",
        description="市区町村（完全一致検索）"
    )
    
    # 従来のパラメーター
    filterGroups: List[Dict[str, Any]] = Field(
        default=[],
        example=[
            {
                "filters": [
                    {
                        "propertyName": "bukken_name",
                        "operator": "CONTAINS_TOKEN",
                        "value": "テスト"
                    }
                ]
            }
        ],
        description="検索フィルターグループ（手動指定時はこちらを使用）"
    )
    sorts: Optional[List[Dict[str, Any]]] = Field(
        default=[
            {
                "propertyName": "hs_createdate",
                "direction": "DESCENDING"
            }
        ],
        example=[
            {
                "propertyName": "hs_createdate",
                "direction": "DESCENDING"
            }
        ],
        description="ソート条件"
    )
    query: Optional[str] = Field(
        default=None,
        example="",
        description="検索クエリ（空文字列またはnullで全件検索）"
    )
    properties: Optional[List[str]] = Field(
        default=[
            "bukken_name",
            "bukken_state", 
            "bukken_city",
            "bukken_address"
        ],
        example=[
            "bukken_name",
            "bukken_state",
            "bukken_city",
            "bukken_address"
        ],
        description="取得するプロパティ"
    )
    limit: Optional[int] = Field(
        default=100,
        example=100,
        description="取得件数上限"
    )
    after: Optional[str] = Field(
        default=None,
        example="",
        description="ページネーション用のカーソル（空文字列またはnullで最初から検索）"
    )

# HubSpotクライアントのインスタンス
hubspot_owners_client = HubSpotOwnersClient()
hubspot_contacts_client = HubSpotContactsClient()
hubspot_companies_client = HubSpotCompaniesClient()
hubspot_deals_client = HubSpotDealsClient()
hubspot_bukken_client = HubSpotBukkenClient()

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
            {"path": "/hubspot/deals", "method": "GET", "description": "HubSpot取引一覧取得"},
            {"path": "/hubspot/deals", "method": "POST", "description": "HubSpot取引作成"},
            {"path": "/hubspot/deals/{deal_id}", "method": "GET", "description": "HubSpot取引詳細取得"},
            {"path": "/hubspot/deals/{deal_id}", "method": "PATCH", "description": "HubSpot取引情報更新"},
            {"path": "/hubspot/deals/{deal_id}", "method": "DELETE", "description": "HubSpot取引削除"},
            {"path": "/hubspot/bukken", "method": "GET", "description": "HubSpot物件情報一覧取得"},
            {"path": "/hubspot/bukken", "method": "POST", "description": "HubSpot物件情報作成"},
            {"path": "/hubspot/bukken/{bukken_id}", "method": "GET", "description": "HubSpot物件情報詳細取得"},
            {"path": "/hubspot/bukken/{bukken_id}", "method": "PATCH", "description": "HubSpot物件情報更新"},
            {"path": "/hubspot/bukken/{bukken_id}", "method": "DELETE", "description": "HubSpot物件情報削除"},
            {"path": "/hubspot/bukken/search", "method": "POST", "description": "HubSpot物件情報検索"},
            {"path": "/hubspot/bukken/schema", "method": "GET", "description": "HubSpot物件情報スキーマ取得"},
            {"path": "/hubspot/bukken/properties", "method": "GET", "description": "HubSpot物件情報プロパティ一覧取得"},
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

# HubSpot取引関連エンドポイント
@app.get("/hubspot/deals", response_model=HubSpotResponse)
async def get_hubspot_deals(limit: int = 100, after: Optional[str] = None):
    """HubSpot取引一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        deals = await hubspot_deals_client.get_deals(limit=limit, after=after)
        return HubSpotResponse(
            status="success",
            message="取引一覧を正常に取得しました",
            data={"deals": deals},
            count=len(deals)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot deals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引一覧の取得に失敗しました: {str(e)}")

@app.get("/hubspot/deals/{deal_id}", response_model=HubSpotResponse)
async def get_hubspot_deal(deal_id: str):
    """HubSpot取引詳細を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        deal = await hubspot_deals_client.get_deal_by_id(deal_id)
        if not deal:
            raise HTTPException(status_code=404, detail="指定された取引が見つかりません")
        
        return HubSpotResponse(
            status="success",
            message="取引情報を正常に取得しました",
            data={"deal": deal}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot deal {deal_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引情報の取得に失敗しました: {str(e)}")

@app.post("/hubspot/deals", response_model=HubSpotResponse)
async def create_hubspot_deal(deal_data: DealCreateRequest):
    """HubSpot取引を作成"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        deal = await hubspot_deals_client.create_deal(deal_data.dict())
        if not deal:
            raise HTTPException(status_code=400, detail="取引の作成に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="取引を正常に作成しました",
            data={"deal": deal}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create HubSpot deal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引の作成に失敗しました: {str(e)}")

@app.patch("/hubspot/deals/{deal_id}", response_model=HubSpotResponse)
async def update_hubspot_deal(deal_id: str, deal_data: DealUpdateRequest):
    """HubSpot取引情報を更新"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        deal = await hubspot_deals_client.update_deal(deal_id, deal_data.dict())
        if not deal:
            raise HTTPException(status_code=404, detail="指定された取引が見つからないか、更新に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="取引情報を正常に更新しました",
            data={"deal": deal}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HubSpot deal {deal_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引情報の更新に失敗しました: {str(e)}")

@app.delete("/hubspot/deals/{deal_id}", response_model=HubSpotResponse)
async def delete_hubspot_deal(deal_id: str):
    """HubSpot取引を削除"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        success = await hubspot_deals_client.delete_deal(deal_id)
        if not success:
            raise HTTPException(status_code=404, detail="指定された取引が見つからないか、削除に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="取引を正常に削除しました",
            data={"deal_id": deal_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HubSpot deal {deal_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取引の削除に失敗しました: {str(e)}")

# HubSpot物件情報関連エンドポイント
@app.get("/hubspot/bukken", response_model=HubSpotResponse)
async def get_hubspot_bukken_list(limit: int = 100, after: Optional[str] = None):
    """HubSpot物件情報一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        bukken_list = await hubspot_bukken_client.get_bukken_list(limit=limit, after=after)
        return HubSpotResponse(
            status="success",
            message="物件情報一覧を正常に取得しました",
            data={"bukken_list": bukken_list},
            count=len(bukken_list)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot bukken list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報一覧の取得に失敗しました: {str(e)}")

@app.get("/hubspot/bukken/{bukken_id}", response_model=HubSpotResponse)
async def get_hubspot_bukken(bukken_id: str):
    """HubSpot物件情報詳細を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        bukken = await hubspot_bukken_client.get_bukken_by_id(bukken_id)
        if not bukken:
            raise HTTPException(status_code=404, detail="指定された物件情報が見つかりません")
        
        return HubSpotResponse(
            status="success",
            message="物件情報を正常に取得しました",
            data={"bukken": bukken}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot bukken {bukken_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報の取得に失敗しました: {str(e)}")

@app.post("/hubspot/bukken", response_model=HubSpotResponse)
async def create_hubspot_bukken(bukken_data: BukkenCreateRequest):
    """HubSpot物件情報を作成"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        bukken = await hubspot_bukken_client.create_bukken(bukken_data.dict())
        if not bukken:
            raise HTTPException(status_code=400, detail="物件情報の作成に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="物件情報を正常に作成しました",
            data={"bukken": bukken}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create HubSpot bukken: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報の作成に失敗しました: {str(e)}")

@app.patch("/hubspot/bukken/{bukken_id}", response_model=HubSpotResponse)
async def update_hubspot_bukken(bukken_id: str, bukken_data: BukkenUpdateRequest):
    """HubSpot物件情報を更新"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        bukken = await hubspot_bukken_client.update_bukken(bukken_id, bukken_data.dict())
        if not bukken:
            raise HTTPException(status_code=404, detail="指定された物件情報が見つからないか、更新に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="物件情報を正常に更新しました",
            data={"bukken": bukken}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HubSpot bukken {bukken_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報の更新に失敗しました: {str(e)}")

@app.delete("/hubspot/bukken/{bukken_id}", response_model=HubSpotResponse)
async def delete_hubspot_bukken(bukken_id: str):
    """HubSpot物件情報を削除"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        success = await hubspot_bukken_client.delete_bukken(bukken_id)
        if not success:
            raise HTTPException(status_code=404, detail="指定された物件情報が見つからないか、削除に失敗しました")
        
        return HubSpotResponse(
            status="success",
            message="物件情報を正常に削除しました",
            data={"bukken_id": bukken_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HubSpot bukken {bukken_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報の削除に失敗しました: {str(e)}")

@app.post(
    "/hubspot/bukken/search", 
    response_model=HubSpotResponse,
    responses={
        200: {
            "description": "物件情報検索が正常に実行されました",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "検索成功（100件の物件を取得）",
                            "description": "物件情報検索が正常に実行され、100件の物件が取得されました",
                            "value": {
                                "status": "success",
                                "message": "物件情報検索を正常に実行しました（100件の物件を取得）",
                                "data": {
                                    "results": [
                                        {
                                            "id": "144611322612",
                                            "properties": {
                                                "bukken_name": "柏市一棟アパート",
                                                "bukken_state": "千葉県",
                                                "bukken_city": "柏市",
                                                "bukken_address": "中新宿二丁目"
                                            },
                                            "createdAt": "2025-09-04T05:50:12.453Z",
                                            "updatedAt": "2025-09-04T05:50:12.920Z",
                                            "archived": False
                                        }
                                    ]
                                },
                                "count": 100
                            }
                        },
                        "empty": {
                            "summary": "検索結果なし（0件）",
                            "description": "検索条件に一致する物件が見つかりませんでした",
                            "value": {
                                "status": "success",
                                "message": "物件情報検索を正常に実行しました（0件の物件を取得）",
                                "data": {
                                    "results": []
                                },
                                "count": 0
                            }
                        }
                    }
                }
            }
        }
    }
)
async def search_hubspot_bukken(search_criteria: BukkenSearchRequest):
    """HubSpot物件情報を検索"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        search_data = search_criteria.dict()
        
        # 新しいパラメーターからfilterGroupsを構築
        filters = []
        
        # 物件名の部分一致検索
        if search_data.get('bukken_name') and search_data.get('bukken_name').strip():
            filters.append({
                "propertyName": "bukken_name",
                "operator": "CONTAINS_TOKEN",
                "value": search_data.get('bukken_name').strip()
            })
        
        # 都道府県の完全一致検索
        if search_data.get('bukken_state') and search_data.get('bukken_state').strip():
            filters.append({
                "propertyName": "bukken_state",
                "operator": "EQ",
                "value": search_data.get('bukken_state').strip()
            })
        
        # 市区町村の完全一致検索
        if search_data.get('bukken_city') and search_data.get('bukken_city').strip():
            filters.append({
                "propertyName": "bukken_city",
                "operator": "EQ",
                "value": search_data.get('bukken_city').strip()
            })
        
        # 新しいパラメーターでフィルターが構築された場合、filterGroupsを上書き
        if filters:
            search_data['filterGroups'] = [{"filters": filters}]
        
        logger.info(f"Search request received: {search_data}")
        logger.info(f"Search criteria details - filterGroups: {search_data.get('filterGroups', [])}")
        logger.info(f"Search criteria details - properties: {search_data.get('properties', [])}")
        logger.info(f"Search criteria details - limit: {search_data.get('limit', 100)}")
        
        results = await hubspot_bukken_client.search_bukken(search_data)
        logger.info(f"Search completed. Found {len(results)} results")
        
        return HubSpotResponse(
            status="success",
            message=f"物件情報検索を正常に実行しました（{len(results)}件の物件を取得）",
            data={"results": results},
            count=len(results)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search HubSpot bukken: {str(e)}")
        return HubSpotResponse(
            status="error",
            message=f"物件情報検索に失敗しました: {str(e)}",
            data={"results": []},
            count=0
        )

@app.get("/hubspot/bukken/schema", response_model=HubSpotResponse)
async def get_hubspot_bukken_schema():
    """HubSpot物件情報カスタムオブジェクトのスキーマを取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        schema = await hubspot_bukken_client.get_bukken_schema()
        if not schema:
            raise HTTPException(status_code=404, detail="物件情報カスタムオブジェクトのスキーマが見つかりません")
        
        return HubSpotResponse(
            status="success",
            message="物件情報スキーマを正常に取得しました",
            data={"schema": schema}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot bukken schema: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報スキーマの取得に失敗しました: {str(e)}")

@app.get("/hubspot/bukken/properties", response_model=HubSpotResponse)
async def get_hubspot_bukken_properties():
    """HubSpot物件情報カスタムオブジェクトのプロパティ一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        properties = await hubspot_bukken_client.get_bukken_properties()
        
        return HubSpotResponse(
            status="success",
            message="物件情報プロパティ一覧を正常に取得しました",
            data={"properties": properties},
            count=len(properties)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot bukken properties: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報プロパティ一覧の取得に失敗しました: {str(e)}")

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
