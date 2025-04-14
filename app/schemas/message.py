from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Base Message Schema
class MessageBase(BaseModel):
    content: str = Field(..., min_length=1)
    chat_id: int

# Schema for creating a Message
class MessageCreate(MessageBase):
    pass

# Schema for updating a Message
class MessageUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)
    is_read: Optional[bool] = None

# Schema for Message response
class Message(MessageBase):
    id: int
    sender_id: int
    is_read: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema for detailed Message response (with sender info)
class MessageDetail(Message):
    sender_username: str
    
    class Config:
        from_attributes = True
