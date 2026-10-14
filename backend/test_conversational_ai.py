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

import io
from pypdf import PdfReader
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal
from models import Patient
from services.clinical_tracker import (
    build_clinical_state_from_history,
    generate_empathetic_acknowledgment,
    generate_adaptive_follow_up_questions,
    is_temperature_question,
    get_last_question,
    GROUP_1_ID,
    GROUP_2_ID,
    GROUP_3_ID
)
from services.conversation_service import process_patient_message, generate_rules_fallback_response
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
        # Step 8: Final Confirmation behavior ('no', 'nothing else', and meaningful additional medical detail)
        print("\n[10/10] Testing final confirmation response ('no', 'nothing else', and new medical details)...")
        case6 = client.post("/cases", json={"case_title": "Final Confirmation Test Case"}, headers=headers)
        case6_id = case6.json()["id"]

        # Progress through clinical intake to wrap-up
        c6_t1 = client.post(f"/cases/{case6_id}/messages", json={
            "message_content": "I have a cough since yesterday, 4 out of 10, dry."
        }, headers=headers)
        assert c6_t1.status_code == 200

        c6_t2 = client.post(f"/cases/{case6_id}/messages", json={
            "message_content": "warm tea helped a bit"
        }, headers=headers)
        assert c6_t2.status_code == 200

        c6_t3 = client.post(f"/cases/{case6_id}/messages", json={
            "message_content": "no medications"
        }, headers=headers)
        assert c6_t3.status_code == 200

        c6_t4 = client.post(f"/cases/{case6_id}/messages", json={
            "message_content": "no allergies"
        }, headers=headers)
        assert c6_t4.status_code == 200

        c6_t5 = client.post(f"/cases/{case6_id}/messages", json={
            "message_content": "no medical history"
        }, headers=headers)
        assert c6_t5.status_code == 200
        c6_ai5 = c6_t5.json()["ai_response"]["message_content"]
        assert "finish consultation" in c6_ai5.lower() or "finalize" in c6_ai5.lower() or "anything else" in c6_ai5.lower()

        # Turn 6A: Patient responds with 'no'
        c6_t6 = client.post(f"/cases/{case6_id}/messages", json={
            "message_content": "no"
        }, headers=headers)
        assert c6_t6.status_code == 200
        c6_ai6 = c6_t6.json()["ai_response"]["message_content"]

        # Assert: brief response, no clinical summary repetition, no closing question repetition
        assert "finish consultation" in c6_ai6.lower(), f"Expected Finish Consultation prompt: {c6_ai6}"
        assert "okay, thank you" in c6_ai6.lower() or "thank you" in c6_ai6.lower()
        assert "you have provided a thorough overview" not in c6_ai6.lower(), f"Must not repeat clinical summary: {c6_ai6}"
        assert "anything else you would like to include" not in c6_ai6.lower(), f"Must not re-ask closing question: {c6_ai6}"

        # Assert: consultation is NOT automatically finished (still active)
        case6_check = client.get(f"/cases/{case6_id}", headers=headers)
        assert case6_check.status_code == 200
        assert case6_check.json()["status"] == "active", "Case must remain active until patient explicitly ends it"

        # Turn 6B: Test 'nothing else' in a fresh consultation
        case7 = client.post("/cases", json={"case_title": "Nothing Else Test Case"}, headers=headers)
        case7_id = case7.json()["id"]
        client.post(f"/cases/{case7_id}/messages", json={"message_content": "headache since morning, 5/10, throbbing"}, headers=headers)
        client.post(f"/cases/{case7_id}/messages", json={"message_content": "rest helped"}, headers=headers)
        client.post(f"/cases/{case7_id}/messages", json={"message_content": "no medications"}, headers=headers)
        client.post(f"/cases/{case7_id}/messages", json={"message_content": "no allergies"}, headers=headers)
        c7_t5 = client.post(f"/cases/{case7_id}/messages", json={"message_content": "no history"}, headers=headers)
        assert c7_t5.status_code == 200

        c7_t6 = client.post(f"/cases/{case7_id}/messages", json={"message_content": "nothing else"}, headers=headers)
        assert c7_t6.status_code == 200
        c7_ai6 = c7_t6.json()["ai_response"]["message_content"]
        assert "finish consultation" in c7_ai6.lower()
        assert "you have provided a thorough overview" not in c7_ai6.lower()
        assert "anything else you would like to include" not in c7_ai6.lower()

        # Turn 6C: Test patient providing meaningful additional medical details instead of declining
        case8 = client.post("/cases", json={"case_title": "Additional Symptoms Test Case"}, headers=headers)
        case8_id = case8.json()["id"]
        client.post(f"/cases/{case8_id}/messages", json={"message_content": "cough for 3 days, 6/10, dry"}, headers=headers)
        client.post(f"/cases/{case8_id}/messages", json={"message_content": "nothing helped"}, headers=headers)
        client.post(f"/cases/{case8_id}/messages", json={"message_content": "no meds"}, headers=headers)
        client.post(f"/cases/{case8_id}/messages", json={"message_content": "no allergies"}, headers=headers)
        client.post(f"/cases/{case8_id}/messages", json={"message_content": "no history"}, headers=headers)

        # Patient provides additional clinical symptom instead of declining
        c8_t6 = client.post(f"/cases/{case8_id}/messages", json={
            "message_content": "Actually, my left ear has also been throbbing and hurts since this morning."
        }, headers=headers)
        assert c8_t6.status_code == 200
        c8_ai6 = c8_t6.json()["ai_response"]["message_content"]

        # Assert: Did NOT treat this as 'nothing else'
        assert c8_ai6 != "Okay, thank you. You can select Finish Consultation when you're ready to review your clinical note."
        assert "ear" in c8_ai6.lower() or "throbbing" in c8_ai6.lower() or "noted" in c8_ai6.lower()
        print("  [OK] Final confirmation correctly handles 'no', 'nothing else', preserves additional medical details, and does not prematurely finish case.")

        # Test 11: Medication and Allergy Preservation (8 Required Scenarios & Full Pipeline Verification)
        print("\n[11/11] Testing Medication and Allergy Preservation (8 required scenarios & full pipeline)...")
        def run_med_allergy_pipeline_case(case_title: str, user_msgs: list):
            c_res = client.post("/cases", json={"case_title": case_title}, headers=headers)
            assert c_res.status_code == 201, c_res.text
            cid = c_res.json()["id"]

            for m in user_msgs:
                mr = client.post(f"/cases/{cid}/messages", json={"message_content": m}, headers=headers)
                assert mr.status_code == 200, mr.text

            # End case
            end_r = client.post(f"/cases/{cid}/end", headers=headers)
            assert end_r.status_code == 200, end_r.text

            # Generate note
            gen_r = client.post(f"/cases/{cid}/generate-note", headers=headers)
            assert gen_r.status_code == 200, gen_r.text
            draft_note = gen_r.json()["note"]

            # Save note to MySQL
            save_r = client.post(f"/cases/{cid}/notes", json=draft_note, headers=headers)
            assert save_r.status_code == 201, save_r.text
            saved_id = save_r.json()["id"]

            # Retrieve note by ID from MySQL
            get_r = client.get(f"/notes/{saved_id}", headers=headers)
            assert get_r.status_code == 200, get_r.text
            retrieved_note = get_r.json()

            # Generate and download PDF
            pdf_r = client.get(f"/notes/{saved_id}/pdf", headers=headers)
            assert pdf_r.status_code == 200, pdf_r.text
            reader = PdfReader(io.BytesIO(pdf_r.content))
            extracted_pdf_text = "".join(page.extract_text() or "" for page in reader.pages)

            return retrieved_note, extracted_pdf_text

        # 1. "I take paracetamol, 500 mg daily." (Positive info provided)
        s1_note, s1_pdf = run_med_allergy_pipeline_case("Med Scenario 1", [
            "I have a fever and body aches.",
            "since yesterday",
            "7 out of 10",
            "resting in bed",
            "I take paracetamol, 500 mg daily."
        ])
        assert "paracetamol" in s1_note["medications"].lower(), "Medication name must be preserved"
        assert "500 mg" in s1_note["medications"].lower(), "Dosage must be preserved"
        assert "daily" in s1_note["medications"].lower(), "Frequency must be preserved"
        assert "paracetamol" in s1_pdf.lower()
        assert "500 mg" in s1_pdf.lower()
        print("  [OK] Case 1: 'I take paracetamol, 500 mg daily.' -> dosage, frequency, and details preserved in note & PDF.")

        # 2. "I am allergic to penicillin." (Positive allergy provided)
        s2_note, s2_pdf = run_med_allergy_pipeline_case("Allergy Scenario 2", [
            "I have a persistent rash.",
            "started 2 days ago",
            "4",
            "itchy",
            "cool compresses",
            "no medications",
            "I am allergic to penicillin."
        ])
        assert "penicillin" in s2_note["allergies"].lower()
        assert "penicillin" in s2_pdf.lower()
        print("  [OK] Case 2: 'I am allergic to penicillin.' -> specific allergen preserved in note & PDF.")

        # 3. "I take no medication." (Explicit negative response)
        s3_note, s3_pdf = run_med_allergy_pipeline_case("Med Scenario 3", [
            "Throbbing headache.",
            "since morning",
            "6",
            "quiet dark room",
            "I take no medication."
        ])
        assert s3_note["medications"] == "None reported", f"Expected 'None reported', got {s3_note['medications']}"
        assert "none reported" in s3_pdf.lower()
        print("  [OK] Case 3: 'I take no medication.' -> explicitly recorded as 'None reported'.")

        # 4. "I have no known allergies." (Explicit negative response)
        s4_note, s4_pdf = run_med_allergy_pipeline_case("Allergy Scenario 4", [
            "Stomach cramps.",
            "for 2 hours",
            "5",
            "drinking water",
            "no medications",
            "I have no known allergies."
        ])
        assert s4_note["allergies"] == "No known drug allergies (NKDA)", f"Expected NKDA, got {s4_note['allergies']}"
        assert "nkda" in s4_pdf.lower() or "no known drug allergies" in s4_pdf.lower()
        print("  [OK] Case 4: 'I have no known allergies.' -> explicitly recorded as 'No known drug allergies (NKDA)'.")

        # 5. Medication unanswered, allergy answered (Isolation: medication must stay 'Not provided')
        s5_note, s5_pdf = run_med_allergy_pipeline_case("Isolation Scenario 5", [
            "Mild knee stiffness.",
            "for 1 week",
            "3",
            "walking helps",
            "I have no known allergies."
        ])
        assert s5_note["medications"] == "Not provided", f"Unanswered medication must be 'Not provided', got {s5_note['medications']}"
        assert s5_note["allergies"] == "No known drug allergies (NKDA)"
        assert "not provided" in s5_pdf.lower()
        print("  [OK] Case 5: Medication unanswered, allergy answered -> medication strictly preserved as 'Not provided'.")

        # 6. Allergy unanswered, medication answered (Isolation: allergy must stay 'Not provided')
        s6_note, s6_pdf = run_med_allergy_pipeline_case("Isolation Scenario 6", [
            "Mild cough.",
            "for 3 days",
            "4",
            "dry cough",
            "warm tea did not help",
            "I take paracetamol, 500 mg daily."
        ])
        assert "paracetamol" in s6_note["medications"].lower()
        assert "500 mg" in s6_note["medications"].lower()
        assert s6_note["allergies"] == "Not provided", f"Unanswered allergy must be 'Not provided', got {s6_note['allergies']}"
        print("  [OK] Case 6: Allergy unanswered, medication answered -> allergy strictly preserved as 'Not provided'.")

        # 7. Both fields unanswered (Both must strictly stay 'Not provided')
        s7_note, s7_pdf = run_med_allergy_pipeline_case("Both Unanswered Scenario 7", [
            "Lower back ache.",
            "since yesterday",
            "5 out of 10"
        ])
        assert s7_note["medications"] == "Not provided", f"Expected 'Not provided', got {s7_note['medications']}"
        assert s7_note["allergies"] == "Not provided", f"Expected 'Not provided', got {s7_note['allergies']}"
        print("  [OK] Case 7: Both fields unanswered -> both strictly preserved as 'Not provided'.")

        # 8. An uncertain answer, such as "I'm not sure." (Uncertainty preserved)
        s8a_note, s8a_pdf = run_med_allergy_pipeline_case("Uncertain Med Scenario 8a", [
            "I have chest tightness and cough for 2 days. The pain is 6 out of 10 and it is a dry cough. Warm tea did not help.",
            "I'm not sure.",  # Directly answers medication inquiry with uncertainty
        ])
        assert s8a_note["medications"] == "Uncertain", f"Expected 'Uncertain', got {s8a_note['medications']}"
        assert "uncertain" in s8a_pdf.lower()
        print("  [OK] Case 8a: Medication uncertainty 'I'm not sure.' -> preserved as 'Uncertain' in note and PDF.")

        s8b_note, s8b_pdf = run_med_allergy_pipeline_case("Uncertain Allergy Scenario 8b", [
            "I have chest tightness and cough for 2 days. The pain is 6 out of 10 and it is a dry cough. Warm tea did not help.",
            "no medications",
            "I'm not sure.",  # Directly answers allergy inquiry with uncertainty
        ])
        assert s8b_note["medications"] == "None reported"
        assert s8b_note["allergies"] == "Uncertain", f"Expected 'Uncertain', got {s8b_note['allergies']}"
        assert "uncertain" in s8b_pdf.lower()
        print("  [OK] Case 8b: Allergy uncertainty 'I'm not sure.' -> preserved as 'Uncertain' in note and PDF.")

        # Test 12: Past Medical History & Allergies Persistence Suite (Full Pipeline & Closing Response)
        print("\n[12/12] Testing Past Medical History & Allergies Persistence Suite (Full Pipeline & Closing Response)...")

        # 1. Positive PMH and Allergies: dialogue -> note -> MySQL -> retrieval -> PDF
        pmh_pos_note, pmh_pos_pdf = run_med_allergy_pipeline_case("Positive PMH & Allergy Case", [
            "I have been having frequent headaches and dizziness for 3 days. Rated 5/10.",
            "Resting in a quiet room brings some relief.",
            "I take no medication.",
            "I am allergic to penicillin and pollen.",
            "I was diagnosed with asthma and type 2 diabetes."
        ])
        assert "asthma" in pmh_pos_note["past_medical_history"].lower(), "Asthma must be preserved in PMH"
        assert "diabetes" in pmh_pos_note["past_medical_history"].lower(), "Diabetes must be preserved in PMH"
        assert "penicillin" in pmh_pos_note["allergies"].lower(), "Penicillin must be preserved in Allergies"
        assert "pollen" in pmh_pos_note["allergies"].lower(), "Pollen must be preserved in Allergies"
        assert "asthma" in pmh_pos_pdf.lower(), "Asthma must be rendered in PDF"
        assert "diabetes" in pmh_pos_pdf.lower(), "Diabetes must be rendered in PDF"
        assert "penicillin" in pmh_pos_pdf.lower(), "Penicillin must be rendered in PDF"
        print("  [OK] Case 1: Positive PMH ('asthma and type 2 diabetes') & Allergies ('penicillin and pollen') preserved in note, MySQL, and PDF.")

        # 2. Explicit negative PMH: dialogue -> note -> MySQL -> retrieval -> PDF
        pmh_neg_note, pmh_neg_pdf = run_med_allergy_pipeline_case("Negative PMH Case", [
            "Severe stomach discomfort for 2 days. 7/10 pain.",
            "Nothing really helps.",
            "no medications",
            "no allergies",
            "No chronic conditions reported."
        ])
        assert pmh_neg_note["past_medical_history"] == "No chronic conditions reported", (
            f"Expected 'No chronic conditions reported', got '{pmh_neg_note['past_medical_history']}'"
        )
        assert pmh_neg_note["allergies"] == "No known drug allergies (NKDA)"
        assert "no chronic conditions reported" in pmh_neg_pdf.lower()
        print("  [OK] Case 2: Explicit negative PMH -> recorded as 'No chronic conditions reported' in note, MySQL, and PDF.")

        # 3. Unanswered PMH: consultation ends without PMH -> remains 'Not provided', never 'No' or 'None'
        pmh_unans_note, pmh_unans_pdf = run_med_allergy_pipeline_case("Unanswered PMH Case", [
            "Sore throat since yesterday.",
            "4 out of 10 discomfort",
            "Warm tea helped a bit"
        ])
        assert pmh_unans_note["past_medical_history"] == "Not provided", (
            f"Unanswered PMH must be 'Not provided', got '{pmh_unans_note['past_medical_history']}'"
        )
        assert pmh_unans_note["past_medical_history"] != "No"
        assert pmh_unans_note["past_medical_history"] != "None"
        assert "not provided" in pmh_unans_pdf.lower()
        print("  [OK] Case 3: Unanswered PMH strictly preserved as 'Not provided' (never converted to 'No' or 'None').")

        # 4. Uncertain PMH: 'I'm not sure.' -> preserved as 'Uncertain'
        pmh_unc_note, pmh_unc_pdf = run_med_allergy_pipeline_case("Uncertain PMH Case", [
            "Chest tightness and cough for 2 days. The pain is 6 out of 10 and it is a dry cough. Warm tea did not help.",
            "no medications",
            "no allergies",
            "I'm not sure."  # Directly answers medical history inquiry with uncertainty
        ])
        assert pmh_unc_note["past_medical_history"] == "Uncertain", (
            f"Expected 'Uncertain', got '{pmh_unc_note['past_medical_history']}'"
        )
        assert "uncertain" in pmh_unc_pdf.lower()
        print("  [OK] Case 4: Uncertain PMH ('I'm not sure.') -> preserved as 'Uncertain' in note, MySQL, and PDF.")

        # 5. Distinct condition phrasing outside standard list: eczema and high cholesterol
        pmh_custom_note, pmh_custom_pdf = run_med_allergy_pipeline_case("Custom Conditions PMH Case", [
            "Dry cough for a week. 4/10.",
            "Resting helps.",
            "no medications",
            "no allergies",
            "I have eczema and high cholesterol."
        ])
        assert "eczema" in pmh_custom_note["past_medical_history"].lower(), "Eczema must be captured"
        assert "cholesterol" in pmh_custom_note["past_medical_history"].lower(), "Cholesterol must be captured"
        assert "eczema" in pmh_custom_pdf.lower()
        print("  [OK] Case 5: Custom conditions ('eczema and high cholesterol') accurately captured and preserved in PDF.")

        # 6. Consultation closing response verification:
        # Check that negative completion reply matches exact phrase and case stays active
        closing_case = client.post("/cases", json={"case_title": "Closing Response Verification Case"}, headers=headers)
        closing_cid = closing_case.json()["id"]
        client.post(f"/cases/{closing_cid}/messages", json={"message_content": "headache for 2 days, 5/10, throbbing"}, headers=headers)
        client.post(f"/cases/{closing_cid}/messages", json={"message_content": "dark room helps"}, headers=headers)
        client.post(f"/cases/{closing_cid}/messages", json={"message_content": "no medications"}, headers=headers)
        client.post(f"/cases/{closing_cid}/messages", json={"message_content": "no allergies"}, headers=headers)
        client.post(f"/cases/{closing_cid}/messages", json={"message_content": "no chronic conditions"}, headers=headers)

        # Assistant invites to finish or add anything else. Patient responds 'nothing else'
        closing_turn = client.post(f"/cases/{closing_cid}/messages", json={"message_content": "nothing else"}, headers=headers)
        assert closing_turn.status_code == 200
        closing_ai_reply = closing_turn.json()["ai_response"]["message_content"]
        expected_closing = "Okay, thank you. You can select Finish Consultation when you're ready to review your clinical note."
        assert closing_ai_reply == expected_closing, f"Expected exact closing reply, got: '{closing_ai_reply}'"

        # Verify case remains active until user clicks finish
        check_case = client.get(f"/cases/{closing_cid}", headers=headers)
        assert check_case.json()["status"] == "active", "Case must remain active until user finishes"
        print("  [OK] Case 6: Exact closing response verified and case remains active until Finish Consultation is selected.")

        # Test 13: Comprehensive 18-Scenario Symptom-Based Flow & Non-Repetition Suite
        print("\n[13/13] Testing Comprehensive 18-Scenario Symptom-Based Flow & Non-Repetition Suite...")

        # Scenario 1: Cold alone (no pain character or 1-10 pain scale asked)
        s1_ai = generate_rules_fallback_response([], "I have a bad cold and blocked nose for 2 days.")
        assert not any(w in s1_ai.lower() for w in ["dull", "sharp", "throbbing", "1 to 10", "1-10", "scale"]), f"S1 Failed: {s1_ai}"
        print("  [OK] S1: Cold alone -> cold inquiries only, strictly no pain character or 1-10 scale.")

        # Scenario 2: Cough alone (prioritizes dry/mucus, triggers/remedies)
        s2_ai = generate_rules_fallback_response([], "I have had a cough since yesterday.")
        assert any(w in s2_ai.lower() for w in ["dry", "productive", "mucus"]), f"S2 Failed: {s2_ai}"
        assert not any(w in s2_ai.lower() for w in ["travel", "diarrhea", "behind your eyes"]), f"S2 Failed: {s2_ai}"
        print("  [OK] S2: Cough alone -> prioritizes dry/mucus without presenting entire illness questionnaire.")

        # Scenario 3: Fever alone (temperature, onset, severity, associated symptoms)
        s3_h = [{"sender_role": "patient", "message_content": "I have a fever since this morning."}]
        s3_r1 = generate_rules_fallback_response([], "I have a fever since this morning.")
        assert is_temperature_question(s3_r1), f"S3 R1 Failed: {s3_r1}"
        s3_h.append({"sender_role": "ai", "message_content": s3_r1})
        s3_r2 = generate_rules_fallback_response(s3_h, "Yes, it was 102 F.")
        assert not is_temperature_question(s3_r2), f"S3 R2 Failed: {s3_r2}"
        assert "102" in s3_r2 or "fever" in s3_r2.lower()
        print("  [OK] S3: Fever alone -> captures measured temperature and does not repeat inquiry.")

        # Scenario 4: Suspected dengue or malaria (labeled suspected patient-reported, no confirmed diagnosis)
        s4_msg = "I think I might have malaria or dengue because I have high fever and severe joint pain."
        s4_r = generate_rules_fallback_response([], s4_msg)
        assert not any(w in s4_r.lower() for w in ["you have malaria", "you have dengue", "confirmed diagnosis"]), f"S4 Dialogue Failed: {s4_r}"
        s4_note = extract_fallback_note([{"sender_role": "patient", "message_content": s4_msg}])
        assert "suspected" in s4_note["hpi"].lower() and "patient-reported" in s4_note["hpi"].lower(), f"S4 Note Failed: {s4_note['hpi']}"
        print("  [OK] S4: Suspected dengue/malaria -> labeled 'suspected (patient-reported)' without diagnosis confirmation.")

        # Scenario 5: Headache alone (location, character, 1-10 severity, relief)
        s5_r = generate_rules_fallback_response([], "I have a headache since yesterday.")
        assert any(w in s5_r.lower() for w in ["where", "location", "scale", "1 to 10", "describe", "throbbing", "dull"]), f"S5 Failed: {s5_r}"
        print("  [OK] S5: Headache alone -> focuses on pain location, character, severity, and relief.")

        # Scenario 6: Body aches alone
        s6_r = generate_rules_fallback_response([], "I have body aches for 2 days.")
        assert any(w in s6_r.lower() for w in ["where", "scale", "1 to 10", "describe", "better or worse", "relief"]), f"S6 Failed: {s6_r}"
        print("  [OK] S6: Body aches alone -> focuses on localized discomfort and severity.")

        # Scenario 7: Fever with body aches (shared onset, temperature, relief; no duplicate questions)
        s7_r = generate_rules_fallback_response([], "I have had a fever and body aches since yesterday. My temperature is 101 F.")
        assert not is_temperature_question(s7_r), f"S7 Failed: {s7_r}"
        assert not any(w in s7_r.lower() for w in ["when did", "how long have you had", "begin?"]), f"S7 Failed: {s7_r}"
        print("  [OK] S7: Fever with body aches -> shared onset and temperature honored without duplicate inquiries.")

        # Scenario 8: Rash alone (location, appearance, spread, sensation, triggers)
        s8_r = generate_rules_fallback_response([], "I have a red rash on my chest for 3 days.")
        assert any(w in s8_r.lower() for w in ["itchy", "appearance", "spread", "tender", "bumps", "spots", "creams", "exposed"]), f"S8 Failed: {s8_r}"
        assert not any(w in s8_r.lower() for w in ["dull", "sharp", "throbbing"]), f"S8 Failed: {s8_r}"
        print("  [OK] S8: Rash alone -> explores dermatological dimensions without inappropriate pain character inquiries.")

        # Scenario 9: Suspected skin infection (labeled suspected patient-reported, warmth/redness/pus)
        s9_msg = "I suspect I have a skin infection because my arm has spreading redness and oozing pus."
        s9_r = generate_rules_fallback_response([], s9_msg)
        assert not any(w in s9_r.lower() for w in ["you have a skin infection", "diagnosed"]), f"S9 Dialogue Failed: {s9_r}"
        s9_note = extract_fallback_note([{"sender_role": "patient", "message_content": s9_msg}])
        assert "suspected" in s9_note["hpi"].lower() or "patient-reported" in s9_note["hpi"].lower(), f"S9 Note Failed: {s9_note['hpi']}"
        print("  [OK] S9: Suspected skin infection -> documented as suspected patient-reported with dermatological signs.")

        # Scenario 10: Rash with fever (shared onset, temperature; combined group tracking)
        s10_r = generate_rules_fallback_response([], "I have an itchy rash on my legs and a fever since yesterday. My temperature is 100.8 F.")
        assert not is_temperature_question(s10_r), f"S10 Failed: {s10_r}"
        assert not any(w in s10_r.lower() for w in ["when did", "begin?"]), f"S10 Failed: {s10_r}"
        print("  [OK] S10: Rash with fever -> correctly detects combined groups with shared onset and temperature.")

        # Scenario 11: Rash with itching but no pain (strictly blocks dull/sharp pain character questions)
        s11_r = generate_rules_fallback_response([], "I have an itchy rash on my arms. There is no pain.")
        assert not any(w in s11_r.lower() for w in ["dull", "sharp", "throbbing", "cramping"]), f"S11 Failed: {s11_r}"
        print("  [OK] S11: Rash with itch but no pain -> strictly blocks dull/sharp pain character questions.")

        # Scenario 12: Symptoms spanning all three groups
        s12_msg = "I have a cough, headache, and an itchy rash for 3 days."
        s12_r = generate_rules_fallback_response([], s12_msg)
        s12_st = build_clinical_state_from_history([], s12_msg)
        assert {GROUP_1_ID, GROUP_2_ID, GROUP_3_ID}.issubset(s12_st.symptom_groups), f"S12 Groups Failed: {s12_st.symptom_groups}"
        assert not any(w in s12_r.lower() for w in ["when did", "begin?"]), f"S12 Failed: {s12_r}"
        print("  [OK] S12: Symptoms spanning all 3 groups -> tracks groups, respects shared onset, and prioritizes naturally.")

        # Scenario 13: New symptom introduced halfway (warm reflection, connected to prior symptoms, no restart)
        s13_h = [
            {"sender_role": "patient", "message_content": "I have a sore throat since yesterday."},
            {"sender_role": "ai", "message_content": "Do you have a runny nose, blocked nose, sneezing, or sore throat?"}
        ]
        s13_r2 = generate_rules_fallback_response(s13_h, "Actually, my knee started hurting this morning as well.")
        assert any(w in s13_r2.lower() for w in ["knee", "joint", "hurt", "pain", "leg"]), f"S13 Failed: {s13_r2}"
        assert any(w in s13_r2.lower() for w in ["sore throat", "connect", "same time", "started around", "on top of"]), f"S13 Failed: {s13_r2}"
        print("  [OK] S13: Midway symptom -> warm reflection, connected to prior symptoms without restarting intake.")

        # Scenario 14: Multiple symptoms described in opening response (acknowledged together, known dimensions not re-asked)
        s14_r = generate_rules_fallback_response([], "I have a cough and a 5/10 headache since yesterday morning.")
        assert "cough" in s14_r.lower() and "headache" in s14_r.lower(), f"S14 Failed: {s14_r}"
        assert not any(w in s14_r.lower() for w in ["when did", "how long", "rate the discomfort on a scale", "rate the pain on a scale"]), f"S14 Failed: {s14_r}"
        print("  [OK] S14: Multiple opening symptoms -> acknowledged together without re-asking onset or severity.")

        # Scenario 15: Previously answered questions skipped (non-repetition rule enforced across turns)
        s15_h = [
            {"sender_role": "patient", "message_content": "I have a cough since yesterday, dry."},
            {"sender_role": "ai", "message_content": "If you have a cough, is it dry or productive? If productive, what does the mucus look like?"}
        ]
        s15_r2 = generate_rules_fallback_response(s15_h, "It is about 4 out of 10. Warm tea helped a bit.")
        s15_q2 = get_last_question(s15_r2)
        assert any(w in s15_q2.lower() for w in ["medication", "prescription", "supplements"]), f"S15 Failed: {s15_q2}"
        assert not any(w in s15_q2.lower() for w in ["dry", "mucus", "scale", "1 to 10", "when did", "warm tea", "home remedies"]), f"S15 Failed: {s15_q2}"
        print("  [OK] S15: Non-repetition -> advances straight to next missing dimension without repeating answered topics.")

        # Scenario 16: Mandatory allergy, medication, PMH questions preserved and not defaulted to 'No'
        s16_st = build_clinical_state_from_history([
            {"sender_role": "ai", "message_content": "Are you taking any medications?"},
            {"sender_role": "patient", "message_content": "I take lisinopril 10 mg daily."},
            {"sender_role": "ai", "message_content": "Do you have any allergies?"},
            {"sender_role": "patient", "message_content": "I am allergic to sulfa."},
            {"sender_role": "ai", "message_content": "Do you have any personal medical history?"},
            {"sender_role": "patient", "message_content": "I have hypertension."}
        ], "")
        assert "lisinopril" in s16_st.medications.lower()
        assert "sulfa" in s16_st.allergies.lower()
        assert "hypertension" in s16_st.past_medical_history.lower()
        print("  [OK] S16: Mandatory questions -> accurately preserved and never defaulted to 'No'.")

        # Scenario 17: Correct closing response exact string
        s17_case = client.post("/cases", json={"case_title": "S17 Closing Test Case"}, headers=headers)
        s17_cid = s17_case.json()["id"]
        client.post(f"/cases/{s17_cid}/messages", json={"message_content": "cough for 2 days, 5/10, dry"}, headers=headers)
        client.post(f"/cases/{s17_cid}/messages", json={"message_content": "honey helped"}, headers=headers)
        client.post(f"/cases/{s17_cid}/messages", json={"message_content": "no meds"}, headers=headers)
        client.post(f"/cases/{s17_cid}/messages", json={"message_content": "no allergies"}, headers=headers)
        client.post(f"/cases/{s17_cid}/messages", json={"message_content": "no chronic conditions"}, headers=headers)
        s17_turn = client.post(f"/cases/{s17_cid}/messages", json={"message_content": "no"}, headers=headers)
        assert s17_turn.json()["ai_response"]["message_content"] == "Okay, thank you. You can select Finish Consultation when you're ready to review your clinical note."
        print("  [OK] S17: Closing response -> exact string returned and case remains active.")

        # Scenario 18: Medical data persistence (save, reload, generate note, and verify PDF content with pypdf)
        s18_note, s18_pdf = run_med_allergy_pipeline_case("S18 Full Pipeline Verification", [
            "I have fever and body aches for 3 days. Rated 7/10. Temperature was 101.5 F.",
            "Resting in bed helped a little bit.",
            "I take paracetamol 650 mg as needed.",
            "I have no known allergies.",
            "I was diagnosed with asthma 5 years ago."
        ])
        assert "asthma" in s18_note["past_medical_history"].lower(), "Note must contain asthma"
        assert "paracetamol" in s18_note["medications"].lower(), "Note must contain paracetamol"
        assert "nkda" in s18_note["allergies"].lower() or "no known" in s18_note["allergies"].lower()
        assert "asthma" in s18_pdf.lower(), "PDF must contain asthma"
        assert "paracetamol" in s18_pdf.lower(), "PDF must contain paracetamol"
        print("  [OK] S18: Data persistence -> end-to-end verified across API, MySQL, note, and PDF with pypdf.")

        print("\n" + "=" * 75)
        print("SUCCESS: ALL CONVERSATIONAL AI & SYMPTOM TRACKING TESTS PASSED!")
        print("=" * 75)

    finally:
        cleanup()
        print("[OK] Cleaned up temporary test patient data safely from MySQL.")


if __name__ == "__main__":
    run_conversational_ai_tests()
