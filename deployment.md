# API Deployment

# Phase 1 API Deployment

---

# Recommended Environment

- FastAPI app
- PostgreSQL database
- S3-compatible object storage + CDN
- Background task worker (FastAPI BackgroundTasks or Celery)
- Environment variables for secrets

---

# Required Environment Variables

```text
DATABASE_URL
JWT_SECRET
STORAGE_BUCKET
STORAGE_ACCESS_KEY
STORAGE_SECRET_KEY
STORAGE_CDN_BASE_URL
PUBLIC_APP_URL
SEED_ADMIN_EMAIL       ← used once for initial admin seed
SEED_ADMIN_PASSWORD    ← used once for initial admin seed
```

---

# Deployment Checklist

- Run migrations (`alembic upgrade head`)
- Run admin seed script (first deploy only)
- Verify database connection
- Verify storage bucket access and CDN URL
- Set CORS for frontend domain
- Enable HTTPS
- Confirm health endpoint responds
- Test DXF + Excel upload end to end
- Confirm preview PNG and hotspot JSON appear on CDN
