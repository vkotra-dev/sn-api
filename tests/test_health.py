from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

import app.api.router as api_router
from app.main import app


class _FakeConnection:
    def execute(self, *_args, **_kwargs) -> None:
        return None

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_args) -> None:
        return None


class _FakeEngine:
    def connect(self) -> _FakeConnection:
        return _FakeConnection()


class _FailingEngine:
    def connect(self) -> _FakeConnection:
        raise SQLAlchemyError("boom")


def test_health_reports_ok(monkeypatch) -> None:
    monkeypatch.setattr(api_router, "get_engine", lambda: _FakeEngine())
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok", "database": "ok"}}


def test_health_reports_database_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(api_router, "get_engine", lambda: _FailingEngine())
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "error": {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Database unavailable",
        },
    }
