"""
dependencies.py — FastAPI dependencies for authentication and database sessions.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import Patient
from security import decode_access_token

# HTTPBearer extracts the "Bearer <token>" header from requests
security_bearer = HTTPBearer(auto_error=False)


def get_current_patient(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Patient:
    """
    Dependency to validate the JWT bearer token and retrieve the authenticated patient.
    Raises HTTP 401 Unauthorized if the token is missing, expired, invalid, or patient not found.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    patient_id_str: str = payload.get("sub")
    if not patient_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        patient_id = int(patient_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid patient identifier in token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated patient record no longer exists",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return patient
