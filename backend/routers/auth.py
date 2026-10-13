"""
routers/auth.py — Authentication endpoints for DocuMedi.
Handles patient registration, login, and profile retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Patient
from schemas import PatientRegisterRequest, PatientLoginRequest, TokenResponse, PatientResponse
from security import hash_password, verify_password, create_access_token
from dependencies import get_current_patient

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient account"
)
def register_patient(payload: PatientRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new patient:
    - Verifies email uniqueness.
    - Securely hashes the password with bcrypt.
    - Saves the patient to MySQL.
    - Issues a JWT authentication token.
    """
    normalized_email = payload.email.lower().strip()

    # Check for duplicate email
    existing_patient = db.query(Patient).filter(Patient.email == normalized_email).first()
    if existing_patient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists"
        )

    # Hash the password — plain text is never stored
    hashed_pwd = hash_password(payload.password)

    new_patient = Patient(
        full_name=payload.full_name.strip(),
        email=normalized_email,
        password_hash=hashed_pwd
    )

    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)

    # Issue initial JWT token for seamless sign-in
    token = create_access_token(subject=new_patient.id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        patient=PatientResponse.model_validate(new_patient)
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate patient and return JWT token"
)
def login_patient(payload: PatientLoginRequest, db: Session = Depends(get_db)):
    """
    Log in an existing patient:
    - Validates email and password against stored bcrypt hash.
    - Issues a fresh JWT authentication token.
    """
    normalized_email = payload.email.lower().strip()

    patient = db.query(Patient).filter(Patient.email == normalized_email).first()
    if not patient or not verify_password(payload.password, patient.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(subject=patient.id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        patient=PatientResponse.model_validate(patient)
    )


@router.get(
    "/me",
    response_model=PatientResponse,
    summary="Get current authenticated patient profile"
)
def get_authenticated_patient(current_patient: Patient = Depends(get_current_patient)):
    """
    Returns the profile of the currently logged-in patient.
    Protected route requiring a valid Bearer token.
    """
    return PatientResponse.model_validate(current_patient)
