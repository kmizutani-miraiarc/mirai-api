from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uvicorn
import logging
import tempfile
import os
from hubspot.owners import HubSpotOwnersClient
from hubspot.contacts import HubSpotContactsClient
from hubspot.companies import HubSpotCompaniesClient
from hubspot.deals import HubSpotDealsClient
from hubspot.bukken import HubSpotBukkenClient
from hubspot.deal_histories import HubSpotDealHistoriesClient
from hubspot.config import Config
from database.connection import db_connection
from database.api_keys import api_key_manager
from database.gmail_credentials import gmail_credentials_manager
from processors import DocumentProcessor, AIProcessor
from routers.profit_management import router as profit_management_router
from routers.profit_target import router as profit_target_router
from routers.property_owner import router as property_owner_router
from routers.slack import router as slack_router
from routers.satei import router as satei_router
from routers.haihai_click_log import router as haihai_click_log_router
from routers.purchase_achievement import router as purchase_achievement_router

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API認証の依存関数
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """API認証キーを検証（データベースベース）"""
    if not x_api_key:
        raise HTTPException(
            status_code=401, 
            detail="API key is required. Please provide X-API-Key header."
        )
    
    # データベースからAPIキーを検証
    api_key_info = await api_key_manager.validate_api_key(x_api_key)
    if not api_key_info:
        raise HTTPException(
            status_code=401, 
            detail="Invalid API key. Please check your X-API-Key header."
        )
    
    return api_key_info

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Mirai API Server",
    description="AlmaLinuxで動作するPython APIサーバー",
    version="1.0.0"
)

# アプリケーション起動時のイベントハンドラー
@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    try:
        # データベース接続プールを作成
        await db_connection.create_pool()
        
        # データベース接続をテスト
        if await db_connection.test_connection():
            logger.info("データベース接続が正常に確立されました")
        else:
            logger.error("データベース接続テストに失敗しました")
            raise Exception("データベース接続に失敗しました")
        
        # APIキーテーブルを作成
        await api_key_manager.create_tables()
        logger.info("APIキーテーブルの初期化が完了しました")
        
        # Gmail認証情報テーブルを作成
        await gmail_credentials_manager.create_tables()
        logger.info("Gmail認証情報テーブルの初期化が完了しました")
        
        # 物件買取実績テーブルを作成（存在しない場合）
        await create_purchase_achievements_table_if_not_exists()
        logger.info("物件買取実績テーブルの初期化が完了しました")
        
        # 粗利目標管理テーブルを作成（存在しない場合）
        await create_profit_target_table_if_not_exists()
        logger.info("粗利目標管理テーブルの初期化が完了しました")
        
    except Exception as e:
        logger.error(f"アプリケーション起動時にエラーが発生しました: {str(e)}")
        raise

