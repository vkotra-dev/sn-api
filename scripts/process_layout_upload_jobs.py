from sqlalchemy import select

from app.database.session import get_session_local
from app.layouts.service import process_layout_upload
from app.models.layout_upload_job import LayoutUploadJob


def run_once() -> None:
    session_local = get_session_local()
    db = session_local()
    try:
        job_ids = db.execute(
            select(LayoutUploadJob.id)
            .where(LayoutUploadJob.status == "pending")
            .order_by(LayoutUploadJob.created_at.asc())
        ).scalars().all()
    finally:
        db.close()

    for job_id in job_ids:
        process_layout_upload(job_id)


if __name__ == "__main__":
    run_once()
