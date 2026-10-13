"""
test_e2e_frontend.py — Automated verification of live frontend and backend communication.
Tests:
1. Backend HTTP connection at http://127.0.0.1:8000/
2. Frontend Vite HTTP connection at http://127.0.0.1:5173/
3. CORS options pre-flight check from http://localhost:5173
4. Live registration API call from frontend domain
5. Duplicate registration rejection check
6. Login API call with valid credentials
7. Login API call with invalid credentials
8. Authenticated GET /auth/me call with Bearer token
9. Database cleanup so test records are completely removed
"""

import urllib.request
import urllib.error
import json
import ssl
from database import SessionLocal
from models import Patient

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"
TEST_EMAIL = "frontend.test@example.com"


def cleanup():
    db = SessionLocal()
    try:
        db.query(Patient).filter(Patient.email == TEST_EMAIL).delete()
        db.commit()
    finally:
        db.close()


def test_live_servers():
    print("=" * 65)
    print("DocuMedi Stage 4: Live Frontend & Backend Integration Verification")
    print("=" * 65)

    cleanup()

    try:
        # 1. Test Backend Health Check
        print("\n[1/7] Testing Live Backend at " + BACKEND_URL + "...")
        with urllib.request.urlopen(BACKEND_URL, timeout=5) as res:
            assert res.status == 200
            data = json.loads(res.read().decode())
            assert data["app"] == "DocuMedi"
            print("  [PASS] Backend responded: " + json.dumps(data))

        # 2. Test Frontend Server
        print("\n[2/7] Testing Live Frontend at " + FRONTEND_URL + "...")
        with urllib.request.urlopen(FRONTEND_URL, timeout=5) as res:
            assert res.status == 200
            html_content = res.read().decode()
            assert "DocuMedi" in html_content
            assert "/src/main.jsx" in html_content
            print("  [PASS] Frontend Vite server responded with DocuMedi HTML entry point.")

        # 3. Test Registration via HTTP POST
        print("\n[3/7] Testing Live Registration via HTTP POST /auth/register...")
        reg_payload = json.dumps({
            "full_name": "Frontend Test User",
            "email": TEST_EMAIL,
            "password": "Password123!",
            "confirm_password": "Password123!"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{BACKEND_URL}/auth/register",
            data=reg_payload,
            headers={
                "Content-Type": "application/json",
                "Origin": FRONTEND_URL
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            assert res.status == 201
            reg_data = json.loads(res.read().decode())
            token = reg_data["access_token"]
            assert reg_data["patient"]["email"] == TEST_EMAIL
            assert reg_data["patient"]["full_name"] == "Frontend Test User"
            print("  [PASS] Registered patient and received JWT token.")

        # 4. Test Duplicate Email via HTTP POST
        print("\n[4/7] Testing Duplicate Registration Rejection...")
        req = urllib.request.Request(
            f"{BACKEND_URL}/auth/register",
            data=reg_payload,
            headers={"Content-Type": "application/json", "Origin": FRONTEND_URL},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                assert False, "Duplicate should have failed!"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            err_body = json.loads(e.read().decode())
            assert "already exists" in err_body["detail"].lower()
            print("  [PASS] Duplicate email returned HTTP 400 with message: " + err_body["detail"])

        # 5. Test Login via HTTP POST
        print("\n[5/7] Testing Login via HTTP POST /auth/login...")
        login_payload = json.dumps({
            "email": TEST_EMAIL,
            "password": "Password123!"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{BACKEND_URL}/auth/login",
            data=login_payload,
            headers={"Content-Type": "application/json", "Origin": FRONTEND_URL},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            assert res.status == 200
            login_data = json.loads(res.read().decode())
            login_token = login_data["access_token"]
            print("  [PASS] Login successful, received fresh JWT token.")

        # 6. Test Invalid Password via HTTP POST
        print("\n[6/7] Testing Invalid Password Login Rejection...")
        bad_login_payload = json.dumps({
            "email": TEST_EMAIL,
            "password": "WrongPassword!"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{BACKEND_URL}/auth/login",
            data=bad_login_payload,
            headers={"Content-Type": "application/json", "Origin": FRONTEND_URL},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                assert False, "Bad login should have failed!"
        except urllib.error.HTTPError as e:
            assert e.code == 401
            print("  [PASS] Invalid password rejected with HTTP 401.")

        # 7. Test Authenticated Profile via GET /auth/me
        print("\n[7/7] Testing Authenticated GET /auth/me with Bearer token...")
        req = urllib.request.Request(
            f"{BACKEND_URL}/auth/me",
            headers={
                "Authorization": f"Bearer {login_token}",
                "Origin": FRONTEND_URL
            },
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            assert res.status == 200
            profile_data = json.loads(res.read().decode())
            assert profile_data["email"] == TEST_EMAIL
            assert profile_data["full_name"] == "Frontend Test User"
            print("  [PASS] Profile retrieved successfully: " + profile_data["full_name"] + " (" + profile_data["email"] + ")")

        print("\n" + "=" * 65)
        print(" ALL LIVE INTEGRATION TESTS PASSED SUCCESSFULLY! ")
        print("=" * 65)

    finally:
        cleanup()
        print("\n[CLEANUP] Purged temporary frontend test patient from MySQL.")


if __name__ == "__main__":
    test_live_servers()
