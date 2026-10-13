from datetime import datetime
from typing import Optional, List
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


class GenericResponse(BaseModel):
    """Generic status/message response."""
    message: str


# -------------------------------------------------------------
# Case & Conversation Schemas (Stage 5)
# -------------------------------------------------------------

class CaseCreateRequest(BaseModel):
    """Optional customization for a new case consultation."""
    case_title: Optional[str] = Field(
        default="Health Concern Consultation",
        max_length=255,
        description="Title or brief topic for this consultation"
    )


class ConversationMessageResponse(BaseModel):
    """Schema for an individual conversation message."""
    id: int
    case_id: int
    sender_role: str  # 'patient', 'ai', 'system'
    message_content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageSendRequest(BaseModel):
    """Schema for a patient submitting a message to the AI."""
    message_content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Patient's message to the clinical intake AI"
    )

    @field_validator("message_content")
    @classmethod
    def not_empty_whitespace(cls, content: str):
        stripped = content.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or whitespace only")
        return stripped


class CaseDetailResponse(BaseModel):
    """Detailed case response including full conversation history."""
    id: int
    patient_id: int
    case_title: str
    status: str  # 'active', 'completed', 'cancelled'
    created_at: datetime
    updated_at: datetime
    messages: List[ConversationMessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CaseSummaryResponse(BaseModel):
    """Summary case item for listing on dashboard/timeline."""
    id: int
    patient_id: int
    case_title: str
    status: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SendMessageResponse(BaseModel):
    """Response returned when a message is sent to the case."""
    patient_message: ConversationMessageResponse
    ai_response: ConversationMessageResponse
    case_status: str
    is_live_ai: bool = False
    ai_provider: str = "rules_intake"
    system_notice: Optional[str] = None
