from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import uvicorn
import os

from app.api.routes import users, messages, chats
from app.database import engine, Base, get_db
from app.models.user import User
from app.services.user_service import check_ip_authorization
from app.api.deps import get_current_active_user

# Crear tablas en la base de datos
# Nota: En producción, deberías usar Alembic para migraciones
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Mensajería",
    description="API para una aplicación de mensajería con autenticación por IP y cifrado de mensajes",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, limitar a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware para validar IP autorizada
@app.middleware("http")
async def validate_ip(request: Request, call_next):
    # Obtener la dirección IP del cliente
    client_ip = request.client.host
    
    # Rutas públicas que no requieren verificación de IP
    public_routes = [
        ("/users/", "POST"),  # Registro de usuario
        ("/users/token", "POST"),  # Login
        ("/", "GET"),  # Ruta principal
        ("/health", "GET"),  # Verificación de salud
        ("/health/db", "GET"),  # Verificación de DB
        ("/docs", "GET"),  # Documentación de la API
        ("/openapi.json", "GET"),  # Esquema OpenAPI
    ]
    
    # Verificar si es una ruta pública
    if any(request.url.path == route[0] and request.method == route[1] for route in public_routes):
        return await call_next(request)
    
    # Para rutas protegidas, verificar la IP si hay un usuario autenticado
    try:
        # Verificar si hay un token en la solicitud
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            
            # Necesitamos una sesión de base de datos
            from app.api.deps import get_current_user
            from app.services.user_service import check_ip_authorization
            from app.database import get_db
            
            # Obtener una sesión de DB
            db_generator = get_db()
            db = next(db_generator)
            
            try:
                # Obtener el usuario actual desde el token
                user = get_current_user(token, db)
                
                # Verificar si la IP está autorizada
                if not check_ip_authorization(db, user.id, client_ip):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "detail": "IP address not authorized for this user",
                            "client_ip": client_ip
                        }
                    )
            finally:
                # Cerrar la sesión de DB
                db_generator.close()
    except Exception as e:
        # Log del error pero permitir que el middleware de autenticación
        # maneje los errores relacionados con tokens inválidos
        print(f"Error validating IP: {str(e)}")
    
    # Continuar con la solicitud
    return await call_next(request)

# Incluir routers
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(chats.router, prefix="/chats", tags=["chats"])

@app.get("/", tags=["root"])
def read_root():
    return {
        "message": "Bienvenido a la API de Mensajería",
        "documentation": "/docs",
        "version": "1.0.0"
    }

# Endpoint para verificar el estado de la API
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}

# Endpoint para verificar la conexión a la base de datos
@app.get("/health/db", tags=["health"])
def db_health_check(db: Session = Depends(get_db)):
    try:
        # Intentar hacer una consulta simple
        db.execute("SELECT 1").fetchall()
        return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }

if __name__ == "__main__":
    # Permitir configurar el host y puerto mediante variables de entorno
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    # Iniciar el servidor
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
