from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET = os.getenv("JWT_SECRET")
ALGO = "HS256"

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)

def create_token(data):
    expire = datetime.utcnow() + timedelta(hours=8)
    data.update({"exp": expire})
    return jwt.encode(data, SECRET, algorithm=ALGO)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        return payload
    except JWTError:
        return None