async def create_purchase_achievements_table_if_not_exists():
    """物件買取実績テーブルが存在しない場合、作成する"""
    try:
        # テーブルの存在確認
        check_query = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'purchase_achievements'
        """
        result = await db_connection.execute_query(check_query)
        
        if result and result[0].get("count", 0) > 0:
            logger.info("物件買取実績テーブルは既に存在します")
            return
        
        # テーブルが存在しない場合は作成
        logger.info("物件買取実績テーブルが存在しないため、作成します...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS purchase_achievements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            property_image_url TEXT COMMENT '物件写真URL',
            purchase_date DATE COMMENT '買取日',
            title VARCHAR(255) COMMENT 'タイトル（例：◯県◯市一棟アパート）',
            property_name VARCHAR(255) COMMENT '物件名',
            building_age INT COMMENT '築年数',
            structure VARCHAR(100) COMMENT '構造',
            nearest_station VARCHAR(255) COMMENT '最寄り',
            prefecture VARCHAR(50) COMMENT '都道府県',
            city VARCHAR(100) COMMENT '市区町村',
            address_detail VARCHAR(255) COMMENT '番地以下',
            hubspot_bukken_id VARCHAR(255) COMMENT 'HubSpotの物件ID',
            hubspot_bukken_created_date DATETIME COMMENT 'HubSpotの物件登録日（オブジェクトの作成日）',
            hubspot_deal_id VARCHAR(255) COMMENT 'HubSpotの取引ID',
            is_public BOOLEAN DEFAULT FALSE COMMENT '公開フラグ',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'レコード作成日',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'レコード更新日',
            INDEX idx_hubspot_bukken_id (hubspot_bukken_id),
            INDEX idx_hubspot_deal_id (hubspot_deal_id),
            INDEX idx_purchase_date (purchase_date),
            INDEX idx_is_public (is_public),
            INDEX idx_created_at (created_at),
            INDEX idx_prefecture (prefecture),
            INDEX idx_city (city),
            INDEX idx_bukken_deal (hubspot_bukken_id, hubspot_deal_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物件買取実績テーブル';
        """
        
        await db_connection.execute_update(create_table_sql)
        
        # 既存テーブルに住所カラムを追加（存在しない場合のみ）
        # カラムの存在確認
        check_columns_query = """
            SELECT COLUMN_NAME 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'purchase_achievements'
            AND COLUMN_NAME IN ('prefecture', 'city', 'address_detail')
        """
        try:
            existing_columns_result = await db_connection.execute_query(check_columns_query)
            # 辞書またはタプルで返される可能性があるため、両方に対応
            existing_columns = set()
            if existing_columns_result:
                for row in existing_columns_result:
                    if isinstance(row, dict):
                        column_name = row.get("COLUMN_NAME") or row.get("column_name")
                    else:
                        column_name = row[0] if len(row) > 0 else None
                    if column_name:
                        existing_columns.add(column_name)
            
            logger.info(f"既存カラム確認結果: {existing_columns}")
            
            alter_queries = []
            if "prefecture" not in existing_columns:
                alter_queries.append("ALTER TABLE purchase_achievements ADD COLUMN prefecture VARCHAR(50) COMMENT '都道府県' AFTER nearest_station")
            if "city" not in existing_columns:
                alter_queries.append("ALTER TABLE purchase_achievements ADD COLUMN city VARCHAR(100) COMMENT '市区町村' AFTER prefecture")
            if "address_detail" not in existing_columns:
                alter_queries.append("ALTER TABLE purchase_achievements ADD COLUMN address_detail VARCHAR(255) COMMENT '番地以下' AFTER city")
            
            for query in alter_queries:
                try:
                    await db_connection.execute_update(query)
                    column_name = query.split("ADD COLUMN")[1].split("COMMENT")[0].strip()
                    logger.info(f"カラムを追加しました: {column_name}")
                except Exception as e:
                    error_msg = str(e)
                    # カラムが既に存在する場合のエラーは無視
                    if "Duplicate column name" not in error_msg and "already exists" not in error_msg.lower():
                        logger.warning(f"カラム追加に失敗しました: {error_msg}")
                        logger.exception(e)
            
            # インデックスの存在確認と追加
            check_indexes_query = """
                SELECT INDEX_NAME 
                FROM information_schema.STATISTICS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'purchase_achievements'
                AND INDEX_NAME IN ('idx_prefecture', 'idx_city')
            """
            try:
                existing_indexes_result = await db_connection.execute_query(check_indexes_query)
                existing_indexes = set()
                if existing_indexes_result:
                    for row in existing_indexes_result:
                        if isinstance(row, dict):
                            index_name = row.get("INDEX_NAME") or row.get("index_name")
                        else:
                            index_name = row[0] if len(row) > 0 else None
                        if index_name:
                            existing_indexes.add(index_name)
                
                logger.info(f"既存インデックス確認結果: {existing_indexes}")
                
                if "idx_prefecture" not in existing_indexes:
                    try:
                        await db_connection.execute_update("CREATE INDEX idx_prefecture ON purchase_achievements (prefecture)")
                        logger.info("インデックス idx_prefecture を追加しました")
                    except Exception as e:
                        error_msg = str(e)
                        if "Duplicate key name" not in error_msg and "already exists" not in error_msg.lower():
                            logger.warning(f"インデックス追加に失敗しました: {error_msg}")
                else:
                    logger.info("インデックス idx_prefecture は既に存在します")
                
                if "idx_city" not in existing_indexes:
                    try:
                        await db_connection.execute_update("CREATE INDEX idx_city ON purchase_achievements (city)")
                        logger.info("インデックス idx_city を追加しました")
                    except Exception as e:
                        error_msg = str(e)
                        if "Duplicate key name" not in error_msg and "already exists" not in error_msg.lower():
                            logger.warning(f"インデックス追加に失敗しました: {error_msg}")
                else:
                    logger.info("インデックス idx_city は既に存在します")
            except Exception as e:
                logger.warning(f"インデックス確認に失敗しました（無視して続行）: {str(e)}")
        except Exception as e:
            logger.warning(f"カラム追加処理中にエラーが発生しました（無視して続行）: {str(e)}")
            logger.exception(e)
        
        await db_connection.execute_update(create_table_sql)
        logger.info("物件買取実績テーブルを作成しました")
        
    except Exception as e:
        logger.error(f"物件買取実績テーブルの作成に失敗しました: {str(e)}")
        # テーブル作成に失敗してもアプリケーションは起動を続ける
        # （既にテーブルが存在する場合など）

async def create_profit_target_table_if_not_exists():
    """粗利目標管理テーブルが存在しない場合、作成する"""
    try:
        # テーブルの存在確認
        check_query = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'profit_target'
        """
        result = await db_connection.execute_query(check_query)
        
        if result and result[0].get("count", 0) > 0:
            logger.info("粗利目標管理テーブルは既に存在します")
            return
        
        # テーブルが存在しない場合は作成
        logger.info("粗利目標管理テーブルが存在しないため、作成します...")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS profit_target (
            id INT AUTO_INCREMENT PRIMARY KEY COMMENT 'ID',
            
            -- 基本情報
            owner_id VARCHAR(255) NOT NULL COMMENT '担当者ID（HubSpotの担当者ID）',
            owner_name VARCHAR(255) NOT NULL COMMENT '担当者名',
            year INT NOT NULL COMMENT '年度',
            
            -- 四半期目標
            q1_target DECIMAL(15, 2) DEFAULT NULL COMMENT '1Q目標額',
            q2_target DECIMAL(15, 2) DEFAULT NULL COMMENT '2Q目標額',
            q3_target DECIMAL(15, 2) DEFAULT NULL COMMENT '3Q目標額',
            q4_target DECIMAL(15, 2) DEFAULT NULL COMMENT '4Q目標額',
            
            -- タイムスタンプ
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
            
            -- インデックス
            INDEX idx_owner_id (owner_id),
            INDEX idx_year (year),
            INDEX idx_owner_year (owner_id, year),
            INDEX idx_created_at (created_at),
            INDEX idx_updated_at (updated_at),
            
            -- ユニーク制約（同じ担当者・同じ年の組み合わせは1つだけ）
            UNIQUE KEY uk_owner_year (owner_id, year)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='粗利目標管理テーブル'
        """
        
        await db_connection.execute_update(create_table_sql)
        logger.info("粗利目標管理テーブルを作成しました")
        
    except Exception as e:
        logger.error(f"粗利目標管理テーブルの作成に失敗しました: {str(e)}")
        # テーブル作成に失敗してもアプリケーションは起動を続ける
        # （既にテーブルが存在する場合など）
        logger.warning("物件買取実績テーブルの作成をスキップします")

