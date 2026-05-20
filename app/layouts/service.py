from __future__ import annotations

import contextlib
from dataclasses import dataclass
import json
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.database.session import get_session_local
from app.layouts.parser.dxf import extract_plot_positions, load_layout_block, render_preview_and_hotspots
from app.layouts.parser.excel import parse_excel_metadata
from app.layouts.storage import get_storage_backend
from app.models.layout import Layout
from app.models.plot import Plot


MAX_DXF_BYTES = 50 * 1024 * 1024
MAX_EXCEL_BYTES = 10 * 1024 * 1024
DXF_EXTENSIONS = {".dxf"}
EXCEL_EXTENSIONS = {".xlsx"}
DXF_CONTENT_TYPES = {"application/dxf", "application/x-dxf", "text/plain", "application/octet-stream"}
EXCEL_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


@dataclass(slots=True)
class LayoutUploadJob:
    layout: Layout
    dxf_path: Path
    excel_path: Path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "layout"


def _build_share_url(slug: str) -> str:
    return f"/layouts/{slug}"


def _normalize_filename(filename: str | None, expected_exts: set[str]) -> str:
    if not filename:
        raise APIError("INVALID_UPLOAD", "Uploaded file is missing a filename", status_code=400)
    suffix = Path(filename).suffix.lower()
    if suffix not in expected_exts:
        raise APIError("INVALID_UPLOAD", "Uploaded file has an invalid extension", status_code=400)
    return filename


def _validate_upload_file(upload: UploadFile | None, expected_exts: set[str], content_types: set[str]) -> None:
    if upload is None:
        raise APIError("INVALID_UPLOAD", "Required file is missing", status_code=400)
    _normalize_filename(upload.filename, expected_exts)
    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in content_types:
        raise APIError("INVALID_UPLOAD", "Uploaded file has an invalid MIME type", status_code=400)


def _generate_unique_slug(db: Session, name: str) -> str:
    base_slug = _slugify(name)
    existing = set(
        db.execute(
            select(Layout.slug).where(or_(Layout.slug == base_slug, Layout.slug.like(f"{base_slug}-%")))
        )
        .scalars()
        .all()
    )
    if base_slug not in existing:
        return base_slug
    suffix = 2
    while True:
        candidate = f"{base_slug}-{suffix}"
        if candidate not in existing:
            return candidate
        suffix += 1


