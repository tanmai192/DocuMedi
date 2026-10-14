DocuMedi

Your Health Story, Organized.

DocuMedi is an AI-assisted patient case-taking and personal health record management web application designed to help users document their health concerns through a conversational interface. It transforms patient-provided information into structured clinical notes, allowing users to review, edit, confirm, and securely access their medical history.

The project focuses on simplifying health documentation through conversational AI while maintaining clarity, accuracy, and user control.

Key Features

User Authentication: Secure registration and login.

AI-Assisted Case Taking: Conversational interface that asks relevant follow-up questions based on the user's responses.

Structured Clinical Notes: Converts collected information into an organized clinical note with 11 sections.

Review and Confirmation: Allows users to review and edit notes before confirming them.

Medical History Timeline: Provides access to previously saved consultation notes.

PDF Export: Allows users to download current and previous clinical notes as PDFs.

Context-Aware Conversations: Avoids unnecessary repeated questions and preserves relevant patient-provided information.

Medication and Allergy Documentation: Records medication and allergy information while distinguishing explicit negative responses from uncertain or missing information.

Technology Stack

Frontend

React.js

Vite

React Router

CSS

Backend

Python

FastAPI

SQLAlchemy

PyMySQL

Database

MySQL

AI Integration

Configurable AI provider

Gemini/OpenAI integration, depending on the configured provider

Rules-based fallback for structured information collection

PDF Generation

ReportLab

pypdf

Application Workflow

The user registers or logs in.

The user starts a new consultation.

The conversational assistant collects relevant health information.

The conversation is processed into a structured clinical note.

The user reviews, edits, and confirms the note.

The confirmed note is stored in the MySQL database.

The user can view previous notes through the medical history timeline.

Current or previous notes can be downloaded as PDF documents.

Design Theme

DocuMedi uses a distinctive, modern color palette:

Black Bean: #3D2528 — primary background

Martini Olive: #8A8B55 — secondary accents

Cotton Candy: #FFB7D5 — highlights and interactive elements

The interface aims to provide a clean, accessible, and user-friendly experience.

Project Structure

patient_case_taking/
├── backend/
│   ├── main.py
│   ├── services/
│   ├── test_auth.py
│   ├── test_cases.py
│   ├── test_notes.py
│   ├── test_timeline.py
│   ├── test_pdf.py
│   ├── test_conversational_ai.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md

The exact structure may vary depending on the files present in the project.

Prerequisites

Install the following before running DocuMedi:

Python 3.11 or a compatible version

Node.js and npm

MySQL Server

MySQL Workbench (optional, for database management)

Visual Studio Code (recommended)

Installation and Setup

1. Clone the repository

git clone <your-repository-url>
cd patient_case_taking

2. Set up the backend

cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt

Create a .env file in the backend directory using .env.example as a reference. Configure the database connection and AI provider settings according to the existing application configuration.

Important: Never commit your .env file, database passwords, API keys, or other secrets to GitHub.

3. Configure the database

Create a MySQL database named:

CREATE DATABASE patient_case_system;

Ensure that the database credentials and connection settings in .env match your local MySQL configuration.

4. Start the backend

From the backend directory, run:

.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

Backend URL: http://127.0.0.1:8000

API documentation: http://127.0.0.1:8000/docs

5. Set up the frontend

Open a separate terminal:

cd frontend
npm install
npm.cmd run dev

Frontend URL: http://localhost:5173

Keep both the backend and frontend running while using the application.

Clinical Documentation and Safety

DocuMedi is designed for health information documentation, not medical diagnosis or treatment.

Clinical notes should be based on information supplied by the user.

Missing information should be recorded as “Not provided” rather than invented.

Uncertain responses should remain distinguishable from confirmed negative responses.

Medication and allergy information should be documented accurately.

Users should be able to review and correct notes before confirming them.

The application should not generate unsupported diagnoses or prescriptions.

Users experiencing a medical emergency should be directed to appropriate emergency services.

Privacy and Security

The project is designed with privacy-conscious development practices, including environment-based configuration for secrets and authenticated access to personal records.

Before production deployment, additional review is required to validate authorization, secure session or token handling, HTTPS, database protection, backups, logging practices, and applicable health-data privacy requirements.

Use fictional data during development and testing. Do not upload real patient information to a public deployment until appropriate privacy and security safeguards are in place.

Testing

Run the existing backend tests from the backend directory using the project's configured Python environment. For example:

.\venv\Scripts\python.exe -m pytest

Build the frontend to check for production compilation errors:

cd frontend
npm.cmd run build

The test commands and test coverage should be verified against the files and dependencies available in the repository.

Future Enhancements

Improved multilingual conversational support

Additional export formats

Enhanced accessibility

More comprehensive automated testing

Improved patient-controlled data export and deletion

Production-ready deployment and security hardening

Project Objective

DocuMedi aims to make personal health documentation more organized, accessible, and user-friendly through conversational AI and structured clinical note generation.

DocuMedi — Your Health Story, Organized.