# アプリケーション終了時のイベントハンドラー
@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時の処理"""
    try:
        await db_connection.close_pool()
        logger.info("データベース接続プールを閉じました")
    except Exception as e:
        logger.error(f"アプリケーション終了時にエラーが発生しました: {str(e)}")

# CORSミドルウェアを追加（外部からのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限してください
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを追加
app.include_router(profit_management_router)
app.include_router(profit_target_router)
app.include_router(property_owner_router)
app.include_router(slack_router)
app.include_router(satei_router)
app.include_router(haihai_click_log_router)
app.include_router(purchase_achievement_router)

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

# APIキー管理用のPydanticモデル
class APIKeyCreateRequest(BaseModel):
    """APIキー作成リクエスト"""
    site_name: str = Field(..., description="サイト名", example="example-site")
    description: Optional[str] = Field(None, description="APIキーの説明", example="テスト用APIキー")
    expires_days: Optional[int] = Field(None, description="有効期限（日数）", example=365)

class APIKeyResponse(BaseModel):
    """APIキーレスポンス"""
    id: int
    site_name: str
    api_key_prefix: str
    description: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str
    last_used_at: Optional[str]
    expires_at: Optional[str]

class APIKeyCreateResponse(BaseModel):
    """APIキー作成レスポンス"""
    site_name: str
    api_key: str  # 作成時のみプレーンテキストで返す
    api_key_prefix: str
    description: Optional[str]
    expires_at: Optional[str]
    created_at: str

class DealSearchRequest(BaseModel):
    """取引検索リクエスト"""
    dealname: Optional[str] = Field(
        default=None,
        example="",
        description="取引名（部分一致検索）"
    )
    pipeline: Optional[str] = Field(
        default=None,
        example="",
        description="パイプラインID（完全一致検索）"
    )
    dealstage: Optional[str] = Field(
        default=None,
        example="",
        description="ステージID（完全一致検索）"
    )
    hubspot_owner_id: Optional[str] = Field(
        default=None,
        example="",
        description="取引担当者ID（完全一致検索）"
    )
    query: Optional[str] = Field(
        default=None,
        example="",
        description="検索クエリ（空文字列またはnullで全件検索）"
    )
    properties: Optional[List[str]] = Field(
        default=[
            "dealname",
            "pipeline",
            "dealstage",
            "hubspot_owner_id",
            "amount",
            "closedate",
            "createdate",
            "hs_lastmodifieddate",
            "contract_date",
            "settlement_date",
            "bukken_created",
            "deal_hold_date",
            "deal_survey_review_date",
            "research_purchase_price_date",
            "deal_probability_a_date",
            "deal_probability_b_date",
            "deal_farewell_date",
            "deal_lost_date",
            "introduction_datetime",
            "deal_disclosure_date",
            "deal_non_applicable",
            "appraisal_property"
        ],
        example=[
            "dealname",
            "pipeline",
            "dealstage",
            "hubspot_owner_id",
            "amount",
            "closedate"
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
    fromDate: Optional[str] = Field(
        default=None,
        example="2024-01-01",
        description="作成日の開始日（YYYY-MM-DD形式）"
    )
    toDate: Optional[str] = Field(
        default=None,
        example="2024-12-31",
        description="作成日の終了日（YYYY-MM-DD形式）"
    )
# HubSpotクライアントのインスタンス
hubspot_owners_client = HubSpotOwnersClient()
hubspot_contacts_client = HubSpotContactsClient()
hubspot_companies_client = HubSpotCompaniesClient()
hubspot_deals_client = HubSpotDealsClient()
hubspot_bukken_client = HubSpotBukkenClient()
hubspot_deal_histories_client = HubSpotDealHistoriesClient()

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {"message": "Mirai API Server is running!"}

@app.get("/test", response_model=TestResponse)
async def test_endpoint(api_key: str = Depends(verify_api_key)):
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
            {"path": "/hubspot/deals/search", "method": "POST", "description": "HubSpot取引検索（パイプライン、取引名、ステージ、取引担当者で検索）"},
            {"path": "/hubspot/deals/pipelines", "method": "GET", "description": "HubSpotパイプライン一覧取得"},
            {"path": "/hubspot/deals/pipelines/{pipeline_id}/stages", "method": "GET", "description": "HubSpotパイプラインに紐づくステージ一覧取得"},
            {"path": "/hubspot/deals/pipelines/{pipeline_id}/history", "method": "GET", "description": "HubSpotパイプラインの変更履歴取得（履歴付き取引データ）"},
            {"path": "/hubspot/bukken/{bukken_id}/deals", "method": "GET", "description": "HubSpot物件に関連づけられた取引取得"},
            {"path": "/hubspot/bukken", "method": "GET", "description": "HubSpot物件情報一覧取得"},
            {"path": "/hubspot/bukken", "method": "POST", "description": "HubSpot物件情報作成"},
            {"path": "/hubspot/bukken/{bukken_id}", "method": "GET", "description": "HubSpot物件情報詳細取得"},
            {"path": "/hubspot/bukken/{bukken_id}", "method": "PATCH", "description": "HubSpot物件情報更新"},
            {"path": "/hubspot/bukken/{bukken_id}", "method": "DELETE", "description": "HubSpot物件情報削除"},
            {"path": "/hubspot/bukken/search", "method": "POST", "description": "HubSpot物件情報検索"},
            {"path": "/hubspot/bukken/schema", "method": "GET", "description": "HubSpot物件情報スキーマ取得"},
            {"path": "/hubspot/bukken/properties", "method": "GET", "description": "HubSpot物件情報プロパティ一覧取得"},
            {"path": "/hubspot/property-options/{property_name}", "method": "GET", "description": "HubSpotプロパティの選択肢取得"},
            {"path": "/hubspot/health", "method": "GET", "description": "HubSpot API接続テスト"},
            {"path": "/hubspot/debug", "method": "GET", "description": "HubSpot設定デバッグ情報"},
            {"path": "/hubspot/deal-histories/schema", "method": "GET", "description": "deal_historiesカスタムオブジェクトスキーマ取得"},
            {"path": "/hubspot/deal-histories", "method": "GET", "description": "deal_historiesカスタムオブジェクト一覧取得"},
            {"path": "/hubspot/deal-histories/by-deal/{deal_id}", "method": "GET", "description": "特定の取引IDの履歴取得"},
            {"path": "/hubspot/deal-histories/contracts", "method": "GET", "description": "契約ステージの履歴取得"},
            {"path": "/hubspot/deal-histories/settlements", "method": "GET", "description": "決済ステージの履歴取得"},
            {"path": "/hubspot/deal-histories/monthly-contracts", "method": "GET", "description": "月別契約件数取得"},
            {"path": "/hubspot/deal-histories/monthly-settlements", "method": "GET", "description": "月別決済件数取得"},
            {"path": "/purchase-achievements", "method": "GET", "description": "物件買取実績一覧取得"},
            {"path": "/purchase-achievements/{id}", "method": "GET", "description": "物件買取実績詳細取得"},
            {"path": "/purchase-achievements", "method": "POST", "description": "物件買取実績作成"},
            {"path": "/purchase-achievements/{id}", "method": "PATCH", "description": "物件買取実績更新"}
        ]
    }

# HubSpot API エンドポイント
@app.get("/hubspot/owners", response_model=HubSpotResponse)
async def get_hubspot_owners(api_key: str = Depends(verify_api_key)):
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
async def get_hubspot_owner(owner_id: str, api_key: str = Depends(verify_api_key)):
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
            data={"owner": owner},
            count=1
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot owner {owner_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"担当者詳細の取得に失敗しました: {str(e)}")

@app.post("/hubspot/owners", response_model=HubSpotResponse)
async def create_hubspot_owner(owner_data: OwnerCreateRequest, api_key: str = Depends(verify_api_key)):
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
async def update_hubspot_owner(owner_id: str, owner_data: OwnerUpdateRequest, api_key: str = Depends(verify_api_key)):
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
            data={"owner": owner},
            count=1
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HubSpot owner {owner_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"担当者情報の更新に失敗しました: {str(e)}")

@app.delete("/hubspot/owners/{owner_id}", response_model=HubSpotResponse)
async def delete_hubspot_owner(owner_id: str, api_key: str = Depends(verify_api_key)):
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
            data={"owner_id": owner_id},
            count=1
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete HubSpot owner {owner_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"担当者の削除に失敗しました: {str(e)}")

@app.get("/hubspot/contacts", response_model=HubSpotResponse)
async def get_hubspot_contacts(
    limit: int = 100, 
    after: Optional[str] = None, 
    properties: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """HubSpotコンタクト一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        # propertiesパラメータをリストに変換
        properties_list = None
        if properties:
            properties_list = [p.strip() for p in properties.split(",") if p.strip()]
        
        contacts_data = await hubspot_contacts_client.get_contacts(limit=limit, after=after, properties=properties_list)
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
async def get_hubspot_contact(contact_id: str, api_key: str = Depends(verify_api_key)):
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
async def create_hubspot_contact(contact_data: ContactCreateRequest, api_key: str = Depends(verify_api_key)):
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
async def update_hubspot_contact(contact_id: str, contact_data: ContactUpdateRequest, api_key: str = Depends(verify_api_key)):
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
async def delete_hubspot_contact(contact_id: str, api_key: str = Depends(verify_api_key)):
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
async def get_hubspot_companies(limit: int = 100, after: Optional[str] = None, api_key: str = Depends(verify_api_key)):
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
async def get_hubspot_company(company_id: str, api_key: str = Depends(verify_api_key)):
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
async def create_hubspot_company(company_data: CompanyCreateRequest, api_key: str = Depends(verify_api_key)):
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
async def update_hubspot_company(company_id: str, company_data: CompanyUpdateRequest, api_key: str = Depends(verify_api_key)):
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
async def delete_hubspot_company(company_id: str, api_key: str = Depends(verify_api_key)):
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
async def get_hubspot_deals(limit: int = 100, after: Optional[str] = None, api_key: str = Depends(verify_api_key)):
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

