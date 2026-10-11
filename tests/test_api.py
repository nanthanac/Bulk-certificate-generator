import io
import os
import zipfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database, service
from app.database import Base
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    test_out = str(tmp_path / "test_generated")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{test_db}")
    monkeypatch.setenv("OUTPUT_DIR", test_out)

    test_engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(service, "SessionLocal", TestingSessionLocal)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_ui_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Bulk Certificate Generator" in response.text


def test_create_job_and_complete(client):
    payload = {
        "course_name": "FastAPI Full Course",
        "issue_date": "2026-10-11",
        "recipients": [
            {"name": "Alice Smith", "email": "alice@example.com"},
            {"name": "Bob Jones", "email": "bob@example.com"},
        ],
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    job_id = data["job_id"]

    # Background task finishes before response in TestClient
    status_resp = client.get(f"/jobs/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "completed"
    assert status_data["total"] == 2
    assert status_data["success_count"] == 2
    assert status_data["failed_count"] == 0
    assert len(status_data["recipients"]) == 2
    assert all(r["status"] == "success" for r in status_data["recipients"])
    assert all(r["download_url"] is not None for r in status_data["recipients"])


def test_input_validation_empty_recipients(client):
    payload = {
        "course_name": "Python 101",
        "issue_date": "2026-10-11",
        "recipients": [],
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == 422


def test_input_validation_missing_course_name(client):
    payload = {
        "course_name": "   ",
        "issue_date": "2026-10-11",
        "recipients": [{"name": "Alice", "email": "alice@example.com"}],
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == 422


def test_invalid_recipient_handled_per_recipient(client):
    payload = {
        "course_name": "Cloud Architecture",
        "issue_date": "2026-10-11",
        "recipients": [
            {"name": "Valid User", "email": "valid@example.com"},
            {"name": "Bad Email User", "email": "not-an-email"},
            {"name": "   ", "email": "no-name@example.com"},
        ],
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status_resp = client.get(f"/jobs/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] == "completed_with_errors"
    assert data["total"] == 3
    assert data["success_count"] == 1
    assert data["failed_count"] == 2

    # Verify per-recipient details
    recipients_by_name = {r["name"]: r for r in data["recipients"]}
    assert recipients_by_name["Valid User"]["status"] == "success"
    assert recipients_by_name["Valid User"]["download_url"] is not None

    assert recipients_by_name["Bad Email User"]["status"] == "failed"
    assert "email" in recipients_by_name["Bad Email User"]["error_message"].lower()

    assert recipients_by_name[""]["status"] == "failed"
    assert "name" in recipients_by_name[""]["error_message"].lower()


def test_individual_failure_with_monkeypatch(client, monkeypatch):
    original_generator = service.generate_certificate_pdf

    def faulty_generator(recipient_name, course_name, issue_date, output_path):
        if recipient_name == "Failing Recipient":
            raise RuntimeError("Simulated PDF generator crash")
        return original_generator(recipient_name, course_name, issue_date, output_path)

    monkeypatch.setattr(service, "generate_certificate_pdf", faulty_generator)

    payload = {
        "course_name": "Resilience Engineering",
        "issue_date": "2026-10-11",
        "recipients": [
            {"name": "Success Recipient", "email": "success@example.com"},
            {"name": "Failing Recipient", "email": "fail@example.com"},
        ],
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status_resp = client.get(f"/jobs/{job_id}")
    data = status_resp.json()
    assert data["status"] == "completed_with_errors"
    assert data["total"] == 2
    assert data["success_count"] == 1
    assert data["failed_count"] == 1

    recipients_by_name = {r["name"]: r for r in data["recipients"]}
    assert recipients_by_name["Success Recipient"]["status"] == "success"
    assert recipients_by_name["Failing Recipient"]["status"] == "failed"
    assert "Simulated PDF generator crash" in recipients_by_name["Failing Recipient"]["error_message"]


def test_retrieve_certificate_and_zip_download(client):
    payload = {
        "course_name": "Database Systems",
        "issue_date": "2026-10-11",
        "recipients": [
            {"name": "Alice Green", "email": "alice@example.com"},
            {"name": "Bob Invalid", "email": "invalid-email"},
        ],
    }
    response = client.post("/jobs", json=payload)
    job_id = response.json()["job_id"]

    status_data = client.get(f"/jobs/{job_id}").json()
    successful_cert = next(r for r in status_data["recipients"] if r["status"] == "success")
    failed_cert = next(r for r in status_data["recipients"] if r["status"] == "failed")

    # 1. Download successful certificate
    cert_resp = client.get(f"/jobs/{job_id}/certificates/{successful_cert['id']}")
    assert cert_resp.status_code == 200
    assert cert_resp.headers["content-type"] == "application/pdf"
    assert cert_resp.content.startswith(b"%PDF")

    # 2. 404 for failed certificate
    failed_resp = client.get(f"/jobs/{job_id}/certificates/{failed_cert['id']}")
    assert failed_resp.status_code == 404

    # 3. 404 for nonexistent certificate
    nonexistent_resp = client.get(f"/jobs/{job_id}/certificates/unknown-id")
    assert nonexistent_resp.status_code == 404

    # 4. Download ZIP with all successful certificates
    zip_resp = client.get(f"/jobs/{job_id}/download")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        file_list = zf.namelist()
        assert f"{successful_cert['id']}.pdf" in file_list
        assert len(file_list) == 1
