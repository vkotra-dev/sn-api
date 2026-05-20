import bcrypt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import (
    AuthUser,
    LoginRequest,
    LoginResponse,
    LoginResponseEnvelope,
)
from app.auth.security import create_access_token
from app.auth.service import get_admin_user_by_email
from app.core.errors import APIError
from app.database.session import get_db

router = APIRouter()


@router.post("/login", response_model=LoginResponseEnvelope)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponseEnvelope:
    user = get_admin_user_by_email(db, payload.email)
    if user is None or not user.is_active:
        raise APIError("UNAUTHORIZED", "Invalid email or password", status_code=401)

    if not bcrypt.checkpw(payload.password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise APIError("UNAUTHORIZED", "Invalid email or password", status_code=401)

    token = create_access_token(subject=user.id, email=user.email, role=user.role)
    response = LoginResponse(
        accessToken=token,
        user=AuthUser(id=user.id, email=user.email, role=user.role),
    )
    return LoginResponseEnvelope(data=response)
