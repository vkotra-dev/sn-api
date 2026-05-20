# API Authentication

# Phase 1 Authentication

---

# Auth Model

- Admin logs in with email + password
- API returns JWT access token
- Admin sends token in Authorization header

```text
Authorization: Bearer <token>
```

---

# Admin User Creation

Admin users are not created via API in Phase 1. They are seeded directly via a migration script on first deploy.

## Seed script

```python
# scripts/seed_admin.py
import os
import bcrypt
from app.database.session import get_db
from app.models import AdminUser

def seed():
    email = os.environ["SEED_ADMIN_EMAIL"]
    password = os.environ["SEED_ADMIN_PASSWORD"]
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))

    db = next(get_db())
    user = AdminUser(email=email, password_hash=hashed.decode(), role="admin")
    db.add(user)
    db.commit()
    print(f"Admin created: {email}")

if __name__ == "__main__":
    seed()
```

Run once after first migration:

```bash
SEED_ADMIN_EMAIL=admin@example.com \
SEED_ADMIN_PASSWORD=strongpassword \
python scripts/seed_admin.py
```

Additional admin users must be added directly to the database in Phase 1. A user management UI is Phase 2.

---

# Public APIs

Public APIs do not require auth.

Allowed public endpoints:

```text
GET /api/public/layouts/{slug}
```

---

# Admin APIs

All admin endpoints require a valid JWT:

```text
POST  /api/auth/login
POST  /api/admin/layouts
GET   /api/admin/layouts
GET   /api/admin/layouts/{layoutId}
PATCH /api/admin/layouts/{layoutId}/plots/{plotNo}/status
```

---

# JWT

- Algorithm: HS256
- Expiry: 24 hours
- Secret: `JWT_SECRET` environment variable
- Payload: `{ sub: userId, email, role, exp }`

---

# Phase 1 Role

One role only:

```text
admin
```

Additional roles and user management deferred to Phase 2.
