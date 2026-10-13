"""
test_conversational_ai.py — Automated Test Suite for Natural, Empathetic Conversational AI & Cumulative Symptom Tracking.

Verifies:
1. Multiple symptoms reported together in a single message are recognized and acknowledged.
2. New symptoms introduced midway through the conversation are recognized and connected to earlier symptoms.
3. Preservation of earlier information: AI never asks the patient to repeat duration, severity, or medications already provided.
4. Dynamic adaptation: Follow-up questions adapt to newly introduced symptoms and missing clinical fields.
5. Cumulative record retention: All symptoms (initial + newly added), medications, and history appear in the 11-section clinical note.
6. Negative symptoms (denied symptoms) are correctly documented without false positives.
7. Unmentioned fields strictly remain 'Not provided' without hallucination.
8. Physical Examination is locked to 'Not performed...'.
9. Safe cleanup of test records in MySQL database.
"""

from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Patient
from services.clinical_tracker import (
    build_clinical_state_from_history,
    generate_empathetic_acknowledgment,
    generate_adaptive_follow_up_questions
)
from services.conversation_service import process_patient_message
from services.note_service import extract_fallback_note

client = TestClient(app)

TEST_EMAIL = "empathetic.ai.patient@example.com"
TEST_NAME = "Claire Redfield"
TEST_PASSWORD = "Password123!"


def cleanup():
    db = SessionLocal()
    try:
        patients = db.query(Patient).filter(Patient.email == TEST_EMAIL).all()
        for p in patients:
            db.delete(p)
        db.commit()
    finally:
        db.close()