@app.get("/hubspot/deals/pipelines", response_model=HubSpotResponse)
async def get_hubspot_pipelines(api_key: str = Depends(verify_api_key)):
    """パイプライン一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        pipelines = await hubspot_deals_client.get_pipelines()
        logger.info(f"Retrieved {len(pipelines)} pipelines")
        
        return HubSpotResponse(
            status="success",
            message=f"パイプライン一覧を正常に取得しました（{len(pipelines)}件のパイプライン）",
            data={"pipelines": pipelines},
            count=len(pipelines)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipelines: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"パイプライン一覧の取得に失敗しました: {str(e)}"
        )

@app.get("/hubspot/deals/pipelines/{pipeline_id}/stages", response_model=HubSpotResponse)
async def get_hubspot_pipeline_stages(pipeline_id: str, api_key: str = Depends(verify_api_key)):
    """パイプラインに紐づくステージ一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        stages = await hubspot_deals_client.get_pipeline_stages(pipeline_id)
        logger.info(f"Retrieved {len(stages)} stages for pipeline {pipeline_id}")
        
        return HubSpotResponse(
            status="success",
            message=f"パイプライン '{pipeline_id}' のステージ一覧を正常に取得しました（{len(stages)}件のステージ）",
            data={"stages": stages, "pipeline_id": pipeline_id},
            count=len(stages)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline stages for {pipeline_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"パイプライン '{pipeline_id}' のステージ一覧取得に失敗しました: {str(e)}"
        )

@app.get("/hubspot/deals/{deal_id}", response_model=HubSpotResponse)
async def get_hubspot_deal(deal_id: str, api_key: str = Depends(verify_api_key)):
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
async def create_hubspot_deal(deal_data: DealCreateRequest, api_key: str = Depends(verify_api_key)):
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
async def update_hubspot_deal(deal_id: str, deal_data: DealUpdateRequest, api_key: str = Depends(verify_api_key)):
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
async def delete_hubspot_deal(deal_id: str, api_key: str = Depends(verify_api_key)):
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
async def get_hubspot_bukken_list(limit: int = 100, after: Optional[str] = None, api_key: str = Depends(verify_api_key)):
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

@app.get("/hubspot/property-options/{property_name}", response_model=HubSpotResponse)
async def get_hubspot_property_options(property_name: str, api_key: str = Depends(verify_api_key)):
    """HubSpotプロパティの選択肢を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        # プロパティの詳細情報を取得
        options = await hubspot_bukken_client.get_property_options(property_name)
        if not options:
            raise HTTPException(status_code=404, detail=f"プロパティ '{property_name}' の選択肢が見つかりません")
        
        return HubSpotResponse(
            status="success",
            message=f"プロパティ '{property_name}' の選択肢を正常に取得しました",
            data={"options": options},
            count=len(options)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get property options for {property_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"プロパティ選択肢の取得に失敗しました: {str(e)}")

@app.get("/hubspot/bukken/{bukken_id}", response_model=HubSpotResponse)
async def get_hubspot_bukken(bukken_id: str, api_key: str = Depends(verify_api_key)):
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
            data={"bukken": bukken},
            count=1
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get HubSpot bukken {bukken_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報の取得に失敗しました: {str(e)}")

@app.post("/hubspot/bukken", response_model=HubSpotResponse)
async def create_hubspot_bukken(bukken_data: BukkenCreateRequest, api_key: str = Depends(verify_api_key)):
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
async def update_hubspot_bukken(bukken_id: str, bukken_data: BukkenUpdateRequest, api_key: str = Depends(verify_api_key)):
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
            data={"bukken": bukken},
            count=1
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update HubSpot bukken {bukken_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"物件情報の更新に失敗しました: {str(e)}")

@app.delete("/hubspot/bukken/{bukken_id}", response_model=HubSpotResponse)
async def delete_hubspot_bukken(bukken_id: str, api_key: str = Depends(verify_api_key)):
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
            data={"bukken_id": bukken_id},
            count=1
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
        },
        401: {
            "description": "認証エラー",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_api_key": {
                            "summary": "APIキーが未提供",
                            "description": "X-API-Keyヘッダーが提供されていません",
                            "value": {
                                "detail": "API key is required. Please provide X-API-Key header."
                            }
                        },
                        "invalid_api_key": {
                            "summary": "無効なAPIキー",
                            "description": "提供されたAPIキーが無効です",
                            "value": {
                                "detail": "Invalid API key. Please check your X-API-Key header."
                            }
                        }
                    }
                }
            }
        }
    }
)
async def search_hubspot_bukken(search_criteria: BukkenSearchRequest, api_key: str = Depends(verify_api_key)):
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
        
        search_result = await hubspot_bukken_client.search_bukken(search_data)
        results = search_result.get("results", [])
        paging = search_result.get("paging", {})
        logger.info(f"Search completed. Found {len(results)} results")
        
        return HubSpotResponse(
            status="success",
            message=f"物件情報検索を正常に実行しました（{len(results)}件の物件を取得）",
            data={"results": results, "paging": paging},
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
async def get_hubspot_bukken_schema(api_key: str = Depends(verify_api_key)):
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
async def get_hubspot_bukken_properties(api_key: str = Depends(verify_api_key)):
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

# APIキー管理エンドポイント
@app.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(request: APIKeyCreateRequest):
    """新しいAPIキーを作成"""
    try:
        result = await api_key_manager.create_api_key(
            site_name=request.site_name,
            description=request.description,
            expires_days=request.expires_days
        )
        return APIKeyCreateResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"APIキーの作成に失敗しました: {str(e)}"
        )

@app.get("/api-keys", response_model=List[APIKeyResponse])
async def get_api_keys(include_inactive: bool = False):
    """APIキー一覧を取得"""
    try:
        api_keys = await api_key_manager.get_api_keys(include_inactive=include_inactive)
        return [APIKeyResponse(**key) for key in api_keys]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"APIキー一覧の取得に失敗しました: {str(e)}"
        )

@app.get("/api-keys/{site_name}", response_model=APIKeyResponse)
async def get_api_key_by_site(site_name: str):
    """サイト名でAPIキー情報を取得"""
    try:
        api_key = await api_key_manager.get_api_key_by_site(site_name)
        if not api_key:
            raise HTTPException(
                status_code=404,
                detail=f"サイト '{site_name}' のAPIキーが見つかりません"
            )
        return APIKeyResponse(**api_key)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"APIキー情報の取得に失敗しました: {str(e)}"
        )

@app.patch("/api-keys/{site_name}/deactivate")
async def deactivate_api_key(site_name: str):
    """APIキーを無効化"""
    try:
        success = await api_key_manager.deactivate_api_key(site_name)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"サイト '{site_name}' のAPIキーが見つかりません"
            )
        return {"message": f"サイト '{site_name}' のAPIキーを無効化しました"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"APIキーの無効化に失敗しました: {str(e)}"
        )

@app.patch("/api-keys/{site_name}/activate")
async def activate_api_key(site_name: str):
    """APIキーを有効化"""
    try:
        success = await api_key_manager.activate_api_key(site_name)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"サイト '{site_name}' のAPIキーが見つかりません"
            )
        return {"message": f"サイト '{site_name}' のAPIキーを有効化しました"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"APIキーの有効化に失敗しました: {str(e)}"
        )

@app.delete("/api-keys/{site_name}")
async def delete_api_key(site_name: str):
    """APIキーを削除"""
    try:
        success = await api_key_manager.delete_api_key(site_name)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"サイト '{site_name}' のAPIキーが見つかりません"
            )
        return {"message": f"サイト '{site_name}' のAPIキーを削除しました"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"APIキーの削除に失敗しました: {str(e)}"
        )

# 新しい取引関連APIエンドポイント

@app.post(
    "/hubspot/deals/search", 
    response_model=HubSpotResponse,
    responses={
        200: {
            "description": "取引検索が正常に実行されました",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "検索成功（10件の取引を取得）",
                            "description": "取引検索が正常に実行され、10件の取引が取得されました",
                            "value": {
                                "status": "success",
                                "message": "取引検索を正常に実行しました（10件の取引を取得）",
                                "data": {"results": []},
                                "count": 10
                            }
                        }
                    }
                }
            }
        }
    }
)
async def search_hubspot_deals(search_criteria: DealSearchRequest, api_key: str = Depends(verify_api_key)):
    """HubSpot取引を検索（パイプライン、取引名、ステージ、取引担当者で検索）"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        search_data = search_criteria.dict()
        
        # 新しいパラメーターからfilterGroupsを構築
        filters = []
        
        # 取引名の部分一致検索
        if search_data.get('dealname') and search_data.get('dealname').strip():
            filters.append({
                "propertyName": "dealname",
                "operator": "CONTAINS_TOKEN",
                "value": search_data.get('dealname').strip()
            })
        
        # パイプラインの完全一致検索
        if search_data.get('pipeline') and search_data.get('pipeline').strip():
            filters.append({
                "propertyName": "pipeline",
                "operator": "EQ",
                "value": search_data.get('pipeline').strip()
            })
        
        # ステージの完全一致検索
        if search_data.get('dealstage') and search_data.get('dealstage').strip():
            filters.append({
                "propertyName": "dealstage",
                "operator": "EQ",
                "value": search_data.get('dealstage').strip()
            })
        
        # 取引担当者の完全一致検索
        if search_data.get('hubspot_owner_id') and search_data.get('hubspot_owner_id').strip():
            filters.append({
                "propertyName": "hubspot_owner_id",
                "operator": "EQ",
                "value": search_data.get('hubspot_owner_id').strip()
            })

        # 作成日の範囲検索
        if search_data.get('fromDate') and search_data.get('fromDate').strip():
            filters.append({
                "propertyName": "createdate",
                "operator": "GTE",
                "value": search_data.get('fromDate').strip()
            })

        if search_data.get('toDate') and search_data.get('toDate').strip():
            filters.append({
                "propertyName": "createdate",
                "operator": "LTE",
                "value": search_data.get('toDate').strip()
            })
        
        # 新しいパラメーターでフィルターが構築された場合、filterGroupsを上書き
        if filters:
            search_data['filterGroups'] = [{"filters": filters}]
        
        logger.info(f"Deal search request received: {search_data}")
        logger.info(f"Search criteria details - filterGroups: {search_data.get('filterGroups', [])}")
        logger.info(f"Search criteria details - properties: {search_data.get('properties', [])}")
        logger.info(f"Search criteria details - limit: {search_data.get('limit', 100)}")
        
        search_result = await hubspot_deals_client.search_deals(search_data)
        results = search_result.get("results", [])
        paging = search_result.get("paging", {})
        logger.info(f"Deal search completed. Found {len(results)} results")
        
        return HubSpotResponse(
            status="success",
            message=f"取引検索を正常に実行しました（{len(results)}件の取引を取得）",
            data={"results": results, "paging": paging},
            count=len(results)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search deals: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"取引検索に失敗しました: {str(e)}"
        )

@app.get("/hubspot/bukken/{bukken_id}/deals", response_model=HubSpotResponse)
async def get_hubspot_bukken_deals(bukken_id: str, api_key: str = Depends(verify_api_key)):
    """物件に関連づけられた取引を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        deals = await hubspot_deals_client.get_deals_by_bukken(bukken_id)
        logger.info(f"Retrieved {len(deals)} deals for bukken {bukken_id}")
        
        return HubSpotResponse(
            status="success",
            message=f"物件 '{bukken_id}' に関連づけられた取引を正常に取得しました（{len(deals)}件の取引）",
            data={"deals": deals, "bukken_id": bukken_id},
            count=len(deals)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deals for bukken {bukken_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"物件 '{bukken_id}' の取引取得に失敗しました: {str(e)}"
        )

@app.get("/hubspot/deals/pipelines/{pipeline_id}/history", response_model=HubSpotResponse)
async def get_hubspot_pipeline_history(
    pipeline_id: str, 
    stage: Optional[str] = None,
    owner: Optional[str] = None,
    keyword: Optional[str] = None,
    fromDate: Optional[str] = None,
    toDate: Optional[str] = None,
    limit: Optional[int] = 100,
    api_key: str = Depends(verify_api_key)
):
    """パイプラインの変更履歴を取得（mirai-baseのgetPipelineHistoryと同等）"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500, 
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )
        
        # オプションを構築
        options = {}
        if stage:
            options["stage"] = stage
        if owner:
            options["owner"] = owner
        if keyword:
            options["keyword"] = keyword
        if fromDate:
            options["fromDate"] = fromDate
        if toDate:
            options["toDate"] = toDate
        if limit:
            options["limit"] = limit
        
        logger.info(f"Getting pipeline history for pipeline {pipeline_id} with options: {options}")
        
        # パイプライン履歴を取得
        history_result = await hubspot_deals_client.get_pipeline_history(pipeline_id, options)
        
        if not history_result.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=f"パイプライン履歴の取得に失敗しました: {history_result.get('error', 'Unknown error')}"
            )
        
        deals = history_result.get("deals", [])
        pipeline_info = history_result.get("pipeline", {})
        
        logger.info(f"Retrieved {len(deals)} deals with history for pipeline {pipeline_id}")
        
        return HubSpotResponse(
            status="success",
            message=f"パイプライン '{pipeline_id}' の変更履歴を正常に取得しました（{len(deals)}件の取引）",
            data={
                "pipeline": pipeline_info,
                "deals": deals,
                "total": len(deals)
            },
            count=len(deals)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline history for {pipeline_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"パイプライン '{pipeline_id}' の履歴取得に失敗しました: {str(e)}"
        )



# 物件情報分析API
class PropertyAnalysisResponse(BaseModel):
    status: str = Field(..., example='success')
    message: str = Field(..., example='物件情報の解析が完了しました')
    data: Dict[str, Any] = Field(..., description='解析された物件情報')

@app.post('/property/analyze', response_model=PropertyAnalysisResponse)
async def analyze_property_document(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """
    物件情報のPDFや画像を解析してJSONで返す
    
    Args:
        file: アップロードされたファイル（PDFまたは画像）
        api_key: API認証キー
        
    Returns:
        解析された物件情報のJSON
    """
    logger.info(f'Property analysis request received for file: {file.filename}')
    
    # ファイルタイプの検証
    if not file.filename:
        raise HTTPException(status_code=400, detail='ファイル名が指定されていません')
    
    file_extension = file.filename.lower().split('.')[-1]
    supported_types = ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff']
    
    if file_extension not in supported_types:
        raise HTTPException(
            status_code=400, 
            detail="サポートされていないファイル形式です。対応形式: " + ", ".join(supported_types)
        )
    
    # ファイルサイズの検証（10MB制限）
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail='ファイルサイズが大きすぎます（最大10MB）')
    
    # 一時ファイルの作成
    temp_file_path = None
    try:
        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        logger.info(f'Temporary file created: {temp_file_path}')
        
        # 文書処理
        document_processor = DocumentProcessor()
        try:
            # ファイルタイプの判定
            if file_extension == 'pdf':
                file_type = 'pdf'
            else:
                file_type = 'image'
            
            # テキスト抽出
            logger.info('Starting text extraction')
            extracted_text = document_processor.process_file(temp_file_path, file_type)
            
            if not extracted_text or not extracted_text.strip():
                raise HTTPException(status_code=400, detail='ファイルからテキストを抽出できませんでした')
            
            logger.info(f'Text extraction completed. Length: {len(extracted_text)} characters')
            
        finally:
            document_processor.cleanup()
        
        # AI処理
        ai_processor = AIProcessor()
        try:
            # テキスト解析
            logger.info('Starting AI analysis')
            analysis_result = ai_processor.analyze_text(extracted_text)
            
            # 結果の検証
            if not ai_processor.validate_analysis_result(analysis_result):
                logger.warning('Analysis result validation failed, but continuing')
            
            logger.info('AI analysis completed successfully')
            
        except Exception as ai_error:
            logger.error(f'AI analysis failed: {str(ai_error)}')
            raise HTTPException(status_code=500, detail=f'AI解析に失敗しました: {str(ai_error)}')
        
        # レスポンスの作成
        response = PropertyAnalysisResponse(
            status='success',
            message='物件情報の解析が完了しました',
            data=analysis_result
        )
        
        logger.info('Property analysis completed successfully')
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Property analysis failed: {str(e)}')
        raise HTTPException(status_code=500, detail=f'解析処理中にエラーが発生しました: {str(e)}')
    
    finally:
        # 一時ファイルの削除
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f'Temporary file deleted: {temp_file_path}')
            except Exception as cleanup_error:
                logger.error(f'Failed to delete temporary file: {str(cleanup_error)}')


