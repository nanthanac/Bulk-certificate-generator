import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    recipient_name: str,
    course_name: str,
    issue_date: str,
    output_path: str,
) -> str:
    """Generate an A4 landscape certificate PDF with borders and recipient details."""
    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    page_width, page_height = landscape(A4)
    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    c.setTitle(f"Certificate - {recipient_name}")

    # Outer decorative border
    c.setStrokeColor(colors.HexColor("#1A365D"))
    c.setLineWidth(3)
    c.rect(25, 25, page_width - 50, page_height - 50)

    # Inner decorative border
    c.setStrokeColor(colors.HexColor("#C59B27"))
    c.setLineWidth(1)
    c.rect(32, 32, page_width - 64, page_height - 64)

    center_x = page_width / 2

    # Title: Certificate of Completion
    c.setFillColor(colors.HexColor("#1A365D"))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(center_x, 435, "Certificate of Completion")

    # Subtitle: This is to certify that
    c.setFillColor(colors.HexColor("#4A5568"))
    c.setFont("Helvetica-Oblique", 15)
    c.drawCentredString(center_x, 375, "This is to certify that")

    # Recipient name (large)
    c.setFillColor(colors.HexColor("#1A202C"))
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(center_x, 315, recipient_name)

    # Decorative separator line under recipient name
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(1)
    c.line(center_x - 160, 300, center_x + 160, 300)

    # has successfully completed
    c.setFillColor(colors.HexColor("#4A5568"))
    c.setFont("Helvetica", 15)
    c.drawCentredString(center_x, 255, "has successfully completed")

    # Course name
    c.setFillColor(colors.HexColor("#2B6CB0"))
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(center_x, 205, course_name)

    # Issue date
    c.setFillColor(colors.HexColor("#718096"))
    c.setFont("Helvetica", 13)
    c.drawCentredString(center_x, 140, f"Issued on: {issue_date}")

    c.showPage()
    c.save()

    return output_path
