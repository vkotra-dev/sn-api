from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.auth.security import decode_access_token, is_valid_token_payload
from app.auth.service import get_admin_user_by_id
from app.core.errors import APIError
from app.database.session import get_db
from app.models.admin_user import AdminUser

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError("UNAUTHORIZED", "Login required", status_code=401)

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise APIError("UNAUTHORIZED", "Login required", status_code=401) from exc

    if not is_valid_token_payload(payload):
        raise APIError("UNAUTHORIZED", "Login required", status_code=401)

    user = get_admin_user_by_id(db, str(payload["sub"]))
    if user is None or not user.is_active:
        raise APIError("UNAUTHORIZED", "Login required", status_code=401)

    if user.role != "admin":
        raise APIError("FORBIDDEN", "Access denied", status_code=403)

    return user
