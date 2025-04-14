from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.message import Message
from app.models.chat import Chat, UserChat
from app.schemas.message import MessageCreate, Message as MessageSchema, MessageDetail, MessageUpdate
from app.api.deps import get_current_active_user

router = APIRouter()

@router.post("/", response_model=MessageSchema, status_code=status.HTTP_201_CREATED)
def create_message(
    message: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el chat existe
    chat = db.query(Chat).filter(Chat.id == message.chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Verificar que el usuario pertenece al chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == current_user.id,
        UserChat.chat_id == message.chat_id
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this chat"
        )
    
    # Crear el mensaje
    db_message = Message(
        content=message.content,
        sender_id=current_user.id,
        chat_id=message.chat_id
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

@router.get("/chat/{chat_id}", response_model=List[MessageDetail])
def read_chat_messages(
    chat_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el usuario pertenece al chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == current_user.id,
        UserChat.chat_id == chat_id
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this chat"
        )
    
    # Obtener mensajes con información adicional del remitente
    messages = db.query(
        Message,
        User.username.label("sender_username")
    ).join(
        User, Message.sender_id == User.id
    ).filter(
        Message.chat_id == chat_id
    ).order_by(
        Message.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    # Construir respuesta
    result = []
    for msg, username in messages:
        msg_dict = {**msg.__dict__}
        if "_sa_instance_state" in msg_dict:
            del msg_dict["_sa_instance_state"]
        msg_dict["sender_username"] = username
        result.append(msg_dict)
    
    return result

@router.put("/{message_id}", response_model=MessageSchema)
def update_message(
    message_id: int,
    message_update: MessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el mensaje existe
    db_message = db.query(Message).filter(Message.id == message_id).first()
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Verificar que el usuario es el remitente del mensaje
    if db_message.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update messages from other users"
        )
    
    # Actualizar el mensaje
    if message_update.content is not None:
        db_message.content = message_update.content
    
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el mensaje existe
    db_message = db.query(Message).filter(Message.id == message_id).first()
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Verificar que el usuario es el remitente del mensaje
    if db_message.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete messages from other users"
        )
    
    # Eliminar el mensaje
    db.delete(db_message)
    db.commit()
    
    return None

@router.put("/{message_id}/read", response_model=MessageSchema)
def mark_message_as_read(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el mensaje existe
    db_message = db.query(Message).filter(Message.id == message_id).first()
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Verificar que el usuario pertenece al chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == current_user.id,
        UserChat.chat_id == db_message.chat_id
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this chat"
        )
    
    # Marcar como leído
    db_message.is_read = True
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    return db_message
