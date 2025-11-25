from fastapi import APIRouter, HTTPException, Depends, Header, Query, Body, UploadFile, File, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
import logging
import asyncio
import sys
import os
import uuid
import shutil
from pathlib import Path
from models.purchase_achievement import PurchaseAchievement, PurchaseAchievementCreate, PurchaseAchievementUpdate
from services.purchase_achievement_service import PurchaseAchievementService
from database.api_keys import api_key_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# 画像アップロード用のディレクトリ（mirai-imageサーバー用）
IMAGE_SERVER_UPLOAD_DIR = os.getenv('IMAGE_SERVER_UPLOAD_DIR', '/app/images')
os.makedirs(IMAGE_SERVER_UPLOAD_DIR, exist_ok=True)

# 画像サーバーのベースURL（環境変数で設定可能、デフォルトはmirai-imageサーバー）
# 外部からアクセス可能なURLを設定（ブラウザからアクセスするため）
IMAGE_SERVER_BASE_URL = os.getenv('IMAGE_SERVER_BASE_URL', 'http://mirai-image:80')
IMAGE_SERVER_PUBLIC_URL = os.getenv('IMAGE_SERVER_PUBLIC_URL', 'http://localhost:8080')

# 許可する画像形式
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

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

# レスポンス用のモデル
class PurchaseAchievementListResponse(BaseModel):
    """物件買取実績一覧レスポンス"""
    status: str = Field(example="success", description="レスポンスステータス")
    message: str = Field(example="物件買取実績一覧を正常に取得しました", description="レスポンスメッセージ")
    data: List[Dict[str, Any]] = Field(description="物件買取実績一覧")
    count: int = Field(example=10, description="取得件数")
    total: Optional[int] = Field(None, example=100, description="総件数")

class PurchaseAchievementDetailResponse(BaseModel):
    """物件買取実績詳細レスポンス"""
    status: str = Field(example="success", description="レスポンスステータス")
    message: str = Field(example="物件買取実績詳細を正常に取得しました", description="レスポンスメッセージ")
    data: Dict[str, Any] = Field(description="物件買取実績詳細")

# リクエスト用のモデル
class PurchaseAchievementCreateRequest(BaseModel):
    """物件買取実績作成リクエスト"""
    property_image_url: Optional[str] = None
    purchase_date: Optional[date] = None
    title: Optional[str] = None
    property_name: Optional[str] = None
    building_age: Optional[int] = None
    structure: Optional[str] = None
    nearest_station: Optional[str] = None
    prefecture: Optional[str] = None
    city: Optional[str] = None
    address_detail: Optional[str] = None
    hubspot_bukken_id: Optional[str] = None
    hubspot_bukken_created_date: Optional[datetime] = None
    hubspot_deal_id: Optional[str] = None
    is_public: bool = False

class PurchaseAchievementUpdateRequest(BaseModel):
    """物件買取実績更新リクエスト"""
    property_image_url: Optional[str] = None
    purchase_date: Optional[date] = None
    title: Optional[str] = None
    property_name: Optional[str] = None
    building_age: Optional[int] = None
    structure: Optional[str] = None
    nearest_station: Optional[str] = None
    prefecture: Optional[str] = None
    city: Optional[str] = None
    address_detail: Optional[str] = None
    hubspot_bukken_created_date: Optional[datetime] = None
    hubspot_deal_id: Optional[str] = None
    is_public: Optional[bool] = None

def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """datetimeをISO形式の文字列に変換"""
    if dt is None:
        return None
    return dt.isoformat()

def format_date(d: Optional[date]) -> Optional[str]:
    """dateを文字列に変換"""
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")

