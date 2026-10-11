# Bulk Certificate Generator

A minimal, high-performance backend built with FastAPI, SQLAlchemy, SQLite, and ReportLab for generating customized completion certificates in bulk.

---

## Features
- **Asynchronous Job Submission:** Enqueues generation jobs via FastAPI `BackgroundTasks` and returns `202 Accepted` immediately.
- **Granular Error Isolation:** Each certificate is generated inside its own `try/except` block. A single failure never prevents remaining certificates from being generated.
- **Per-Recipient Validation:** Invalid recipient records (empty name, malformed email) are recorded with error descriptions without rejecting the entire batch.
- **Live Progress Updates:** Real-time job status tracking (`pending`, `processing`, `completed`, `completed_with_errors`) and progress counters (`total`, `success_count`, `failed_count`).
- **Single & Bulk Downloads:** Individual PDF downloads and single-click bulk ZIP download for all successful certificates.
- **Minimal Web UI:** Plain HTML5/CSS and Vanilla JavaScript frontend served at `/`.

---

## Project Structure
```text
bulk-certificate-generator/
│
├── app/
│   ├── __init__.py
│   ├── database.py        # SQLAlchemy engine, session maker, Base, and DB dependency
│   ├── generator.py       # ReportLab PDF certificate template generator
│   ├── main.py            # FastAPI application routes and lifecycle
│   ├── models.py          # Job and Certificate SQLAlchemy models
│   ├── schemas.py         # Pydantic schemas and recipient validation
│   ├── service.py         # Background job processor and progress updates
│   └── static/
│       └── index.html     # Minimal vanilla JS frontend UI
│
├── tests/
│   ├── test_api.py        # Comprehensive API & endpoint integration tests
│   └── test_generator.py  # ReportLab PDF template generation unit tests
│
├── generated/             # Output certificate PDFs (gitignored)
├── requirements.txt       # Project dependencies
├── pytest.ini             # Pytest configuration
└── README.md
```

---

## Setup & Installation

### 1. Create and Activate Virtual Environment
```bash
# Windows
py -3.12 -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Application

Start the development server with Uvicorn:
```bash
uvicorn app.main:app --reload
```

- **Interactive Web UI:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Running Tests

Run the test suite using `pytest`:
```bash
pytest -v
```

---

## Example cURL Commands

### 1. Submit a Certificate Generation Job
```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "course_name": "Modern Web Architecture",
    "issue_date": "2026-10-11",
    "recipients": [
      { "name": "Jane Doe", "email": "jane@example.com" },
      { "name": "John Smith", "email": "john@example.com" },
      { "name": "Invalid Recipient", "email": "invalid-email" }
    ]
  }'
```
**Response (202 Accepted):**
```json
{
  "job_id": "a93e3d92-1c2f-4882-95f7-873b223c7f99",
  "status": "pending"
}
```

### 2. Check Job Status and Progress
```bash
curl http://127.0.0.1:8000/jobs/a93e3d92-1c2f-4882-95f7-873b223c7f99
```
**Response (200 OK):**
```json
{
  "id": "a93e3d92-1c2f-4882-95f7-873b223c7f99",
  "status": "completed_with_errors",
  "total": 3,
  "success_count": 2,
  "failed_count": 1,
  "created_at": "2026-10-11T03:42:10.123456",
  "recipients": [
    {
      "id": "c1f13b63-bb02-4fc8-9f2e-13c5fdfb2812",
      "name": "Jane Doe",
      "email": "jane@example.com",
      "status": "success",
      "error_message": null,
      "download_url": "/jobs/a93e3d92-1c2f-4882-95f7-873b223c7f99/certificates/c1f13b63-bb02-4fc8-9f2e-13c5fdfb2812"
    },
    {
      "id": "84d580cf-f30a-4828-98e1-95c589b21f90",
      "name": "John Smith",
      "email": "john@example.com",
      "status": "success",
      "error_message": null,
      "download_url": "/jobs/a93e3d92-1c2f-4882-95f7-873b223c7f99/certificates/84d580cf-f30a-4828-98e1-95c589b21f90"
    },
    {
      "id": "18fbf41e-399a-411f-827c-619f79883503",
      "name": "Invalid Recipient",
      "email": "invalid-email",
      "status": "failed",
      "error_message": "Invalid email format",
      "download_url": null
    }
  ]
}
```

### 3. Download an Individual Certificate PDF
```bash
curl -O -J http://127.0.0.1:8000/jobs/a93e3d92-1c2f-4882-95f7-873b223c7f99/certificates/c1f13b63-bb02-4fc8-9f2e-13c5fdfb2812
```

### 4. Download All Successful Certificates as a ZIP Archive
```bash
curl -O -J http://127.0.0.1:8000/jobs/a93e3d92-1c2f-4882-95f7-873b223c7f99/download
```

---

## Design Decisions & Architecture

- **Background Processing:** Large batches (up to 1,000 recipients) would cause HTTP client timeouts if processed synchronously. FastAPI `BackgroundTasks` allow immediate `202 Accepted` responses so clients can poll asynchronously for status and live counters.
- **Per-Certificate Error Isolation:** Generating PDFs involves file I/O, canvas rendering, and dynamic text. Wrapping each certificate generation in its own `try/except` block ensures that a single bad font, character, or unexpected I/O glitch never disrupts the rest of the batch.
- **Per-Recipient Validation:** Rather than aborting an entire batch of 500 recipients because one email is typo'd, invalid entries are flagged as `failed` with descriptive error messages, while valid recipients proceed uninterrupted.
- **SQLite Relational Persistence:** SQLite provides an zero-configuration relational database engine for local development and simplicity. Using SQLAlchemy models ensures that switching to PostgreSQL or MySQL in production requires changing only the `DATABASE_URL` connection string.
- **System Limitations & Production Scalability:** In-process FastAPI background tasks are bound to the worker process memory. If the server process restarts or crashes during execution, active tasks would be lost. For production scale, an external distributed task queue (e.g., Celery, RQ, or ARQ backed by Redis or RabbitMQ) would provide durable task persistence, automatic retries, and horizontal worker scaling.
