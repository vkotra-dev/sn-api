from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import ezdxf
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app import models  # noqa: F401
from app.auth.dependencies import get_current_admin_user
from app.database.base import Base
from app.database.session import get_db
from app.layouts import service as layout_service
from app.layouts.storage import LocalStorageBackend
from app.main import app


def _build_sample_dxf(path: Path, plots: list[tuple[str, float]]) -> None:
    doc = ezdxf.new("R2010")
    block = doc.blocks.new(name="LAYOUT_BLOCK")

    block.add_line((0, 0), (40, 0), dxfattribs={"layer": "boundry"})
    block.add_line((40, 0), (40, 20), dxfattribs={"layer": "boundry"})
    block.add_line((40, 20), (0, 20), dxfattribs={"layer": "boundry"})
    block.add_line((0, 20), (0, 0), dxfattribs={"layer": "boundry"})

    for plot_no, x in plots:
        text = block.add_text(plot_no, dxfattribs={"layer": "Plot_No", "height": 2.0})
        text.dxf.insert = (x, 10)
        block.add_circle((x, 10), radius=1.5, dxfattribs={"layer": "Plot_No"})

    doc.modelspace().add_blockref(block.name, (0, 0))
    doc.saveas(path)


def _build_sample_excel(path: Path, plots: list[tuple[str, str, str, float, float, str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Plot no", "Owner", "Dim ft", "Size ft", "Size yards", "Facing"])
    for plot_no, owner, dim_ft, size_ft, size_yards, facing in plots:
        sheet.append([plot_no, owner, dim_ft, size_ft, size_yards, facing])
    workbook.save(path)


@pytest.fixture
def test_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    storage = LocalStorageBackend(root=tmp_path / "storage")

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
    monkeypatch.setattr(layout_service, "get_session_local", lambda: SessionLocal)
    monkeypatch.setattr(layout_service, "get_storage_backend", lambda: storage)

    yield
    app.dependency_overrides.clear()


def test_upload_layout_publishes_and_serves_public_layout(tmp_path: Path, test_app: None) -> None:
    dxf_path = tmp_path / "layout.dxf"
    excel_path = tmp_path / "layout.xlsx"
    _build_sample_dxf(dxf_path, [("28A", 10), ("29B", 30)])
    _build_sample_excel(excel_path, [("28A", "Mr. A", "33*50", 1650, 183.33, "East"), ("29B", "Mr. B", "40*50", 2000, 222.22, "West")])

    client = TestClient(app)
    with dxf_path.open("rb") as dxf_file, excel_path.open("rb") as excel_file:
        response = client.post(
            "/api/admin/layouts",
            data={"name": "Suryapet Phase 1"},
            files={
                "dxf_file": ("layout.dxf", dxf_file, "application/dxf"),
                "excel_file": (
                    "layout.xlsx",
                    excel_file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )

    assert response.status_code == 200
    upload = response.json()
    assert upload == {
        "success": True,
        "data": {
            "layoutId": upload["data"]["layoutId"],
            "name": "Suryapet Phase 1",
            "slug": "suryapet-phase-1",
            "status": "processing",
        },
    }

    layout_id = upload["data"]["layoutId"]
    slug = upload["data"]["slug"]
    storage_root = tmp_path / "storage"
    assert (storage_root / f"layouts/{layout_id}/source/layout.dxf").exists()
    assert (storage_root / f"layouts/{layout_id}/source/layout.xlsx").exists()

    admin_detail = client.get(f"/api/admin/layouts/{layout_id}")
    assert admin_detail.status_code == 200
    admin_data = admin_detail.json()["data"]
    assert admin_data["status"] == "published"
    assert admin_data["plotCount"] == 2
    assert admin_data["previewUrl"] == f"/storage/layouts/{layout_id}/preview.png"
    assert admin_data["hotspotsUrl"] == f"/storage/layouts/{layout_id}/hotspots.json"

    list_response = client.get("/api/admin/layouts")
    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["slug"] == "suryapet-phase-1"

    public_response = client.get(f"/api/public/layouts/{slug}")
    assert public_response.status_code == 200
    public_layout = public_response.json()["data"]
    assert "id" not in public_layout
    assert public_layout["slug"] == "suryapet-phase-1"
    assert public_layout["previewUrl"] == f"/storage/layouts/{layout_id}/preview.png"
    assert public_layout["hotspotsUrl"] == f"/storage/layouts/{layout_id}/hotspots.json"
    assert len(public_layout["plots"]) == 2
    assert public_layout["plots"][0]["plotNo"] == "28A"
    assert "owner" not in public_layout["plots"][0]
    assert "extra" not in public_layout["plots"][0]


def test_upload_layout_ignores_non_integer_plot_labels(tmp_path: Path, test_app: None) -> None:
    dxf_path = tmp_path / "layout-mixed.dxf"
    excel_path = tmp_path / "layout-mixed.xlsx"
    _build_sample_dxf(
        dxf_path,
        [("28A", 10), ("10.0M BUILDING LINE", 15), ("29B", 30), ("revised club house - 24-5-2021", 35)],
    )
    _build_sample_excel(
        excel_path,
        [("28A", "Mr. A", "33*50", 1650, 183.33, "East"), ("29B", "Mr. B", "40*50", 2000, 222.22, "West")],
    )

    client = TestClient(app)
    with dxf_path.open("rb") as dxf_file, excel_path.open("rb") as excel_file:
        response = client.post(
            "/api/admin/layouts",
            data={"name": "Alpha Layout"},
            files={
                "dxf_file": ("layout-alpha.dxf", dxf_file, "application/dxf"),
                "excel_file": (
                    "layout-alpha.xlsx",
                    excel_file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )

    assert response.status_code == 200
    layout_id = response.json()["data"]["layoutId"]
    public_response = client.get(f"/api/public/layouts/{response.json()['data']['slug']}")
    assert public_response.status_code == 200
    public_plots = public_response.json()["data"]["plots"]
    assert [plot["plotNo"] for plot in public_plots] == ["28A", "29B"]
    assert layout_id


def test_upload_layout_real_sample_files_publish(tmp_path: Path, test_app: None) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    dxf_source = repo_root / "SURYAPET-DTCP-LAYOUT-2 - REVISED 24-5-21 club house.dxf"
    excel_source = repo_root / "complete plots.xlsx"

    dxf_path = tmp_path / dxf_source.name
    excel_path = tmp_path / excel_source.name
    shutil.copyfile(dxf_source, dxf_path)
    shutil.copyfile(excel_source, excel_path)

    client = TestClient(app)
    with dxf_path.open("rb") as dxf_file, excel_path.open("rb") as excel_file:
        response = client.post(
            "/api/admin/layouts",
            data={"name": "Real Sample Layout"},
            files={
                "dxf_file": (dxf_path.name, dxf_file, "application/dxf"),
                "excel_file": (excel_path.name, excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
        )

    assert response.status_code == 200
    upload = response.json()["data"]
    layout_id = upload["layoutId"]
    slug = upload["slug"]

    admin_detail = client.get(f"/api/admin/layouts/{layout_id}")
    assert admin_detail.status_code == 200
    admin_data = admin_detail.json()["data"]
    assert admin_data["status"] == "published"
    assert admin_data["plotCount"] == 941
    assert admin_data["previewUrl"] == f"/storage/layouts/{layout_id}/preview.png"
    assert admin_data["hotspotsUrl"] == f"/storage/layouts/{layout_id}/hotspots.json"

    public_response = client.get(f"/api/public/layouts/{slug}")
    assert public_response.status_code == 200
    public_layout = public_response.json()["data"]
    assert len(public_layout["plots"]) == 941


def test_upload_layout_rejects_missing_excel(tmp_path: Path, test_app: None) -> None:
    dxf_path = tmp_path / "layout.dxf"
    _build_sample_dxf(dxf_path, [("28A", 10), ("29B", 30)])

    client = TestClient(app)
    with dxf_path.open("rb") as dxf_file:
        response = client.post(
            "/api/admin/layouts",
            data={"name": "Another Layout"},
            files={"dxf_file": ("layout.dxf", dxf_file, "application/dxf")},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_UPLOAD"


def test_upload_layout_rejects_duplicate_name(tmp_path: Path, test_app: None) -> None:
    dxf_path = tmp_path / "layout.dxf"
    excel_path = tmp_path / "layout.xlsx"
    _build_sample_dxf(dxf_path, [("28A", 10), ("29B", 30)])
    _build_sample_excel(excel_path, [("28A", "Mr. A", "33*50", 1650, 183.33, "East"), ("29B", "Mr. B", "40*50", 2000, 222.22, "West")])

    client = TestClient(app)
    with dxf_path.open("rb") as dxf_file, excel_path.open("rb") as excel_file:
        first = client.post(
            "/api/admin/layouts",
            data={"name": "Duplicate Layout"},
            files={
                "dxf_file": ("layout.dxf", dxf_file, "application/dxf"),
                "excel_file": (
                    "layout.xlsx",
                    excel_file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )
    assert first.status_code == 200

    with dxf_path.open("rb") as dxf_file, excel_path.open("rb") as excel_file:
        second = client.post(
            "/api/admin/layouts",
            data={"name": "Duplicate Layout"},
            files={
                "dxf_file": ("layout.dxf", dxf_file, "application/dxf"),
                "excel_file": (
                    "layout.xlsx",
                    excel_file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_LAYOUT_NAME"
