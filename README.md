# backend-api

FastAPI backend for layout uploads, public layout viewing, and plot management.

## Environment

Copy `.env.example` to `.env` and set `DATABASE_URL` to your PostgreSQL connection string.

## Run

```bash
uvicorn app.main:app --reload
```

## Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "message"
```
