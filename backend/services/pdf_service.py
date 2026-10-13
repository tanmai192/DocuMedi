"""
services/pdf_service.py — Professional Medical Clinical Record PDF Generator for DocuMedi.
Tagline: "Your Health Story, Organized."

Generates an authoritative, beautifully formatted clinical note PDF report
using ReportLab Platypus. Strictly isolated and rendered from saved MySQL records.
"""

import html
import io
from datetime import datetime
from typing import Optional, List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.pdfgen import canvas

from models import Patient, PatientCase, PatientNote


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas that records all page states and renders running headers,
    footers, medical disclaimer, and dynamic 'Page X of Y' numbering.
    """
    patient_name: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()

        # Letter page dimensions: 612 x 792 pt
        page_width, page_height = letter
        margin = 40.0

        # --- Running Header (on pages 2 and later) ---
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(colors.HexColor("#0f766e"))
            self.drawString(margin, page_height - 26, "DocuMedi")

            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(margin + 46, page_height - 26, "|   Patient Clinical Record")

            if self.patient_name:
                self.drawRightString(page_width - margin, page_height - 26, f"Patient: {self.patient_name}")

            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(margin, page_height - 30, page_width - margin, page_height - 30)

        # --- Running Footer (on all pages) ---
        # Top dividing line at y = 54
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(margin, 54, page_width - margin, 54)

        # AI Consultation Documentation Disclaimer
        self.setFont("Helvetica-Oblique", 6.5)
        self.setFillColor(colors.HexColor("#64748b"))
        disclaimer_line1 = (
            "AI-assisted patient record based on information provided during the consultation."
        )
        disclaimer_line2 = (
            "This document is for documentation purposes only and is not a confirmed medical diagnosis or a substitute for professional medical advice."
        )
        self.drawCentredString(page_width / 2.0, 42, disclaimer_line1)
        self.drawCentredString(page_width / 2.0, 33, disclaimer_line2)

        # Bottom row: Brand & Tagline on left, Page numbers on right
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#0f766e"))
        self.drawString(margin, 20, "DocuMedi")

        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(margin + 42, 20, "— Your Health Story, Organized.")

        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(page_width - margin, 20, page_str)

        self.restoreState()


def clean_text_for_pdf(text: Optional[str]) -> str:
    """
    Safely escapes user or model text for ReportLab Paragraph rendering.
    Maps newlines to <br/> and ensures markup tags are harmlessly escaped.
    Returns 'Not provided.' if empty or whitespace-only.
    """
    if not text or not text.strip():
        return "Not provided."

    cleaned = text.strip()
    if cleaned in ("Not provided", "Not provided.", "Not Provided", "none", "None"):
        return "Not provided."

    escaped = html.escape(cleaned)
    # Convert line endings
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
    return escaped



def build_pdf_styles():
    """
    Constructs custom ReportLab ParagraphStyles adhering to DocuMedi's
    teal, deep-blue, and slate design palette.
    """
    styles = getSampleStyleSheet()

    # Brand Title
    styles.add(ParagraphStyle(
        name="DocuMediBrand",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0d9488"),  # Primary Teal
        spaceAfter=2,
    ))

    # Brand Tagline
    styles.add(ParagraphStyle(
        name="DocuMediTagline",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f766e"),  # Dark Teal
        spaceAfter=6,
    ))

    # Document Header Title
    styles.add(ParagraphStyle(
        name="DocuMediDocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0f172a"),  # Deep Slate/Blue
        alignment=2,  # Right-aligned
    ))

    # Document Subtitle / Badge
    styles.add(ParagraphStyle(
        name="DocuMediDocBadge",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748b"),
        alignment=2,  # Right-aligned
    ))

    # Metadata Label & Value styles for the info table
    styles.add(ParagraphStyle(
        name="MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    ))

    styles.add(ParagraphStyle(
        name="MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155"),
    ))

    # Clinical Section Heading
    styles.add(ParagraphStyle(
        name="ClinicalHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0f766e"),  # Dark Teal
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,  # Prevent orphaned headers at page bottoms
    ))

    # Clinical Section Body Text
    styles.add(ParagraphStyle(
        name="ClinicalBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#334155"),  # Slate-700
        spaceBefore=0,
        spaceAfter=6,
    ))

    # Clinical Section Body for Empty / "Not provided."
    styles.add(ParagraphStyle(
        name="ClinicalBodyMuted",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#64748b"),  # Slate-500
        spaceBefore=0,
        spaceAfter=6,
    ))

    return styles


def generate_patient_note_pdf(
    note: PatientNote,
    patient: Patient,
    case: Optional[PatientCase] = None
) -> bytes:
    """
    Generates an authoritative, professionally formatted PDF report for a saved
    patient note.
    
    Includes:
    - DocuMedi brand header & tagline
    - Document title: 'Patient Clinical Record'
    - Secure patient & case metadata box
    - All 11 clinical sections in strict order:
      1. Chief Complaint
      2. HPI
      3. Past Medical History
      4. Medications
      5. Allergies
      6. Family History
      7. Social History
      8. Review of Systems
      9. Physical Examination
      10. Assessment and Plan
      11. Follow-up
    - Running footer with page count and healthcare documentation disclaimer
    
    Returns raw PDF bytes in an in-memory buffer.
    """
    buffer = io.BytesIO()

    # Document Geometry
    # Margins: Left=40pt, Right=40pt, Top=45pt, Bottom=68pt (clearance for footer)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=45,
        bottomMargin=68,
        title="DocuMedi Patient Clinical Record",
        author="DocuMedi Health System",
        subject=f"Clinical Consultation Record for {patient.full_name}",
        keywords="DocuMedi, Patient Record, Clinical Note, Healthcare",
    )

    styles = build_pdf_styles()
    story = []

    # 1. Top Decorative Brand Banner Table (Logo + Title)
    # Printable width: 612 - 80 = 532 pt
    header_data = [
        [
            Paragraph("DocuMedi", styles["DocuMediBrand"]),
            Paragraph("<b>PATIENT CLINICAL RECORD</b>", styles["DocuMediDocTitle"]),
        ],
        [
            Paragraph("Your Health Story, Organized.", styles["DocuMediTagline"]),
            Paragraph("CONFIDENTIAL HEALTHCARE DOCUMENT", styles["DocuMediDocBadge"]),
        ],
    ]

    header_table = Table(header_data, colWidths=[266, 266])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)

    # Teal/Emerald accent bar below top banner
    story.append(HRFlowable(
        width="100%",
        thickness=2.5,
        color=colors.HexColor("#0d9488"),
        spaceBefore=6,
        spaceAfter=10,
        hAlign="CENTER",
    ))

    # 2. Patient & Record Information Metadata Card
    created_str = (
        note.created_at.strftime("%B %d, %Y, %I:%M %p")
        if note.created_at
        else datetime.now().strftime("%B %d, %Y, %I:%M %p")
    )
    updated_str = (
        note.updated_at.strftime("%B %d, %Y, %I:%M %p")
        if note.updated_at
        else created_str
    )
    case_title = case.case_title if case and case.case_title else "Health Concern Consultation"
    record_id = f"DOCU-REC-{note.id:05d}"

    meta_data = [
        [
            Paragraph("<b>Patient Name:</b>", styles["MetaLabel"]),
            Paragraph(clean_text_for_pdf(patient.full_name), styles["MetaValue"]),
            Paragraph("<b>Record ID:</b>", styles["MetaLabel"]),
            Paragraph(record_id, styles["MetaValue"]),
        ],
        [
            Paragraph("<b>Case Title:</b>", styles["MetaLabel"]),
            Paragraph(clean_text_for_pdf(case_title), styles["MetaValue"]),
            Paragraph("<b>Date Recorded:</b>", styles["MetaLabel"]),
            Paragraph(created_str, styles["MetaValue"]),
        ],
        [
            Paragraph("<b>Patient Email:</b>", styles["MetaLabel"]),
            Paragraph(clean_text_for_pdf(patient.email), styles["MetaValue"]),
            Paragraph("<b>Last Updated:</b>", styles["MetaLabel"]),
            Paragraph(updated_str, styles["MetaValue"]),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[85, 181, 85, 181])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),  # Slate-50 tint
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),      # Slate-300 border
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Section Banner
    section_banner = Table(
        [[Paragraph("<b>STRUCTURED CLINICAL ASSESSMENT (11 STANDARD SECTIONS)</b>", ParagraphStyle(
            name="SectionBannerText",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            textColor=colors.HexColor("#0f766e"),
        ))]],
        colWidths=[532]
    )
    section_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),  # Light teal-50
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#ccfbf1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(section_banner)
    story.append(Spacer(1, 8))

    # 3. All 11 Clinical Sections in Strict Order
    sections: List[Tuple[str, Optional[str]]] = [
        ("1. Chief Complaint", note.chief_complaint),
        ("2. HPI", note.hpi),
        ("3. Past Medical History", note.past_medical_history),
        ("4. Medications", note.medications),
        ("5. Allergies", note.allergies),
        ("6. Family History", note.family_history),
        ("7. Social History", note.social_history),
        ("8. Review of Systems", note.review_of_systems),
        ("9. Physical Examination", note.physical_examination),
        ("10. Assessment and Plan", note.assessment_and_plan),
        ("11. Follow-up", note.follow_up),
    ]

    for title, content in sections:
        # Heading with keepWithNext=True
        story.append(Paragraph(title, styles["ClinicalHeading"]))
        
        # Section Content
        is_empty = not content or not content.strip()
        body_style = styles["ClinicalBodyMuted"] if is_empty else styles["ClinicalBody"]
        body_text = clean_text_for_pdf(content)
        story.append(Paragraph(body_text, body_style))

        # Thin divider between sections (except last)
        if title != "11. Follow-up":
            story.append(HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#f1f5f9"),
                spaceBefore=1,
                spaceAfter=5,
                hAlign="CENTER",
            ))

    # Configure custom canvasmaker with patient name for running header
    class ConfiguredNumberedCanvas(NumberedCanvas):
        patient_name = patient.full_name or ""

    # Build the document
    doc.build(story, canvasmaker=ConfiguredNumberedCanvas)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
