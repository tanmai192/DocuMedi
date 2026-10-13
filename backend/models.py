from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from database import Base


class Patient(Base):
    """
    Represents a registered patient in DocuMedi.
    Stores account credentials, profile details, and timestamps.
    """
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    # If a patient is deleted, their cases and notes are cleanly deleted
    cases = relationship("PatientCase", back_populates="patient", cascade="all, delete-orphan")
    notes = relationship("PatientNote", back_populates="patient", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Patient(id={self.id}, email='{self.email}', full_name='{self.full_name}')>"


class PatientCase(Base):
    """
    Represents a single clinical intake session / case created by a patient.
    Acts as the parent container for the conversation messages and the resulting note.
    """
    __tablename__ = "patient_cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    case_title = Column(String(255), nullable=False, default="Health Concern Consultation")
    status = Column(String(50), nullable=False, default="active")  # active, completed, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="cases")
    messages = relationship("ConversationMessage", back_populates="case", cascade="all, delete-orphan")
    notes = relationship("PatientNote", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PatientCase(id={self.id}, patient_id={self.patient_id}, title='{self.case_title}', status='{self.status}')>"


class ConversationMessage(Base):
    """
    Represents an individual message exchanged in the AI case-taking chat.
    sender_role can be 'patient', 'ai', or 'system'.
    """
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("patient_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_role = Column(String(50), nullable=False)  # 'patient', 'ai', 'system'
    message_content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    case = relationship("PatientCase", back_populates="messages")

    def __repr__(self):
        return f"<ConversationMessage(id={self.id}, case_id={self.case_id}, sender='{self.sender_role}')>"


class PatientNote(Base):
    """
    Represents a structured clinical note generated from the patient consultation.
    Contains all 11 required clinical sections in order, linked to the patient and case.
    """
    __tablename__ = "patient_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("patient_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)

    # The 11 Standard Clinical Note Headings
    chief_complaint = Column(Text, nullable=True)
    hpi = Column(Text, nullable=True)  # History of Present Illness
    past_medical_history = Column(Text, nullable=True)
    medications = Column(Text, nullable=True)
    allergies = Column(Text, nullable=True)
    family_history = Column(Text, nullable=True)
    social_history = Column(Text, nullable=True)
    review_of_systems = Column(Text, nullable=True)
    physical_examination = Column(Text, nullable=True)
    assessment_and_plan = Column(Text, nullable=True)
    follow_up = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    case = relationship("PatientCase", back_populates="notes")
    patient = relationship("Patient", back_populates="notes")

    def __repr__(self):
        return f"<PatientNote(id={self.id}, case_id={self.case_id}, patient_id={self.patient_id})>"
