from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AuthorizedIPBase(BaseModel):
    ip_address: str
    description: Optional[str] = None

class AuthorizedIPCreate(AuthorizedIPBase):
    pass

class AuthorizedIP(AuthorizedIPBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True
