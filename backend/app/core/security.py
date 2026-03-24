import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt

from app.core.config import get_settings
from app.core.enums import StepUpAction
from app.core.exceptions import UnauthorizedException

settings = get_settings()

bearer_scheme = HTTPBearer(
    scheme_name="bearerAuth",
    description="JWT Bearer Token Authentication",
    auto_error=False,
)



# PIN hashing — bcrypt (slow, appropriate for secrets users choose)

def hash_pin(pin: str) -> str:
    return bcrypt.using(rounds=12).hash(pin)


def verify_pin(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


def verify_pin_constant_time(plain: str, hashed: str | None) -> bool:
    
    """
    Always runs a bcrypt operation regardless of whether a hash exists.
    Prevents timing-based phone number enumeration on login.
    When hashed is None (member not found or no PIN set), dummy_verify()
    """
    if hashed is None:
        bcrypt.using(rounds=12).dummy_verify()
        return False
    return bcrypt.verify(plain, hashed)


# Refresh token hashing — SHA-256

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(incoming: str, stored_hash: str) -> bool:
    return secrets.compare_digest(hash_refresh_token(incoming), stored_hash)


# JWT helpers
def _build_token(payload: dict, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        {**payload, "exp": expire},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(subject: str) -> str:
    return _build_token(
        {"sub": subject, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> str:
    return _build_token(
        {"sub": subject, "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )


def create_step_up_token(subject: str, action: StepUpAction) -> str:
    return _build_token(
        {"sub": subject, "type": "step_up", "action": action.value},
        timedelta(minutes=5),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise UnauthorizedException("Invalid or expired token")