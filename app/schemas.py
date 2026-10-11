from datetime import date
import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class RecipientInput(BaseModel):
    name: str = Field(..., description="Recipient full name")
    email: str = Field(..., description="Recipient email address")


class JobCreateRequest(BaseModel):
    course_name: str = Field(..., description="Course name")
    issue_date: str = Field(..., description="Issue date in YYYY-MM-DD format")
    recipients: List[RecipientInput] = Field(..., description="List of certificate recipients")

    @field_validator("course_name")
    def validate_course_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("course_name is required and cannot be empty")
        return v.strip()

    @field_validator("issue_date")
    def validate_issue_date(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("issue_date is required")
        try:
            date.fromisoformat(v.strip())
        except ValueError:
            raise ValueError("issue_date must be in YYYY-MM-DD format")
        return v.strip()

    @field_validator("recipients")
    def validate_recipients(cls, v: List[RecipientInput]) -> List[RecipientInput]:
        if not v or len(v) == 0:
            raise ValueError("recipients list cannot be empty")
        if len(v) > 1000:
            raise ValueError("recipients list cannot exceed 1000")
        return v


def validate_recipient_record(name: str, email: str) -> tuple[bool, Optional[str]]:
    """Validate an individual recipient. Returns (is_valid, error_message)."""
    clean_name = name.strip() if name else ""
    clean_email = email.strip() if email else ""

    if not clean_name:
        return False, "Recipient name cannot be empty"
    if not clean_email or not EMAIL_REGEX.match(clean_email):
        return False, "Invalid email format"
    return True, None


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class RecipientStatusResponse(BaseModel):
    id: str
    name: str
    email: str
    status: str
    error_message: Optional[str] = None
    download_url: Optional[str] = None


class JobDetailResponse(BaseModel):
    id: str
    status: str
    total: int
    success_count: int
    failed_count: int
    created_at: str
    recipients: List[RecipientStatusResponse]
