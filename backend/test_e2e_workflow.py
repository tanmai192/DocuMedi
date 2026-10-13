"""
test_e2e_workflow.py — Complete End-to-End Patient Workflow Verification for DocuMedi.

Executes all 15 patient journey steps sequentially:
1. Register a new patient (fictional).
2. Log in successfully and acquire JWT.
3. Start a new consultation case.
4. Exchange multiple messages with clinical conversational AI.
5. Finish the consultation (status -> completed).
6. Generate structured clinical note from dialogue.
7. Review and edit the draft note with patient clarifications.
8. Confirm and save the note to MySQL.
9. Open the saved clinical note by ID and verify persistence.
10. Navigate to My Medical History (/notes/timeline).
11. Verify the saved note appears in the timeline with accurate summary.
12. Download the note as a PDF from the note detail endpoint.
13. Download the note as a PDF using the timeline entry reference.
14. Parse downloaded PDFs with pypdf and verify branding, metadata, sections, and disclaimer.
15. Log out and confirm protected endpoints reject unauthenticated requests with HTTP 401.
"""

import io
import pypdf
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Patient

client = TestClient(app)

FICTIONAL_EMAIL = "evelyn.harper.e2e@example.com"
FICTIONAL_NAME = "Evelyn Harper"
FICTIONAL_PASSWORD = "DocuMedi2026!"


def cleanup():
    db = SessionLocal()
    try:
        patients = db.query(Patient).filter(Patient.email == FICTIONAL_EMAIL).all()
        for p in patients:
            db.delete(p)
        db.commit()
    finally:
        db.close()


