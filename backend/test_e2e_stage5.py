"""
test_e2e_stage5.py — Comprehensive end-to-end integration test for Stage 5.
Tests the complete conversational case-taking workflow using FastAPI TestClient.
"""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Patient, PatientCase, ConversationMessage
from services.conversation_service import INITIAL_GREETING

client = TestClient(app)

TEST_EMAIL = "e2e.stage5.patient@example.com"


def cleanup():
    db = SessionLocal()
    try:
        p = db.query(Patient).filter(Patient.email == TEST_EMAIL).first()
        if p:
            db.delete(p)
            db.commit()
    finally:
        db.close()


def run_e2e_test():
    print("=" * 65)
    print("DocuMedi Stage 5: End-to-End Conversational Case Intake Test")
    print("=" * 65)

    cleanup()

    try:
        # 1. Register patient
        print("\n[1/7] Registering test patient...")
        res_reg = client.post("/auth/register", json={
            "full_name": "E2E Stage 5 Patient",
            "email": TEST_EMAIL,
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!"
        })
        assert res_reg.status_code == 201
        token = res_reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [PASS] Registration succeeded.")

        # 2. Create a case
        print("\n[2/7] Creating new consultation case...")
        res_case = client.post("/cases", headers=headers, json={
            "case_title": "Acute Sinus Pressure & Pain"
        })
        assert res_case.status_code == 201
        case_data = res_case.json()
        case_id = case_data["id"]
        assert case_data["status"] == "active"
        assert case_data["messages"][0]["message_content"] == INITIAL_GREETING
        print(f"  [PASS] Case #{case_id} initialized with greeting.")

        # 3. Patient sends chief complaint
        print("\n[3/7] Patient sends chief complaint...")
        res_msg1 = client.post(
            f"/cases/{case_id}/messages",
            headers=headers,
            json={"message_content": "I have severe facial pressure and congestion for 4 days."}
        )
        assert res_msg1.status_code == 200
        data1 = res_msg1.json()
        assert data1["patient_message"]["message_content"] == "I have severe facial pressure and congestion for 4 days."
        assert len(data1["ai_response"]["message_content"]) > 10
        print("  [PASS] AI returned clinical follow-up: " + data1["ai_response"]["message_content"][:75] + "...")

        # 4. Patient answers severity question
        print("\n[4/7] Patient responds with symptom severity...")
        res_msg2 = client.post(
            f"/cases/{case_id}/messages",
            headers=headers,
            json={"message_content": "It is around a 6 out of 10. Feels like a heavy throbbing ache."}
        )
        assert res_msg2.status_code == 200
        data2 = res_msg2.json()
        assert len(data2["ai_response"]["message_content"]) > 10
        print("  [PASS] AI returned next intake question: " + data2["ai_response"]["message_content"][:75] + "...")

        # 5. Verify conversation history retrieval
        print("\n[5/7] Retrieving case history via GET /cases/{case_id}...")
        res_detail = client.get(f"/cases/{case_id}", headers=headers)
        assert res_detail.status_code == 200
        all_msgs = res_detail.json()["messages"]
        # Expected: Initial greeting (AI) + Msg 1 (Patient) + AI 1 + Msg 2 (Patient) + AI 2 = 5 messages
        assert len(all_msgs) == 5
        assert all_msgs[0]["sender_role"] == "ai"
        assert all_msgs[1]["sender_role"] == "patient"
        assert all_msgs[2]["sender_role"] == "ai"
        assert all_msgs[3]["sender_role"] == "patient"
        assert all_msgs[4]["sender_role"] == "ai"
        print(f"  [PASS] Chronological history verified with {len(all_msgs)} total messages.")

        # 6. End consultation
        print("\n[6/7] Ending consultation session...")
        res_end = client.post(f"/cases/{case_id}/end", headers=headers)
        assert res_end.status_code == 200
        assert res_end.json()["status"] == "completed"
        print("  [PASS] Case completed and locked.")

        # 7. Verify dashboard case listing
        print("\n[7/7] Verifying case appears in patient cases list...")
        res_list = client.get("/cases", headers=headers)
        assert res_list.status_code == 200
        cases_list = res_list.json()
        assert len(cases_list) == 1
        assert cases_list[0]["id"] == case_id
        assert cases_list[0]["status"] == "completed"
        print("  [PASS] Case properly reflected in patient summary.")

        print("\n" + "=" * 65)
        print(" ALL END-TO-END TESTS PASSED SUCCESSFULLY! ")
        print("=" * 65)

    finally:
        cleanup()
        print("\n[CLEANUP] Cleaned test patient records from MySQL.")


if __name__ == "__main__":
    run_e2e_test()
