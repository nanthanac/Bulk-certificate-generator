import io
import os
import uuid
import zipfile
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Certificate, Job
from app.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobDetailResponse,
    RecipientStatusResponse,
    validate_recipient_record,
)
from app.service import process_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Bulk Certificate Generator", lifespan=lifespan)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/", include_in_schema=False)
def get_ui():
    """Serve the basic frontend UI."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_file):
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index_file, media_type="text/html")


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=JobCreateResponse)
def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a bulk certificate generation job and start processing in the background.
    Validates recipients individually; invalid recipients are marked as failed immediately.
    """
    job_id = str(uuid.uuid4())
    total = len(request.recipients)
    failed_initial = 0

    job = Job(
        id=job_id,
        status="pending",
        total=total,
        success_count=0,
        failed_count=0,
    )
    db.add(job)

    # Process and add each recipient
    for r in request.recipients:
        cert_id = str(uuid.uuid4())
        is_valid, error_msg = validate_recipient_record(r.name, r.email)

        cert_status = "pending" if is_valid else "failed"
        if not is_valid:
            failed_initial += 1

        certificate = Certificate(
            id=cert_id,
            job_id=job_id,
            recipient_name=r.name.strip() if r.name else "",
            recipient_email=r.email.strip() if r.email else "",
            course_name=request.course_name,
            issue_date=request.issue_date,
            status=cert_status,
            error_message=error_msg,
        )
        db.add(certificate)

    job.failed_count = failed_initial
    db.commit()

    # Enqueue background processing
    background_tasks.add_task(process_job, job_id)

    return JobCreateResponse(job_id=job_id, status=job.status)


@app.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job_status(job_id: str, db: Annotated[Session, Depends(get_db)]):
    """Retrieve job details, live progress counters, and per-recipient status."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    recipients_data = []
    for cert in job.certificates:
        download_url = (
            f"/jobs/{job.id}/certificates/{cert.id}"
            if cert.status == "success"
            else None
        )
        recipients_data.append(
            RecipientStatusResponse(
                id=cert.id,
                name=cert.recipient_name,
                email=cert.recipient_email,
                status=cert.status,
                error_message=cert.error_message,
                download_url=download_url,
            )
        )

    return JobDetailResponse(
        id=job.id,
        status=job.status,
        total=job.total,
        success_count=job.success_count,
        failed_count=job.failed_count,
        created_at=job.created_at.isoformat(),
        recipients=recipients_data,
    )


@app.get("/jobs/{job_id}/certificates/{certificate_id}")
def download_certificate(
    job_id: str,
    certificate_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Download a single generated certificate PDF."""
    cert = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id, Certificate.id == certificate_id)
        .first()
    )
    if not cert or cert.status != "success" or not cert.file_path:
        raise HTTPException(
            status_code=404,
            detail="Certificate not found or generation failed",
        )

    if not os.path.exists(cert.file_path):
        raise HTTPException(status_code=404, detail="Certificate file missing")

    filename = f"{cert.id}.pdf"
    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=filename,
    )


@app.get("/jobs/{job_id}/download")
def download_all_certificates(
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Download all successful certificates for a job as a single ZIP archive."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    successful_certs = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id, Certificate.status == "success")
        .all()
    )

    valid_files = [
        cert for cert in successful_certs if cert.file_path and os.path.exists(cert.file_path)
    ]
    if not valid_files:
        raise HTTPException(
            status_code=404,
            detail="No successful certificates available for download",
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for cert in valid_files:
            zf.write(cert.file_path, arcname=f"{cert.id}.pdf")

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="certificates_{job_id}.zip"'
        },
    )
