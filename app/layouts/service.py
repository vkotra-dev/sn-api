from __future__ import annotations

import contextlib
import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.database.session import get_session_local
from app.layouts.parser.dxf import extract_plot_positions, load_layout_block, render_preview_and_hotspots
from app.layouts.parser.excel import parse_excel_metadata
from app.layouts.storage import get_storage_backend
from app.models.layout import Layout
from app.models.layout_upload_job import LayoutUploadJob
from app.models.plot import Plot


logger = logging.getLogger(__name__)

MAX_DXF_BYTES = 50 * 1024 * 1024
MAX_EXCEL_BYTES = 10 * 1024 * 1024
DXF_EXTENSIONS = {".dxf"}
EXCEL_EXTENSIONS = {".xlsx"}
DXF_CONTENT_TYPES = {"application/dxf", "application/x-dxf", "application/octet-stream"}
EXCEL_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}


@dataclass(slots=True)
class PreparedLayoutUpload:
    layout: Layout
    job_record: LayoutUploadJob


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "layout"


def _build_share_url(slug: str) -> str:
    return f"/layouts/{slug}"


def _plot_sort_key(value: str) -> tuple[int, str]:
    match = re.match(r"^(\d+)(.*)$", value)
    if match:
        return int(match.group(1)), match.group(2).lower()
    return (10**12, value.lower())


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
) -> PreparedLayoutUpload:
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
    db.flush()
    job: LayoutUploadJob | None = None

    try:
        storage = get_storage_backend()
        source_dxf_key = f"layouts/{layout.id}/source/layout.dxf"
        source_excel_key = f"layouts/{layout.id}/source/layout.xlsx"
        source_dxf_url = storage.upload_bytes(source_dxf_key, dxf_bytes, "application/dxf")
        source_excel_url = storage.upload_bytes(
            source_excel_key,
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        job = LayoutUploadJob(
            layout_id=layout.id,
            status="pending",
            source_dxf_key=source_dxf_key,
            source_excel_key=source_excel_key,
        )
        db.add(job)
        layout.dxf_file_url = source_dxf_url
        layout.excel_file_url = source_excel_url
        db.commit()
        db.refresh(layout)
        db.refresh(job)
    except Exception:
        db.rollback()
        raise

    assert job is not None
    return PreparedLayoutUpload(layout=layout, job_record=job)


def _set_layout_job_failed(db: Session, job: LayoutUploadJob, layout: Layout | None, message: str) -> None:
    job.status = "failed"
    job.error_message = message
    job.finished_at = datetime.now(timezone.utc)
    if layout is not None:
        layout.status = "failed"
    db.commit()


def process_layout_upload(job_id: str) -> None:
    session_local = get_session_local()
    db = session_local()
    storage = get_storage_backend()
    preview_path: Path | None = None
    temp_dir: Path | None = None

    try:
        job = db.get(LayoutUploadJob, job_id)
        if job is None or job.status != "pending":
            return

        layout = db.get(Layout, job.layout_id)
        if layout is None:
            job.status = "failed"
            job.error_message = "Layout does not exist"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        temp_dir = Path(tempfile.mkdtemp(prefix="layout-upload-"))
        dxf_path = temp_dir / "layout.dxf"
        excel_path = temp_dir / "layout.xlsx"
        storage.download_file(job.source_dxf_key, dxf_path)
        storage.download_file(job.source_excel_key, excel_path)

        block = load_layout_block(dxf_path)
        plot_positions = extract_plot_positions(block)
        plot_metadata = parse_excel_metadata(excel_path)

        dxf_plot_nos = set(plot_positions)
        excel_plot_nos = set(plot_metadata)
        missing = sorted(dxf_plot_nos - excel_plot_nos)
        if missing:
            raise ValueError(f"DXF and Excel plot numbers do not match: {', '.join(missing)}")

        preview_path = dxf_path.parent / "preview.png"
        hotspots = render_preview_and_hotspots(block, plot_positions, preview_path)

        preview_key = f"layouts/{layout.id}/preview.png"
        hotspots_key = f"layouts/{layout.id}/hotspots.json"
        preview_url = storage.upload_file(preview_path, preview_key, "image/png")
        hotspots_bytes = json.dumps(hotspots, ensure_ascii=False, indent=2).encode("utf-8")
        hotspots_url = storage.upload_bytes(hotspots_key, hotspots_bytes, "application/json")

        for plot_no in sorted(plot_positions, key=_plot_sort_key):
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
        job.status = "succeeded"
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(LayoutUploadJob, job_id)
        layout = db.get(Layout, job.layout_id) if job is not None else None
        if job is not None:
            _set_layout_job_failed(db, job, layout, str(exc))
        logger.exception("layout upload job %s failed", job_id)
        return
    finally:
        db.close()
        if temp_dir is not None:
            with contextlib.suppress(FileNotFoundError):
                shutil.rmtree(temp_dir)


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
        "name": layout.name,
        "slug": layout.slug,
        "previewUrl": layout.preview_url,
        "hotspotsUrl": layout.hotspots_url,
        "plots": [
            serialize_public_plot(plot)
            for plot in sorted(layout.plots, key=lambda plot: _plot_sort_key(plot.plot_no))
        ],
    }


def list_layouts(db: Session) -> list[dict[str, object]]:
    layouts = db.execute(select(Layout).order_by(Layout.created_at.desc())).scalars().all()
    return [serialize_admin_layout_summary(layout) for layout in layouts]


def get_layout(db: Session, layout_id: str) -> Layout | None:
    return db.get(Layout, layout_id)


def get_public_layout(db: Session, slug: str) -> Layout | None:
    statement = select(Layout).options(selectinload(Layout.plots)).where(Layout.slug == slug).limit(1)
    return db.execute(statement).scalar_one_or_none()
