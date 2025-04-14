from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Dict

from app.database import get_db
from app.models.user import User
from app.models.authorized_ip import AuthorizedIP
from app.schemas.user import UserCreate, User as UserSchema, UserUpdate, UserLogin, Token
from app.api.deps import get_password_hash, verify_password, create_access_token, get_current_active_user
from app.services.user_service import register_authorized_ip, get_authorized_ips, deactivate_authorized_ip
from datetime import timedelta
from app.config import settings
from pydantic import BaseModel

router = APIRouter()

@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    db_email = db.query(User).filter(User.email == user.email).first()
    if db_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
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

@router.get("/me", response_model=UserSchema)
def read_user_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.put("/me", response_model=UserSchema)
def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if user_update.username is not None:
        db_user = db.query(User).filter(User.username == user_update.username).first()
        if db_user and db_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        current_user.username = user_update.username
    
    if user_update.email is not None:
        db_email = db.query(User).filter(User.email == user_update.email).first()
        if db_email and db_email.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = user_update.email
    
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    
    if user_update.profile_pic_url is not None:
        current_user.profile_pic_url = user_update.profile_pic_url
    
    if user_update.password is not None:
        current_user.hashed_password = get_password_hash(user_update.password)
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/", response_model=List[UserSchema])
def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=UserSchema)
def read_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user

@router.post("/token", response_model=Token)
def login_for_access_token(user_login: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_login.username).first()
    if not user or not verify_password(user_login.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Registrar la IP del cliente como autorizada
    client_ip = request.client.host
    register_authorized_ip(db, user.id, client_ip, "IP used for login")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoints para gestionar IPs autorizadas
from app.schemas.authorized_ip import AuthorizedIP as AuthorizedIPSchema, AuthorizedIPCreate

@router.get("/me/ips", response_model=List[AuthorizedIPSchema])
def read_authorized_ips(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Obtiene todas las IPs autorizadas para el usuario actual
    """
    return get_authorized_ips(db, current_user.id)

@router.post("/me/ips", response_model=AuthorizedIPSchema, status_code=status.HTTP_201_CREATED)
def add_authorized_ip(
    ip_data: AuthorizedIPCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Añade una nueva IP autorizada para el usuario actual
    """
    from app.models.authorized_ip import AuthorizedIP
    
    # Verificar si la IP ya existe
    existing_ip = db.query(AuthorizedIP).filter(
        AuthorizedIP.user_id == current_user.id,
        AuthorizedIP.ip_address == ip_data.ip_address
    ).first()
    
    if existing_ip:
        if existing_ip.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IP address already authorized"
            )
        else:
            # Reactivar la IP
            existing_ip.is_active = True
            existing_ip.description = ip_data.description
            db.add(existing_ip)
            db.commit()
            db.refresh(existing_ip)
            return existing_ip
    
    # Crear nueva IP autorizada
    new_ip = AuthorizedIP(
        user_id=current_user.id,
        ip_address=ip_data.ip_address,
        description=ip_data.description
    )
    db.add(new_ip)
    db.commit()
    db.refresh(new_ip)
    return new_ip

@router.delete("/me/ips/{ip_address}", status_code=status.HTTP_204_NO_CONTENT)
def remove_authorized_ip(
    ip_address: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Elimina una IP autorizada para el usuario actual
    """
    # No permitir eliminar la IP desde la que se está haciendo la solicitud
    from fastapi import Request
    request = Request.scope.get("fastapi_aio_request")
    client_ip = request.client.host
    
    if client_ip == ip_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the IP address you are currently using"
        )
    
    success = deactivate_authorized_ip(db, current_user.id, ip_address)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP address not found or already deactivated"
        )
    
    return None
