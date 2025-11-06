from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class HaihaiClickLogBase(BaseModel):
    """配配メールログの基本モデル"""
    email: str = Field(..., description="メールアドレス")
    mail_type: str = Field(..., description="メール種別")
    mail_id: str = Field(..., description="メールID")
    subject: str = Field(..., description="件名")
    click_date: datetime = Field(..., description="クリック日時")
    url: str = Field(..., description="URL")


class HaihaiClickLogCreate(HaihaiClickLogBase):
    """配配メールログ作成用モデル"""
    pass


class HaihaiClickLogUpdate(BaseModel):
    """配配メールログ更新用モデル"""
    email: Optional[str] = Field(None, description="メールアドレス")
    mail_type: Optional[str] = Field(None, description="メール種別")
    mail_id: Optional[str] = Field(None, description="メールID")
    subject: Optional[str] = Field(None, description="件名")
    click_date: Optional[datetime] = Field(None, description="クリック日時")
    url: Optional[str] = Field(None, description="URL")


class HaihaiClickLogResponse(HaihaiClickLogBase):
    """配配メールログレスポンス用モデル"""
    id: int = Field(..., description="ID")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")

    class Config:
        from_attributes = True


class HaihaiClickLogSearchRequest(BaseModel):
    """配配メールログ検索リクエスト"""
    email: Optional[str] = Field(None, description="メールアドレスで検索（部分一致）")
    mail_type: Optional[str] = Field(None, description="メール種別で検索")
    mail_id: Optional[str] = Field(None, description="メールIDで検索（部分一致）")
    start_date: Optional[datetime] = Field(None, description="クリック日時（開始）")
    end_date: Optional[datetime] = Field(None, description="クリック日時（終了）")
    limit: Optional[int] = Field(100, description="取得件数制限")
    offset: Optional[int] = Field(0, description="オフセット")


class HaihaiClickLogListResponse(BaseModel):
    """配配メールログ一覧レスポンス"""
    items: list[HaihaiClickLogResponse] = Field(..., description="配配メールログ一覧")
    total: int = Field(..., description="総件数")
    limit: int = Field(..., description="取得件数制限")
    offset: int = Field(..., description="オフセット")

