"""
test_production_connection.py — Regression Test Suite for Production Backend Connection,
CORS Preflight, and Health Check Diagnostics for DocuMedi.
"""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Patient

client = TestClient(app)

TEST_EMAIL = "prod.connection.test@example.com"


def cleanup():
    db = SessionLocal()
    try:
        db.query(Patient).filter(Patient.email == TEST_EMAIL).delete()
        db.commit()
    finally:
        db.close()


def test_production_cors_and_endpoints():
    print("=" * 70)
    print("DocuMedi: Production Backend Connection & CORS Preflight Test Suite")
    print("=" * 70)

    try:
        # 1. Health check endpoints
        print("\n[1/6] Testing GET / (Root Service Probe)...")
        r_root = client.get("/")
        assert r_root.status_code == 200, f"Root failed: {r_root.text}"
        data_root = r_root.json()
        assert data_root["status"] == "online"
        assert "DocuMedi" in data_root["app"]
        print("  [PASS] Root endpoint returned 200 with online status.")

        print("\n[2/6] Testing GET /health (Detailed Health & DB Probe)...")
        r_health = client.get("/health")
        assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
        data_health = r_health.json()
        assert data_health["status"] in ("healthy", "degraded")
        assert "database" in data_health
        assert "password" not in r_health.text.lower()
        assert "mysql://" not in r_health.text.lower()
        print(f"  [PASS] /health returned status '{data_health['status']}', DB '{data_health['database']}' without exposing secrets.")

        # 2. CORS Preflight Testing for Vercel Domains
        print("\n[3/6] Testing CORS Preflight (OPTIONS) for all Vercel Production & Preview Domains...")
        vercel_origins = [
            "https://docu-medi-git-main-tanmai2.vercel.app",
            "https://docu-medi-9m37rn7jh-tanmai2.vercel.app",
            "https://docu-medi.vercel.app",
            "https://docu-medi-preview-feature.vercel.app",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

        endpoints_to_probe = ["/auth/register", "/auth/login", "/cases", "/notes"]

        for origin in vercel_origins:
            for ep in endpoints_to_probe:
                res = client.options(ep, headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type, Authorization",
                })
                assert res.status_code == 200, f"OPTIONS {ep} failed for origin {origin}: {res.status_code} {res.text}"
                assert res.headers.get("access-control-allow-origin") == origin, f"Mismatched allow-origin: {res.headers}"
                assert res.headers.get("access-control-allow-credentials") == "true", "Credentials must be allowed"
            print(f"  [PASS] Origin: {origin} successfully allowed across all endpoints.")

        # 3. Registration with Invalid Input
        print("\n[4/6] Testing POST /auth/register with invalid data...")
        r_inv = client.post("/auth/register", json={
            "full_name": "A",
            "email": "not-an-email",
            "password": "123",
            "confirm_password": "456",
        })
        assert r_inv.status_code == 422, f"Expected 422, got {r_inv.status_code}"
        print("  [PASS] Validation errors correctly returned as structured JSON 422.")

        # 4. Registration with Valid Input
        print("\n[5/6] Testing POST /auth/register with valid credentials...")
        r_reg = client.post("/auth/register", json={
            "full_name": "Production Test Patient",
            "email": TEST_EMAIL,
            "password": "Password123!",
            "confirm_password": "Password123!",
        })
        assert r_reg.status_code == 201, f"Expected 201, got {r_reg.status_code}: {r_reg.text}"
        reg_data = r_reg.json()
        assert "access_token" in reg_data
        assert reg_data["patient"]["email"] == TEST_EMAIL
        print("  [PASS] Valid registration succeeded with 201 and issued JWT bearer token.")

        # 5. Clean Duplicate Registration Check
        print("\n[6/6] Testing POST /auth/register with duplicate email...")
        r_dup = client.post("/auth/register", json={
            "full_name": "Duplicate Test Patient",
            "email": TEST_EMAIL,
            "password": "Password123!",
            "confirm_password": "Password123!",
        })
        assert r_dup.status_code == 400, f"Expected 400, got {r_dup.status_code}"
        assert "already exists" in r_dup.json()["detail"].lower()
        print("  [PASS] Duplicate registration rejected with friendly 400 detail message.")

        print("\n" + "=" * 70)
        print("SUCCESS: ALL PRODUCTION CONNECTION & CORS TESTS PASSED!")
        print("=" * 70)

    finally:
        cleanup()
        print("[OK] Cleaned up temporary test patient from MySQL.")


if __name__ == "__main__":
    test_production_cors_and_endpoints()
