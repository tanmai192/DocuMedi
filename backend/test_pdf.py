"""
test_pdf.py — Automated Test Suite for DocuMedi Stage 8: PDF Report Generation and Download.

Validates:
1. Authenticated patient can download their own saved note.
2. Response has correct application/pdf content type and safe attachment filename header.
3. Response body is a valid, parseable PDF starting with %PDF- header.
4. Generated PDF contains all 11 section headings in strict order.
5. Saved section contents appear faithfully in the PDF document.
6. Empty or blank sections properly render "Not provided."
7. Long notes generate a multi-page PDF with accurate "Page X of Y" pagination without truncation.
8. Unauthenticated requests are rejected with HTTP 401.
9. Cross-patient isolation: Patient B cannot download Patient A's note (HTTP 403 Forbidden).
10. Nonexistent note ID returns HTTP 404 Not Found.
11. PDF generation exceptions are handled gracefully with HTTP 500.
12. Database cleanup leaves MySQL in a pristine state.
"""

import io
from unittest.mock import patch
import pypdf
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Patient, PatientCase, PatientNote

client = TestClient(app)

EMAIL_PDF_PATIENT_A = "patient.pdf.alpha@example.com"
EMAIL_PDF_PATIENT_B = "patient.pdf.beta@example.com"


def cleanup_test_data():
    """Removes test patients and cascades associated cases and notes."""
    db = SessionLocal()
    try:
        patients = (
            db.query(Patient)
            .filter(Patient.email.in_([EMAIL_PDF_PATIENT_A, EMAIL_PDF_PATIENT_B]))
            .all()
        )
        for p in patients:
            db.delete(p)
        db.commit()
    finally:
        db.close()