@router.get("/purchase-achievements", response_model=PurchaseAchievementListResponse)
async def get_purchase_achievements(
    is_public: Optional[bool] = Query(None, description="公開フラグでフィルタリング"),
    prefecture: Optional[str] = Query(None, description="都道府県でフィルタリング"),
    limit: int = Query(100, ge=1, le=1000, description="取得件数上限"),
    offset: int = Query(0, ge=0, description="オフセット"),
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績一覧を取得"""
    try:
        service = PurchaseAchievementService()
        
        # 一覧を取得
        achievements = await service.get_list(
            is_public=is_public,
            prefecture=prefecture,
            limit=limit,
            offset=offset
        )
        
        # 総件数を取得
        total = await service.get_count(is_public=is_public, prefecture=prefecture)
        
        # 日付を文字列に変換
        for achievement in achievements:
            if achievement.get("purchase_date"):
                achievement["purchase_date"] = format_date(achievement["purchase_date"])
            if achievement.get("hubspot_bukken_created_date"):
                achievement["hubspot_bukken_created_date"] = format_datetime(achievement["hubspot_bukken_created_date"])
            if achievement.get("created_at"):
                achievement["created_at"] = format_datetime(achievement["created_at"])
            if achievement.get("updated_at"):
                achievement["updated_at"] = format_datetime(achievement["updated_at"])
        
        return PurchaseAchievementListResponse(
            status="success",
            message=f"物件買取実績一覧を正常に取得しました（{len(achievements)}件）",
            data=achievements,
            count=len(achievements),
            total=total
        )
        
    except Exception as e:
        logger.error(f"物件買取実績一覧の取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"物件買取実績一覧の取得に失敗しました: {str(e)}"
        )

@router.get("/purchase-achievements/{achievement_id}", response_model=PurchaseAchievementDetailResponse)
async def get_purchase_achievement(
    achievement_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績詳細を取得"""
    try:
        service = PurchaseAchievementService()
        achievement = await service.get_by_id(achievement_id)
        
        if not achievement:
            raise HTTPException(
                status_code=404,
                detail=f"物件買取実績（ID: {achievement_id}）が見つかりません"
            )
        
        # 日付を文字列に変換
        if achievement.get("purchase_date"):
            achievement["purchase_date"] = format_date(achievement["purchase_date"])
        if achievement.get("hubspot_bukken_created_date"):
            achievement["hubspot_bukken_created_date"] = format_datetime(achievement["hubspot_bukken_created_date"])
        if achievement.get("created_at"):
            achievement["created_at"] = format_datetime(achievement["created_at"])
        if achievement.get("updated_at"):
            achievement["updated_at"] = format_datetime(achievement["updated_at"])
        
        return PurchaseAchievementDetailResponse(
            status="success",
            message="物件買取実績詳細を正常に取得しました",
            data=achievement
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件買取実績詳細の取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"物件買取実績詳細の取得に失敗しました: {str(e)}"
        )

@router.post("/purchase-achievements", response_model=PurchaseAchievementDetailResponse)
async def create_purchase_achievement(
    request: PurchaseAchievementCreateRequest,
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績を作成"""
    try:
        service = PurchaseAchievementService()
        
        achievement_create = PurchaseAchievementCreate(
            property_image_url=request.property_image_url,
            purchase_date=request.purchase_date,
            title=request.title,
            property_name=request.property_name,
            building_age=request.building_age,
            structure=request.structure,
            nearest_station=request.nearest_station,
            prefecture=request.prefecture,
            city=request.city,
            address_detail=request.address_detail,
            hubspot_bukken_id=request.hubspot_bukken_id,
            hubspot_bukken_created_date=request.hubspot_bukken_created_date,
            hubspot_deal_id=request.hubspot_deal_id,
            is_public=request.is_public
        )
        
        achievement_id = await service.create(achievement_create)
        achievement = await service.get_by_id(achievement_id)
        
        if not achievement:
            raise HTTPException(
                status_code=500,
                detail="物件買取実績の作成に失敗しました"
            )
        
        # 日付を文字列に変換
        if achievement.get("purchase_date"):
            achievement["purchase_date"] = format_date(achievement["purchase_date"])
        if achievement.get("hubspot_bukken_created_date"):
            achievement["hubspot_bukken_created_date"] = format_datetime(achievement["hubspot_bukken_created_date"])
        if achievement.get("created_at"):
            achievement["created_at"] = format_datetime(achievement["created_at"])
        if achievement.get("updated_at"):
            achievement["updated_at"] = format_datetime(achievement["updated_at"])
        
        return PurchaseAchievementDetailResponse(
            status="success",
            message="物件買取実績を正常に作成しました",
            data=achievement
        )
        
    except Exception as e:
        logger.error(f"物件買取実績の作成に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"物件買取実績の作成に失敗しました: {str(e)}"
        )

@router.patch("/purchase-achievements/{achievement_id}", response_model=PurchaseAchievementDetailResponse)
async def update_purchase_achievement(
    achievement_id: int,
    request: PurchaseAchievementUpdateRequest,
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績を更新"""
    try:
        service = PurchaseAchievementService()
        
        # 既存レコードの確認
        existing = await service.get_by_id(achievement_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"物件買取実績（ID: {achievement_id}）が見つかりません"
            )
        
        achievement_update = PurchaseAchievementUpdate(
            property_image_url=request.property_image_url,
            purchase_date=request.purchase_date,
            title=request.title,
            property_name=request.property_name,
            building_age=request.building_age,
            structure=request.structure,
            nearest_station=request.nearest_station,
            prefecture=request.prefecture,
            city=request.city,
            address_detail=request.address_detail,
            hubspot_bukken_created_date=request.hubspot_bukken_created_date,
            hubspot_deal_id=request.hubspot_deal_id,
            is_public=request.is_public
        )
        
        success = await service.update(achievement_id, achievement_update)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="物件買取実績の更新に失敗しました"
            )
        
        achievement = await service.get_by_id(achievement_id)
        
        # 日付を文字列に変換
        if achievement.get("purchase_date"):
            achievement["purchase_date"] = format_date(achievement["purchase_date"])
        if achievement.get("hubspot_bukken_created_date"):
            achievement["hubspot_bukken_created_date"] = format_datetime(achievement["hubspot_bukken_created_date"])
        if achievement.get("created_at"):
            achievement["created_at"] = format_datetime(achievement["created_at"])
        if achievement.get("updated_at"):
            achievement["updated_at"] = format_datetime(achievement["updated_at"])
        
        return PurchaseAchievementDetailResponse(
            status="success",
            message="物件買取実績を正常に更新しました",
            data=achievement
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件買取実績の更新に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"物件買取実績の更新に失敗しました: {str(e)}"
        )

@router.delete("/purchase-achievements/{achievement_id}")
async def delete_purchase_achievement(
    achievement_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績を削除（HubSpotのデータは削除しない）"""
    try:
        service = PurchaseAchievementService()
        
        # 既存レコードの確認
        existing = await service.get_by_id(achievement_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"物件買取実績（ID: {achievement_id}）が見つかりません"
            )
        
        # 削除処理（HubSpotのデータは削除しない）
        success = await service.delete(achievement_id)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="物件買取実績の削除に失敗しました"
            )
        
        return {
            "status": "success",
            "message": "物件買取実績を正常に削除しました",
            "data": {"id": achievement_id}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"物件買取実績の削除に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"物件買取実績の削除に失敗しました: {str(e)}"
        )

@router.post("/purchase-achievements/sync")
async def sync_purchase_achievements(
    api_key: dict = Depends(verify_api_key)
):
    """HubSpotから物件買取実績情報を取り込むバッチ処理を実行"""
    try:
        # バッチスクリプトのパスを取得
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(script_dir, "scripts", "sync_purchase_achievements.py")
        
        logger.info(f"バッチ処理開始: script_dir={script_dir}, script_path={script_path}")
        
        # スクリプトが存在するか確認
        if not os.path.exists(script_path):
            error_msg = f"バッチスクリプトが見つかりません: {script_path}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )
        
        # スクリプトのディレクトリをパスに追加（インポート前に）
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
            logger.info(f"パスに追加しました: {script_dir}")
        
        # バックグラウンドでバッチを実行
        async def run_sync():
            """バッチ処理を非同期で実行"""
            try:
                logger.info("バッチ処理のインポートを開始します")
                
                # バッチスクリプトのクラスをインポート
                try:
                    from scripts.sync_purchase_achievements import PurchaseAchievementsSync
                    logger.info("PurchaseAchievementsSync クラスのインポートに成功しました")
                except ImportError as e:
                    logger.error(f"インポートエラー: {str(e)}", exc_info=True)
                    raise
                except Exception as e:
                    logger.error(f"インポート時の予期しないエラー: {str(e)}", exc_info=True)
                    raise
                
                # 同期処理を実行
                logger.info("バッチ処理の実行を開始します")
                sync = PurchaseAchievementsSync()
                await sync.sync()
                
                logger.info("バッチ処理が正常に完了しました")
                
            except ImportError as e:
                logger.error(f"モジュールのインポートに失敗しました: {str(e)}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"バッチ処理の実行中にエラーが発生しました: {str(e)}", exc_info=True)
                raise
        
        # バックグラウンドタスクとして非同期で実行（エラーをハンドリング）
        async def run_with_error_handling():
            """エラーハンドリング付きでバッチ処理を実行"""
            try:
                await run_sync()
            except Exception as e:
                logger.error(f"バックグラウンドタスクの実行中にエラーが発生しました: {str(e)}", exc_info=True)
        
        # タスクを作成してバックグラウンドで実行
        logger.info("バックグラウンドタスクを作成します")
        asyncio.create_task(run_with_error_handling())
        
        return {
            "status": "success",
            "message": "バッチ処理を開始しました。バックグラウンドで実行中です。",
            "data": {
                "script": "sync_purchase_achievements.py",
                "status": "running"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"バッチ処理の開始に失敗しました: {str(e)}"
        logger.error(error_detail, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@router.post("/purchase-achievements/upload-image")
async def upload_purchase_achievement_image(
    file: UploadFile = File(...),
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績の画像をアップロード（mirai-imageサーバーに保存）"""
    try:
        # ファイル名の検証
        if not file.filename:
            raise HTTPException(status_code=400, detail="ファイル名が指定されていません")
        
        # ファイル拡張子の検証
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"サポートされていない画像形式です。対応形式: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
            )
        
        # ファイルサイズの検証
        file_content = await file.read()
        file_size = len(file_content)
        if file_size > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"ファイルサイズが大きすぎます（最大10MB）。現在のサイズ: {file_size / (1024 * 1024):.2f}MB"
            )
        
        # ファイルポインタを先頭に戻す
        await file.seek(0)
        
        # 一意のファイル名を生成
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(IMAGE_SERVER_UPLOAD_DIR, unique_filename)
        
        # ファイルをmirai-imageサーバーのディレクトリに保存
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        logger.info(f"画像をmirai-imageサーバーにアップロードしました: {file_path} ({file_size} bytes)")
        
        # 画像URLを返す（外部からアクセス可能なURLを使用）
        image_url = f"{IMAGE_SERVER_PUBLIC_URL}/images/{unique_filename}"
        
        return {
            "status": "success",
            "message": "画像のアップロードに成功しました",
            "data": {
                "image_url": image_url,
                "filename": unique_filename,
                "size": file_size
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"画像アップロードに失敗しました: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"画像のアップロードに失敗しました: {str(e)}"
        )

@router.get("/purchase-achievements/images/{filename}")
async def get_purchase_achievement_image(
    filename: str,
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績の画像を取得（mirai-imageサーバーにリダイレクト）"""
    try:
        # セキュリティチェック：ファイル名にパス区切り文字が含まれていないか確認
        if '/' in filename or '..' in filename:
            raise HTTPException(status_code=400, detail="無効なファイル名です")
        
        # mirai-imageサーバーにリダイレクト（外部からアクセス可能なURLを使用）
        image_url = f"{IMAGE_SERVER_PUBLIC_URL}/images/{filename}"
        return RedirectResponse(url=image_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"画像取得に失敗しました: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"画像の取得に失敗しました: {str(e)}"
        )