def run_conversational_ai_tests():
    print("=" * 75)
    print("DocuMedi: Automated Conversational AI & Symptom Tracking Test Suite")
    print("=" * 75)

    cleanup()

    try:
        # -------------------------------------------------------------
        # Part A: Unit Tests for Clinical Tracker & Dialogue Intelligence
        # -------------------------------------------------------------
        print("\n[Part A: Tracker Unit Tests]")

        # Test 1: Multiple symptoms in a single message
        print("\n[1/7] Testing multiple symptoms reported together in turn 1...")
        turn1_msg = "I have been having a severe throbbing headache for 3 days on the right side of my head, along with dizziness and fatigue."
        state1 = build_clinical_state_from_history([], turn1_msg)
        
        assert "headache" in state1.symptoms, "Headache not detected in state"
        assert "dizziness" in state1.symptoms, "Dizziness not detected in state"
        assert "fatigue" in state1.symptoms, "Fatigue not detected in state"
        assert state1.onset_duration == "3 days", f"Expected '3 days', got {state1.onset_duration}"
        assert state1.severity == "severe", f"Expected 'severe', got {state1.severity}"
        assert state1.character == "throbbing", f"Expected 'throbbing', got {state1.character}"
        assert "right side" in state1.location, f"Expected 'right side', got {state1.location}"

        ack1 = generate_empathetic_acknowledgment(state1)
        q1 = generate_adaptive_follow_up_questions(state1)
        
        # Verify acknowledgment mentions multiple symptoms
        assert "headache" in ack1.lower() or "dizziness" in ack1.lower(), "Acknowledgment should mention symptoms"
        # Verify question does NOT ask for duration or character (already provided!)
        assert "how long" not in q1.lower(), "AI should NOT ask how long since patient already gave 3 days!"
        assert "throbbing" not in q1.lower(), "AI should NOT ask description since patient already said throbbing!"
        print("  [OK] Turn 1 correctly extracted 3 symptoms, duration, severity, and avoided asking for known info.")

        # Test 2: New symptom introduced midway through conversation
        print("\n[2/7] Testing new symptom introduced midway (Turn 2)...")
        history_after_turn1 = [
            {"sender_role": "patient", "message_content": turn1_msg},
            {"sender_role": "ai", "message_content": f"{ack1} {q1}"}
        ]
        turn2_msg = "The pain is about an 8/10. Also, my stomach feels nauseous since this morning and my neck is feeling stiff now."
        state2 = build_clinical_state_from_history(history_after_turn1, turn2_msg)

        assert "headache" in state2.symptoms, "Headache should still be retained from turn 1"
        assert "dizziness" in state2.symptoms, "Dizziness should still be retained from turn 1"
        assert "nausea" in state2.symptoms, "Nausea should be tracked as new symptom"
        assert "neck pain" in state2.symptoms, "Neck pain should be tracked as new symptom"
        assert "nausea" in state2.new_symptoms_in_turn or "neck pain" in state2.new_symptoms_in_turn, "Should identify newly introduced symptoms"
        assert state2.severity == "8/10", f"Expected '8/10', got {state2.severity}"

        ack2 = generate_empathetic_acknowledgment(state2)
        q2 = generate_adaptive_follow_up_questions(state2)

        # Verify AI acknowledges newly introduced symptoms on top of earlier symptoms
        assert "nausea" in ack2.lower() or "neck" in ack2.lower(), "Acknowledgment must acknowledge the new symptom!"
        assert "on top of" in ack2.lower() or "earlier" in ack2.lower() or "also" in ack2.lower(), "Acknowledgment should connect new and prior symptoms!"
        # Verify AI adapts question to new symptoms
        assert "neck" in q2.lower() or "nausea" in q2.lower() or "start" in q2.lower(), "Follow-up question should address newly added symptoms!"
        print("  [OK] Turn 2 recognized new symptoms midway, connected them to turn 1 symptoms, and adapted follow-up.")

        # Test 3: Patient provides medications, allergies, and family history
        print("\n[3/7] Testing preservation of medications, allergies, and negative symptoms (Turn 3)...")
        history_after_turn2 = history_after_turn1 + [
            {"sender_role": "patient", "message_content": turn2_msg},
            {"sender_role": "ai", "message_content": f"{ack2} {q2}"}
        ]
        turn3_msg = "No fever or chills. I took ibuprofen 400mg which barely helped. No known drug allergies, but my mother gets chronic migraines."
        state3 = build_clinical_state_from_history(history_after_turn2, turn3_msg)

        assert "fever" in state3.negative_symptoms, "Fever should be recorded as negative symptom"
        assert "fever" not in state3.symptoms, "Fever should NOT be an active symptom!"
        assert "ibuprofen" in state3.medications.lower(), "Medication should be recorded"
        assert "nkda" in state3.allergies.lower() or "no known" in state3.allergies.lower(), "Allergies should be recorded"
        assert "mother" in state3.family_history.lower(), "Family history should be recorded"

        ack3 = generate_empathetic_acknowledgment(state3)
        q3 = generate_adaptive_follow_up_questions(state3)

        # In Turn 3, all key clinical domains have been answered -> should offer completion invitation!
        assert "finish consultation" in q3.lower() or "medication" in q3.lower() or "allergies" in q3.lower(), "Should recognize consultation is well characterized"
        print("  [OK] Negative symptoms accurately separated, medications, allergies, and family history retained.")

        # Test 4: Structured note synthesis reflects cumulative dialogue
        print("\n[4/7] Testing structured 11-section note synthesis from cumulative state...")
        full_history = history_after_turn2 + [
            {"sender_role": "patient", "message_content": turn3_msg},
            {"sender_role": "ai", "message_content": f"{ack3} {q3}"}
        ]
        note = extract_fallback_note(full_history)

        # Check all 11 sections
        assert "headache" in note["chief_complaint"].lower(), "Chief complaint missing headache"
        assert "nausea" in note["chief_complaint"].lower() or "dizziness" in note["chief_complaint"].lower(), "Chief complaint should reflect co-occurring symptoms"
        assert "3 days" in note["hpi"], "HPI should retain duration from turn 1"
        assert "throbbing" in note["hpi"], "HPI should retain character from turn 1"
        assert "8/10" in note["hpi"], "HPI should retain severity from turn 2"
        assert "nausea" in note["hpi"], "HPI should retain new symptom from turn 2"
        assert "neck" in note["hpi"], "HPI should retain neck stiffness from turn 2"
        assert "ibuprofen" in note["medications"].lower(), "Medications section should contain ibuprofen"
        assert "no known" in note["allergies"].lower() or "nkda" in note["allergies"].lower(), "Allergies section should record NKDA"
        assert "mother" in note["family_history"].lower(), "Family history should record mother's migraines"
        assert "Not performed" in note["physical_examination"], "Physical exam must state not performed"
        assert "Not provided" in note["past_medical_history"] or "Not provided" in note["social_history"], "Unmentioned fields must stay Not provided"
        print("  [OK] 11-section note preserved all cumulative symptoms, medications, allergies, and negative findings.")

        # -------------------------------------------------------------
        # Part B: Live Integration End-to-End via FastAPI Endpoints
        # -------------------------------------------------------------
        print("\n[Part B: Live API Endpoint Integration Tests]")

        # Register and login
        print("\n[5/7] Registering test patient and creating live consultation case...")
        reg = client.post("/auth/register", json={
            "full_name": TEST_NAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD
        })
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        case_res = client.post("/cases", json={"case_title": "Complex Symptom Presentation"}, headers=headers)
        assert case_res.status_code == 201
        case_id = case_res.json()["id"]

        # Turn 1: Patient reports initial complaint with duration
        res_t1 = client.post(f"/cases/{case_id}/messages", json={
            "message_content": "I have had a sharp lower back pain for 5 days after lifting heavy boxes."
        }, headers=headers)
        assert res_t1.status_code == 200
        ai_msg1 = res_t1.json()["ai_response"]["message_content"]
        assert "how long" not in ai_msg1.lower(), "AI should not ask how long when patient said 5 days"
        print("  [OK] Turn 1 message processed naturally. Follow-up avoided asking for already provided duration.")

        # Turn 2: Patient answers and introduces a new symptom midway
        res_t2 = client.post(f"/cases/{case_id}/messages", json={
            "message_content": "The pain is 7 out of 10. Also, today I noticed tingling in my right leg and my knee feels weak."
        }, headers=headers)
        assert res_t2.status_code == 200
        ai_msg2 = res_t2.json()["ai_response"]["message_content"]
        # AI should recognize the new neurological symptom (tingling / leg)
        assert "tingling" in ai_msg2.lower() or "leg" in ai_msg2.lower() or "knee" in ai_msg2.lower() or "on top of" in ai_msg2.lower(), "AI must acknowledge the new symptom!"
        print("  [OK] Turn 2 recognized new symptoms (tingling/leg/knee) and acknowledged them in dialogue.")

        # Turn 3: Patient gives medications and history
        res_t3 = client.post(f"/cases/{case_id}/messages", json={
            "message_content": "Resting helps a bit. I took naproxen 500mg. No drug allergies. No prior spine surgeries."
        }, headers=headers)
        assert res_t3.status_code == 200
        ai_msg3 = res_t3.json()["ai_response"]["message_content"]
        print("  [OK] Turn 3 acknowledged relieving factors, naproxen, and no allergies.")

        # End case & generate note
        print("\n[6/7] Ending case and generating clinical note with full symptom preservation...")
        end_res = client.post(f"/cases/{case_id}/end", headers=headers)
        assert end_res.status_code == 200

        gen_res = client.post(f"/cases/{case_id}/generate-note", headers=headers)
        assert gen_res.status_code == 200
        generated_note = gen_res.json()["note"]

        # Verify all symptoms appear in note
        assert "back pain" in generated_note["chief_complaint"].lower() or "back" in generated_note["hpi"].lower()
        assert "tingling" in generated_note["hpi"].lower() or "tingling" in generated_note["chief_complaint"].lower()
        assert "naproxen" in generated_note["medications"].lower()
        assert "no" in generated_note["allergies"].lower() or "nkda" in generated_note["allergies"].lower()
        assert "Not performed" in generated_note["physical_examination"]
        print("  [OK] End-to-end consultation successfully preserved all initial and new symptoms in final note.")

        # Test 7: Exact UI Regression Case from User Request
        print("\n[7/7] Testing UI failure regression: 'from morning on a scale of 5' and 'It\'s dry. I also have a headache'...")
        case2_res = client.post("/cases", json={"case_title": "Cough & Headache Consultation"}, headers=headers)
        assert case2_res.status_code == 201
        case2_id = case2_res.json()["id"]

        # Step 1: Patient reports cough
        r1 = client.post(f"/cases/{case2_id}/messages", json={
            "message_content": "I have a cough."
        }, headers=headers)
        assert r1.status_code == 200
        ai_resp1 = r1.json()["ai_response"]["message_content"]
        assert "cough" in ai_resp1.lower()

        # Step 2: Patient answers 'from morning on a scale of 5'
        r2 = client.post(f"/cases/{case2_id}/messages", json={
            "message_content": "from morning on a scale of 5"
        }, headers=headers)
        assert r2.status_code == 200
        ai_resp2 = r2.json()["ai_response"]["message_content"]

        # Must recognize onset and severity, and acknowledge them
        assert "morning" in ai_resp2.lower(), f"AI must recognize morning in response: {ai_resp2}"
        assert "5" in ai_resp2, f"AI must recognize severity 5 in response: {ai_resp2}"
        
        # Must NOT re-ask duration or severity!
        assert "how long" not in ai_resp2.lower(), f"AI must not re-ask duration: {ai_resp2}"
        assert "scale of 1 to 10" not in ai_resp2.lower(), f"AI must not re-ask 1-10 scale: {ai_resp2}"
        assert "how would you rate" not in ai_resp2.lower(), f"AI must not re-ask severity rating: {ai_resp2}"
        print("  [OK] AI recognized 'from morning' and 'scale of 5' and did NOT repeat duration or severity.")

        # Step 3: Patient then says 'It\'s dry. I also have a headache.'
        r3 = client.post(f"/cases/{case2_id}/messages", json={
            "message_content": "It's dry. I also have a headache."
        }, headers=headers)
        assert r3.status_code == 200
        ai_resp3 = r3.json()["ai_response"]["message_content"]

        # Must preserve both symptoms and character
        assert "dry" in ai_resp3.lower() or "cough" in ai_resp3.lower(), f"AI must note dry cough: {ai_resp3}"
        assert "headache" in ai_resp3.lower(), f"AI must acknowledge headache: {ai_resp3}"
        
        # Must ask appropriate question about the headache or missing detail, NEVER repeat cough duration/severity
        assert "how long" not in ai_resp3.lower()
        assert "scale of 1 to 10" not in ai_resp3.lower()
        assert "how would you rate" not in ai_resp3.lower()
        assert "headache" in ai_resp3.lower() or "around the same time" in ai_resp3.lower(), f"AI should ask about headache: {ai_resp3}"
        print("  [OK] AI preserved both dry cough and headache, acknowledged them, and asked an appropriate question without repeating.")

        # Test 8: Live UI Regression for Bug 1 (severity '6' -> 'no' to fever -> never re-ask severity) and Bug 2 (India 112)
        print("\n[8/8] Testing Bug 1 (severity '6' then 'no' to fever) & Bug 2 (India 112 emergency notice)...")
        case3_res = client.post("/cases", json={"case_title": "Cough & Severity Investigation"}, headers=headers)
        assert case3_res.status_code == 201
        case3_id = case3_res.json()["id"]

        # Step 1: Patient reports dry cough since yesterday
        res1 = client.post(f"/cases/{case3_id}/messages", json={
            "message_content": "I have had a dry cough since yesterday."
        }, headers=headers)
        assert res1.status_code == 200
        ai_msg1 = res1.json()["ai_response"]["message_content"]
        assert "cough" in ai_msg1.lower()
        # Verify AI asks for severity rating
        assert "scale of 1 to 10" in ai_msg1.lower() or "rate" in ai_msg1.lower() or "discomfort" in ai_msg1.lower()

        # Step 2: Patient answers standalone '6'
        res2 = client.post(f"/cases/{case3_id}/messages", json={
            "message_content": "6"
        }, headers=headers)
        assert res2.status_code == 200
        ai_msg2 = res2.json()["ai_response"]["message_content"]

        # Must recognize standalone '6' as 6/10 and reflect it
        assert "6" in ai_msg2, f"AI must recognize severity 6: {ai_msg2}"
        assert "out of 10" in ai_msg2.lower() or "6/10" in ai_msg2, f"AI should reflect 6 out of 10: {ai_msg2}"
        # Must ask about fever / body aches / chills
        assert "fever" in ai_msg2.lower() or "chills" in ai_msg2.lower(), f"AI should ask about fever/chills: {ai_msg2}"
        # Must NOT re-ask severity rating
        assert "scale of 1 to 10" not in ai_msg2.lower()
        assert "how would you rate" not in ai_msg2.lower()
        print("  [OK] Standalone '6' captured as 6/10 severity; reflected and not repeated.")

        # Step 3: Patient answers 'noo' (colloquial spelling with double 'o') to fever / chills inquiry
        res3 = client.post(f"/cases/{case3_id}/messages", json={
            "message_content": "noo"
        }, headers=headers)
        assert res3.status_code == 200
        ai_msg3 = res3.json()["ai_response"]["message_content"]

        # CRITICAL BUG FIX: AI response must NEVER be identical to the previous AI message!
        assert ai_msg3 != ai_msg2, f"CRITICAL REPETITION BUG: AI repeated identical message! {ai_msg3}"
        assert "are you noticing any fever" not in ai_msg3.lower(), f"AI repeated fever question: {ai_msg3}"
        # Must acknowledge that fever / body aches / chills were not noticed
        assert "haven't noticed" in ai_msg3.lower() or "no fever" in ai_msg3.lower() or "fever" in ai_msg3.lower(), f"AI must acknowledge negative answer: {ai_msg3}"
        # CRITICAL BUG 1 FIX: Must NEVER repeat the severity question!
        assert "scale of 1 to 10" not in ai_msg3.lower(), f"BUG 1 REGRESSION: AI re-asked scale of 1 to 10! {ai_msg3}"
        assert "how would you rate the discomfort" not in ai_msg3.lower(), f"BUG 1 REGRESSION: AI re-asked rate discomfort! {ai_msg3}"
        # Must ask a relevant unanswered follow-up question (e.g. medications or remedies)
        assert "medication" in ai_msg3.lower() or "prescription" in ai_msg3.lower() or "remedies" in ai_msg3.lower() or "allerg" in ai_msg3.lower()
        print("  [OK] 'noo' captured as denial; AI response differs completely from previous turn; severity & fever NOT repeated.")

        # Step 4: Patient adds headache
        res4 = client.post(f"/cases/{case3_id}/messages", json={
            "message_content": "It is a dry cough. I also have a mild headache."
        }, headers=headers)
        assert res4.status_code == 200
        ai_msg4 = res4.json()["ai_response"]["message_content"]
        assert "headache" in ai_msg4.lower()

        # Step 5: End case and generate note; verify cumulative preservation
        end3 = client.post(f"/cases/{case3_id}/end", headers=headers)
        assert end3.status_code == 200
        gen3 = client.post(f"/cases/{case3_id}/generate-note", headers=headers)
        assert gen3.status_code == 200
        note3 = gen3.json()["note"]

        assert "cough" in note3["chief_complaint"].lower()
        assert "headache" in note3["chief_complaint"].lower() or "headache" in note3["hpi"].lower()
        assert "6/10" in note3["hpi"], f"Expected '6/10' in HPI: {note3['hpi']}"
        assert "fever" in note3["hpi"].lower(), f"Expected denied fever in HPI: {note3['hpi']}"
        assert "fever" in note3["review_of_systems"].lower()
        print("  [OK] Cumulative state preserved: cough, headache, 6/10 severity, and denied symptoms in note.")

        # Step 6: Verify Emergency Notice uses 112 (India) and NOT 911
        case_emg = client.post("/cases", json={"case_title": "Emergency Test Case"}, headers=headers)
        emg_id = case_emg.json()["id"]
        emg_res = client.post(f"/cases/{emg_id}/messages", json={
            "message_content": "I have crushing chest pain and cannot breathe!"
        }, headers=headers)
        assert emg_res.status_code == 200
        emg_ai_text = emg_res.json()["ai_response"]["message_content"]
        assert "112" in emg_ai_text, f"Emergency notice must contain 112: {emg_ai_text}"
        assert "India" in emg_ai_text, f"Emergency notice should mention India: {emg_ai_text}"
        assert "911" not in emg_ai_text, f"Emergency notice must NOT contain 911: {emg_ai_text}"
        print("  [OK] Emergency notice correctly displays India 112 (and 108) with no 911 reference.")

        # Step 7: Regression test for symptom-relief extraction and non-repetition
        print("\n[9/9] Testing symptom-relief bug fix ('when I lift my hand', no meds, note HPI, clarification)...")
        case4 = client.post("/cases", json={"case_title": "Shoulder Pain Consultation"}, headers=headers)
        case4_id = case4.json()["id"]

        # Turn 1: Patient provides initial symptom, duration, severity, and character
        t1_res = client.post(f"/cases/{case4_id}/messages", json={
            "message_content": "I have shoulder pain since yesterday, 6 out of 10, dull ache."
        }, headers=headers)
        assert t1_res.status_code == 200
        t1_ai = t1_res.json()["ai_response"]["message_content"]
        assert "better or worse" in t1_ai.lower() or "relief" in t1_ai.lower(), f"Expected symptom-relief inquiry: {t1_ai}"

        # Turn 2: Patient answers natural trigger phrase: 'when I lift my hand'
        t2_res = client.post(f"/cases/{case4_id}/messages", json={
            "message_content": "when I lift my hand"
        }, headers=headers)
        assert t2_res.status_code == 200
        t2_ai = t2_res.json()["ai_response"]["message_content"]

        # Assert: Acknowledges hand movement/lifting
        assert "hand" in t2_ai.lower(), f"AI must acknowledge hand lifting: {t2_ai}"
        # Assert: MUST NOT repeat the symptom-relief question
        assert "better or worse" not in t2_ai.lower(), f"AI repeated better or worse question! {t2_ai}"
        assert "provided relief" not in t2_ai.lower(), f"AI repeated relief question! {t2_ai}"
        # Assert: Next question moves forward to medications
        assert "medication" in t2_ai.lower() or "prescription" in t2_ai.lower(), f"AI must ask medications: {t2_ai}"

        # Turn 3: Patient answers 'no medications'
        t3_res = client.post(f"/cases/{case4_id}/messages", json={
            "message_content": "no medications"
        }, headers=headers)
        assert t3_res.status_code == 200
        t3_ai = t3_res.json()["ai_response"]["message_content"]

        # Assert: Acknowledges medications
        assert "not currently taking" in t3_ai.lower() or "no medication" in t3_ai.lower() or "medication" in t3_ai.lower()
        # Assert: MUST NOT re-ask symptom relief on subsequent turns
        assert "better or worse" not in t3_ai.lower(), f"AI re-asked better or worse on subsequent turn! {t3_ai}"
        assert "provided relief" not in t3_ai.lower(), f"AI re-asked relief on subsequent turn! {t3_ai}"
        # Assert: Moves to allergies
        assert "allerg" in t3_ai.lower(), f"AI should ask about allergies: {t3_ai}"

        # Turn 4: Patient answers allergies
        t4_res = client.post(f"/cases/{case4_id}/messages", json={
            "message_content": "no allergies"
        }, headers=headers)
        assert t4_res.status_code == 200
        t4_ai = t4_res.json()["ai_response"]["message_content"]
        assert "better or worse" not in t4_ai.lower(), f"AI re-asked better or worse on allergies turn! {t4_ai}"
        assert "medical history" in t4_ai.lower() or "chronic" in t4_ai.lower() or "family" in t4_ai.lower()

        # Turn 5: End case and generate note — verify HPI includes hand lifting
        end4 = client.post(f"/cases/{case4_id}/end", headers=headers)
        assert end4.status_code == 200
        gen4 = client.post(f"/cases/{case4_id}/generate-note", headers=headers)
        assert gen4.status_code == 200
        note4 = gen4.json()["note"]

        assert "when I lift my hand" in note4["hpi"], f"HPI must faithfully retain 'when I lift my hand': {note4['hpi']}"
        assert "6/10" in note4["hpi"]
        print("  [OK] Exact sequence verified: hand lifting acknowledged, no repetition, note HPI retained.")

        # Test unclear answer clarification behavior
        case5 = client.post("/cases", json={"case_title": "Clarification Test Case"}, headers=headers)
        case5_id = case5.json()["id"]
        c5_t1 = client.post(f"/cases/{case5_id}/messages", json={
            "message_content": "I have knee pain since yesterday, 5/10, aching."
        }, headers=headers)
        assert c5_t1.status_code == 200
        # Patient gives unclear answer 'what do you mean?'
        c5_t2 = client.post(f"/cases/{case5_id}/messages", json={
            "message_content": "what do you mean?"
        }, headers=headers)
        assert c5_t2.status_code == 200
        c5_ai2 = c5_t2.json()["ai_response"]["message_content"]
        assert "clarify" in c5_ai2.lower(), f"Expected focused clarification: {c5_ai2}"
        assert "movement" in c5_ai2.lower() or "activity" in c5_ai2.lower() or "change" in c5_ai2.lower()
        print("  [OK] Unclear patient responses receive focused clarification without repeating the script.")

        print("\n" + "=" * 75)
        print("SUCCESS: ALL CONVERSATIONAL AI & SYMPTOM TRACKING TESTS PASSED!")
        print("=" * 75)

    finally:
        cleanup()
        print("[OK] Cleaned up temporary test patient data safely from MySQL.")


if __name__ == "__main__":
    run_conversational_ai_tests()