def run_pdf_tests():
    print("=" * 70)
    print("DocuMedi Stage 8: Automated PDF Generation & Download Test Suite")
    print("=" * 70)

    cleanup_test_data()

    try:
        # Step 1: Register Patient A and Patient B
        print("\n[1/11] Registering Patient A and Patient B...")
        res_a = client.post("/auth/register", json={
            "full_name": "Eleanor Vance",
            "email": EMAIL_PDF_PATIENT_A,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_a.status_code == 201, f"Register A failed: {res_a.text}"
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        res_b = client.post("/auth/register", json={
            "full_name": "Theodora Crain",
            "email": EMAIL_PDF_PATIENT_B,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_b.status_code == 201, f"Register B failed: {res_b.text}"
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        print("  [OK] Registered Patient A (Eleanor) and Patient B (Theodora)")

        # Step 2: Create Case and Save Note for Patient A with all 11 sections
        print("\n[2/11] Creating consultation case and saving clinical note for Patient A...")
        case_res = client.post("/cases", json={"case_title": "Acute Bronchitis Evaluation"}, headers=headers_a)
        assert case_res.status_code == 201
        case_a_id = case_res.json()["id"]

        note_payload_a = {
            "chief_complaint": "Persistent chesty cough with yellowish phlegm for 5 days.",
            "hpi": "32-year-old female presents with productive cough, low-grade fever, and retrosternal chest soreness when coughing.",
            "past_medical_history": "Mild childhood asthma, resolved without medication.",
            "medications": "Ibuprofen 400mg as needed for fever.",
            "allergies": "No known drug allergies (NKDA).",
            "family_history": "No significant cardiopulmonary illness in immediate family.",
            "social_history": "Non-smoker, works as university librarian, denies alcohol misuse.",
            "review_of_systems": "Constitutional: mild malaise. Respiratory: productive cough, retrosternal soreness. Denies hemoptysis or shortness of breath.",
            "physical_examination": "Not performed — information not collected during the patient consultation",
            "assessment_and_plan": "Suspected acute viral bronchitis. Plan: supportive care, warm hydration, honey-lemon tea, OTC expectorant, rest.",
            "follow_up": "Return if high fever > 38.5C develops, breathing becomes labored, or cough persists > 3 weeks."
        }
        note_res = client.post(f"/cases/{case_a_id}/notes", json=note_payload_a, headers=headers_a)
        assert note_res.status_code == 201
        note_a_id = note_res.json()["id"]
        print(f"  [OK] Saved Note #{note_a_id} linked to Case #{case_a_id}")

        # Step 3: Test Download Note PDF (HTTP 200, Content-Type, Content-Disposition)
        print("\n[3/11] Testing GET /notes/{note_id}/pdf response headers and attachment filename...")
        pdf_res = client.get(f"/notes/{note_a_id}/pdf", headers=headers_a)
        assert pdf_res.status_code == 200, f"Expected 200, got {pdf_res.status_code}: {pdf_res.text}"
        assert pdf_res.headers["content-type"] == "application/pdf", f"Unexpected content-type: {pdf_res.headers.get('content-type')}"
        
        disposition = pdf_res.headers.get("content-disposition", "")
        assert "attachment" in disposition, f"Expected attachment disposition, got: {disposition}"
        assert "DocuMedi_Report_" in disposition, f"Expected DocuMedi filename, got: {disposition}"
        assert disposition.endswith('.pdf"') or disposition.endswith('.pdf'), f"Filename should end with .pdf: {disposition}"
        print(f"  [OK] Content-Type: application/pdf")
        print(f"  [OK] Content-Disposition: {disposition}")

        # Step 4: Verify Valid PDF Structure (%PDF- header and pypdf parsing)
        print("\n[4/11] Verifying PDF binary format and parsing with pypdf...")
        pdf_bytes = pdf_res.content
        assert pdf_bytes.startswith(b"%PDF-"), "Response does not start with standard %PDF- magic bytes!"
        
        pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(pdf_reader.pages)
        assert num_pages >= 1, "PDF should have at least 1 page"
        print(f"  [OK] Valid %PDF header, total bytes: {len(pdf_bytes)}, pages: {num_pages}")

        # Step 5: Verify Header Information & Metadata in Extracted Text
        print("\n[5/11] Verifying DocuMedi branding, patient info, and disclaimer...")
        extracted_text = "\n".join(page.extract_text() for page in pdf_reader.pages)
        
        assert "DocuMedi" in extracted_text, "Missing DocuMedi brand title in PDF"
        assert "Your Health Story, Organized." in extracted_text, "Missing tagline in PDF"
        assert "PATIENT CLINICAL RECORD" in extracted_text, "Missing document title in PDF"
        assert "Eleanor Vance" in extracted_text, "Missing patient full name in PDF"
        assert "Acute Bronchitis Evaluation" in extracted_text, "Missing case title in PDF"
        assert f"DOCU-REC-{note_a_id:05d}" in extracted_text, "Missing record ID in PDF"
        assert "AI-assisted patient record" in extracted_text, "Missing AI documentation disclaimer"
        assert "Page 1 of 1" in extracted_text or "Page 1 of" in extracted_text, "Missing page number string"
        print("  [OK] DocuMedi branding, tagline, patient name, and legal disclaimer verified")

        # Step 6: Verify all 11 Clinical Sections in Strict Order
        print("\n[6/11] Verifying all 11 clinical sections in strict sequential order...")
        expected_headings = [
            "Chief Complaint",
            "HPI",
            "Past Medical History",
            "Medications",
            "Allergies",
            "Family History",
            "Social History",
            "Review of Systems",
            "Physical Examination",
            "Assessment and Plan",
            "Follow-up"
        ]

        last_pos = -1
        for heading in expected_headings:
            pos = extracted_text.find(heading)
            assert pos != -1, f"Heading '{heading}' not found in extracted PDF text!"
            assert pos > last_pos, f"Heading '{heading}' at index {pos} appeared out of order (previous was {last_pos})!"
            last_pos = pos

        # Verify saved contents appear in text
        assert "chesty cough with yellowish phlegm" in extracted_text, "Chief complaint text missing"
        assert "32-year-old female presents" in extracted_text, "HPI text missing"
        assert "Not performed — information not collected" in extracted_text, "Physical exam text missing"
        assert "honey-lemon tea" in extracted_text, "Assessment and plan text missing"
        print("  [OK] All 11 headings confirmed in strict clinical sequence (1 to 11)")
        print("  [OK] Saved clinical content verified in generated document")

        # Step 7: Test Empty Sections Display "Not provided."
        print("\n[7/11] Verifying empty sections display 'Not provided.'...")
        case_sparse = client.post("/cases", json={"case_title": "Brief Symptom Check"}, headers=headers_a)
        assert case_sparse.status_code == 201
        case_sparse_id = case_sparse.json()["id"]

        note_payload_sparse = {
            "chief_complaint": "Mild headache",
            "hpi": "Started 2 hours ago",
            "past_medical_history": "",
            "medications": "   ",
            "allergies": "",
            "family_history": "Not provided",
            "social_history": "",
            "review_of_systems": "",
            "physical_examination": "Not performed — information not collected during the patient consultation",
            "assessment_and_plan": "Tension headache",
            "follow_up": ""
        }
        res_sparse_note = client.post(f"/cases/{case_sparse_id}/notes", json=note_payload_sparse, headers=headers_a)
        assert res_sparse_note.status_code == 201, f"Save sparse note failed: {res_sparse_note.text}"
        note_sparse_id = res_sparse_note.json()["id"]

        pdf_sparse_res = client.get(f"/notes/{note_sparse_id}/pdf", headers=headers_a)
        assert pdf_sparse_res.status_code == 200
        sparse_reader = pypdf.PdfReader(io.BytesIO(pdf_sparse_res.content))
        sparse_text = "\n".join(page.extract_text() for page in sparse_reader.pages)
        
        assert "Not provided." in sparse_text, "Expected 'Not provided.' for empty sections"
        count_not_provided = sparse_text.count("Not provided.")
        assert count_not_provided >= 6, f"Expected at least 6 'Not provided.' sections, got {count_not_provided}"
        print(f"  [OK] Empty sections display 'Not provided.' ({count_not_provided} occurrences)")


        # Step 8: Multi-page Generation and Pagination
        print("\n[8/11] Verifying multi-page clinical notes render without truncation...")
        case_long = client.post("/cases", json={"case_title": "Complex Rheumatology Intake"}, headers=headers_a)
        assert case_long.status_code == 201
        case_long_id = case_long.json()["id"]

        note_payload_long = {
            "chief_complaint": "Extensive polyarthralgia and autoimmune evaluation over 18 months.",
            "hpi": "Detailed chronological narrative: " + ("Patient reports persistent morning stiffness lasting >90 minutes, symmetric swelling in PIP and MCP joints, bilateral knee effusion, and profound afternoon fatigue. Initial symptom onset followed an acute viral syndrome in early 2025. " * 12),
            "past_medical_history": "Hypothyroidism managed with levothyroxine 50mcg. Unremarkable surgical history. " * 6,
            "medications": "Levothyroxine 50mcg daily. Naproxen 500mg BID with meals. Omeprazole 20mg daily. " * 5,
            "allergies": "Sulfa trimethoprim-sulfamethoxazole (severe maculopapular exanthem). " * 4,
            "family_history": "First-degree relative (sister) diagnosed with systemic lupus erythematosus. Maternal aunt with Sjögren syndrome. " * 5,
            "social_history": "Works as university administrator. No tobacco or illicit drug use. Moderate aerobic exercise when joint pain permits. " * 5,
            "review_of_systems": "Constitutional: fatigue, malaise. Musculoskeletal: symmetric polyarthralgia. Cutaneous: photosensitivity. Ocular: keratoconjunctivitis sicca symptoms. " * 4,
            "physical_examination": "Not performed — information not collected during the patient consultation",
            "assessment_and_plan": "High clinical suspicion for inflammatory arthritis, seronegative rheumatoid arthritis versus undifferentiated connective tissue disease. Diagnostic plan: Comprehensive metabolic panel, CBC with diff, ESR, high-sensitivity CRP, ANA with reflex titer, anti-CCP antibodies, rheumatoid factor, HLA-B27. Baseline bilateral hand/wrist radiographs. " * 4,
            "follow_up": "Urgent rheumatology consultation within 10 business days upon receipt of serologic and radiographic studies. Return immediately for high spikes in temperature or unilateral joint redness."
        }
        res_long_note = client.post(f"/cases/{case_long_id}/notes", json=note_payload_long, headers=headers_a)
        assert res_long_note.status_code == 201
        note_long_id = res_long_note.json()["id"]

        pdf_long_res = client.get(f"/notes/{note_long_id}/pdf", headers=headers_a)
        assert pdf_long_res.status_code == 200
        long_reader = pypdf.PdfReader(io.BytesIO(pdf_long_res.content))
        total_long_pages = len(long_reader.pages)
        assert total_long_pages >= 2, f"Expected at least 2 pages for extensive note, got {total_long_pages}"
        
        # Verify page numbering on every page
        for page_idx, page in enumerate(long_reader.pages):
            page_text = page.extract_text()
            expected_page_str = f"Page {page_idx + 1} of {total_long_pages}"
            assert expected_page_str in page_text, f"Page {page_idx + 1} missing accurate pagination '{expected_page_str}'"
            assert "AI-assisted patient record" in page_text, f"Page {page_idx + 1} missing legal disclaimer"

        # Verify running header on page 2
        page2_text = long_reader.pages[1].extract_text()
        assert "DocuMedi" in page2_text, "Running header brand missing on page 2"
        assert "Patient Clinical Record" in page2_text, "Running header title missing on page 2"
        assert "Eleanor Vance" in page2_text, "Running header patient name missing on page 2"
        print(f"  [OK] Multi-page document generated successfully ({total_long_pages} pages)")
        print(f"  [OK] Dynamic 'Page X of {total_long_pages}' confirmed on every page")

        # Step 9: Test Unauthenticated Request (HTTP 401)
        print("\n[9/11] Testing unauthenticated PDF download rejection...")
        unauth_res = client.get(f"/notes/{note_a_id}/pdf")
        assert unauth_res.status_code == 401, f"Expected 401, got {unauth_res.status_code}"
        print("  [OK] Unauthenticated request rejected with HTTP 401")

        # Step 10: Test Cross-Patient Isolation (Patient B -> Note A)
        print("\n[10/11] Testing cross-patient authorization isolation...")
        forbidden_res = client.get(f"/notes/{note_a_id}/pdf", headers=headers_b)
        assert forbidden_res.status_code == 403, f"Expected 403 Forbidden, got {forbidden_res.status_code}"
        assert "forbidden" in forbidden_res.json()["detail"].lower() or "access" in forbidden_res.json()["detail"].lower()
        print("  [OK] Patient B cannot download Patient A's note (HTTP 403 Forbidden)")

        # Step 11: Nonexistent Note (HTTP 404) & PDF Generation Failure Handling (HTTP 500)
        print("\n[11/11] Testing nonexistent note ID (404) and generator failure handling (500)...")
        not_found_res = client.get("/notes/999999/pdf", headers=headers_a)
        assert not_found_res.status_code == 404, f"Expected 404, got {not_found_res.status_code}"
        print("  [OK] Nonexistent note ID returned HTTP 404 Not Found")

        with patch("routers.notes.generate_patient_note_pdf", side_effect=RuntimeError("Simulated engine crash")):
            error_res = client.get(f"/notes/{note_a_id}/pdf", headers=headers_a)
            assert error_res.status_code == 500, f"Expected 500, got {error_res.status_code}"
            assert "Failed to generate clinical PDF report" in error_res.json()["detail"]

        print("  [OK] PDF generation engine errors handled gracefully with HTTP 500")

        print("\n" + "=" * 70)
        print("SUCCESS: ALL STAGE 8 PDF TESTS PASSED PERFECTLY!")
        print("=" * 70)

    finally:
        cleanup_test_data()
        print("[OK] Cleaned up temporary test patients, cases, and notes safely.")



if __name__ == "__main__":
    run_pdf_tests()
