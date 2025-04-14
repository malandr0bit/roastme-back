from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy import desc

from app.database import get_db
from app.models.user import User
from app.models.chat import Chat, UserChat
from app.models.message import Message
from app.schemas.chat import ChatCreate, Chat as ChatSchema, ChatDetail, ChatUpdate, ChatAddUsers
from app.api.deps import get_current_active_user

router = APIRouter()

@router.post("/", response_model=ChatSchema, status_code=status.HTTP_201_CREATED)
def create_chat(
    chat: ChatCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que todos los usuarios existen
    user_ids = chat.user_ids
    if current_user.id not in user_ids:
        user_ids.append(current_user.id)  # Asegurar que el creador esté en el chat
    
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    if len(users) != len(user_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more users not found"
        )
    
    # Crear el chat
    db_chat = Chat(
        name=chat.name,
        is_group=chat.is_group
    )
    db.add(db_chat)
    db.flush()
    
    # Asociar usuarios al chat
    for user_id in user_ids:
        is_admin = user_id == current_user.id  # El creador es administrador
        user_chat = UserChat(
            user_id=user_id,
            chat_id=db_chat.id,
            is_admin=is_admin
        )
        db.add(user_chat)
    
    db.commit()
    db.refresh(db_chat)
    return db_chat

@router.get("/", response_model=List[ChatDetail])
def read_user_chats(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Obtener todos los chats del usuario
    user_chats = db.query(UserChat).filter(UserChat.user_id == current_user.id).all()
    chat_ids = [uc.chat_id for uc in user_chats]
    
    # Obtener detalles de cada chat
    chats = []
    for chat_id in chat_ids:
        # Obtener el chat
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        
        # Obtener usuarios del chat
        chat_users = db.query(User).join(UserChat).filter(UserChat.chat_id == chat_id).all()
        
        # Obtener último mensaje
        last_message = db.query(Message).filter(
            Message.chat_id == chat_id
        ).order_by(desc(Message.created_at)).first()
        
        # Construir objeto de respuesta
        chat_detail = {
            "id": chat.id,
            "name": chat.name,
            "is_group": chat.is_group,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "users": chat_users,
            "last_message": last_message
        }
        chats.append(chat_detail)
    
    return chats[skip:skip+limit]

@router.get("/{chat_id}", response_model=ChatDetail)
def read_chat(
    chat_id: int,
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
    
    # Obtener el chat
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Obtener usuarios del chat
    chat_users = db.query(User).join(UserChat).filter(UserChat.chat_id == chat_id).all()
    
    # Obtener último mensaje
    last_message = db.query(Message).filter(
        Message.chat_id == chat_id
    ).order_by(desc(Message.created_at)).first()
    
    # Construir objeto de respuesta
    chat_detail = {
        "id": chat.id,
        "name": chat.name,
        "is_group": chat.is_group,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
        "users": chat_users,
        "last_message": last_message
    }
    
    return chat_detail

@router.put("/{chat_id}", response_model=ChatSchema)
def update_chat(
    chat_id: int,
    chat_update: ChatUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el usuario es administrador del chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == current_user.id,
        UserChat.chat_id == chat_id,
        UserChat.is_admin == True
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an admin of this chat"
        )
    
    # Obtener el chat
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Actualizar el chat
    if chat_update.name is not None:
        chat.name = chat_update.name
    
    db.add(chat)
    db.commit()
    db.refresh(chat)
    
    return chat

@router.post("/{chat_id}/users", response_model=ChatSchema)
def add_users_to_chat(
    chat_id: int,
    chat_add_users: ChatAddUsers,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el usuario es administrador del chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == current_user.id,
        UserChat.chat_id == chat_id,
        UserChat.is_admin == True
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an admin of this chat"
        )
    
    # Obtener el chat
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Verificar que el chat es grupal
    if not chat.is_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add users to individual chat"
        )
    
    # Verificar que los usuarios existen
    user_ids = chat_add_users.user_ids
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    if len(users) != len(user_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more users not found"
        )
    
    # Verificar si algún usuario ya está en el chat
    existing_users = db.query(UserChat).filter(
        UserChat.chat_id == chat_id,
        UserChat.user_id.in_(user_ids)
    ).all()
    
    existing_user_ids = [eu.user_id for eu in existing_users]
    new_user_ids = [uid for uid in user_ids if uid not in existing_user_ids]
    
    # Añadir nuevos usuarios al chat
    for user_id in new_user_ids:
        user_chat = UserChat(
            user_id=user_id,
            chat_id=chat_id,
            is_admin=False
        )
        db.add(user_chat)
    
    db.commit()
    db.refresh(chat)
    
    return chat

@router.delete("/{chat_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_from_chat(
    chat_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verificar que el usuario es administrador del chat o se elimina a sí mismo
    is_self_removal = current_user.id == user_id
    
    if not is_self_removal:
        admin_check = db.query(UserChat).filter(
            UserChat.user_id == current_user.id,
            UserChat.chat_id == chat_id,
            UserChat.is_admin == True
        ).first()
        
        if not admin_check:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not an admin of this chat"
            )
    
    # Verificar que el usuario a eliminar existe en el chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == user_id,
        UserChat.chat_id == chat_id
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in chat"
        )
    
    # Eliminar usuario del chat
    db.delete(user_chat)
    
    # Si el chat queda sin usuarios, eliminarlo
    remaining_users = db.query(UserChat).filter(UserChat.chat_id == chat_id).count()
    if remaining_users <= 1:  # Solo queda un usuario o ninguno
        # Eliminar todos los mensajes del chat
        db.query(Message).filter(Message.chat_id == chat_id).delete()
        # Eliminar todas las asociaciones usuario-chat
        db.query(UserChat).filter(UserChat.chat_id == chat_id).delete()
        # Eliminar el chat
        db.query(Chat).filter(Chat.id == chat_id).delete()
    
    db.commit()
    
    return None