# =============================================================================
# deal_histories カスタムオブジェクト エンドポイント
# =============================================================================

@app.get("/hubspot/deal-histories/schema", response_model=HubSpotResponse)
async def get_deal_histories_schema(
    api_key: str = Depends(verify_api_key)
):
    """deal_historiesカスタムオブジェクトのスキーマを取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500,
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )

        logger.info("Getting deal_histories schema")

        schema = await hubspot_deal_histories_client.get_deal_histories_schema()

        logger.info(f"Retrieved deal_histories schema")

        return HubSpotResponse(
            status="success",
            message="deal_historiesスキーマを正常に取得しました",
            data={"schema": schema},
            count=1
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deal_histories schema: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"deal_historiesスキーマの取得に失敗しました: {str(e)}"
        )


@app.get("/hubspot/deal-histories", response_model=HubSpotResponse)
async def get_deal_histories(
    limit: Optional[int] = 100,
    after: Optional[str] = None,
    deal_id: Optional[str] = None,
    stage: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """deal_historiesカスタムオブジェクトの一覧を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500,
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )

        logger.info(f"Getting deal histories with filters: deal_id={deal_id}, stage={stage}, from_date={from_date}, to_date={to_date}")

        histories = await hubspot_deal_histories_client.get_deal_histories(
            limit=limit,
            after=after,
            deal_id=deal_id,
            stage=stage,
            from_date=from_date,
            to_date=to_date
        )

        logger.info(f"Retrieved {len(histories)} deal histories")

        return HubSpotResponse(
            status="success",
            message=f"deal_historiesを正常に取得しました（{len(histories)}件）",
            data={"histories": histories, "total": len(histories)},
            count=len(histories)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deal histories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"deal_historiesの取得に失敗しました: {str(e)}"
        )


