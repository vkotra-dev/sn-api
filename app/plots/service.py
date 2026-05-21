from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.layout import Layout
from app.models.plot import Plot


ALLOWED_STATUSES = {"available", "reserved", "sold", "blocked"}


def get_plot(db: Session, layout_id: str, plot_no: str) -> Plot | None:
    statement = select(Plot).where(Plot.layout_id == layout_id, Plot.plot_no == plot_no)
    return db.execute(statement).scalar_one_or_none()


def serialize_admin_plot(plot: Plot) -> dict[str, object]:
    return {
        "plotNo": plot.plot_no,
        "status": plot.status,
        "owner": plot.owner,
        "dimFt": plot.dim_ft,
        "dimType": plot.dim_type,
        "areaSqFt": float(plot.area_sq_ft) if plot.area_sq_ft is not None else None,
        "areaSqYd": float(plot.area_sq_yd) if plot.area_sq_yd is not None else None,
        "facing": plot.facing,
        "hotspot": plot.hotspot,
    }


def serialize_plot_status(plot: Plot) -> dict[str, object]:
    return {
        "plotNo": plot.plot_no,
        "status": plot.status,
    }


def validate_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in ALLOWED_STATUSES:
        raise APIError("INVALID_STATUS", "Status value not recognised", status_code=400)
    return normalized


def update_plot_status(db: Session, layout_id: str, plot_no: str, status: str) -> Plot:
    plot = get_plot(db, layout_id, plot_no)
    if plot is None:
        raise APIError("PLOT_NOT_FOUND", "Plot does not exist", status_code=404)

    plot.status = validate_status(status)
    db.commit()
    db.refresh(plot)
    return plot


def get_layout_or_raise(db: Session, layout_id: str) -> Layout:
    layout = db.get(Layout, layout_id)
    if layout is None:
        raise APIError("LAYOUT_NOT_FOUND", "Layout does not exist", status_code=404)
    return layout

