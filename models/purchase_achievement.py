from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class PurchaseAchievementBase(BaseModel):
    """物件買取実績のベースモデル"""
    # 一覧表示項目
    property_image_url: Optional[str] = Field(None, description="物件写真URL")
    purchase_date: Optional[date] = Field(None, description="買取日")
    title: Optional[str] = Field(None, description="タイトル（例：◯県◯市一棟アパート）")
    
    # 詳細表示項目
    property_name: Optional[str] = Field(None, description="物件名")
    building_age: Optional[int] = Field(None, description="築年数")
    structure: Optional[str] = Field(None, description="構造")
    nearest_station: Optional[str] = Field(None, description="最寄り")
    
    # 住所情報
    prefecture: Optional[str] = Field(None, description="都道府県")
    city: Optional[str] = Field(None, description="市区町村")
    address_detail: Optional[str] = Field(None, description="番地以下")
    
    # その他管理項目（HubSpot関連はオプショナル）
    hubspot_bukken_id: Optional[str] = Field(None, description="HubSpotの物件ID")
    hubspot_bukken_created_date: Optional[datetime] = Field(None, description="HubSpotの物件登録日（オブジェクトの作成日）")
    hubspot_deal_id: Optional[str] = Field(None, description="HubSpotの取引ID")
    is_public: bool = Field(False, description="公開フラグ")

class PurchaseAchievementCreate(PurchaseAchievementBase):
    """物件買取実績作成用モデル"""
    pass

class PurchaseAchievementUpdate(BaseModel):
    """物件買取実績更新用モデル"""
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

class PurchaseAchievement(PurchaseAchievementBase):
    """物件買取実績レスポンス用モデル"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

