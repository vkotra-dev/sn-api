# backend-api

FastAPI backend for layout uploads, public layout viewing, and plot management.

## Environment

Copy `.env.example` to `.env` and set `DATABASE_URL` to your PostgreSQL connection string.
For local upload testing, generated assets are served from `/storage` using `storage_root` in `.env`.

## Run

```bash
uvicorn app.main:app --reload
```

## Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "message"
```
