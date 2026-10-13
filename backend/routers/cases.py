"""
routers/cases.py — Endpoints for managing patient cases, conversational intake, and note generation.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Patient, PatientCase, ConversationMessage, PatientNote
from dependencies import get_current_patient
from schemas import (
    CaseCreateRequest,
    CaseDetailResponse,
    CaseSummaryResponse,
    MessageSendRequest,
    SendMessageResponse,
    ConversationMessageResponse,
    GeneratedNoteResponse,
    NoteSections,
    SaveNoteRequest,
    PatientNoteResponse,
)
from services.conversation_service import INITIAL_GREETING, process_patient_message
from services.note_service import generate_note_from_dialogue

router = APIRouter(prefix="/cases", tags=["Patient Cases"])


@router.post(
    "",
    response_model=CaseDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new patient consultation case"
)
def create_case(
    payload: CaseCreateRequest = CaseCreateRequest(),
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Creates a new consultation case for the authenticated patient and
    seeds the initial AI greeting message.
    """
    new_case = PatientCase(
        patient_id=current_patient.id,
        case_title=payload.case_title or "Health Concern Consultation",
        status="active"
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    # Seed initial AI greeting
    initial_msg = ConversationMessage(
        case_id=new_case.id,
        sender_role="ai",
        message_content=INITIAL_GREETING
    )
    db.add(initial_msg)
    db.commit()
    db.refresh(new_case)

    return new_case


@router.get(
    "",
    response_model=List[CaseSummaryResponse],
    summary="List all cases for the authenticated patient"
)
def list_patient_cases(
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Retrieves all cases belonging to the currently logged-in patient.
    Cross-patient data access is strictly prevented.
    """
    cases = (
        db.query(PatientCase)
        .filter(PatientCase.patient_id == current_patient.id)
        .order_by(PatientCase.created_at.desc())
        .all()
    )

    summaries = []
    for c in cases:
        summaries.append(
            CaseSummaryResponse(
                id=c.id,
                patient_id=c.patient_id,
                case_title=c.case_title,
                status=c.status,
                message_count=len(c.messages),
                created_at=c.created_at,
                updated_at=c.updated_at
            )
        )
    return summaries


@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
    summary="Get case details and conversation history"
)
def get_case_details(
    case_id: int,
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Retrieves a single case and its full conversation history.
    Verifies that the requested case belongs to the authenticated patient.
    """
    case = db.query(PatientCase).filter(PatientCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation case not found"
        )

    if case.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot access another patient's medical records"
        )

    return case


@router.post(
    "/{case_id}/messages",
    response_model=SendMessageResponse,
    summary="Submit a patient message and receive the AI response"
)
async def send_message_to_case(
    case_id: int,
    payload: MessageSendRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Sends a patient message to the active case:
    1. Validates ownership and active status.
    2. Persists patient message to MySQL.
    3. Executes conversational AI service.
    4. Persists AI response to MySQL.
    """
    case = db.query(PatientCase).filter(PatientCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation case not found"
        )

    if case.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot submit messages to another patient's case"
        )

    if case.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This consultation has already ended. Please start a new case to document new concerns."
        )

    # 1. Store patient message
    patient_message = ConversationMessage(
        case_id=case.id,
        sender_role="patient",
        message_content=payload.message_content.strip()
    )
    db.add(patient_message)
    db.commit()
    db.refresh(patient_message)

    # 2. Build history for context
    all_msgs = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.case_id == case.id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    history = [
        {"sender_role": m.sender_role, "message_content": m.message_content}
        for m in all_msgs
        if m.id != patient_message.id
    ]

    # 3. Call Conversational AI service
    ai_text, is_live_ai, ai_provider, system_notice = await process_patient_message(
        history=history,
        patient_message=patient_message.message_content
    )

    # 4. Store AI response
    ai_message = ConversationMessage(
        case_id=case.id,
        sender_role="ai",
        message_content=ai_text
    )
    db.add(ai_message)
    db.commit()
    db.refresh(ai_message)

    return SendMessageResponse(
        patient_message=ConversationMessageResponse.model_validate(patient_message),
        ai_response=ConversationMessageResponse.model_validate(ai_message),
        case_status=case.status,
        is_live_ai=is_live_ai,
        ai_provider=ai_provider,
        system_notice=system_notice
    )


@router.post(
    "/{case_id}/end",
    response_model=CaseDetailResponse,
    summary="End an active consultation"
)
def end_case_conversation(
    case_id: int,
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Marks an active consultation as 'completed', concluding the intake session.
    """
    case = db.query(PatientCase).filter(PatientCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation case not found"
        )

    if case.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot modify another patient's case"
        )

    if case.status == "active":
        case.status = "completed"
        closing_msg = ConversationMessage(
            case_id=case.id,
            sender_role="system",
            message_content=(
                "Consultation ended by patient. All dialogue has been saved. "
                "You are ready to proceed to structured note generation."
            )
        )
        db.add(closing_msg)
        db.commit()
        db.refresh(case)

    return case


@router.post(
    "/{case_id}/generate-note",
    response_model=GeneratedNoteResponse,
    summary="Generate a structured 11-section patient note from conversation"
)
async def generate_patient_note(
    case_id: int,
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Generates a structured 11-section clinical note from the consultation dialogue.
    The note is returned for patient review and editing, NOT yet saved to MySQL.
    """
    case = db.query(PatientCase).filter(PatientCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation case not found"
        )

    if case.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot access another patient's medical records"
        )

    # Retrieve all messages for this case
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.case_id == case.id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    history = [
        {"sender_role": m.sender_role, "message_content": m.message_content}
        for m in messages
    ]

    note_dict, is_live_ai, ai_provider, system_notice = await generate_note_from_dialogue(
        case_title=case.case_title,
        history=history
    )

    return GeneratedNoteResponse(
        case_id=case.id,
        case_title=case.case_title,
        note=NoteSections(**note_dict),
        is_live_ai=is_live_ai,
        ai_provider=ai_provider,
        system_notice=system_notice
    )


@router.post(
    "/{case_id}/notes",
    response_model=PatientNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save the patient-confirmed and edited note to MySQL"
)
def save_patient_note(
    case_id: int,
    payload: SaveNoteRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Persists the patient-reviewed and confirmed note to MySQL in the patient_notes table.
    Enforces strict ownership and avoids duplicate records on retry.
    """
    case = db.query(PatientCase).filter(PatientCase.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation case not found"
        )

    if case.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot create notes for another patient's case"
        )

    # Idempotent check: if a note for this case already exists, update it cleanly
    existing_note = db.query(PatientNote).filter(PatientNote.case_id == case.id).first()
    if existing_note:
        existing_note.chief_complaint = payload.chief_complaint.strip()
        existing_note.hpi = payload.hpi.strip()
        existing_note.past_medical_history = payload.past_medical_history.strip()
        existing_note.medications = payload.medications.strip()
        existing_note.allergies = payload.allergies.strip()
        existing_note.family_history = payload.family_history.strip()
        existing_note.social_history = payload.social_history.strip()
        existing_note.review_of_systems = payload.review_of_systems.strip()
        existing_note.physical_examination = payload.physical_examination.strip()
        existing_note.assessment_and_plan = payload.assessment_and_plan.strip()
        existing_note.follow_up = payload.follow_up.strip()

        db.commit()
        db.refresh(existing_note)
        return existing_note

    # Otherwise, create a new note record
    new_note = PatientNote(
        case_id=case.id,
        patient_id=current_patient.id,
        chief_complaint=payload.chief_complaint.strip(),
        hpi=payload.hpi.strip(),
        past_medical_history=payload.past_medical_history.strip(),
        medications=payload.medications.strip(),
        allergies=payload.allergies.strip(),
        family_history=payload.family_history.strip(),
        social_history=payload.social_history.strip(),
        review_of_systems=payload.review_of_systems.strip(),
        physical_examination=payload.physical_examination.strip(),
        assessment_and_plan=payload.assessment_and_plan.strip(),
        follow_up=payload.follow_up.strip()
    )

    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return new_note
