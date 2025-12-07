from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from models.property_owner import PropertyOwnerResponse


class ProfitManagementBase(BaseModel):
    """粗利按分管理の基本モデル"""
    property_id: str = Field(..., description="物件番号（HubSpotの物件ID）")
    property_name: str = Field(..., description="物件名")
    property_type: Optional[str] = Field(None, description="種別")
    gross_profit: Optional[Decimal] = Field(None, description="粗利")
    profit_confirmed: bool = Field(False, description="粗利確定")
    accounting_year_month: Optional[date] = Field(None, description="計上年月（年月のみ、月初の日付）")


class ProfitManagementCreate(ProfitManagementBase):
    """粗利按分管理作成用モデル"""
    pass


class ProfitManagementUpdate(BaseModel):
    """粗利按分管理更新用モデル"""
    property_id: Optional[str] = Field(None, description="物件番号（HubSpotの物件ID）")
    property_name: Optional[str] = Field(None, description="物件名")
    property_type: Optional[str] = Field(None, description="種別")
    gross_profit: Optional[Decimal] = Field(None, description="粗利")
    profit_confirmed: Optional[bool] = Field(None, description="粗利確定")
    accounting_year_month: Optional[date] = Field(None, description="計上年月（年月のみ、月初の日付）")


class ProfitManagementResponse(ProfitManagementBase):
    """粗利按分管理レスポンス用モデル"""
    seq_no: int = Field(..., description="登録時自動採番する番号")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")
    owners: Optional[List[PropertyOwnerResponse]] = Field(None, description="物件担当者一覧")

    class Config:
        from_attributes = True


class ProfitManagementSearchRequest(BaseModel):
    """粗利按分管理検索リクエスト"""
    property_id: Optional[str] = Field(None, description="物件番号で検索")
    property_name: Optional[str] = Field(None, description="物件名で検索")
    profit_confirmed: Optional[bool] = Field(None, description="粗利確定で検索")
    limit: Optional[int] = Field(100, description="取得件数制限")
    offset: Optional[int] = Field(0, description="オフセット")


class ProfitManagementListResponse(BaseModel):
    """粗利按分管理一覧レスポンス"""
    items: list[ProfitManagementResponse] = Field(..., description="粗利按分管理一覧")
    total: int = Field(..., description="総件数")
    limit: int = Field(..., description="取得件数制限")
    offset: int = Field(..., description="オフセット")