@app.get("/hubspot/deal-histories/by-deal/{deal_id}", response_model=HubSpotResponse)
async def get_deal_histories_by_deal_id(
    deal_id: str,
    api_key: str = Depends(verify_api_key)
):
    """特定の取引IDの履歴を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500,
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )

        logger.info(f"Getting deal histories for deal ID: {deal_id}")

        histories = await hubspot_deal_histories_client.get_deal_histories_by_deal_id(deal_id)

        logger.info(f"Retrieved {len(histories)} histories for deal {deal_id}")

        return HubSpotResponse(
            status="success",
            message=f"取引ID '{deal_id}' の履歴を正常に取得しました（{len(histories)}件）",
            data={"histories": histories, "total": len(histories)},
            count=len(histories)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deal histories for deal {deal_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"取引ID '{deal_id}' の履歴取得に失敗しました: {str(e)}"
        )


@app.get("/hubspot/deal-histories/contracts", response_model=HubSpotResponse)
async def get_contract_histories(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """契約ステージの履歴を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500,
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )

        logger.info(f"Getting contract histories from {from_date} to {to_date}")

        histories = await hubspot_deal_histories_client.get_contract_histories(from_date, to_date)

        logger.info(f"Retrieved {len(histories)} contract histories")

        return HubSpotResponse(
            status="success",
            message=f"契約履歴を正常に取得しました（{len(histories)}件）",
            data={"histories": histories, "total": len(histories)},
            count=len(histories)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contract histories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"契約履歴の取得に失敗しました: {str(e)}"
        )


