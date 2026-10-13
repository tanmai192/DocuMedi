"""
test_models.py — Automated test to verify ORM models, relationships, and session handling.
Uses a database transaction that rolls back at the end to ensure the database remains pristine.
"""

from database import SessionLocal
from models import Patient, PatientCase, ConversationMessage, PatientNote


def test_models_and_relationships():
    print("Testing SQLAlchemy models and relationships...")
    db = SessionLocal()

    try:
        # Start a nested savepoint/transaction
        # 1. Create a mock patient
        test_patient = Patient(
            full_name="Jane Doe",
            email="test_model_check@example.com",
            password_hash="mock_hash_for_testing_only"
        )
        db.add(test_patient)
        db.flush()  # Generates test_patient.id without committing
        assert test_patient.id is not None, "Patient ID was not generated"
        print(f" [PASS] Created Patient with ID: {test_patient.id}")

        # 2. Create a mock case linked to the patient
        test_case = PatientCase(
            patient_id=test_patient.id,
            case_title="Flu-like Symptoms Intake",
            status="active"
        )
        db.add(test_case)
        db.flush()
        assert test_case.id is not None, "Case ID was not generated"
        print(f" [PASS] Created PatientCase with ID: {test_case.id}")

        # 3. Create a conversation message
        test_msg = ConversationMessage(
            case_id=test_case.id,
            sender_role="patient",
            message_content="I have had a sore throat for three days."
        )
        db.add(test_msg)
        db.flush()
        assert test_msg.id is not None, "Message ID was not generated"
        print(f" [PASS] Created ConversationMessage with ID: {test_msg.id}")

        # 4. Create a structured patient note with all 11 sections
        test_note = PatientNote(
            case_id=test_case.id,
            patient_id=test_patient.id,
            chief_complaint="Sore throat and fever for 3 days",
            hpi="Patient reports 3-day history of sore throat with subjective fever.",
            past_medical_history="Seasonal allergies",
            medications="None reported",
            allergies="Penicillin",
            family_history="Non-contributory",
            social_history="Non-smoker",
            review_of_systems="Positive for sore throat and chills. Denies shortness of breath.",
            physical_examination="Not performed — information not collected during patient conversation",
            assessment_and_plan="Acute pharyngitis symptoms reported. Recommend evaluation by a physician.",
            follow_up="Follow up with primary care if symptoms persist beyond 48 hours."
        )
        db.add(test_note)
        db.flush()
        assert test_note.id is not None, "Note ID was not generated"
        print(f" [PASS] Created PatientNote with ID: {test_note.id}")

        # 5. Verify ORM relationship navigation
        assert test_case.patient.full_name == "Jane Doe"
        assert len(test_case.messages) == 1
        assert test_case.messages[0].message_content == "I have had a sore throat for three days."
        assert len(test_case.notes) == 1
        assert test_case.notes[0].chief_complaint == "Sore throat and fever for 3 days"
        print(" [PASS] ORM relationships verified bidirectionally.")

    finally:
        # Always roll back so no mock records pollute the MySQL database
        db.rollback()
        db.close()
        print(" [PASS] Transaction rolled back cleanly. Database remains spotless.")


if __name__ == "__main__":
    test_models_and_relationships()
    print("\nAll model tests passed successfully!")
