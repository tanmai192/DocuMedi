"""
test_cases.py — Automated Test Suite for DocuMedi Stage 5: Conversational AI & Cases.

Covers:
1. Case creation with initial AI greeting.
2. Retrieving only the authenticated patient's cases.
3. Strict cross-patient isolation (Patient B cannot access or message Patient A's case).
4. Message submission and conversational intake progression.
5. Red flag emergency symptom detection and urgent care notice.
6. Validation rejection on empty or whitespace message (HTTP 422).
7. Ending an active consultation (status becomes 'completed').
8. Rejection of new messages to an ended consultation (HTTP 400).
9. Full cleanup leaving MySQL clean.
"""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Patient, PatientCase, ConversationMessage
from services.conversation_service import INITIAL_GREETING

client = TestClient(app)

EMAIL_A = "patient.a.stage5@example.com"
EMAIL_B = "patient.b.stage5@example.com"


def cleanup_test_cases():
    """Ensure all test patients and related cascaded data are deleted from MySQL."""
    db = SessionLocal()
    try:
        patients = db.query(Patient).filter(Patient.email.in_([EMAIL_A, EMAIL_B])).all()
        for p in patients:
            db.delete(p)
        db.commit()
    finally:
        db.close()


def run_stage5_tests():
    print("=" * 65)
    print("DocuMedi Stage 5: Automated Cases & Conversational AI Test Suite")
    print("=" * 65)

    cleanup_test_cases()

    try:
        # Step 1: Register two distinct patients
        print("\n[1/9] Registering Patient A and Patient B...")
        res_a = client.post("/auth/register", json={
            "full_name": "Patient Alpha",
            "email": EMAIL_A,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_a.status_code == 201
        token_a = res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        res_b = client.post("/auth/register", json={
            "full_name": "Patient Beta",
            "email": EMAIL_B,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        assert res_b.status_code == 201
        token_b = res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        print("  [PASS] Patients created with valid JWT tokens.")

        # Step 2: Create a case for Patient A
        print("\n[2/9] Creating a new consultation case for Patient A...")
        res_case = client.post("/cases", headers=headers_a, json={
            "case_title": "Severe Migraine Consultation"
        })
        assert res_case.status_code == 201
        case_data = res_case.json()
        case_id = case_data["id"]
        assert case_data["case_title"] == "Severe Migraine Consultation"
        assert case_data["status"] == "active"
        assert len(case_data["messages"]) == 1
        assert case_data["messages"][0]["sender_role"] == "ai"
        assert case_data["messages"][0]["message_content"] == INITIAL_GREETING
        print(f"  [PASS] Case #{case_id} created with initial AI greeting seeded.")

        # Step 3: Verify list of cases belongs only to Patient A
        print("\n[3/9] Verifying GET /cases returns only Patient A's cases...")
        res_list_a = client.get("/cases", headers=headers_a)
        assert res_list_a.status_code == 200
        assert len(res_list_a.json()) == 1
        assert res_list_a.json()[0]["id"] == case_id

        res_list_b = client.get("/cases", headers=headers_b)
        assert res_list_b.status_code == 200
        assert len(res_list_b.json()) == 0  # Patient B has 0 cases
        print("  [PASS] Case isolation verified: Patient B sees 0 cases.")

        # Step 4: Strict cross-patient authorization checks
        print("\n[4/9] Testing cross-patient authorization blocking...")
        res_unauthorized = client.get(f"/cases/{case_id}", headers=headers_b)
        assert res_unauthorized.status_code == 403
        assert "cannot access another patient" in res_unauthorized.json()["detail"].lower()

        res_unauth_msg = client.post(
            f"/cases/{case_id}/messages",
            headers=headers_b,
            json={"message_content": "I am snooping into another case"}
        )
        assert res_unauth_msg.status_code == 403
        print("  [PASS] Patient B strictly forbidden from viewing or messaging Case A (HTTP 403).")

        # Step 5: Send conversation message
        print("\n[5/9] Sending first patient message to Case A...")
        res_msg1 = client.post(
            f"/cases/{case_id}/messages",
            headers=headers_a,
            json={"message_content": "I have had a throbbing headache on the right side of my head for 2 days."}
        )
        assert res_msg1.status_code == 200
        data_msg1 = res_msg1.json()
        assert data_msg1["patient_message"]["sender_role"] == "patient"
        assert data_msg1["ai_response"]["sender_role"] == "ai"
        assert len(data_msg1["ai_response"]["message_content"]) > 10
        print("  [PASS] Patient message saved and AI responded with follow-up.")

        # Step 6: Empty message validation
        print("\n[6/9] Testing empty / whitespace message validation...")
        res_empty = client.post(
            f"/cases/{case_id}/messages",
            headers=headers_a,
            json={"message_content": "   "}
        )
        assert res_empty.status_code == 422
        print("  [PASS] Empty whitespace message rejected with HTTP 422.")

        # Step 7: Red flag emergency detection
        print("\n[7/9] Testing red-flag emergency detection...")
        res_emergency = client.post(
            f"/cases/{case_id}/messages",
            headers=headers_a,
            json={"message_content": "I now also have severe shortness of breath and crushing chest pain."}
        )
        assert res_emergency.status_code == 200
        ai_resp_emergency = res_emergency.json()["ai_response"]["message_content"]
        assert "URGENT MEDICAL NOTICE" in ai_resp_emergency
        assert "112" in ai_resp_emergency
        print("  [PASS] Emergency red flags triggered urgent care / 112 warning.")

        # Step 8: End the consultation
        print("\n[8/9] Ending the active consultation...")
        res_end = client.post(f"/cases/{case_id}/end", headers=headers_a)
        assert res_end.status_code == 200
        assert res_end.json()["status"] == "completed"
        print("  [PASS] Consultation status transitioned to 'completed'.")

        # Step 9: Verify message rejection on ended case
        print("\n[9/9] Verifying messages rejected on ended case...")
        res_after_end = client.post(
            f"/cases/{case_id}/messages",
            headers=headers_a,
            json={"message_content": "Can I ask one more question?"}
        )
        assert res_after_end.status_code == 400
        assert "already ended" in res_after_end.json()["detail"].lower()
        print("  [PASS] New messages to ended case rejected with HTTP 400.")

        print("\n" + "=" * 65)
        print(" ALL 9 STAGE 5 CASE & AI TESTS PASSED! ")
        print("=" * 65)

    finally:
        cleanup_test_cases()
        print("\n[CLEANUP] All Stage 5 test patients and cases removed from MySQL.")


if __name__ == "__main__":
    run_stage5_tests()
