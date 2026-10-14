"""
main.py — Root Entrypoint for DocuMedi FastAPI Backend.
Enables seamless execution whether deployed with Root Directory = 'backend' or repository root.
"""
import sys
import os

backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.main import app  # noqa: F401
