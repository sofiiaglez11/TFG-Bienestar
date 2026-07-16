import os
import jwt # para los tokens
import bcrypt # para hashear contraseñas
from datetime import datetime, timedelta, timezone

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas


def hash_password(plain: str) -> str:
    '''
    Encripta la contraseña
    '''
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifica si la contraseña es correcta
    """
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str) -> str:
    '''
    Crea un token con el id del usuario, el email y la fecha de expiración.
    '''
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
