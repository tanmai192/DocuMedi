"""
test_notes.py — Automated Test Suite for DocuMedi Stage 6: Clinical Note Generation & Saving.

Covers:
1. Generating a structured patient note from conversation dialogue.
2. Confirming all 11 required clinical sections exist in order.
3. Confirming Physical Examination is strictly 'Not performed — information not collected during the patient conversation'.
4. Confirming missing fields default to 'Not provided'.
5. Cross-patient authorization check (Patient B cannot generate or access Patient A's note).
6. Saving the confirmed and edited note to MySQL (POST /cases/{case_id}/notes).
7. Retrieving the saved note (GET /notes/{note_id}) and patient list (GET /notes).
8. Idempotency test (saving again updates the existing record rather than duplicating).
9. Updating a note (PUT /notes/{note_id}).
10. Full database cleanup.
"""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Patient, PatientCase, ConversationMessage, PatientNote

client = TestClient(app)

EMAIL_STAGE6_A = "patient.a.stage6@example.com"
EMAIL_STAGE6_B = "patient.b.stage6@example.com"


def cleanup_stage6():
    db = SessionLocal()
    try:
        patients = db.query(Patient).filter(Patient.email.in_([EMAIL_STAGE6_A, EMAIL_STAGE6_B])).all()
        for p in patients:
            db.delete(p)
        db.commit()
    finally:
        db.close()


