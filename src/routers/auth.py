from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import (
    MONITORING_API_KEY,
    create_access_token,
    create_monitoring_token,
    decode_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from ..database import get_db
from ..models import Role, User
from ..schemas import LoginRequest, MonitoringTokenRequest, SignupRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=422, detail="Email already registered")

    # Validate institution_id if provided
    if body.institution_id:
        inst = db.query(User).filter(
            User.id == body.institution_id,
            User.role == Role.institution,
        ).first()
        if not inst:
            raise HTTPException(
                status_code=404,
                detail=f"Institution '{body.institution_id}' not found",
            )

    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        institution_id=body.institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role.value, user.email)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.role.value, user.email)
    return TokenResponse(access_token=token)


@router.post("/monitoring-token", response_model=TokenResponse)
def get_monitoring_token(
    body: MonitoringTokenRequest,
    current_user: User = Depends(require_roles(Role.monitoring_officer)),
):
    """
    Exchange a valid Monitoring Officer JWT + the API key for a short-lived
    scoped monitoring token (1 hour, read-only).
    """
    if body.key != MONITORING_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    scoped_token = create_monitoring_token(current_user.id)
    return TokenResponse(access_token=scoped_token)
