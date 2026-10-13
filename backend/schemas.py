from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


# -------------------------------------------------------------
# Patient Authentication Schemas
# -------------------------------------------------------------

class PatientRegisterRequest(BaseModel):
    """Schema for patient self-registration with password confirmation."""
    full_name: str = Field(..., min_length=2, max_length=255, description="Patient full name")
    email: EmailStr = Field(..., description="Valid unique email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (at least 6 characters)")
    confirm_password: str = Field(..., description="Must match password exactly")

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, confirm_password: str, info):
        if "password" in info.data and confirm_password != info.data["password"]:
            raise ValueError("Passwords do not match")
        return confirm_password

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, name: str):
        stripped = name.strip()
        if len(stripped) < 2:
            raise ValueError("Full name must be at least 2 characters long")
        return stripped


class PatientLoginRequest(BaseModel):
    """Schema for patient login."""
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Patient password")


class PatientResponse(BaseModel):
    """
    Public patient profile response.
    Never exposes password_hash or internal secrets.
    """
    id: int
    full_name: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """JWT bearer token response upon successful login or registration."""
    access_token: str
    token_type: str = "bearer"
    patient: PatientResponse


class MessageResponse(BaseModel):
    """Generic status/message response."""
    message: str
