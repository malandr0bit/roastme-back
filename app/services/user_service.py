from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional

from app.models.user import User
from app.models.authorized_ip import AuthorizedIP
from app.schemas.user import UserCreate, UserUpdate
from app.api.deps import get_password_hash, verify_password

def get_user(db: Session, user_id: int) -> User:
    """
    Obtiene un usuario por su ID
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Obtiene un usuario por su nombre de usuario
    """
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Obtiene un usuario por su correo electrónico
    """
    return db.query(User).filter(User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """
    Obtiene una lista de usuarios
    """
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> User:
    """
    Crea un nuevo usuario
    """
    # Verificar si el usuario ya existe
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    db_email = get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Crear el nuevo usuario
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        profile_pic_url=user.profile_pic_url
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def update_user(db: Session, user_id: int, user_update: UserUpdate) -> User:
    """
    Actualiza los datos de un usuario
    """
    db_user = get_user(db, user_id)
    
    # Actualizar campos si se proporcionan
    if user_update.username is not None:
        # Verificar si el nombre de usuario ya está en uso
        existing_user = get_user_by_username(db, user_update.username)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        db_user.username = user_update.username
    
    if user_update.email is not None:
        # Verificar si el correo ya está en uso
        existing_email = get_user_by_email(db, user_update.email)
        if existing_email and existing_email.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        db_user.email = user_update.email
    
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    
    if user_update.profile_pic_url is not None:
        db_user.profile_pic_url = user_update.profile_pic_url
    
    if user_update.password is not None:
        db_user.hashed_password = get_password_hash(user_update.password)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Autentica a un usuario verificando su nombre de usuario y contraseña
    """
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def deactivate_user(db: Session, user_id: int) -> User:
    """
    Desactiva un usuario (no lo elimina)
    """
    db_user = get_user(db, user_id)
    db_user.is_active = False
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def reactivate_user(db: Session, user_id: int) -> User:
    """
    Reactiva un usuario que estaba desactivado
    """
    db_user = get_user(db, user_id)
    db_user.is_active = True
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def check_ip_authorization(db: Session, user_id: int, ip_address: str) -> bool:
    """
    Verifica si la dirección IP está autorizada para el usuario
    """
    from app.models.authorized_ip import AuthorizedIP
    from datetime import datetime
    
    # Localhost siempre está permitido para desarrollo
    if ip_address == "127.0.0.1" or ip_address == "::1" or ip_address.startswith("192.168."):
        return True
    
    # Verificar si la IP está en la lista de IPs autorizadas
    authorized_ip = db.query(AuthorizedIP).filter(
        AuthorizedIP.user_id == user_id,
        AuthorizedIP.ip_address == ip_address,
        AuthorizedIP.is_active == True
    ).first()
    
    if authorized_ip:
        # Actualizar la fecha de último uso
        authorized_ip.last_used_at = datetime.now()
        db.add(authorized_ip)
        db.commit()
        return True
    
    return False

def register_authorized_ip(db: Session, user_id: int, ip_address: str, description: str = None) -> None:
    """
    Registra una dirección IP como autorizada para el usuario
    """
    from app.models.authorized_ip import AuthorizedIP
    
    # Verificar si la IP ya está registrada
    existing_ip = db.query(AuthorizedIP).filter(
        AuthorizedIP.user_id == user_id,
        AuthorizedIP.ip_address == ip_address
    ).first()
    
    if existing_ip:
        # Si existe pero está desactivada, activarla
        if not existing_ip.is_active:
            existing_ip.is_active = True
            existing_ip.description = description or existing_ip.description
            db.add(existing_ip)
            db.commit()
    else:
        # Crear nuevo registro de IP autorizada
        new_authorized_ip = AuthorizedIP(
            user_id=user_id,
            ip_address=ip_address,
            description=description
        )
        db.add(new_authorized_ip)
        db.commit()

def get_authorized_ips(db: Session, user_id: int) -> List[AuthorizedIP]:
    """
    Obtiene todas las IPs autorizadas para un usuario
    """
    from app.models.authorized_ip import AuthorizedIP
    
    return db.query(AuthorizedIP).filter(
        AuthorizedIP.user_id == user_id,
        AuthorizedIP.is_active == True
    ).all()

def deactivate_authorized_ip(db: Session, user_id: int, ip_address: str) -> bool:
    """
    Desactiva una IP autorizada para un usuario
    """
    from app.models.authorized_ip import AuthorizedIP
    
    authorized_ip = db.query(AuthorizedIP).filter(
        AuthorizedIP.user_id == user_id,
        AuthorizedIP.ip_address == ip_address,
        AuthorizedIP.is_active == True
    ).first()
    
    if authorized_ip:
        authorized_ip.is_active = False
        db.add(authorized_ip)
        db.commit()
        return True
    
    return False
