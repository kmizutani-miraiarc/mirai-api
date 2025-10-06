from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class OwnerType(str, Enum):
    """担当者種別"""
    PURCHASE = "purchase"
    SALES = "sales"


class PropertyOwnerBase(BaseModel):
    """物件担当者の基本モデル"""
    property_id: str = Field(..., description="物件番号（HubSpotの物件ID）")
    owner_type: OwnerType = Field(..., description="種別（仕入or販売）")
    owner_id: str = Field(..., description="担当者ID")
    owner_name: str = Field(..., description="担当者名")
    settlement_date: Optional[date] = Field(None, description="決済日")
    price: Optional[Decimal] = Field(None, description="価格")
    profit_rate: Optional[Decimal] = Field(None, description="粗利率(%)")
    profit_amount: Optional[Decimal] = Field(None, description="粗利")


class PropertyOwnerCreate(PropertyOwnerBase):
    """物件担当者作成用モデル"""
    pass


class PropertyOwnerUpdate(BaseModel):
    """物件担当者更新用モデル"""
    owner_id: Optional[str] = Field(None, description="担当者ID")
    owner_name: Optional[str] = Field(None, description="担当者名")
    settlement_date: Optional[date] = Field(None, description="決済日")
    price: Optional[Decimal] = Field(None, description="価格")
    profit_rate: Optional[Decimal] = Field(None, description="粗利率(%)")
    profit_amount: Optional[Decimal] = Field(None, description="粗利")


class PropertyOwnerResponse(PropertyOwnerBase):
    """物件担当者レスポンス用モデル"""
    id: int = Field(..., description="ID")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")

    class Config:
        from_attributes = True


class PropertyOwnerSearchRequest(BaseModel):
    """物件担当者検索リクエスト"""
    property_id: Optional[str] = Field(None, description="物件番号で検索")
    owner_type: Optional[OwnerType] = Field(None, description="担当者種別で検索")
    owner_id: Optional[str] = Field(None, description="担当者IDで検索")
    owner_name: Optional[str] = Field(None, description="担当者名で検索")
    settlement_date_from: Optional[date] = Field(None, description="決済日（開始）")
    settlement_date_to: Optional[date] = Field(None, description="決済日（終了）")
    limit: Optional[int] = Field(100, description="取得件数制限")
    offset: Optional[int] = Field(0, description="オフセット")


class PropertyOwnerListResponse(BaseModel):
    """物件担当者一覧レスポンス"""
    items: list[PropertyOwnerResponse] = Field(..., description="物件担当者一覧")
    total: int = Field(..., description="総件数")
    limit: int = Field(..., description="取得件数制限")
    offset: int = Field(..., description="オフセット")
