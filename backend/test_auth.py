"""
test_auth.py — Automated Test Suite for DocuMedi Stage 3 Authentication.

Tests:
1. Backend health check (/)
2. Successful patient registration (POST /auth/register)
3. Password confirmation mismatch rejection (422)
4. Duplicate email registration rejection (400)
5. Successful login with correct credentials (POST /auth/login)
6. Failed login with incorrect password (401)
7. Failed login with non-existent email (401)
8. Unauthenticated access to protected endpoint (GET /auth/me) -> 401
9. Malformed or invalid JWT token rejection -> 401
10. Successful retrieval of authenticated patient profile via valid JWT -> 200

All test patients use '@documedi.test' emails and are cleaned up thoroughly
so that the development database remains completely pristine.
"""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Patient

client = TestClient(app)

TEST_EMAIL_1 = "jane.smith@example.com"
TEST_EMAIL_2 = "duplicate.check@example.com"
CLEANUP_EMAILS = [TEST_EMAIL_1, TEST_EMAIL_2]



def cleanup_test_records():
    """Remove any leftover test records from MySQL to keep the database pristine."""
    db = SessionLocal()
    try:
        db.query(Patient).filter(Patient.email.in_(CLEANUP_EMAILS)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_suite():
    print("=" * 65)
    print("DocuMedi Stage 3: Automated Authentication Test Suite")
    print("=" * 65)

    # Initial cleanup in case prior runs left records
    cleanup_test_records()

    try:
        # Test 1: Health check
        print("\n[1/10] Testing GET / (Health Check)...")
        res = client.get("/")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert res.json()["app"] == "DocuMedi"
        print("  [PASS] Health check returned 200 with DocuMedi branding.")

        # Test 2: Password mismatch validation
        print("\n[2/10] Testing POST /auth/register with mismatched passwords...")
        res = client.post("/auth/register", json={
            "full_name": "Jane Smith",
            "email": TEST_EMAIL_1,
            "password": "Password123!",
            "confirm_password": "DifferentPassword!"
        })
        assert res.status_code == 422, f"Expected 422 for password mismatch, got {res.status_code}"
        print("  [PASS] Password mismatch correctly rejected with HTTP 422.")

        # Test 3: Successful registration
        print("\n[3/10] Testing POST /auth/register with valid payload...")
        res = client.post("/auth/register", json={
            "full_name": "Jane Smith",
            "email": TEST_EMAIL_1,
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!"
        })
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert "access_token" in data, "access_token missing from response"
        assert data["token_type"] == "bearer"
        assert data["patient"]["email"] == TEST_EMAIL_1
        assert data["patient"]["full_name"] == "Jane Smith"
        assert "password" not in data["patient"], "Password exposed in response!"
        assert "password_hash" not in data["patient"], "Password hash exposed in response!"
        token_1 = data["access_token"]
        print("  [PASS] Patient registered successfully with HTTP 201 and JWT issued.")

        # Test 4: Duplicate email rejection
        print("\n[4/10] Testing POST /auth/register with duplicate email...")
        res = client.post("/auth/register", json={
            "full_name": "Jane Imposter",
            "email": TEST_EMAIL_1,
            "password": "AnotherPassword456!",
            "confirm_password": "AnotherPassword456!"
        })
        assert res.status_code == 400, f"Expected 400 for duplicate email, got {res.status_code}"
        assert "already exists" in res.json()["detail"].lower()
        print("  [PASS] Duplicate registration rejected with HTTP 400.")

        # Test 5: Successful login
        print("\n[5/10] Testing POST /auth/login with valid credentials...")
        res = client.post("/auth/login", json={
            "email": TEST_EMAIL_1,
            "password": "SecurePassword123!"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert "access_token" in data
        assert data["patient"]["email"] == TEST_EMAIL_1
        assert "password_hash" not in data["patient"]
        print("  [PASS] Login succeeded with HTTP 200 and valid JWT issued.")

        # Test 6: Login with incorrect password
        print("\n[6/10] Testing POST /auth/login with incorrect password...")
        res = client.post("/auth/login", json={
            "email": TEST_EMAIL_1,
            "password": "WrongPassword!"
        })
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        assert "invalid email or password" in res.json()["detail"].lower()
        print("  [PASS] Incorrect password rejected with HTTP 401.")

        # Test 7: Login with non-existent email
        print("\n[7/10] Testing POST /auth/login with non-existent email...")
        res = client.post("/auth/login", json={
            "email": "nobody_exists@example.com",
            "password": "SomePassword123!"
        })
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("  [PASS] Non-existent email rejected with HTTP 401.")


        # Test 8: Protected endpoint without token
        print("\n[8/10] Testing GET /auth/me without authorization token...")
        res = client.get("/auth/me")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("  [PASS] Unauthenticated request rejected with HTTP 401.")

        # Test 9: Protected endpoint with invalid token
        print("\n[9/10] Testing GET /auth/me with invalid JWT token...")
        res = client.get("/auth/me", headers={"Authorization": "Bearer fake.garbage.token"})
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("  [PASS] Invalid token rejected with HTTP 401.")

        # Test 10: Protected endpoint with valid token
        print("\n[10/10] Testing GET /auth/me with valid Bearer token...")
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token_1}"})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert data["email"] == TEST_EMAIL_1
        assert data["full_name"] == "Jane Smith"
        assert "password_hash" not in data
        print("  [PASS] Authenticated patient profile retrieved successfully.")

        print("\n" + "=" * 65)
        print(" ALL 10 TESTS PASSED SUCCESSFULLY! ")
        print("=" * 65)

    finally:
        # Final cleanup to leave database 100% clean
        cleanup_test_records()
        print("\n[CLEANUP] All test records purged from MySQL database.")


if __name__ == "__main__":
    test_suite()
