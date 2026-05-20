import os

import bcrypt

from app.database.session import get_db
from app.models.admin_user import AdminUser


def seed() -> None:
    email = os.environ["SEED_ADMIN_EMAIL"]
    password = os.environ["SEED_ADMIN_PASSWORD"]

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    db_gen = get_db()
    db = next(db_gen)
    try:
        user = AdminUser(email=email, password_hash=hashed, role="admin")
        db.add(user)
        db.commit()
        print(f"Admin created: {email}")
    finally:
        db.close()
        db_gen.close()


if __name__ == "__main__":
    seed()