def run_e2e_workflow():
    print("=" * 75)
    print("DocuMedi Stage 9: Full 15-Step End-to-End Application Workflow Test")
    print("=" * 75)

    cleanup()

    try:
        # Step 1: Register new patient
        print("\n[Step 1/15] Registering new fictional patient...")
        reg_res = client.post("/auth/register", json={
            "full_name": FICTIONAL_NAME,
            "email": FICTIONAL_EMAIL,
            "password": FICTIONAL_PASSWORD,
            "confirm_password": FICTIONAL_PASSWORD
        })
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
        initial_token = reg_res.json()["access_token"]
        assert initial_token, "No access token received upon registration"
        print(f"  [OK] Patient registered successfully: {FICTIONAL_NAME} ({FICTIONAL_EMAIL})")

        # Step 2: Log in successfully
        print("\n[Step 2/15] Logging in with patient credentials...")
        login_res = client.post("/auth/login", json={
            "email": FICTIONAL_EMAIL,
            "password": FICTIONAL_PASSWORD
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        assert token, "No access token returned from login"
        headers = {"Authorization": f"Bearer {token}"}
        print("  [OK] Login successful, JWT token issued.")

        # Verify profile via /auth/me
        me_res = client.get("/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == FICTIONAL_EMAIL
        print(f"  [OK] Profile verified: {me_res.json()['full_name']}")

        # Step 3: Start a new consultation
        print("\n[Step 3/15] Starting a new consultation case...")
        case_res = client.post("/cases", json={
            "case_title": "Seasonal Allergy & Sinusitis Intake"
        }, headers=headers)
        assert case_res.status_code == 201, f"Case creation failed: {case_res.text}"
        case_data = case_res.json()
        case_id = case_data["id"]
        assert case_data["status"] == "active"
        print(f"  [OK] Case #{case_id} initialized with status '{case_data['status']}'")

        # Step 4: Exchange multiple messages with conversational AI
        print("\n[Step 4/15] Exchanging multiple dialogue turns with clinical AI...")
        msg1_res = client.post(f"/cases/{case_id}/messages", json={
            "message_content": "I have been experiencing persistent nasal congestion, facial pressure around my cheeks and forehead, and sneezing for 4 days."
        }, headers=headers)
        assert msg1_res.status_code == 200, f"Message 1 failed: {msg1_res.text}"
        ai_reply_1 = msg1_res.json()["ai_response"]["message_content"]
        assert ai_reply_1 and len(ai_reply_1) > 10
        print(f"  [OK] Turn 1 completed. AI follow-up: {ai_reply_1[:80]}...")

        msg2_res = client.post(f"/cases/{case_id}/messages", json={
            "message_content": "I took cetirizine 10mg yesterday which helped slightly with sneezing, but the facial pressure persists. No fever. No drug allergies."
        }, headers=headers)
        assert msg2_res.status_code == 200, f"Message 2 failed: {msg2_res.text}"
        ai_reply_2 = msg2_res.json()["ai_response"]["message_content"]
        assert ai_reply_2 and len(ai_reply_2) > 10
        print(f"  [OK] Turn 2 completed. AI follow-up: {ai_reply_2[:80]}...")

        # Step 5: Finish the consultation
        print("\n[Step 5/15] Finishing the consultation...")
        end_res = client.post(f"/cases/{case_id}/end", headers=headers)
        assert end_res.status_code == 200, f"Ending case failed: {end_res.text}"
        assert end_res.json()["status"] == "completed"
        print(f"  [OK] Case #{case_id} successfully marked 'completed'")

        # Step 6: Generate a structured clinical note
        print("\n[Step 6/15] Generating structured clinical note from dialogue...")
        gen_res = client.post(f"/cases/{case_id}/generate-note", headers=headers)
        assert gen_res.status_code == 200, f"Note generation failed: {gen_res.text}"
        draft_note = gen_res.json()["note"]
        assert draft_note["chief_complaint"], "Missing chief complaint in draft"
        assert draft_note["hpi"], "Missing HPI in draft"
        assert "Not performed" in draft_note["physical_examination"], "Physical exam must state not performed"
        print("  [OK] Structured 11-section note generated for patient review.")

        # Step 7: Review and edit the generated note
        print("\n[Step 7/15] Patient reviewing and adding personal edits to the draft note...")
        edited_note = dict(draft_note)
        edited_note["chief_complaint"] = "Bilateral facial pressure, sinus congestion, and sneezing for 4 days."
        edited_note["hpi"] = draft_note["hpi"] + " Patient explicitly notes bilateral maxillary tenderness."
        edited_note["medications"] = "Cetirizine 10mg daily as needed for allergy symptoms."
        edited_note["allergies"] = "No known drug allergies (NKDA)."
        edited_note["follow_up"] = "Follow up with primary care if sinus symptoms or facial pain persist beyond 10 days."
        print("  [OK] Patient edits applied to draft sections.")

        # Step 8: Confirm and save the note
        print("\n[Step 8/15] Confirming and saving note to MySQL database...")
        save_res = client.post(f"/cases/{case_id}/notes", json=edited_note, headers=headers)
        assert save_res.status_code == 201, f"Saving note failed: {save_res.text}"
        saved_note = save_res.json()
        note_id = saved_note["id"]
        assert note_id > 0
        assert saved_note["case_id"] == case_id
        print(f"  [OK] Note #{note_id} successfully persisted in MySQL database.")

        # Step 9: Open the saved clinical note
        print(f"\n[Step 9/15] Opening saved clinical note #{note_id} by ID...")
        open_res = client.get(f"/notes/{note_id}", headers=headers)
        assert open_res.status_code == 200, f"Retrieving note failed: {open_res.text}"
        retrieved_note = open_res.json()
        assert retrieved_note["id"] == note_id
        assert "Bilateral facial pressure" in retrieved_note["chief_complaint"]
        assert "bilateral maxillary tenderness" in retrieved_note["hpi"]
        print(f"  [OK] Confirmed note #{note_id} retrieved with patient edits intact.")

        # Step 10: Navigate to My Medical History (/notes/timeline)
        print("\n[Step 10/15] Navigating to My Medical History timeline...")
        timeline_res = client.get("/notes/timeline", headers=headers)
        assert timeline_res.status_code == 200, f"Timeline fetch failed: {timeline_res.text}"
        timeline_data = timeline_res.json()
        assert len(timeline_data) >= 1, "Timeline should contain at least 1 entry"
        print(f"  [OK] Timeline loaded with {len(timeline_data)} recorded entry(ies).")

        # Step 11: Verify saved note appears in timeline
        print("\n[Step 11/15] Verifying saved note is properly reflected in timeline...")
        matched_entry = next((e for e in timeline_data if e["note_id"] == note_id), None)
        assert matched_entry is not None, f"Note #{note_id} not found in timeline!"
        assert matched_entry["case_id"] == case_id
        assert matched_entry["case_title"] == "Seasonal Allergy & Sinusitis Intake"
        assert "Bilateral facial pressure" in matched_entry["chief_complaint"]
        assert len(matched_entry["summary"]) > 10
        print(f"  [OK] Timeline entry matched: '{matched_entry['case_title']}' | Note #{matched_entry['note_id']}")
        print(f"       Summary excerpt: {matched_entry['summary'][:90]}...")

        # Step 12: Download note as PDF from note detail page
        print(f"\n[Step 12/15] Downloading note PDF from Note Detail endpoint (/notes/{note_id}/pdf)...")
        detail_pdf_res = client.get(f"/notes/{note_id}/pdf", headers=headers)
        assert detail_pdf_res.status_code == 200, f"Detail PDF download failed: {detail_pdf_res.status_code}"
        assert detail_pdf_res.headers["content-type"] == "application/pdf"
        assert "DocuMedi_Report_" in detail_pdf_res.headers["content-disposition"]
        detail_pdf_bytes = detail_pdf_res.content
        assert detail_pdf_bytes.startswith(b"%PDF-"), "Invalid PDF binary format"
        print(f"  [OK] PDF downloaded from Note Detail ({len(detail_pdf_bytes)} bytes)")

        # Step 13: Download the same note from medical history timeline
        print(f"\n[Step 13/15] Downloading note PDF from timeline reference (note_id={matched_entry['note_id']})...")
        timeline_pdf_res = client.get(f"/notes/{matched_entry['note_id']}/pdf", headers=headers)
        assert timeline_pdf_res.status_code == 200
        assert timeline_pdf_res.headers["content-type"] == "application/pdf"
        timeline_pdf_bytes = timeline_pdf_res.content
        assert len(timeline_pdf_bytes) == len(detail_pdf_bytes), "PDF bytes should match exactly"
        print(f"  [OK] PDF downloaded from Timeline reference ({len(timeline_pdf_bytes)} bytes)")

        # Step 14: Open and parse PDFs with pypdf to verify contents
        print("\n[Step 14/15] Parsing PDF with pypdf and verifying document contents...")
        pdf_reader = pypdf.PdfReader(io.BytesIO(detail_pdf_bytes))
        assert len(pdf_reader.pages) >= 1, "PDF must have at least 1 page"
        full_text = "\n".join(page.extract_text() for page in pdf_reader.pages)

        # Assert branding & metadata
        assert "DocuMedi" in full_text, "DocuMedi brand missing in PDF"
        assert "Your Health Story, Organized." in full_text, "Tagline missing in PDF"
        assert "PATIENT CLINICAL RECORD" in full_text, "Document title missing in PDF"
        assert FICTIONAL_NAME in full_text, "Patient name missing in PDF"
        assert "Seasonal Allergy & Sinusitis Intake" in full_text, "Case title missing in PDF"
        assert f"DOCU-REC-{note_id:05d}" in full_text, "Record ID missing in PDF"

        # Assert all 11 sections in order
        headings = [
            "Chief Complaint", "HPI", "Past Medical History", "Medications",
            "Allergies", "Family History", "Social History", "Review of Systems",
            "Physical Examination", "Assessment and Plan", "Follow-up"
        ]
        last_pos = -1
        for h in headings:
            pos = full_text.find(h)
            assert pos != -1, f"Heading {h} not found in PDF"
            assert pos > last_pos, f"Heading {h} out of order"
            last_pos = pos

        # Assert edited content and disclaimer
        assert "bilateral maxillary tenderness" in full_text, "Edited HPI text missing in PDF"
        assert "AI-assisted patient record" in full_text, "Disclaimer missing in PDF"
        assert "Page 1 of" in full_text, "Page numbering missing in PDF"
        print(f"  [OK] PDF structure verified: branding, metadata, all 11 sections, patient edits, and disclaimer.")

        # Step 15: Log out and confirm protected pages and APIs require authentication
        print("\n[Step 15/15] Simulating logout and verifying authentication barriers...")
        unauth_me = client.get("/auth/me")
        assert unauth_me.status_code == 401, f"Expected 401 on /auth/me, got {unauth_me.status_code}"

        unauth_cases = client.get("/cases")
        assert unauth_cases.status_code == 401, f"Expected 401 on /cases, got {unauth_cases.status_code}"

        unauth_note = client.get(f"/notes/{note_id}")
        assert unauth_note.status_code == 401, f"Expected 401 on /notes/{note_id}, got {unauth_note.status_code}"

        unauth_timeline = client.get("/notes/timeline")
        assert unauth_timeline.status_code == 401, f"Expected 401 on /notes/timeline, got {unauth_timeline.status_code}"

        unauth_pdf = client.get(f"/notes/{note_id}/pdf")
        assert unauth_pdf.status_code == 401, f"Expected 401 on /notes/{note_id}/pdf, got {unauth_pdf.status_code}"
        print("  [OK] All protected routes strictly require JWT Bearer authorization.")

        print("\n" + "=" * 75)
        print("SUCCESS: ALL 15 END-TO-END PATIENT WORKFLOW STEPS PASSED PERFECTLY!")
        print("=" * 75)

    finally:
        cleanup()
        print("[OK] Cleaned up temporary test patient data safely from MySQL.")


if __name__ == "__main__":
    run_e2e_workflow()
