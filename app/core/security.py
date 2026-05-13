import os
import jwt
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import Request,Response, HTTPException, status
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET no configurado")

def hash_pin(pin: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        pin.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_pin_hash(pin: str, pin_hash: str) -> bool:
    return hmac.compare_digest(hash_pin(pin), pin_hash)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str,session_id: str) -> str:
    payload = {
        "sub": user_id,
        "sid": session_id,
        "type": "access",
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def create_refresh_token(session_id: str) -> str:
    payload = {
        "sid": session_id,
        "type": "refresh",
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def set_access_cookie(response: Response, access_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="none" if settings.ENV == "production" else "lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES*60,
        path="/"
    )

def set_refresh_cookie(response: Response, refresh_token: str):
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENV == "production",
        samesite="none" if settings.ENV == "production" else "lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/"
    )

def get_token_from_request(request: Request) -> str:
    token = request.cookies.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado"
    )

def clear_refresh_cookie(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/"
    )
    response.delete_cookie(
        key="refresh_token",
        path="/"
    )