"""
main.py — FastAPI Application Entry Point for DocuMedi.
DocuMedi: Your Health Story, Organized.
"""

import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from dotenv import load_dotenv

load_dotenv()
backend_env = os.path.join(backend_dir, ".env")
if os.path.exists(backend_env):
    load_dotenv(backend_env)

from routers import auth, cases, notes

app = FastAPI(
    title="DocuMedi API",
    description="DocuMedi: AI-Powered Patient Case-Taking and Personal Medical Record Management Platform",
    version="1.0.0"
)

# Allowed Origins for Local Development and Production Deployments
default_origins = [
    # Local Vite & CRA Dev Servers
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Vercel Production & Preview Deployments
    "https://docu-medi-git-main-tanmai2.vercel.app",
    "https://docu-medi-9m37rn7jh-tanmai2.vercel.app",
    "https://docu-medi.vercel.app",
]

# Parse additional origins from FRONTEND_URL or ADDITIONAL_CORS_ORIGINS (supports comma-separated list)
configured_origins = (os.getenv("FRONTEND_URL", "") + "," + os.getenv("ADDITIONAL_CORS_ORIGINS", "")).split(",")
origins = list(default_origins)

for entry in configured_origins:
    clean_origin = entry.strip().rstrip("/")
    if clean_origin and clean_origin not in origins:
        origins.append(clean_origin)

# Register CORS Middleware
# allow_origin_regex permits any preview deployments matching https://docu-medi*.vercel.app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https:\/\/docu-medi.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
    max_age=600,
)


@app.on_event("startup")
def on_startup():
    """Safely verify and create database tables on startup if they do not exist."""
    try:
        from database import Base, engine
        import models  # Register ORM models
        if engine:
            Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        print(f"Notice: Initial table verification encountered an issue: {e}")


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    """Handle database connection failures with a clean, descriptive JSON response."""
    return JSONResponse(
        status_code=503,
        content={"detail": "Database connection error. Please ensure the database server is running and accessible."}
    )


@app.exception_handler(SQLAlchemyError)
async def db_general_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle general database errors without exposing stack traces or sensitive schema details."""
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred while processing your request. Please try again later."}
    )


# Register API Routers
app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(notes.router)


@app.get("/", tags=["Health"])
def home():
    """Health-check endpoint confirming the backend service is running."""
    return {
        "app": "DocuMedi",
        "tagline": "Your Health Story, Organized.",
        "status": "online",
        "message": "DocuMedi Backend is running!"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """
    Detailed health check: verifies application status and database connectivity
    without exposing sensitive credentials, hostnames, or secrets.
    """
    from database import engine
    from sqlalchemy import text

    db_status = "connected"
    detail = "All systems operational"

    if not engine:
        db_status = "unconfigured"
        detail = "DATABASE_URL is not configured."
    else:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            import re
            db_status = "disconnected"
            clean_err = re.sub(r":([^:@\s]{2,})@", ":****@", str(e))
            detail = f"Database connection failed: {clean_err}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "detail": detail,
    }