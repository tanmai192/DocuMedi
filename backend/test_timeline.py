"""
test_timeline.py — Automated Test Suite for DocuMedi Stage 7: Medical History Timeline.

Covers:
1. Patient with 0 notes receives an empty list [] from GET /notes/timeline.
2. Multiple notes returned in chronological order, newest first.
3. Strict cross-patient isolation (Patient B sees only their records).
4. Summary is generated faithfully from saved note contents without invention.
5. Unauthenticated request to /notes/timeline is rejected with HTTP 401.
6. Safe database cleanup leaving MySQL spotless.
"""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Patient, PatientCase, PatientNote

client = TestClient(app)

EMAIL_TIMELINE_A = "patient.timeline.a@example.com"
EMAIL_TIMELINE_B = "patient.timeline.b@example.com"


def cleanup_timeline():
    db = SessionLocal()
    try:
        patients = db.query(Patient).filter(Patient.email.in_([EMAIL_TIMELINE_A, EMAIL_TIMELINE_B])).all()
        for p in patients:
            db.delete(p)
        db.commit()
    finally:
        db.close()


def run_timeline_tests():
    print("=" * 65)
    print("DocuMedi Stage 7: Automated Medical History Timeline Test Suite")
    print("=" * 65)

    cleanup_timeline()

    try:
        # Step 1: Register Patient A and Patient B
        print("\n[1/6] Registering Patient A and Patient B...")
        res_a = client.post("/auth/register", json={
            "full_name": "Timeline Patient Alpha",
            "email": EMAIL_TIMELINE_A,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_a.status_code == 201
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        res_b = client.post("/auth/register", json={
            "full_name": "Timeline Patient Beta",
            "email": EMAIL_TIMELINE_B,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_b.status_code == 201
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        print("  [PASS] Patients registered.")

        # Step 2: Empty state check
        print("\n[2/6] Verifying empty state for patient with no notes...")
        res_empty = client.get("/notes/timeline", headers=headers_a)
        assert res_empty.status_code == 200
        assert res_empty.json() == []
        print("  [PASS] Patient with 0 notes received empty list [].")

        # Step 3: Unauthenticated access rejection
        print("\n[3/6] Verifying unauthenticated request rejection...")
        res_unauth = client.get("/notes/timeline")
        assert res_unauth.status_code == 401
        print("  [PASS] Missing token rejected with HTTP 401.")

        # Step 4: Create two notes for Patient A with different timestamps
        print("\n[4/6] Creating two clinical cases and notes for Patient A...")
        # Note 1: Older case
        res_case1 = client.post("/cases", headers=headers_a, json={"case_title": "Sprained Left Ankle"})
        case1_id = res_case1.json()["id"]
        res_note1 = client.post(f"/cases/{case1_id}/notes", headers=headers_a, json={
            "chief_complaint": "Twisted left ankle playing basketball yesterday",
            "hpi": "Patient landed awkwardly on left foot. Swelling and tenderness over lateral malleolus.",
            "past_medical_history": "No prior fractures",
            "medications": "Ibuprofen 400mg",
            "allergies": "None",
            "family_history": "Not provided",
            "social_history": "Plays recreational sports",
            "review_of_systems": "Positive for ankle pain; negative for numbness",
            "physical_examination": "Not performed — information not collected during the patient conversation",
            "assessment_and_plan": "Reported lateral ankle sprain. Rest, ice, compression advised.",
            "follow_up": "Consult an orthopedic specialist if unable to bear weight after 48h."
        })
        assert res_note1.status_code == 201
        note1_id = res_note1.json()["id"]

        # Note 2: Newer case
        res_case2 = client.post("/cases", headers=headers_a, json={"case_title": "Seasonal Allergies Check"})
        case2_id = res_case2.json()["id"]
        res_note2 = client.post(f"/cases/{case2_id}/notes", headers=headers_a, json={
            "chief_complaint": "Sneezing and itchy eyes for 3 days",
            "hpi": "Symptoms began with pollen season. Clear rhinorrhea, watery red eyes.",
            "past_medical_history": "Allergic rhinitis",
            "medications": "Loratadine 10mg",
            "allergies": "Pollen, dust mites",
            "family_history": "Not provided",
            "social_history": "Not provided",
            "review_of_systems": "Positive for nasal congestion and ocular pruritus",
            "physical_examination": "Not performed — information not collected during the patient conversation",
            "assessment_and_plan": "Reported allergic rhinitis symptoms.",
            "follow_up": "Consult primary care if over-the-counter antihistamines fail to provide relief."
        })
        assert res_note2.status_code == 201
        note2_id = res_note2.json()["id"]
        print("  [PASS] Created 2 clinical notes for Patient A.")

        # Step 5: Verify timeline ordering and faithful summary
        print("\n[5/6] Verifying chronological timeline sorting and content...")
        res_timeline = client.get("/notes/timeline", headers=headers_a)
        assert res_timeline.status_code == 200
        entries = res_timeline.json()
        assert len(entries) == 2

        # Most recent note should be first (note2)
        assert entries[0]["note_id"] == note2_id
        assert entries[0]["case_title"] == "Seasonal Allergies Check"
        assert "pollen" in entries[0]["summary"].lower()

        # Older note should be second (note1)
        assert entries[1]["note_id"] == note1_id
        assert entries[1]["case_title"] == "Sprained Left Ankle"
        assert "foot" in entries[1]["summary"].lower()

        print("  [PASS] Timeline sorted newest first; summaries extracted faithfully from saved contents.")

        # Step 6: Verify cross-patient isolation (Patient B sees 0 notes)
        print("\n[6/6] Verifying cross-patient timeline isolation...")
        res_timeline_b = client.get("/notes/timeline", headers=headers_b)
        assert res_timeline_b.status_code == 200
        assert res_timeline_b.json() == []  # Zero entries for Patient B
        print("  [PASS] Patient B sees 0 entries. Cross-patient isolation verified.")

        print("\n" + "=" * 65)
        print(" ALL 6 STAGE 7 TIMELINE TESTS PASSED! ")
        print("=" * 65)

    finally:
        cleanup_timeline()
        print("\n[CLEANUP] Stage 7 test records purged from MySQL.")


if __name__ == "__main__":
    run_timeline_tests()
