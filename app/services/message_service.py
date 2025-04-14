from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from typing import List, Optional, Dict, Any

from app.models.message import Message
from app.models.chat import Chat, UserChat
from app.models.user import User
from app.schemas.message import MessageCreate, MessageUpdate

def get_message(db: Session, message_id: int) -> Message:
    """
    Obtiene un mensaje por su ID
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    return message

def get_chat_messages(
    db: Session, 
    chat_id: int, 
    user_id: int, 
    skip: int = 0, 
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Obtiene los mensajes de un chat con información adicional del remitente
    """
    # Verificar que el usuario pertenece al chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == user_id,
        UserChat.chat_id == chat_id
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this chat"
        )
    
    # Obtener mensajes con información adicional del remitente
    messages_with_sender = db.query(
        Message,
        User.username.label("sender_username")
    ).join(
        User, Message.sender_id == User.id
    ).filter(
        Message.chat_id == chat_id
    ).order_by(
        desc(Message.created_at)
    ).offset(skip).limit(limit).all()
    
    # Construir respuesta
    result = []
    for msg, username in messages_with_sender:
        msg_dict = {**msg.__dict__}
        if "_sa_instance_state" in msg_dict:
            del msg_dict["_sa_instance_state"]
        msg_dict["sender_username"] = username
        result.append(msg_dict)
    
    return result

def create_message(db: Session, message: MessageCreate, user_id: int) -> Message:
    """
    Crea un nuevo mensaje
    """
    # Verificar que el chat existe
    chat = db.query(Chat).filter(Chat.id == message.chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Verificar que el usuario pertenece al chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == user_id,
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
        sender_id=user_id,
        chat_id=message.chat_id
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    return db_message

def update_message(db: Session, message_id: int, message_update: MessageUpdate, user_id: int) -> Message:
    """
    Actualiza un mensaje
    """
    # Verificar que el mensaje existe
    db_message = get_message(db, message_id)
    
    # Verificar que el usuario es el remitente del mensaje
    if db_message.sender_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update messages from other users"
        )
    
    # Actualizar el mensaje
    if message_update.content is not None:
        db_message.content = message_update.content
    
    if message_update.is_read is not None:
        db_message.is_read = message_update.is_read
    
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    return db_message

def delete_message(db: Session, message_id: int, user_id: int) -> None:
    """
    Elimina un mensaje
    """
    # Verificar que el mensaje existe
    db_message = get_message(db, message_id)
    
    # Verificar que el usuario es el remitente del mensaje
    if db_message.sender_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete messages from other users"
        )
    
    # Eliminar el mensaje
    db.delete(db_message)
    db.commit()

def mark_message_as_read(db: Session, message_id: int, user_id: int) -> Message:
    """
    Marca un mensaje como leído
    """
    # Verificar que el mensaje existe
    db_message = get_message(db, message_id)
    
    # Verificar que el usuario pertenece al chat
    user_chat = db.query(UserChat).filter(
        UserChat.user_id == user_id,
        UserChat.chat_id == db_message.chat_id
    ).first()
    
    if not user_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this chat"
        )
    
    # Marcar como leído
    if not db_message.is_read:
        db_message.is_read = True
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
    
    return db_message

def encrypt_message_content(content: str) -> str:
    """
    Cifra el contenido del mensaje para almacenamiento seguro
    Esta es una implementación simplificada para la descripción actualizada
    que mencionaba un chat cifrado
    """
    # En una implementación real, usarías una biblioteca como cryptography
    # para cifrar correctamente el contenido
    
    # Este es solo un ejemplo simplificado
    # NO usar en producción - implementar cifrado adecuado
    return f"ENCRYPTED:{content}"

def decrypt_message_content(encrypted_content: str) -> str:
    """
    Descifra el contenido del mensaje para visualización
    """
    # Esta es una implementación simplificada
    # En una implementación real, usarías la misma biblioteca de cifrado
    # para descifrar correctamente
    
    if encrypted_content.startswith("ENCRYPTED:"):
        return encrypted_content[10:]
    return encrypted_content

def get_unread_message_count(db: Session, user_id: int) -> Dict[int, int]:
    """
    Obtiene el número de mensajes no leídos por chat para un usuario
    """
    # Obtener todos los chats del usuario
    user_chats = db.query(UserChat).filter(UserChat.user_id == user_id).all()
    chat_ids = [uc.chat_id for uc in user_chats]
    
    result = {}
    for chat_id in chat_ids:
        # Contar mensajes no leídos en cada chat (excepto los enviados por el usuario)
        unread_count = db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.is_read == False,
            Message.sender_id != user_id
        ).count()
        
        result[chat_id] = unread_count
    
    return result
