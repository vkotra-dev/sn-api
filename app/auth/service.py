from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser


def get_admin_user_by_email(db: Session, email: str) -> AdminUser | None:
    statement = select(AdminUser).where(AdminUser.email == email)
    return db.execute(statement).scalar_one_or_none()


def get_admin_user_by_id(db: Session, user_id: str) -> AdminUser | None:
    statement = select(AdminUser).where(AdminUser.id == user_id)
    return db.execute(statement).scalar_one_or_none()

