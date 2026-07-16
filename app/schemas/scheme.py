from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SchemeBase(BaseModel):
    scheme_code: str
    name: str
    description: Optional[str] = None
    discount_percentage: Optional[float] = 0.0
    incentive_amount: Optional[float] = 0.0
    is_active: Optional[bool] = True

class SchemeCreate(SchemeBase):
    pass

class SchemeUpdate(BaseModel):
    scheme_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    discount_percentage: Optional[float] = None
    incentive_amount: Optional[float] = None
    is_active: Optional[bool] = None

class SchemeResponse(SchemeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
