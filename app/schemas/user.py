from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

# Base User Schema (shared properties)
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None

# Schema for creating a User
class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

# Schema for updating a User
class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)

# Schema for User response with additional data from DB
class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema for login
class UserLogin(BaseModel):
    username: str
    password: str

# Schema for token
class Token(BaseModel):
    access_token: str
    token_type: str

# Schema for token data
class TokenData(BaseModel):
    username: Optional[str] = None
