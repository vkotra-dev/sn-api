from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin_user
from app.core.errors import APIError
from app.common.responses import success_response
from app.database.session import get_db
from app.layouts.service import (
    get_layout,
    get_public_layout,
    list_layouts,
    prepare_layout_upload,
    process_layout_upload,
    serialize_admin_layout_detail,
    serialize_layout_upload_response,
    serialize_public_layout,
)

router = APIRouter(prefix="/admin/layouts")
public_router = APIRouter(prefix="/public/layouts")


@router.post("/")
def create_layout(
    background_tasks: BackgroundTasks,
    name: str | None = Form(default=None),
    dxf_file: UploadFile | None = File(default=None),
    excel_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    _current_admin=Depends(get_current_admin_user),
) -> dict[str, object]:
    job = prepare_layout_upload(db, name=name, dxf_file=dxf_file, excel_file=excel_file)
    background_tasks.add_task(process_layout_upload, job.layout.id, job.dxf_path, job.excel_path)
    return success_response(serialize_layout_upload_response(job.layout))


@router.get("/")
def read_layouts(
    db: Session = Depends(get_db),
    _current_admin=Depends(get_current_admin_user),
) -> dict[str, object]:
    return success_response(list_layouts(db))


@router.get("/{layout_id}")
def read_layout(
    layout_id: str,
    db: Session = Depends(get_db),
    _current_admin=Depends(get_current_admin_user),
) -> dict[str, object]:
    layout = get_layout(db, layout_id)
    if layout is None:
        raise APIError("LAYOUT_NOT_FOUND", "Layout does not exist", status_code=404)
    return success_response(serialize_admin_layout_detail(layout))


@public_router.get("/{slug}")
def read_public_layout(slug: str, db: Session = Depends(get_db)) -> dict[str, object]:
    layout = get_public_layout(db, slug)
    if layout is None:
        raise APIError("LAYOUT_NOT_FOUND", "Layout does not exist", status_code=404)
    if layout.status == "processing":
        raise APIError("LAYOUT_PROCESSING", "Layout is still being processed", status_code=409)
    if layout.status == "failed":
        raise APIError("LAYOUT_FAILED", "Layout processing failed", status_code=422)
    return success_response(serialize_public_layout(layout))