@app.get("/hubspot/deal-histories/settlements", response_model=HubSpotResponse)
async def get_settlement_histories(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """決済ステージの履歴を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500,
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )

        logger.info(f"Getting settlement histories from {from_date} to {to_date}")

        histories = await hubspot_deal_histories_client.get_settlement_histories(from_date, to_date)

        logger.info(f"Retrieved {len(histories)} settlement histories")

        return HubSpotResponse(
            status="success",
            message=f"決済履歴を正常に取得しました（{len(histories)}件）",
            data={"histories": histories, "total": len(histories)},
            count=len(histories)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get settlement histories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"決済履歴の取得に失敗しました: {str(e)}"
        )


@app.get("/hubspot/deal-histories/monthly-contracts", response_model=HubSpotResponse)
async def get_monthly_contract_counts(
    from_date: str,
    to_date: str,
    api_key: str = Depends(verify_api_key)
):
    """月別の契約件数を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500,
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )

        logger.info(f"Getting monthly contract counts from {from_date} to {to_date}")

        counts = await hubspot_deal_histories_client.get_monthly_contract_counts(from_date, to_date)

        logger.info(f"Retrieved monthly contract counts: {counts}")

        return HubSpotResponse(
            status="success",
            message=f"月別契約件数を正常に取得しました",
            data={"monthly_counts": counts, "total": sum(counts.values())},
            count=len(counts)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get monthly contract counts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"月別契約件数の取得に失敗しました: {str(e)}"
        )


@app.get("/hubspot/deal-histories/monthly-settlements", response_model=HubSpotResponse)
async def get_monthly_settlement_counts(
    from_date: str,
    to_date: str,
    api_key: str = Depends(verify_api_key)
):
    """月別の決済件数を取得"""
    try:
        if not Config.validate_config():
            raise HTTPException(
                status_code=500,
                detail="HubSpot API設定が正しくありません。環境変数を確認してください。"
            )

        logger.info(f"Getting monthly settlement counts from {from_date} to {to_date}")

        counts = await hubspot_deal_histories_client.get_monthly_settlement_counts(from_date, to_date)

        logger.info(f"Retrieved monthly settlement counts: {counts}")

        return HubSpotResponse(
            status="success",
            message=f"月別決済件数を正常に取得しました",
            data={"monthly_counts": counts, "total": sum(counts.values())},
            count=len(counts)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get monthly settlement counts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"月別決済件数の取得に失敗しました: {str(e)}"
        )


# 継続学習システムの初期化





if __name__ == "__main__":
    # 開発用サーバーの起動
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # 外部からのアクセスを許可
        port=8000,
        reload=True,  # 開発時は自動リロードを有効
        log_level="info"
    )