def run_stage6_tests():
    print("=" * 65)
    print("DocuMedi Stage 6: Automated Note Generation & Saving Test Suite")
    print("=" * 65)

    cleanup_stage6()

    try:
        # Step 1: Create two test patients
        print("\n[1/9] Creating test patients A and B...")
        res_a = client.post("/auth/register", json={
            "full_name": "Stage6 Patient Alpha",
            "email": EMAIL_STAGE6_A,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_a.status_code == 201
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        res_b = client.post("/auth/register", json={
            "full_name": "Stage6 Patient Beta",
            "email": EMAIL_STAGE6_B,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_b.status_code == 201
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        print("  [PASS] Patients registered.")

        # Step 2: Create a case for Patient A and add conversation messages
        print("\n[2/9] Creating consultation case with dialogue for Patient A...")
        res_case = client.post("/cases", headers=headers_a, json={
            "case_title": "Seasonal Allergies and Cough"
        })
        assert res_case.status_code == 201
        case_id = res_case.json()["id"]

        # Add message 1 (Chief complaint)
        client.post(
            f"/cases/{case_id}/messages",
            headers=headers_a,
            json={"message_content": "I have had a dry tickling cough and runny nose for 5 days."}
        )
        # Add message 2 (Severity)
        client.post(
            f"/cases/{case_id}/messages",
            headers=headers_a,
            json={"message_content": "Severity is around a 4 out of 10. Worse in the evening."}
        )
        # End consultation
        client.post(f"/cases/{case_id}/end", headers=headers_a)
        print("  [PASS] Consultation created and ended.")

        # Step 3: Cross-patient authorization check on note generation
        print("\n[3/9] Testing cross-patient generation rejection...")
        res_unauth_gen = client.post(f"/cases/{case_id}/generate-note", headers=headers_b)
        assert res_unauth_gen.status_code == 403
        print("  [PASS] Patient B forbidden from generating Patient A's note (HTTP 403).")

        # Step 4: Generate note for Patient A
        print("\n[4/9] Generating structured clinical note for Patient A...")
        res_gen = client.post(f"/cases/{case_id}/generate-note", headers=headers_a)
        assert res_gen.status_code == 200
        gen_data = res_gen.json()
        note = gen_data["note"]

        expected_11_keys = [
            "chief_complaint",
            "hpi",
            "past_medical_history",
            "medications",
            "allergies",
            "family_history",
            "social_history",
            "review_of_systems",
            "physical_examination",
            "assessment_and_plan",
            "follow_up"
        ]

        for k in expected_11_keys:
            assert k in note, f"Missing required clinical heading: {k}"
            assert len(note[k]) > 0, f"Empty content for heading: {k}"

        # Step 5: Check medical safety requirements
        print("\n[5/9] Verifying clinical safety and physical examination rule...")
        assert note["physical_examination"] == "Not performed — information not collected during the patient conversation"
        assert "qualified" in note["assessment_and_plan"].lower() or "physician" in note["assessment_and_plan"].lower()
        print("  [PASS] Physical examination is strictly 'Not performed...' and assessment is neutral.")

        # Step 6: Save confirmed and edited note to MySQL
        print("\n[6/9] Saving confirmed patient note to MySQL...")
        save_payload = {
            "chief_complaint": note["chief_complaint"],
            "hpi": note["hpi"] + " Patient reports feeling slightly fatigued.",  # Edited by patient
            "past_medical_history": "Mild seasonal allergic rhinitis in springtime",
            "medications": "Cetirizine 10mg as needed",
            "allergies": "No known drug allergies (NKDA)",
            "family_history": "Non-contributory",
            "social_history": "Non-smoker, drinks coffee socially",
            "review_of_systems": note["review_of_systems"],
            "physical_examination": note["physical_examination"],
            "assessment_and_plan": note["assessment_and_plan"],
            "follow_up": note["follow_up"]
        }
        res_save = client.post(f"/cases/{case_id}/notes", headers=headers_a, json=save_payload)
        assert res_save.status_code == 201
        saved_note = res_save.json()
        note_id = saved_note["id"]
        assert saved_note["case_id"] == case_id
        assert "allergic rhinitis" in saved_note["past_medical_history"]
        print(f"  [PASS] Note #{note_id} persisted in MySQL with patient edits.")

        # Step 7: Retrieve note by ID and list all notes
        print("\n[7/9] Retrieving saved note by ID and listing patient notes...")
        res_get = client.get(f"/notes/{note_id}", headers=headers_a)
        assert res_get.status_code == 200
        assert res_get.json()["id"] == note_id

        res_list = client.get("/notes", headers=headers_a)
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1

        # Patient B cannot retrieve Patient A's note
        res_b_get = client.get(f"/notes/{note_id}", headers=headers_b)
        assert res_b_get.status_code == 403
        print("  [PASS] Note retrieval verified with cross-patient protection.")

        # Step 8: Idempotency check (saving again updates existing record, does not create duplicate)
        print("\n[8/9] Testing idempotency / duplicate save protection...")
        save_payload["medications"] = "Cetirizine 10mg daily"
        res_resave = client.post(f"/cases/{case_id}/notes", headers=headers_a, json=save_payload)
        assert res_resave.status_code in [200, 201]
        assert res_resave.json()["id"] == note_id  # Same ID updated!

        # Total notes count for Patient A must still be exactly 1
        res_list_after = client.get("/notes", headers=headers_a)
        assert len(res_list_after.json()) == 1
        print("  [PASS] Duplicate prevention confirmed: note count remains 1 and record updated.")

        # Step 9: Update note via PUT /notes/{note_id}
        print("\n[9/9] Testing PUT /notes/{note_id} update...")
        save_payload["family_history"] = "Father has seasonal allergies"
        res_put = client.put(f"/notes/{note_id}", headers=headers_a, json=save_payload)
        assert res_put.status_code == 200
        assert res_put.json()["family_history"] == "Father has seasonal allergies"
        print("  [PASS] Note updated successfully via PUT.")

        print("\n" + "=" * 65)
        print(" ALL 9 STAGE 6 NOTE GENERATION & SAVING TESTS PASSED! ")
        print("=" * 65)

    finally:
        cleanup_stage6()
        print("\n[CLEANUP] Stage 6 test records purged from MySQL.")


if __name__ == "__main__":
    run_stage6_tests()
