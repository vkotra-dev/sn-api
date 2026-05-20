from fastapi.testclient import TestClient

from app.auth.security import create_access_token, decode_access_token
from app.main import app


def test_login_missing_fields_returns_validation_error() -> None:
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"email": "admin@example.com"})
    assert response.status_code == 422


def test_access_token_contains_expected_claims() -> None:
    token = create_access_token(subject="user-1", email="admin@example.com", role="admin")
    payload = decode_access_token(token)

    assert payload["sub"] == "user-1"
    assert payload["email"] == "admin@example.com"
    assert payload["role"] == "admin"
    assert "exp" in payload
