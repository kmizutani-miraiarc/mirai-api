from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ProfitTargetBase(BaseModel):
    """粗利目標の基本モデル"""
    owner_id: str = Field(..., description="担当者ID（HubSpotの担当者ID）")
    owner_name: str = Field(..., description="担当者名")
    year: int = Field(..., description="年度")
    q1_target: Optional[Decimal] = Field(None, description="1Q目標額")
    q2_target: Optional[Decimal] = Field(None, description="2Q目標額")
    q3_target: Optional[Decimal] = Field(None, description="3Q目標額")
    q4_target: Optional[Decimal] = Field(None, description="4Q目標額")


class ProfitTargetCreate(ProfitTargetBase):
    """粗利目標作成用モデル"""
    pass


class ProfitTargetUpdate(BaseModel):
    """粗利目標更新用モデル"""
    owner_id: Optional[str] = Field(None, description="担当者ID（HubSpotの担当者ID）")
    owner_name: Optional[str] = Field(None, description="担当者名")
    year: Optional[int] = Field(None, description="年度")
    q1_target: Optional[Decimal] = Field(None, description="1Q目標額")
    q2_target: Optional[Decimal] = Field(None, description="2Q目標額")
    q3_target: Optional[Decimal] = Field(None, description="3Q目標額")
    q4_target: Optional[Decimal] = Field(None, description="4Q目標額")


class ProfitTargetResponse(ProfitTargetBase):
    """粗利目標レスポンス用モデル"""
    id: int = Field(..., description="ID")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")

    class Config:
        from_attributes = True


class ProfitTargetSearchRequest(BaseModel):
    """粗利目標検索リクエスト"""
    owner_id: Optional[str] = Field(None, description="担当者IDで検索")
    year: Optional[int] = Field(None, description="年度で検索")
    limit: Optional[int] = Field(100, description="取得件数制限")
    offset: Optional[int] = Field(0, description="オフセット")


class ProfitTargetListResponse(BaseModel):
    """粗利目標一覧レスポンス"""
    items: list[ProfitTargetResponse] = Field(..., description="粗利目標一覧")
    total: int = Field(..., description="総件数")
    limit: int = Field(..., description="取得件数制限")
    offset: int = Field(..., description="オフセット")


