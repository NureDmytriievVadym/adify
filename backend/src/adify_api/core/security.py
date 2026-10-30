import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

from adify_api.core.config import get_settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


@lru_cache
def dummy_password_hash() -> str:
    """Checked for unknown emails so sign-in takes as long as for existing accounts."""
    return hash_password(secrets.token_urlsafe(16))


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "exp"]},
    )


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
