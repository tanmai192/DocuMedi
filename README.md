# DocuMedi — AI-Powered Patient Case-Taking System

> **Tagline:** *Your Health Story, Organized.*

---

## 1. Project Overview & Problem Statement

In modern healthcare, patients often struggle to recall and articulate the exact chronology of their symptoms during rushed clinical consultations. Crucial context—such as timeline of onset, medication responses, and subtle associated symptoms—can be lost. On the clinical side, healthcare providers spend hours converting unstructured patient dialogue into standard clinical records.

**DocuMedi** bridges this communication divide. It is a full-stack, AI-powered patient intake and personal health record platform. Patients engage in an empathetic, conversational intake consultation where the AI gathers detailed symptom history while monitoring for red-flag medical emergencies. DocuMedi then automatically structures this dialogue into the **11 standard clinical note sections**, provides the patient full agency to review and edit their record, saves the confirmed note to a secure MySQL database, visualizes their medical history on an interactive chronological timeline, and compiles downloadable clinical PDF reports using ReportLab.

---

## 2. Objectives & Key Features

* **Secure Patient Authentication:** Account registration, bcrypt password hashing (12 salt rounds), and JWT Bearer token-based session management.
* **Conversational Clinical Intake:** Real-time chat dialogue powered by an adaptive medical intake engine supporting Google Gemini, OpenAI, or intelligent clinical rule-based triage.
* **Emergency Red-Flag Detection:** Proactively flags life-threatening symptoms (e.g., crushing chest pain, anaphylaxis, acute shortness of breath) and displays urgent emergency instructions.
* **Structured 11-Section Note Generation:** Maps conversational exchanges into the standard clinical format:
  1. Chief Complaint
  2. History of Present Illness (HPI)
  3. Past Medical History
  4. Current Medications
  5. Allergies
  6. Family History
  7. Social History
  8. Review of Systems (ROS)
  9. Physical Examination (*locked: "Not performed — information not collected during patient conversation"*)
  10. Assessment and Plan
  11. Follow-up
* **Patient Review & Editorial Agency:** Patients can review, clarify, and edit any draft section before permanently committing it to their clinical record.
* **Idempotent Record Persistence:** Confirmed notes are stored in MySQL (`patient_notes` table) with strict patient-level access control.
* **My Medical History Timeline:** A chronological visual timeline displaying all verified consultations (newest first) with faithful summaries extracted directly from saved records.
* **Authoritative PDF Generation:** Multi-page clinical record PDFs generated via ReportLab Platypus, complete with DocuMedi branding, running headers, two-pass `"Page X of Y"` pagination, and mandatory AI documentation disclaimers.

---

## 3. Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18 / 19, Vite, React Router v6, Native Fetch API, Custom CSS Design System (Teal & Deep Blue) |
| **Backend** | Python 3.11, FastAPI, Starlette, Uvicorn (ASGI) |
| **Database & ORM** | MySQL 8.0+, SQLAlchemy 2.0 ORM, PyMySQL driver |
| **Security** | `bcrypt` (password hashing), `pyjwt` (HS256 JWT tokens), OAuth2 Bearer scheme |
| **PDF Engine** | `reportlab` 5.0 (Platypus document templates, NumberedCanvas), `pypdf` (testing & validation) |
| **Testing** | FastAPI `TestClient`, `unittest.mock`, `pypdf` |
| **Environment** | Windows 11, VS Code, PowerShell |

---

