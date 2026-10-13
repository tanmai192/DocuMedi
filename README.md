# DocuMedi — AI-Powered Patient Case-Taking System

> **Tagline:** *Your Health Story, Organized.*

DocuMedi is a modern, AI-powered patient case-taking and personal medical record management platform. It allows patients to describe their health concerns through an intelligent conversational interface, organizes clinical intake data into structured 11-section patient notes, maintains an authenticated medical history timeline, and generates downloadable PDF reports.

---

## 1. Project Architecture & Technology Stack

- **Frontend:** React 18/19 with Vite, React Router, custom CSS design system
- **Backend:** Python FastAPI, Uvicorn (ASGI)
- **Database:** MySQL via PyMySQL and SQLAlchemy 2.0 ORM
- **Security:** Password hashing with `bcrypt` (12 rounds), JWT authentication via `pyjwt`
- **Environment:** Windows 11, VS Code, Python 3.11.9, Node.js v24+

---

## 2. Directory Structure

```text
patient_case_taking/
├── backend/
│   ├── main.py                  # FastAPI app entry point with CORS & routes
│   ├── database.py              # MySQL engine, SessionLocal & get_db dependency
│   ├── models.py                # SQLAlchemy ORM models (patients, cases, messages, notes)
│   ├── schemas.py               # Pydantic v2 validation models
│   ├── security.py              # Bcrypt hashing & PyJWT token utilities
│   ├── dependencies.py          # get_current_patient Bearer authentication dependency
│   ├── routers/
│   │   └── auth.py              # POST /auth/register, POST /auth/login, GET /auth/me
│   ├── init_db.py               # Safe database initialization & inspection
│   ├── test_models.py           # Unit tests for ORM models and relationships
│   ├── test_auth.py             # 10-point authentication test suite
│   ├── test_e2e_frontend.py     # End-to-end integration test (backend + frontend)
│   ├── requirements.txt         # Pinned Python dependencies
│   ├── .env                     # Local credentials (ignored by Git)
│   └── .env.example             # Configuration template
├── frontend/
│   ├── src/
│   │   ├── components/          # Logo, Navbar, ProtectedRoute, PublicRoute
│   │   ├── pages/               # Login, Register, Dashboard, Profile, Placeholders
│   │   ├── context/             # AuthContext (login, logout, session persistence)
│   │   ├── services/            # api.js (centralized fetch wrapper with Bearer token)
│   │   ├── styles/              # index.css (Teal & deep blue design system)
│   │   ├── App.jsx              # Application router & medical disclaimer
│   │   └── main.jsx             # React entry point
│   ├── public/                  # Favicon & assets
│   ├── package.json             # React dependencies & scripts
│   ├── .env                     # VITE_API_BASE_URL (ignored by Git)
│   └── .env.example             # Template for frontend env
├── .gitignore                   # Ignores venv, node_modules, credentials
└── README.md                    # Setup & operational guide
```

---

## 3. Prerequisites

- **Operating System:** Windows 11
- **Python:** Version 3.11+
- **Node.js & npm:** Node.js v20+ / v24+, npm 10+ / 11+
- **MySQL:** Running locally with database `patient_case_system` created

---

## 4. Environment Variables Setup

### Backend (`backend/.env`)
Ensure `backend/.env` exists with the following configuration:
```env
DATABASE_URL=mysql+pymysql://<user>:<password>@localhost:3306/patient_case_system
SECRET_KEY=<a_strong_64_character_random_hex_string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FRONTEND_URL=http://localhost:5173
```

### Frontend (`frontend/.env`)
Ensure `frontend/.env` contains:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 5. Step-by-Step Windows 11 Execution Guide

Open two separate Windows PowerShell terminals in VS Code:

### Terminal 1 — Backend (FastAPI)
```powershell
# 1. Navigate to backend
cd C:\Users\Tanmai\patient_case_taking\backend

# 2. Activate virtual environment
.\venv\Scripts\activate

# 3. (Optional) Run tests to verify backend health & database
python test_auth.py

# 4. Start the FastAPI development server
uvicorn main:app --reload
```
Backend will start on: **`http://127.0.0.1:8000`**

### Terminal 2 — Frontend (React + Vite)
```powershell
# 1. Navigate to frontend
cd C:\Users\Tanmai\patient_case_taking\frontend

# 2. Start the Vite development server (using npm.cmd on PowerShell)
npm.cmd run dev
```
Frontend will be live at: **`http://127.0.0.1:5173`**

---

## 6. Access URLs

| Component | URL | Description |
| :--- | :--- | :--- |
| **DocuMedi Web App** | [http://127.0.0.1:5173](http://127.0.0.1:5173) | Main patient portal |
| **Backend API Health** | [http://127.0.0.1:8000](http://127.0.0.1:8000) | Root health check |
| **Interactive API Docs** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | Swagger UI for testing endpoints |

---

## 7. Troubleshooting

- **PowerShell `npm.ps1` execution policy restriction:**
  If PowerShell shows *running scripts is disabled*, run `npm.cmd` instead of `npm` (e.g., `npm.cmd run dev`).
- **MySQL Connection Refused:**
  Ensure your MySQL server service is started in Windows Services (`services.msc`) and that the credentials in `backend/.env` match your local MySQL root password.
- **CORS Errors:**
  Confirm that `backend/main.py` has `http://localhost:5173` and `http://127.0.0.1:5173` in its allowed origins.
