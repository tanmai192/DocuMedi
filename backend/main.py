"""
main.py — FastAPI Application Entry Point for DocuMedi.
DocuMedi: Your Health Story, Organized.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers import auth, cases

load_dotenv()

app = FastAPI(
    title="DocuMedi API",
    description="DocuMedi: AI-Powered Patient Case-Taking and Personal Medical Record Management Platform",
    version="1.0.0"
)

# Configure CORS for local React development
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in origins:
    origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router)
app.include_router(cases.router)



@app.get("/", tags=["Health"])
def home():
    """Health-check endpoint confirming the backend service is running."""
    return {
        "app": "DocuMedi",
        "tagline": "Your Health Story, Organized.",
        "status": "online",
        "message": "DocuMedi Backend is running!"
    }