## 4. System Architecture & Request Flow

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Patient (Browser)
    participant Frontend as React / Vite Frontend
    participant Backend as FastAPI Backend
    participant Engine as Clinical AI Intake Engine
    participant DB as MySQL Database
    participant PDF as ReportLab PDF Service

    Note over Patient,DB: Stage 3 & 4 — Authentication
    Patient->>Frontend: Enter credentials (Register/Login)
    Frontend->>Backend: POST /auth/login
    Backend->>DB: Query patient by email & verify bcrypt hash
    Backend-->>Frontend: Return JWT Access Token
    Frontend->>Frontend: Store token in localStorage

    Note over Patient,DB: Stage 5 — Conversational Intake
    Patient->>Frontend: "Start New Case"
    Frontend->>Backend: POST /cases (with Bearer Token)
    Backend->>DB: Insert into patient_cases
    Backend-->>Frontend: Return case_id & initial AI greeting
    loop Consultation Chat
        Patient->>Frontend: Send message describing symptoms
        Frontend->>Backend: POST /cases/{id}/messages
        Backend->>DB: Save patient message
        Backend->>Engine: Evaluate history & red-flags
        Engine-->>Backend: Clinical follow-up question
        Backend->>DB: Save AI response
        Backend-->>Frontend: Return AI message
    end
    Patient->>Frontend: Click "Finish Consultation"
    Frontend->>Backend: POST /cases/{id}/end
    Backend->>DB: Update case status -> 'completed'

    Note over Patient,DB: Stage 6 — Note Generation & Review
    Patient->>Frontend: Click "Generate Clinical Note"
    Frontend->>Backend: POST /cases/{id}/generate-note
    Backend->>Engine: Structure dialogue into 11 headings
    Backend-->>Frontend: Return 11-section draft note
    Patient->>Frontend: Review & edit sections, then click "Save Confirmed Note"
    Frontend->>Backend: POST /cases/{id}/notes
    Backend->>DB: Insert / update patient_notes record
    Backend-->>Frontend: Return confirmed note_id

    Note over Patient,PDF: Stage 7 & 8 — Timeline & PDF Download
    Patient->>Frontend: Navigate to /history
    Frontend->>Backend: GET /notes/timeline
    Backend->>DB: SELECT notes ORDER BY created_at DESC
    Backend-->>Frontend: Return timeline array
    Patient->>Frontend: Click "Download PDF"
    Frontend->>Backend: GET /notes/{note_id}/pdf
    Backend->>DB: Verify patient ownership
    Backend->>PDF: generate_patient_note_pdf()
    PDF-->>Backend: Return raw PDF bytes (io.BytesIO)
    Backend-->>Frontend: application/pdf binary response
    Frontend->>Patient: Browser triggers file download (.pdf)
