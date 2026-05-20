from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.auth.dependencies import get_current_admin_user
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.layout import Layout
from app.models.plot import Plot


def _setup_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(
        id="admin-1", email="admin@example.com", role="admin"
    )

    return SessionLocal


@pytest.fixture
def plot_db(tmp_path):
    SessionLocal = _setup_db(tmp_path)
    try:
        yield SessionLocal
    finally:
        app.dependency_overrides.clear()


def _seed_layout(SessionLocal):
    db = SessionLocal()
    try:
        layout = Layout(
            id="layout-1",
            name="Suryapet Phase 1",
            slug="suryapet-phase-1",
            status="published",
            plot_count=1,
            preview_url="https://cdn.example.com/layouts/layout-1/preview.png",
            hotspots_url="https://cdn.example.com/layouts/layout-1/hotspots.json",
        )
        plot = Plot(
            id="plot-1",
            layout_id="layout-1",
            plot_no="28",
            status="available",
            hotspot={"x": 1204, "y": 876, "r": 18},
            dim_ft="40*50",
            dim_type="rect",
            area_sq_ft=2000,
            area_sq_yd=222.2,
            owner="Mr. Varun",
            facing="East",
            extra={},
        )
        db.add(layout)
        db.add(plot)
        db.commit()
    finally:
        db.close()


def test_get_plot_admin_detail(plot_db):
    _seed_layout(plot_db)

    client = TestClient(app)
    response = client.get("/api/admin/layouts/layout-1/plots/28")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "plotNo": "28",
            "status": "available",
            "owner": "Mr. Varun",
            "dimFt": "40*50",
            "dimType": "rect",
            "areaSqFt": 2000.0,
            "areaSqYd": 222.2,
            "facing": "East",
            "hotspot": {"x": 1204, "y": 876, "r": 18},
        },
    }


def test_patch_plot_status_validation(plot_db):
    _seed_layout(plot_db)

    client = TestClient(app)

    ok_response = client.patch("/api/admin/layouts/layout-1/plots/28/status", json={"status": "reserved"})
    assert ok_response.status_code == 200
    assert ok_response.json() == {
        "success": True,
        "data": {
            "plotNo": "28",
            "status": "reserved",
        },
    }

    sold_response = client.patch("/api/admin/layouts/layout-1/plots/28/status", json={"status": "sold"})
    assert sold_response.status_code == 200
    assert sold_response.json()["data"]["status"] == "sold"

    invalid_response = client.patch("/api/admin/layouts/layout-1/plots/28/status", json={"status": "available"})
    assert invalid_response.status_code == 400
    assert invalid_response.json() == {
        "success": False,
        "error": {
            "code": "INVALID_STATUS_TRANSITION",
            "message": "Cannot transition from sold to available",
        },
    }
