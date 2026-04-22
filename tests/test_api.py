"""
Five required pytest tests for the SkillBridge Attendance API.
All tests hit the real SQLite test database (no mocked DB).
"""
import uuid
import pytest
from fastapi.testclient import TestClient


# ─── helpers ─────────────────────────────────────────────────────────────────

def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}@test.sb"


def signup(client: TestClient, name: str, email: str, password: str, role: str, institution_id: str = None) -> dict:
    payload = {"name": name, "email": email, "password": password, "role": role}
    if institution_id:
        payload["institution_id"] = institution_id
    resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 201, f"signup failed: {resp.text}"
    return resp.json()


def login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Test 1: Student signup and login return a valid JWT ─────────────────────

def test_student_signup_and_login(client: TestClient):
    """Successful student signup and login; asserts a non-empty JWT is returned."""
    email = unique_email("student")
    password = "SecurePass1!"

    # Signup
    signup_resp = client.post(
        "/auth/signup",
        json={"name": "Test Student", "email": email, "password": password, "role": "student"},
    )
    assert signup_resp.status_code == 201
    signup_data = signup_resp.json()
    assert "access_token" in signup_data
    assert len(signup_data["access_token"]) > 20

    # Login with the same credentials
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    assert len(login_data["access_token"]) > 20

    # Tokens are valid JWT strings (three dot-separated parts)
    for token in [signup_data["access_token"], login_data["access_token"]]:
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have three dot-separated parts"


# ─── Test 2: Trainer creates a session with all required fields ───────────────

def test_trainer_creates_session(client: TestClient):
    """A trainer can create a session with all required fields."""
    # Create institution
    inst_email = unique_email("inst")
    inst_data = signup(client, "Test Inst", inst_email, "Pass123!", "institution")
    inst_token = login(client, inst_email, "Pass123!")

    # Get institution id from token payload (decode without verify just to read sub)
    import jwt as pyjwt
    payload = pyjwt.decode(inst_data["access_token"], options={"verify_signature": False})
    inst_id = payload["user_id"]

    # Create trainer under that institution
    tr_email = unique_email("trainer")
    signup(client, "Test Trainer", tr_email, "Pass123!", "trainer", institution_id=inst_id)
    tr_token = login(client, tr_email, "Pass123!")

    # Create a batch (as institution)
    batch_resp = client.post(
        "/batches",
        json={"name": "Test Batch", "institution_id": inst_id},
        headers=auth_header(inst_token),
    )
    assert batch_resp.status_code == 201
    batch_id = batch_resp.json()["id"]

    # Assign trainer to batch via BatchTrainer — done automatically on trainer batch creation,
    # so create a batch as trainer instead
    batch_resp2 = client.post(
        "/batches",
        json={"name": "Trainer Batch", "institution_id": inst_id},
        headers=auth_header(tr_token),
    )
    assert batch_resp2.status_code == 201
    tr_batch_id = batch_resp2.json()["id"]

    # Create session
    sess_resp = client.post(
        "/sessions",
        json={
            "title": "Intro to Python",
            "date": "2025-09-01",
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "batch_id": tr_batch_id,
        },
        headers=auth_header(tr_token),
    )
    assert sess_resp.status_code == 201, f"session creation failed: {sess_resp.text}"
    data = sess_resp.json()
    assert data["title"] == "Intro to Python"
    assert data["batch_id"] == tr_batch_id


# ─── Test 3: Student marks their own attendance ───────────────────────────────

def test_student_marks_attendance(client: TestClient):
    """A student enrolled in a batch can mark attendance for a session in that batch."""
    import jwt as pyjwt

    # Institution
    inst_email = unique_email("inst2")
    inst_data = signup(client, "Inst 2", inst_email, "Pass123!", "institution")
    inst_token = login(client, inst_email, "Pass123!")
    inst_id = pyjwt.decode(inst_data["access_token"], options={"verify_signature": False})["user_id"]

    # Trainer
    tr_email = unique_email("trainer2")
    signup(client, "Trainer 2", tr_email, "Pass123!", "trainer", institution_id=inst_id)
    tr_token = login(client, tr_email, "Pass123!")

    # Trainer creates batch (auto-assigned)
    batch_resp = client.post(
        "/batches",
        json={"name": "Attendance Test Batch", "institution_id": inst_id},
        headers=auth_header(tr_token),
    )
    assert batch_resp.status_code == 201
    batch_id = batch_resp.json()["id"]

    # Trainer creates session
    sess_resp = client.post(
        "/sessions",
        json={
            "title": "Test Session",
            "date": "2025-09-02",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "batch_id": batch_id,
        },
        headers=auth_header(tr_token),
    )
    assert sess_resp.status_code == 201
    session_id = sess_resp.json()["id"]

    # Trainer creates invite
    invite_resp = client.post(
        f"/batches/{batch_id}/invite",
        json={"expires_in_hours": 48},
        headers=auth_header(tr_token),
    )
    assert invite_resp.status_code == 201
    invite_token = invite_resp.json()["token"]

    # Student signs up and joins via invite
    st_email = unique_email("student2")
    signup(client, "Student 2", st_email, "Pass123!", "student")
    st_token = login(client, st_email, "Pass123!")

    join_resp = client.post(
        "/batches/join",
        json={"token": invite_token},
        headers=auth_header(st_token),
    )
    assert join_resp.status_code == 200

    # Student marks attendance
    attend_resp = client.post(
        "/attendance/mark",
        json={"session_id": session_id, "status": "present"},
        headers=auth_header(st_token),
    )
    assert attend_resp.status_code == 201, f"attendance mark failed: {attend_resp.text}"
    data = attend_resp.json()
    assert data["status"] == "present"
    assert data["session_id"] == session_id


# ─── Test 4: POST /monitoring/attendance returns 405 ─────────────────────────

def test_post_to_monitoring_attendance_returns_405(client: TestClient):
    """POST /monitoring/attendance must return 405 Method Not Allowed."""
    resp = client.post("/monitoring/attendance", json={})
    assert resp.status_code == 405, f"Expected 405, got {resp.status_code}: {resp.text}"


# ─── Test 5: Protected endpoint with no token returns 401 ────────────────────

def test_no_token_returns_401(client: TestClient):
    """Requests to protected endpoints without an Authorization header return 401."""
    protected_endpoints = [
        ("POST", "/sessions", {"title": "x", "date": "2025-01-01", "start_time": "09:00:00", "end_time": "10:00:00", "batch_id": "fake"}),
        ("POST", "/attendance/mark", {"session_id": "fake", "status": "present"}),
        ("GET", "/monitoring/attendance", None),
    ]
    for method, path, body in protected_endpoints:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=body)
        assert resp.status_code == 401, (
            f"Expected 401 on {method} {path} without token, got {resp.status_code}"
        )
