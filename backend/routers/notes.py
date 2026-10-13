"""
routers/notes.py — Endpoints for retrieving, viewing, and updating saved patient notes.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Patient, PatientNote
from dependencies import get_current_patient
from schemas import PatientNoteResponse, SaveNoteRequest

router = APIRouter(prefix="/notes", tags=["Patient Notes"])


@router.get(
    "",
    response_model=List[PatientNoteResponse],
    summary="List all saved clinical notes for the authenticated patient"
)
def list_patient_notes(
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Retrieves all clinical notes belonging to the authenticated patient,
    sorted newest first.
    """
    notes = (
        db.query(PatientNote)
        .filter(PatientNote.patient_id == current_patient.id)
        .order_by(PatientNote.created_at.desc())
        .all()
    )
    return notes


@router.get(
    "/{note_id}",
    response_model=PatientNoteResponse,
    summary="Get a specific saved patient note by ID"
)
def get_patient_note(
    note_id: int,
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Retrieves a saved patient note by ID.
    Enforces strict access control: patients can only access their own notes.
    """
    note = db.query(PatientNote).filter(PatientNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient clinical note not found"
        )

    if note.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot access another patient's medical records"
        )

    return note


@router.put(
    "/{note_id}",
    response_model=PatientNoteResponse,
    summary="Update an existing saved patient note"
)
def update_patient_note(
    note_id: int,
    payload: SaveNoteRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: Session = Depends(get_db)
):
    """
    Updates the content of an existing saved clinical note.
    Verifies patient ownership.
    """
    note = db.query(PatientNote).filter(PatientNote.id == note_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient clinical note not found"
        )

    if note.patient_id != current_patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you cannot modify another patient's medical records"
        )

    note.chief_complaint = payload.chief_complaint
    note.hpi = payload.hpi
    note.past_medical_history = payload.past_medical_history
    note.medications = payload.medications
    note.allergies = payload.allergies
    note.family_history = payload.family_history
    note.social_history = payload.social_history
    note.review_of_systems = payload.review_of_systems
    note.physical_examination = payload.physical_examination
    note.assessment_and_plan = payload.assessment_and_plan
    note.follow_up = payload.follow_up

    db.commit()
    db.refresh(note)
    return note
