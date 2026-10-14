# DocuMedi — AI-Powered Patient Case-Taking System

**Tagline: Your Health Story, Organized.**

DocuMedi is a full-stack, AI-powered patient case-taking and personal health record management platform designed to improve how patients communicate their health concerns and organize their medical histories.

The platform guides patients through an adaptive conversational intake, captures relevant symptom information, and transforms the conversation into a structured 11-section clinical note. Patients can review and edit the generated note before confirming it, access their consultation history through a chronological timeline, and download clinical records as PDF documents.

> **Disclaimer:** DocuMedi is an educational project for patient information collection and documentation. It is not a substitute for professional medical advice, diagnosis, or treatment.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Project Objectives](#project-objectives)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [System Architecture](#system-architecture)
- [Database Design](#database-design)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Clinical Note Format](#clinical-note-format)
- [Security and Privacy](#security-and-privacy)
- [Medical Safety](#medical-safety)
- [Limitations](#limitations)
- [Future Enhancements](#future-enhancements)
- [License](#license)

---

## Problem Statement

During clinical consultations, patients may struggle to recall the exact chronology of their symptoms, previous treatments, medication responses, allergies, and other relevant medical details. Time-constrained consultations can make it difficult to capture this information comprehensively.

Healthcare documentation also requires converting unstructured patient descriptions into organized clinical records, which can be time-consuming.

DocuMedi addresses these challenges through conversational patient intake and automated clinical documentation. It helps organize information provided by patients into a structured, reviewable record while maintaining a distinction between patient-reported information and verified clinical findings.

## Project Objectives

- Simplify patient case-taking through an interactive conversational interface.
- Collect relevant symptom history using adaptive, symptom-specific questions.
- Reduce repetitive questions by tracking information already provided.
- Identify potentially urgent symptoms and display appropriate emergency guidance.
- Generate structured clinical notes from the consultation.
- Allow patients to review and edit notes before confirming them.
- Store confirmed notes in a MySQL database.
- Provide a chronological view of previous consultations.
- Generate downloadable PDF reports for saved clinical records.
- Protect patient records through authentication and patient-level access controls.

## Key Features

### 1. Secure Patient Authentication

- Patient registration and login.
- Password hashing using bcrypt.
- JWT-based authentication.
- Protected application routes and authenticated API requests.
- Patient-level authorization for consultations and clinical records.

### 2. Conversational Clinical Intake

An AI-assisted conversational engine guides patients through a case-taking session.

The intake process supports three primary symptom groups:

- **Illnesses and systemic symptoms:** Cold, cough, fever, flu-like symptoms, and suspected infections.
- **Pain and discomfort:** Headaches, body aches, joint pain, back pain, and other localized complaints.
- **Skin conditions:** Rashes, itching, redness, suspected skin infections, and other skin changes.

The engine adapts follow-up questions to the patient's reported symptoms, avoids asking for information already provided, and preserves relevant information throughout the consultation.

The system can be configured to use a supported AI provider or its rule-based intake logic, depending on the project configuration.

### 3. Emergency Red-Flag Detection

The application checks for potentially urgent symptoms and displays appropriate emergency guidance when configured red-flag conditions are identified.

This feature is intended to encourage timely medical attention. It does not diagnose emergencies or replace professional clinical assessment.

### 4. Structured Clinical Note Generation

DocuMedi organizes the consultation into 11 standard sections:

1. Chief Complaint
2. History of Present Illness (HPI)
3. Past Medical History
4. Current Medications
5. Allergies
6. Family History
7. Social History
8. Review of Systems (ROS)
9. Physical Examination
10. Assessment and Plan
11. Follow-up

The physical examination section remains explicitly marked as not performed because a conversational intake cannot independently conduct a physical examination.

Missing information is represented as not provided rather than fabricated.

### 5. Patient Review and Editing

Before confirming a clinical note, patients can review the generated content and edit its sections.

Only confirmed notes should be treated as saved clinical records.

### 6. Persistent Clinical Records

Confirmed notes are stored in MySQL using SQLAlchemy ORM models.

The application associates consultations and notes with their respective patients and supports retrieving previously saved information.

### 7. Medical History Timeline

The medical history page presents saved consultations in reverse chronological order, allowing patients to review their previous records.

### 8. PDF Report Generation

DocuMedi uses ReportLab to generate downloadable clinical PDF reports from saved records.

The PDF service supports structured formatting, branding, headers, page numbering, and documentation disclaimers.

PDF generation should use confirmed database records rather than unconfirmed drafts.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, React Router, JavaScript, CSS |
| Backend | Python 3.11, FastAPI, Starlette, Uvicorn |
| Database | MySQL 8.0+, SQLAlchemy 2.0, PyMySQL |
| Authentication | bcrypt, PyJWT, OAuth2 Bearer authentication |
| AI Integration | Google Gemini or another configured provider; rule-based fallback where supported |
| PDF Generation | ReportLab, pypdf |
| Testing | FastAPI TestClient, unittest.mock, automated integration tests |
| Development Environment | Windows 11, Visual Studio Code, PowerShell |

---

## System Architecture

The application follows a frontend–backend–database architecture.

```mermaid
flowchart TD
    A[Patient] --> B[React Frontend]
    B --> C[FastAPI Backend]
    C --> D[Authentication and Authorization]
    C --> E[Conversational Intake Engine]
    E --> F[Configured AI Provider or Rule-Based Logic]
    C --> G[Clinical Note Service]
    C --> H[MySQL Database]
    G --> H
    H --> I[Medical History Timeline]
    H --> J[ReportLab PDF Service]
    I --> B
    J --> B
    D --> H
```

### Consultation Workflow

1. The patient registers or logs in.
2. The patient starts a new consultation.
3. The conversational engine collects relevant medical information.
4. The system tracks answers and evaluates configured safety warnings.
5. The consultation dialogue is organized into a structured clinical note.
6. The patient reviews and edits the draft.
7. The confirmed note is saved to MySQL.
8. The patient can view the record in the medical history timeline or download it as a PDF.

---

## Database Design

The application uses a MySQL database named `patient_case_system`.

The core schema consists of four tables.

| Table | Purpose |
|---|---|
| `patients` | Stores patient account information and password hashes. |
| `patient_cases` | Stores consultation sessions and their status. |
| `conversation_messages` | Stores patient and AI conversation messages. |
| `patient_notes` | Stores the structured clinical note sections. |

### Entity Relationships

```mermaid
erDiagram
    PATIENTS ||--o{ PATIENT_CASES : owns
    PATIENTS ||--o{ PATIENT_NOTES : owns
    PATIENT_CASES ||--o{ CONVERSATION_MESSAGES : contains
    PATIENT_CASES ||--o{ PATIENT_NOTES : produces

    PATIENTS {
        int id PK
        varchar full_name
        varchar email UK
        varchar password_hash
        datetime created_at
        datetime updated_at
    }

    PATIENT_CASES {
        int id PK
        int patient_id FK
        varchar case_title
        varchar status
        datetime created_at
        datetime updated_at
    }

    CONVERSATION_MESSAGES {
        int id PK
        int case_id FK
        varchar sender_role
        text message_content
        datetime created_at
    }

    PATIENT_NOTES {
        int id PK
        int case_id FK
        int patient_id FK
        text chief_complaint
        text hpi
        text past_medical_history
        text medications
        text allergies
        text family_history
        text social_history
        text review_of_systems
        text physical_examination
        text assessment_and_plan
        text follow_up
        datetime created_at
        datetime updated_at
    }
```

The schema above documents the intended core structure. Confirm the actual model definitions and database migrations before deploying, especially if the implementation has evolved.

---

## Project Structure

```text
patient_case_taking/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── dependencies.py
│   ├── init_db.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   ├── requirements.txt
│   ├── routers/
│   │   ├── auth.py
│   │   ├── cases.py
│   │   └── notes.py
│   ├── services/
│   │   ├── clinical_tracker.py
│   │   ├── conversation_service.py
│   │   ├── note_service.py
│   │   └── pdf_service.py
│   ├── test_auth.py
│   ├── test_cases.py
│   ├── test_conversational_ai.py
│   ├── test_notes.py
│   ├── test_timeline.py
│   ├── test_pdf.py
│   ├── test_e2e_workflow.py
│   ├── .env.example
│   └── .env
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── styles/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── .env.example
├── .gitignore
└── README.md
```

**Note:** This is a documented reference structure. Keep the README aligned with the actual files in your repository.

---

## Prerequisites

Install the following before running the project:

- Windows 10 or Windows 11
- Python 3.11
- Node.js and npm
- MySQL Server 8.0 or higher
- MySQL Workbench (recommended for database management)
- Visual Studio Code
- Git (for version control)
- An API key for your configured AI provider, if using an external AI service

---

## Installation and Setup

### 1. Navigate to the Project

Open PowerShell or the VS Code terminal:

```powershell
cd C:\Users\Tanmai\patient_case_taking
```

### 2. Create the MySQL Database

Open MySQL Workbench and execute:

```sql
CREATE DATABASE IF NOT EXISTS patient_case_system
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Use a dedicated database user with appropriate permissions for production instead of relying on a local root account.

### 3. Configure Backend Environment Variables

Navigate to the backend directory:

```powershell
cd C:\Users\Tanmai\patient_case_taking\backend
```

Create the local environment file from the template:

```powershell
Copy-Item .env.example .env
```

Edit `backend/.env` and configure the variables expected by your application. For example:

```env
DATABASE_URL=mysql+pymysql://DB_USER:DB_PASSWORD@localhost:3306/patient_case_system

SECRET_KEY=replace_with_a_secure_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

AI_PROVIDER=gemini
AI_API_KEY=replace_with_your_gemini_api_key
AI_MODEL=your_configured_model

FRONTEND_URL=http://localhost:5173
```

These are illustrative variable names. Use the exact names supported by your existing backend configuration. If your implementation expects `GEMINI_API_KEY` instead of `AI_API_KEY`, configure the corresponding name.

Never commit real API keys, database passwords, or JWT secrets.

### 4. Create and Install the Python Environment

From the backend directory:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Using the virtual environment's Python executable directly avoids PowerShell activation-policy issues.

### 5. Initialize the Database Tables

Run:

```powershell
.\venv\Scripts\python.exe init_db.py
```

Review the initialization script before executing it. Confirm that it creates or checks the required tables without dropping existing data.

### 6. Configure the Frontend Environment

Navigate to the frontend:

```powershell
cd ..\frontend
Copy-Item .env.example .env
```

Configure the API base URL in `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Ensure that the variable name matches the frontend's actual API configuration.

### 7. Install Frontend Dependencies

```powershell
npm.cmd install
```

---

## Running the Application

Run the backend and frontend in separate terminal windows.

### Terminal 1 — FastAPI Backend

```powershell
cd C:\Users\Tanmai\patient_case_taking\backend
.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend API: `http://127.0.0.1:8000`

Interactive API documentation: `http://127.0.0.1:8000/docs`

Alternative API documentation: `http://127.0.0.1:8000/redoc`

### Terminal 2 — React Frontend

```powershell
cd C:\Users\Tanmai\patient_case_taking\frontend
npm.cmd run dev
```

Frontend: `http://localhost:5173`

---

## Testing

Run the tests from the backend directory using the project's virtual environment.

```powershell
cd C:\Users\Tanmai\patient_case_taking\backend
```

Execute the available test suites:

```powershell
.\venv\Scripts\python.exe test_auth.py
.\venv\Scripts\python.exe test_cases.py
.\venv\Scripts\python.exe test_conversational_ai.py
.\venv\Scripts\python.exe test_notes.py
.\venv\Scripts\python.exe test_timeline.py
.\venv\Scripts\python.exe test_pdf.py
.\venv\Scripts\python.exe test_e2e_workflow.py
```

Build the frontend for production:

```powershell
cd ..\frontend
npm.cmd run build
```

### Recommended Verification Areas

- Registration, login, and JWT validation
- Patient-level authorization for cases, notes, and PDF downloads
- Adaptive questioning and duplicate-question prevention
- Allergy, medication, and past medical history extraction
- Saving and retrieving confirmed notes
- Timeline ordering and saved-record accuracy
- PDF content, pagination, and download authorization
- Emergency warning behavior
- Frontend production build

The tests should be run against the current codebase before claiming that all features work. Test results depend on the current implementation and configuration.

---

## Clinical Note Format

Each consultation produces a structured record containing:

| Section | Content |
|---|---|
| 1. Chief Complaint | Main concern reported by the patient |
| 2. History of Present Illness | Onset, duration, progression, and associated symptoms |
| 3. Past Medical History | Relevant previously reported medical conditions |
| 4. Current Medications | Patient-reported medications and available details |
| 5. Allergies | Patient-reported allergies or explicit absence of known allergies |
| 6. Family History | Relevant reported family medical history |
| 7. Social History | Relevant reported social and lifestyle information |
| 8. Review of Systems | Reported symptoms across relevant body systems |
| 9. Physical Examination | Not performed — information not collected during patient conversation |
| 10. Assessment and Plan | Structured documentation of reported information and appropriate next steps |
| 11. Follow-up | Relevant follow-up information |

The generated note must distinguish reported information from verified findings and must not fabricate missing details.

---

## Security and Privacy

DocuMedi incorporates security mechanisms intended to protect patient records:

- Password hashing rather than plaintext password storage.
- JWT-based authentication for protected endpoints.
- Patient-level access checks for consultations, notes, and downloads.
- Environment variables for database credentials and AI API keys.
- Git ignore rules for local secrets and generated development files.
- Server-side authorization rather than relying solely on frontend route protection.

### Before Deployment

The current local development setup is not automatically production-ready.

Before storing real patient information, review:

- HTTPS and secure production hosting.
- Database encryption, backups, and restoration procedures.
- Access control and session management.
- Secret storage and API key rotation.
- Logging, auditability, and error handling.
- Applicable privacy and data protection requirements.

Never commit `.env` files, API keys, database dumps, or real patient records to a public repository.

---

## Medical Safety

DocuMedi is designed for patient intake and documentation, not independent diagnosis.

- Missing information should be marked as not provided.
- Uncertain information should remain explicitly uncertain.
- Suspected conditions must not be presented as confirmed diagnoses.
- Physical examination findings must not be invented.
- Potentially urgent symptoms should trigger appropriate emergency guidance.
- Patients should be encouraged to consult qualified healthcare professionals for medical assessment and treatment.

The application should not replace professional clinical judgment.

---

## Limitations

DocuMedi is an academic project. Its current security and operational features should not be interpreted as proof of regulatory compliance.

Production use requires additional review of data protection, encryption, audit logging, operational monitoring, backup recovery, and clinical safety.

External AI provider availability, pricing, quotas, and model behavior depend on the provider and configuration.

---

## Future Enhancements

Potential future improvements include:

- Multilingual conversational intake.
- Healthcare interoperability using HL7 and FHIR.
- Secure clinician review and sign-off.
- Patient-uploaded prescriptions and laboratory reports.
- Two-factor authentication.
- Enhanced audit logging and monitoring.
- Improved accessibility and mobile responsiveness.

---

## License

This project is intended for educational and academic purposes. The project may be distributed under the MIT License if the repository includes the corresponding `LICENSE` file.

---

**DocuMedi — Your Health Story, Organized.**