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
from database.connection import db_connection

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
            # 更新するフィールドがない場合（すべてNone）は成功として扱う
            logger.warning(f"更新するフィールドがありませんでした: achievement_id={achievement_id}")
            # ただし、エラーではなく、既存データを返す
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
                message="物件買取実績を正常に取得しました（更新するフィールドがありませんでした）",
                data=achievement
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
        logger.error(f"物件買取実績の更新に失敗しました: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"トレースバック: {traceback.format_exc()}")
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

@router.delete("/purchase-achievements/{achievement_id}/image")
async def delete_purchase_achievement_image(
    achievement_id: int,
    api_key: dict = Depends(verify_api_key)
):
    """物件買取実績の画像を削除"""
    try:
        service = PurchaseAchievementService()
        
        # 既存レコードの確認
        existing = await service.get_by_id(achievement_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"物件買取実績（ID: {achievement_id}）が見つかりません"
            )
        
        # 画像URLが設定されているか確認
        image_url = existing.get("property_image_url")
        if not image_url:
            return {
                "status": "success",
                "message": "画像が設定されていないため、削除する必要がありません",
                "data": {"achievement_id": achievement_id}
            }
        
        # 画像URLからファイル名を抽出
        filename = None
        logger.info(f"画像URLからファイル名を抽出: image_url={image_url}, IMAGE_SERVER_UPLOAD_DIR={IMAGE_SERVER_UPLOAD_DIR}")
        
        if "/images/" in image_url:
            filename = image_url.split("/images/")[-1]
            # クエリパラメータやフラグメントを除去
            if "?" in filename:
                filename = filename.split("?")[0]
            if "#" in filename:
                filename = filename.split("#")[0]
            logger.info(f"抽出されたファイル名: {filename}")
        else:
            logger.warning(f"画像URLに'/images/'が含まれていません: {image_url}")
        
        # ファイル名が取得できた場合、物理ファイルを削除（画像サーバーの画像も削除）
        if filename and '/' not in filename and '..' not in filename:
            file_path = os.path.join(IMAGE_SERVER_UPLOAD_DIR, filename)
            logger.info(f"削除対象ファイルパス: {file_path}")
            logger.info(f"IMAGE_SERVER_UPLOAD_DIR: {IMAGE_SERVER_UPLOAD_DIR}")
            
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"画像サーバーの画像ファイルを削除しました: {file_path}")
                    
                    # ファイルが実際に削除されたか確認
                    if os.path.exists(file_path):
                        logger.warning(f"ファイル削除後もファイルが存在しています: {file_path}")
                    else:
                        logger.info(f"ファイル削除が正常に完了しました: {file_path}")
                except PermissionError as perm_error:
                    logger.error(f"画像ファイルの削除に権限エラーが発生しました: {file_path}, error: {str(perm_error)}", exc_info=True)
                    # 権限エラーの場合は処理を続行（データベースの更新は行う）
                except Exception as file_error:
                    logger.error(f"画像ファイルの削除に失敗しました: {file_path}, error: {str(file_error)}", exc_info=True)
                    # ファイル削除に失敗しても処理は続行（データベースの更新は行う）
            else:
                logger.warning(f"画像ファイルが見つかりませんでした（処理は続行）: {file_path}")
                # ファイルが存在しない場合でも、データベースの更新は行う
        else:
            logger.warning(f"ファイル名を抽出できませんでした。画像URL: {image_url}")
            if not filename:
                logger.warning("ファイル名がNoneまたは空です")
            if filename and ('/' in filename or '..' in filename):
                logger.warning(f"セキュリティチェックに失敗しました: filename={filename}")
        
        # データベースの画像URLをnullに更新（直接SQLで更新）
        try:
            logger.info(f"データベース更新を開始: achievement_id={achievement_id}")
            logger.info(f"db_connectionの状態: pool={db_connection.pool is not None}")
            
            # 接続プールが存在しない場合は作成
            if not db_connection.pool:
                logger.info("データベース接続プールが存在しないため、作成します")
                await db_connection.create_pool()
            
            query = "UPDATE purchase_achievements SET property_image_url = NULL WHERE id = %s"
            logger.info(f"実行するSQL: {query}, params: ({achievement_id},)")
            rowcount = await db_connection.execute_update(query, (achievement_id,))
            logger.info(f"データベース更新完了: achievement_id={achievement_id}, rowcount={rowcount}")
            
            if rowcount == 0:
                logger.warning(f"物件買取実績が見つかりませんでした: achievement_id={achievement_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"物件買取実績（ID: {achievement_id}）が見つかりません"
                )
        except HTTPException:
            raise
        except Exception as db_error:
            logger.error(f"データベース更新に失敗しました: {str(db_error)}", exc_info=True)
            logger.error(f"エラータイプ: {type(db_error).__name__}")
            logger.error(f"エラー詳細: {repr(db_error)}")
            import traceback
            logger.error(f"トレースバック: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"画像の削除に失敗しました: {str(db_error)}"
            )
        
        logger.info(f"物件買取実績の画像を削除しました: achievement_id={achievement_id}")
        
        return {
            "status": "success",
            "message": "画像を正常に削除しました",
            "data": {
                "achievement_id": achievement_id,
                "deleted_image_url": image_url
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"画像削除に失敗しました: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"画像の削除に失敗しました: {str(e)}"
        )
