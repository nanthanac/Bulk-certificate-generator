import os
from app.generator import generate_certificate_pdf


def test_generate_certificate_pdf(tmp_path):
    output_pdf = str(tmp_path / "test_certificate.pdf")
    
    result_path = generate_certificate_pdf(
        recipient_name="Alice Smith",
        course_name="Machine Learning Fundamentals",
        issue_date="2026-10-11",
        output_path=output_pdf,
    )

    assert result_path == output_pdf
    assert os.path.exists(output_pdf)
    assert os.path.getsize(output_pdf) > 0

    with open(output_pdf, "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"
