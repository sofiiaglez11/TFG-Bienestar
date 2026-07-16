import os
import jwt # para los tokens
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext # para hashear contraseñas

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:

    '''
    Encripta la contraseña
    '''
    return pwd_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifica si la contraseña es correcta
    """
    return pwd_context.verify(plain, hashed)

def create_token(user_id: str, email: str) -> str:
    '''
    Crea un token con el id del usuario, el email y la fecha de expiración.
    '''
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
