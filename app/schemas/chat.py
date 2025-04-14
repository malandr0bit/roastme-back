from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.schemas.user import User
from app.schemas.message import Message

# Base Chat Schema
class ChatBase(BaseModel):
    name: Optional[str] = None
    is_group: bool = False

# Schema for creating a Chat
class ChatCreate(ChatBase):
    user_ids: List[int]  # IDs de usuarios para crear el chat

# Schema for updating a Chat
class ChatUpdate(BaseModel):
    name: Optional[str] = None

# Schema for Chat response
class Chat(ChatBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schema for detailed Chat response
class ChatDetail(Chat):
    users: List[User]
    last_message: Optional[Message] = None
    
    class Config:
        from_attributes = True

# Schema for adding users to a chat
class ChatAddUsers(BaseModel):
    user_ids: List[int]
