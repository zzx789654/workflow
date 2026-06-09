from datetime import UTC, datetime, timedelta

import jwt
from jwt import PyJWTError as JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, token_version: int = 0, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode(
        {"sub": subject, "exp": expire, "tv": token_version},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(subject: str, token_version: int = 0) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": subject, "exp": expire, "type": "refresh", "tv": token_version},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str, expected_type: str | None = None) -> str | None:
    """回傳 subject（user id），驗證失敗回 None。不檢查 token_version。"""
    payload = decode_token_payload(token, expected_type)
    return str(payload["sub"]) if payload and payload.get("sub") else None


def decode_token_payload(token: str, expected_type: str | None = None) -> dict | None:
    """回傳完整 payload（含 sub / tv），供需要驗證 token_version 的呼叫端使用。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if expected_type is not None and payload.get("type") != expected_type:
            return None
        return payload if payload.get("sub") else None
    except (JWTError, Exception):
        return None