```

---

## 5. Database Schema & Entity Relationships

The MySQL database (`patient_case_system`) contains four normalized tables linked with foreign keys and cascade deletions:

```mermaid
erDiagram
    PATIENTS ||--o{ PATIENT_CASES : "has many"
    PATIENTS ||--o{ PATIENT_NOTES : "owns"
    PATIENT_CASES ||--o{ CONVERSATION_MESSAGES : "contains"
    PATIENT_CASES ||--o{ PATIENT_NOTES : "summarized in"

    PATIENTS {
        int id PK "Auto-increment"
        varchar full_name "Not null"
        varchar email UK "Unique, Not null"
        varchar password_hash "Bcrypt hash"
        datetime created_at "Default NOW()"
        datetime updated_at "Default NOW()"
    }

    PATIENT_CASES {
        int id PK "Auto-increment"
        int patient_id FK "References patients.id"
        varchar case_title "Default 'Health Concern Consultation'"
        varchar status "'active', 'completed', 'cancelled'"
        datetime created_at "Default NOW()"
        datetime updated_at "Default NOW()"
    }

    CONVERSATION_MESSAGES {
        int id PK "Auto-increment"
        int case_id FK "References patient_cases.id"
        varchar sender_role "'patient', 'ai', 'system'"
        text message_content "Not null"
        datetime created_at "Default NOW()"
    }

    PATIENT_NOTES {
        int id PK "Auto-increment"
        int case_id FK "References patient_cases.id"
        int patient_id FK "References patients.id"
        text chief_complaint "Section 1"
        text hpi "Section 2"
        text past_medical_history "Section 3"
        text medications "Section 4"
        text allergies "Section 5"
        text family_history "Section 6"
        text social_history "Section 7"
        text review_of_systems "Section 8"
        text physical_examination "Section 9 (Not performed disclaimer)"
        text assessment_and_plan "Section 10"
        text follow_up "Section 11"
        datetime created_at "Default NOW()"
        datetime updated_at "Default NOW()"
    }
```

---

## 6. Project Directory Structure

```text
patient_case_taking/
├── backend/
│   ├── database.py              # SQLAlchemy engine, SessionLocal & get_db
│   ├── dependencies.py          # JWT authentication dependency (get_current_patient)
│   ├── init_db.py               # Table creator & schema inspector
│   ├── main.py                  # FastAPI application entry point with CORS
│   ├── models.py                # 4 SQLAlchemy ORM models (Patient, Case, Message, Note)
│   ├── requirements.txt         # Pinned Python package dependencies
│   ├── schemas.py               # Pydantic v2 validation models
│   ├── security.py              # Bcrypt hashing & PyJWT token management
│   ├── routers/
│   │   ├── auth.py              # POST /auth/register, POST /auth/login, GET /auth/me
│   │   ├── cases.py             # CRUD for patient cases, chat messages & note generation
│   │   └── notes.py             # Note retrieval, update, /timeline & /pdf download
│   ├── services/
│   │   ├── clinical_tracker.py  # Cumulative symptom tracker, empathy engine & entity extractor
│   │   ├── conversation_service.py # AI intake engine & red-flag detector
│   │   ├── note_service.py      # 11-section note generator & safety rules
│   │   └── pdf_service.py       # ReportLab Platypus PDF generator & NumberedCanvas
│   ├── test_auth.py             # 10 automated authentication tests
│   ├── test_cases.py            # 9 automated case & AI conversation tests
│   ├── test_conversational_ai.py # 6 automated multi-symptom & dynamic memory tests
│   ├── test_notes.py            # 9 automated clinical note generation tests
│   ├── test_timeline.py         # 6 automated medical history timeline tests
│   ├── test_pdf.py              # 11 automated PDF generation & security tests
│   ├── test_e2e_workflow.py     # 15-step complete patient journey integration test
│   ├── .env                     # Local credentials (ignored by Git)
│   └── .env.example             # Template for backend environment variables
├── frontend/
│   ├── public/                  # Static assets & favicon
│   ├── src/
│   │   ├── components/
│   │   │   ├── Logo.jsx         # Teal cross DocuMedi brand mark
│   │   │   ├── Navbar.jsx       # Responsive navigation with mobile drawer
│   │   │   ├── ProtectedRoute.jsx # Client-side route guard
│   │   │   └── PublicRoute.jsx  # Redirects authenticated users from login/register
│   │   ├── context/
│   │   │   └── AuthContext.jsx  # React Context for session management & token persistence
│   │   ├── pages/
│   │   │   ├── CaseChat.jsx     # Real-time consultation chat UI
│   │   │   ├── Dashboard.jsx    # Patient overview, quick actions & recent cases
│   │   │   ├── Login.jsx        # Login page with validation
│   │   │   ├── MedicalHistory.jsx # Chronological medical history timeline (/history)
│   │   │   ├── NoteDetail.jsx   # Confirmed clinical note viewer & inline editor
│   │   │   ├── NoteReview.jsx   # 11-heading draft review & confirmation page
│   │   │   ├── NotFound.jsx     # 404 error page
│   │   │   ├── Profile.jsx      # Patient profile details
│   │   │   └── Register.jsx     # Registration form with password match validation
│   │   ├── services/
│   │   │   └── api.js           # Centralized API service with Blob download handler
│   │   ├── styles/
│   │   │   └── index.css        # Comprehensive design system (Teal, Slate, Emerald)
│   │   ├── App.jsx              # Top-level router & global medical disclaimer
│   │   └── main.jsx             # React DOM root entry
│   ├── package.json             # NPM dependencies & scripts
│   ├── .env                     # Frontend configuration (ignored by Git)
│   └── .env.example             # Template for frontend environment variables
├── .gitignore                   # Excludes virtualenv, node_modules, .env, and build dist
└── README.md                    # Comprehensive documentation and operational guide
```

---

## 7. Prerequisites

Before running DocuMedi on Windows 11, ensure you have the following installed:

1. **Operating System:** Windows 10 / 11 (64-bit)
2. **Python:** Version 3.11.x (with `pip` and virtual environment support)
3. **Node.js:** Version 20.x or 24.x LTS (with `npm`)
4. **MySQL Server:** Version 8.0 or higher running on `localhost:3306`
5. **Code Editor:** Visual Studio Code (recommended)

---

## 8. Windows 11 Setup Instructions

### Step 1: Clone or Navigate to the Project
```powershell
cd C:\Users\Tanmai\patient_case_taking
```

### Step 2: Configure MySQL Database
Open your MySQL Command Line Client or MySQL Workbench and run:
```sql
CREATE DATABASE IF NOT EXISTS patient_case_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Step 3: Configure Backend Environment Variables
Create `backend\.env` by copying `backend\.env.example`:
```powershell
Copy-Item backend\.env.example backend\.env
```
Open `backend\.env` in VS Code and fill in your values:
```env
# Database connection string (adjust username and password as appropriate)
DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost:3306/patient_case_system

# JWT Authentication
SECRET_KEY=generate_a_random_secret_key_at_least_32_characters_long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# AI Provider (Optional: leave as rules_intake if running locally without an API key)
AI_PROVIDER=rules_intake
AI_API_KEY=
AI_MODEL=

# CORS Configuration
FRONTEND_URL=http://localhost:5173
```

### Step 4: Set Up the Python Virtual Environment
In a PowerShell terminal:
```powershell
cd C:\Users\Tanmai\patient_case_taking\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Initialize Database Tables
```powershell
cd C:\Users\Tanmai\patient_case_taking\backend
.\venv\Scripts\python.exe init_db.py
```
This will safely create all four tables (`patients`, `patient_cases`, `conversation_messages`, `patient_notes`) without deleting existing data.

### Step 6: Configure Frontend Environment Variables
```powershell
cd C:\Users\Tanmai\patient_case_taking\frontend
Copy-Item .env.example .env
```
Ensure `frontend\.env` contains:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### Step 7: Install Frontend Dependencies
```powershell
cd C:\Users\Tanmai\patient_case_taking\frontend
npm.cmd install
```

---

## 9. Starting the Application

DocuMedi requires two terminal windows running side-by-side in VS Code:

### Terminal 1 — Backend (FastAPI)
```powershell
cd C:\Users\Tanmai\patient_case_taking\backend
.\venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
* **Backend API:** `http://127.0.0.1:8000`
* **Interactive API Documentation (Swagger UI):** `http://127.0.0.1:8000/docs`
* **Alternative API Documentation (ReDoc):** `http://127.0.0.1:8000/redoc`

### Terminal 2 — Frontend (React Vite)
```powershell
cd C:\Users\Tanmai\patient_case_taking\frontend
npm.cmd run dev
```
* **Web Application:** `http://localhost:5173`

---

## 10. Running the Automated Test Suites

All backend tests use dedicated, isolated test accounts and clean up their test records in `finally` blocks, never affecting real patient data.

Run the test suites from the `backend/` directory:

```powershell
cd C:\Users\Tanmai\patient_case_taking\backend

# 1. Authentication & JWT security (10 tests)
.\venv\Scripts\python.exe test_auth.py

# 2. Case intake, chat & red-flag safety (9 tests)
.\venv\Scripts\python.exe test_cases.py

# 3. Conversational AI, multi-symptom & dynamic memory tests (6 tests)
.\venv\Scripts\python.exe test_conversational_ai.py

# 4. 11-section clinical note generation & saving (9 tests)
.\venv\Scripts\python.exe test_notes.py

# 5. Medical history timeline & sorting (6 tests)
.\venv\Scripts\python.exe test_timeline.py

# 6. ReportLab PDF generation & download security (11 tests)
.\venv\Scripts\python.exe test_pdf.py

# 7. Complete 15-step end-to-end patient journey (15 steps)
.\venv\Scripts\python.exe test_e2e_workflow.py
```

### Building the Production Frontend
To verify that the React client compiles and bundles cleanly:
```powershell
cd C:\Users\Tanmai\patient_case_taking\frontend
npm.cmd run build
```

---

## 11. Testing PDF Downloads

PDF downloads can be tested in three user-facing locations:

1. **Note Detail Page (`/notes/{note_id}`):** Click the **📄 Download PDF** button in the sticky top toolbar to download the current note.
2. **Medical History Timeline (`/history`):** Click the **📥 Download PDF** button on any consultation card in the timeline to download that specific note.
3. **Note Review Page (`/cases/{case_id}/review-note`):** Click **📄 Save & Download PDF** to permanently confirm the draft note into MySQL records and immediately download the official PDF report.

---

## 12. Security & Privacy Review

* **Password Hashing:** Passwords are never stored in plain text. Hashing is performed via `bcrypt` using 12 salt rounds. Password hashes are excluded from all API responses via Pydantic model configurations (`PatientResponse`).
* **JWT Token Lifespan:** Tokens expire automatically after 24 hours (1440 minutes) and are verified using `pyjwt` with algorithm `HS256`.
* **Zero Secrets in Git:** Secrets (`DATABASE_URL`, `SECRET_KEY`, `AI_API_KEY`) are managed exclusively through `.env` files, which are strictly ignored in `.gitignore`.
* **Cross-Patient Access Isolation:** Every case, message, note, and PDF download endpoint verifies `record.patient_id == current_patient.id`. Manipulating IDs in URL routes results in immediate `HTTP 403 Forbidden` rejection.
* **Persistent Record Grounding:** PDFs are rendered strictly from confirmed database records (`PatientNote`), preventing unsaved client-side drafts from being passed off as official reports.
* **Student Project Disclaimer:** This application was developed as a Computer Science educational project. It does not implement HIPAA compliance controls, audit logging, encrypted data-at-rest storage, or production TLS/SSL termination.

---

## 13. Medical Safety & Clinical Guardrails

* **No Information Fabrication:** Missing clinical details are never hallucinated or invented; they are explicitly rendered as `"Not provided."`.
* **Non-Diagnostic Assessments:** Note generation phrasing is intentionally conservative (e.g., *"Suspected acute viral bronchitis"*, *"Probable tension headache"*), explicitly framing observations as provisional clinical notes rather than definitive diagnoses.
* **Locked Physical Examination:** Telehealth or conversational intakes cannot perform physical examinations. Section 9 is locked to:
  > *"Not performed — information not collected during the patient consultation"*
* **Emergency Red-Flag Escalation:** High-risk symptom keywords (chest pressure, stroke signs, breathing failure, severe allergic reactions) trigger immediate warning banners directing the user to contact emergency services (112 in India, or 108 for ambulance).
* **Universal Disclaimer:** Placed prominently across the web application and embedded on every page footer of generated PDFs:
  > *"AI-assisted patient record based on information provided during the consultation. This document is for documentation purposes only and is not a confirmed medical diagnosis or a substitute for professional medical advice."*

---

## 14. Future Enhancements

* **Multilingual Intake Support:** Real-time translation to support non-English speaking patients.
* **EHR Integration:** Exporting clinical notes in HL7 / FHIR (Fast Healthcare Interoperability Resources) format for direct import into hospital electronic health record systems.
* **Clinician Portal:** A secure clinician-facing dashboard allowing attending physicians to review, sign off on, and append lab results to patient-generated intake notes.
* **File & Lab Result Attachments:** Enabling patients to upload past prescriptions, blood test results, or radiology images into their consultation cases.
* **Two-Factor Authentication (2FA):** Adding TOTP or SMS-based multi-factor authentication for enhanced patient account security.

---

## 15. License

Developed for academic and educational purposes under the MIT License.
