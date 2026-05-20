from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database.session import get_session_local
from app.layouts.service import process_layout_upload
from app.models.layout_upload_job import LayoutUploadJob


RUNNING_JOB_TIMEOUT = timedelta(minutes=30)


def run_once() -> None:
    session_local = get_session_local()
    db = session_local()
    try:
        stale_cutoff = datetime.now(timezone.utc) - RUNNING_JOB_TIMEOUT
        stale_jobs = db.execute(
            select(LayoutUploadJob)
            .where(LayoutUploadJob.status == "running")
            .where(LayoutUploadJob.started_at.is_not(None))
            .where(LayoutUploadJob.started_at < stale_cutoff)
        ).scalars().all()
        for job in stale_jobs:
            job.status = "pending"
        if stale_jobs:
            db.commit()

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
