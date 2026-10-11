import os
from app.database import SessionLocal
from app.generator import generate_certificate_pdf
from app.models import Certificate, Job


def process_job(job_id: str) -> None:
    """
    Process certificate generation for a job in the background.
    Uses a fresh database session and updates progress as certificates are generated.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = "processing"
        db.commit()

        out_dir = os.getenv("OUTPUT_DIR", "generated")
        os.makedirs(out_dir, exist_ok=True)

        pending_certs = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id, Certificate.status == "pending")
            .all()
        )

        for cert in pending_certs:
            try:
                file_path = os.path.abspath(os.path.join(out_dir, f"{cert.id}.pdf"))
                generate_certificate_pdf(
                    recipient_name=cert.recipient_name,
                    course_name=cert.course_name,
                    issue_date=cert.issue_date,
                    output_path=file_path,
                )
                cert.status = "success"
                cert.file_path = file_path
                job.success_count += 1
            except Exception as exc:
                cert.status = "failed"
                cert.error_message = str(exc)
                job.failed_count += 1

            # Commit after each certificate to reflect live progress
            db.commit()

        # Update final job status
        job.status = "completed" if job.failed_count == 0 else "completed_with_errors"
        db.commit()
    finally:
        db.close()
