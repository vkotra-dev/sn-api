from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin_user
from app.common.responses import success_response
from app.core.errors import APIError
from app.database.session import get_db
from app.plots.service import (
    get_layout_or_raise,
    get_plot,
    serialize_admin_plot,
    serialize_plot_status,
    update_plot_status,
)

router = APIRouter(prefix="/admin/layouts/{layout_id}/plots")


class PlotStatusUpdate(BaseModel):
    status: str


@router.get("/{plot_no}")
def read_plot(
    layout_id: str,
    plot_no: str,
    db: Session = Depends(get_db),
    _current_admin=Depends(get_current_admin_user),
) -> dict[str, object]:
    get_layout_or_raise(db, layout_id)
    plot = get_plot(db, layout_id, plot_no)
    if plot is None:
        raise APIError("PLOT_NOT_FOUND", "Plot does not exist", status_code=404)
    return success_response(serialize_admin_plot(plot))


@router.patch("/{plot_no}/status")
def patch_plot_status(
    layout_id: str,
    plot_no: str,
    payload: PlotStatusUpdate = Body(...),
    db: Session = Depends(get_db),
    _current_admin=Depends(get_current_admin_user),
) -> dict[str, object]:
    get_layout_or_raise(db, layout_id)
    plot = update_plot_status(db, layout_id, plot_no, payload.status)
    return success_response(serialize_plot_status(plot))
