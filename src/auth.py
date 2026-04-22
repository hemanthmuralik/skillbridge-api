import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User

load_dotenv()

# ── Startup security checks ───────────────────────────────────────────────────
# Fail fast: refuse to start if critical secrets are missing or weak.
# This prevents the common mistake of running with a hardcoded dev key in prod.

SECRET_KEY: str | None = os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ValueError(
        "SECRET_KEY environment variable must be set and at least 32 characters long. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

MONITORING_API_KEY: str | None = os.getenv("MONITORING_API_KEY")
if not MONITORING_API_KEY:
    raise ValueError("MONITORING_API_KEY environment variable must be set.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
MONITORING_TOKEN_EXPIRE_HOURS = 1

# auto_error=False so we can raise 401 (not 403) on missing token
_bearer_optional = HTTPBearer(auto_error=False)


def _require_bearer(credentials=Depends(_bearer_optional)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")
    return credentials


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Token creation ────────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str, email: str) -> str:
    """Standard 24-hour JWT for all roles."""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "role": role,
        "email": email,
        "token_type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_monitoring_token(user_id: str) -> str:
    """Short-lived 1-hour scoped token exclusively for monitoring endpoints."""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "role": "monitoring_officer",
        "token_type": "monitoring",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=MONITORING_TOKEN_EXPIRE_HOURS)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── Token decoding ────────────────────────────────────────────────────────────

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_require_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the standard access token; return the User row."""
    payload = decode_token(credentials.credentials)
    if payload.get("token_type") != "access":
        raise HTTPException(status_code=401, detail="Standard access token required")
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_roles(*roles: Role):
    """Return a dependency that enforces one of the given roles."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user

    return dependency


def get_monitoring_user(
    credentials: HTTPAuthorizationCredentials = Depends(_require_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Validate the scoped monitoring token (token_type == 'monitoring')."""
    payload = decode_token(credentials.credentials)
    if payload.get("token_type") != "monitoring":
        raise HTTPException(
            status_code=401,
            detail="Monitoring-scoped token required. Obtain one via POST /auth/monitoring-token",
        )
    if payload.get("role") != "monitoring_officer":
        raise HTTPException(status_code=401, detail="Token not issued for monitoring_officer role")
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