def _ensure_name_available(db: Session, name: str) -> None:
    existing = db.execute(
        select(Layout.id).where(func.lower(Layout.name) == name.lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise APIError("DUPLICATE_LAYOUT_NAME", "A layout with this name already exists", status_code=409)


def prepare_layout_upload(
    db: Session,
    *,
    name: str | None,
    dxf_file: UploadFile | None,
    excel_file: UploadFile | None,
) -> LayoutUploadJob:
    if name is None or not name.strip():
        raise APIError("INVALID_UPLOAD", "Layout name is required", status_code=400)
    _validate_upload_file(dxf_file, DXF_EXTENSIONS, DXF_CONTENT_TYPES)
    _validate_upload_file(excel_file, EXCEL_EXTENSIONS, EXCEL_CONTENT_TYPES)

    assert dxf_file is not None
    assert excel_file is not None
    dxf_bytes = dxf_file.file.read()
    excel_bytes = excel_file.file.read()

    if not dxf_bytes or len(dxf_bytes) > MAX_DXF_BYTES:
        raise APIError("INVALID_UPLOAD", "DXF file is empty or too large", status_code=400)
    if not excel_bytes or len(excel_bytes) > MAX_EXCEL_BYTES:
        raise APIError("INVALID_UPLOAD", "Excel file is empty or too large", status_code=400)

    _ensure_name_available(db, name.strip())
    slug = _generate_unique_slug(db, name.strip())

    layout = Layout(name=name.strip(), slug=slug, status="processing", plot_count=0)
    db.add(layout)
    db.commit()
    db.refresh(layout)

    temp_dir = Path(tempfile.mkdtemp(prefix="layout-upload-"))
    dxf_path = temp_dir / f"{uuid4()}.dxf"
    excel_path = temp_dir / f"{uuid4()}.xlsx"
    dxf_path.write_bytes(dxf_bytes)
    excel_path.write_bytes(excel_bytes)

    return LayoutUploadJob(layout=layout, dxf_path=dxf_path, excel_path=excel_path)


def process_layout_upload(layout_id: str, dxf_path: Path, excel_path: Path) -> None:
    session_local = get_session_local()
    db = session_local()
    storage = get_storage_backend()
    preview_path: Path | None = None

    try:
        layout = db.get(Layout, layout_id)
        if layout is None:
            return

        source_dxf_url = storage.upload_file(dxf_path, f"layouts/{layout_id}/source/layout.dxf", "application/dxf")
        source_excel_url = storage.upload_file(
            excel_path,
            f"layouts/{layout_id}/source/layout.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        layout.dxf_file_url = source_dxf_url
        layout.excel_file_url = source_excel_url
        db.commit()

        block = load_layout_block(dxf_path)
        plot_positions = extract_plot_positions(block)
        plot_metadata = parse_excel_metadata(excel_path)

        dxf_plot_nos = set(plot_positions)
        excel_plot_nos = set(plot_metadata)
        if dxf_plot_nos != excel_plot_nos:
            missing = sorted(dxf_plot_nos ^ excel_plot_nos)
            raise ValueError(f"DXF and Excel plot numbers do not match: {', '.join(missing)}")

        preview_path = dxf_path.parent / "preview.png"
        hotspots = render_preview_and_hotspots(block, plot_positions, preview_path)

        preview_url = storage.upload_file(preview_path, f"layouts/{layout_id}/preview.png", "image/png")
        hotspots_bytes = json.dumps(hotspots, ensure_ascii=False, indent=2).encode("utf-8")
        hotspots_url = storage.upload_bytes(
            f"layouts/{layout_id}/hotspots.json",
            hotspots_bytes,
            "application/json",
        )

        for plot_no in sorted(plot_positions, key=lambda value: (len(value), value)):
            metadata = plot_metadata[plot_no]
            db.add(
                Plot(
                    layout_id=layout.id,
                    plot_no=plot_no,
                    status="available",
                    hotspot={"x": hotspots[plot_no]["x"], "y": hotspots[plot_no]["y"], "r": hotspots[plot_no]["r"]},
                    dim_ft=metadata.dim_ft,
                    dim_type=metadata.dim_type,
                    area_sq_ft=metadata.area_sq_ft,
                    area_sq_yd=metadata.area_sq_yd,
                    owner=metadata.owner,
                    facing=metadata.facing,
                    extra={},
                )
            )

        layout.preview_url = preview_url
        layout.hotspots_url = hotspots_url
        layout.plot_count = len(plot_positions)
        layout.status = "published"
        db.commit()
    except Exception:
        db.rollback()
        layout = db.get(Layout, layout_id)
        if layout is not None:
            layout.status = "failed"
            db.commit()
        raise
    finally:
        db.close()
        for path in (dxf_path, excel_path, preview_path):
            with contextlib.suppress(FileNotFoundError):
                if path is not None:
                    path.unlink()
        with contextlib.suppress(OSError):
            dxf_path.parent.rmdir()
        with contextlib.suppress(OSError):
            dxf_path.parent.parent.rmdir()


def _layout_share_url(layout: Layout) -> str:
    return _build_share_url(layout.slug)


def serialize_layout_upload_response(layout: Layout) -> dict[str, object]:
    return {
        "layoutId": layout.id,
        "name": layout.name,
        "slug": layout.slug,
        "status": layout.status,
    }


def serialize_admin_layout_summary(layout: Layout) -> dict[str, object]:
    return {
        "id": layout.id,
        "name": layout.name,
        "slug": layout.slug,
        "status": layout.status,
        "plotCount": layout.plot_count,
        "shareUrl": _layout_share_url(layout),
        "createdAt": layout.created_at.isoformat() if layout.created_at else None,
    }


def serialize_admin_layout_detail(layout: Layout) -> dict[str, object]:
    return {
        "id": layout.id,
        "name": layout.name,
        "slug": layout.slug,
        "status": layout.status,
        "plotCount": layout.plot_count,
        "previewUrl": layout.preview_url,
        "hotspotsUrl": layout.hotspots_url,
        "shareUrl": _layout_share_url(layout),
        "createdAt": layout.created_at.isoformat() if layout.created_at else None,
    }


def serialize_public_plot(plot: Plot) -> dict[str, object]:
    return {
        "plotNo": plot.plot_no,
        "status": plot.status,
        "hotspot": plot.hotspot,
        "areaSqFt": float(plot.area_sq_ft) if plot.area_sq_ft is not None else None,
        "areaSqYd": float(plot.area_sq_yd) if plot.area_sq_yd is not None else None,
        "dimFt": plot.dim_ft,
        "facing": plot.facing,
    }


def serialize_public_layout(layout: Layout) -> dict[str, object]:
    return {
        "id": layout.id,
        "name": layout.name,
        "slug": layout.slug,
        "previewUrl": layout.preview_url,
        "hotspotsUrl": layout.hotspots_url,
        "plots": [serialize_public_plot(plot) for plot in sorted(layout.plots, key=lambda plot: plot.plot_no)],
    }


def list_layouts(db: Session) -> list[dict[str, object]]:
    layouts = db.execute(select(Layout).order_by(Layout.created_at.desc())).scalars().all()
    return [serialize_admin_layout_summary(layout) for layout in layouts]


def get_layout(db: Session, layout_id: str) -> Layout | None:
    return db.get(Layout, layout_id)


def get_public_layout(db: Session, slug: str) -> Layout | None:
    statement = select(Layout).where(Layout.slug == slug).limit(1)
    return db.execute(statement).scalar_one_or_none()
