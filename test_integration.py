"""
CyberSahay Integration & Verification Test Suite
Tests all endpoints, authentication, database persistence, multi-agent RAG, FIR generation, and PDF export.
"""

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_system_endpoints():
    print("\n[1] Testing System Endpoints...")
    res = client.get("/")
    assert res.status_code == 200, f"Root failed: {res.text}"
    data = res.json()
    assert data["success"] is True
    print("  [OK] GET / passed")

    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    assert res.json()["status"] == "ok"
    print("  [OK] GET /health passed")


def test_auth_workflow():
    print("\n[2] Testing Authentication Workflow...")
    email = f"victim_test_{int(__import__('time').time())}@cybersahay.org"
    password = "SecurePassword123!"

    # 1. Register
    reg_payload = {
        "name": "Aarav Sharma",
        "email": email,
        "phone": "9876543210",
        "password": password,
        "emergency_contact": "9123456789 (Brother)",
    }
    res = client.post("/auth/register", json=reg_payload)
    assert res.status_code == 201, f"Register failed: {res.text}"
    reg_data = res.json()
    assert reg_data["success"] is True
    assert "access_token" in reg_data
    token = reg_data["access_token"]
    print("  [OK] POST /auth/register passed")

    # 2. Login
    login_payload = {
        "email": email,
        "password": password,
    }
    res = client.post("/auth/login", json=login_payload)
    assert res.status_code == 200, f"Login failed: {res.text}"
    login_data = res.json()
    assert login_data["success"] is True
    assert login_data["user"]["name"] == "Aarav Sharma"
    print("  [OK] POST /auth/login passed")

    # 3. Get /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/auth/me", headers=headers)
    assert res.status_code == 200, f"Get /auth/me failed: {res.text}"
    profile = res.json()
    assert profile["user"]["email"] == email
    print("  [OK] GET /auth/me passed")

    # 4. Update Profile
    update_payload = {
        "emergency_contact": "9988776655 (Father)",
    }
    res = client.put("/auth/profile", json=update_payload, headers=headers)
    assert res.status_code == 200, f"Update profile failed: {res.text}"
    assert res.json()["user"]["emergency_contact"] == "9988776655 (Father)"
    print("  [OK] PUT /auth/profile passed")

    return token, email


def test_emergency_suite():
    print("\n[3] Testing Emergency Victim Advisory Suite...")

    # 1. Helplines
    res = client.get("/emergency/helplines")
    assert res.status_code == 200
    helplines = res.json()
    assert len(helplines) >= 5
    assert any(h["number"] == "1930" for h in helplines)
    print("  [OK] GET /emergency/helplines passed")

    # 2. Checklists
    res = client.get("/emergency/checklists")
    assert res.status_code == 200
    checklists = res.json()
    assert len(checklists) >= 3
    print("  [OK] GET /emergency/checklists passed")

    # 3. Panic Triage
    triage_payload = {
        "incident_type": "upi_fraud",
        "time_elapsed_hours": 0.75,
        "amount_lost": 30000.0,
        "bank_name": "HDFC Bank",
    }
    res = client.post("/emergency/panic-triage", json=triage_payload)
    assert res.status_code == 200
    triage_data = res.json()
    assert triage_data["urgency_level"] == "CRITICAL - GOLDEN HOUR"
    assert "1930" in triage_data["helpline_numbers"]
    print("  [OK] POST /emergency/panic-triage passed")


def test_chat_persistence(token: str):
    print("\n[4] Testing AI Chat & DB Persistence...")
    session_id = f"test-sess-{int(__import__('time').time())}"
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Send Chat Request
    chat_payload = {
        "session_id": session_id,
        "message": "Someone sent me a fraudulent APK file pretending to be electricity bill update and deducted money.",
    }
    res = client.post("/chat/", json=chat_payload, headers=headers)
    assert res.status_code == 200, f"Chat failed: {res.text}"
    chat_data = res.json()
    assert chat_data["success"] is True
    assert "response" in chat_data["data"]
    print(f"  [OK] POST /chat/ response generated (Intent: {chat_data['data']['intent']}, Workflow: {chat_data['data']['workflow']})")

    # 2. Verify Session listed in /chat/sessions
    res = client.get("/chat/sessions", headers=headers)
    assert res.status_code == 200
    sessions = res.json()
    assert any(s["session_id"] == session_id for s in sessions)
    print("  [OK] GET /chat/sessions persistent record verified")

    # 3. Verify Messages in /chat/sessions/{session_id}/messages
    res = client.get(f"/chat/sessions/{session_id}/messages", headers=headers)
    assert res.status_code == 200
    messages = res.json()
    assert len(messages) >= 2  # user + assistant
    print("  [OK] GET /chat/sessions/{id}/messages verified")


def test_fir_workflow_and_pdf(token: str):
    print("\n[5] Testing FIR Generation & PDF Download...")
    session_id = f"fir-sess-{int(__import__('time').time())}"
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Start FIR
    res = client.post("/fir/start", json={"session_id": session_id}, headers=headers)
    assert res.status_code == 200
    fir_start = res.json()
    assert fir_start["success"] is True
    print("  [OK] POST /fir/start initiated")

    # 2. Continue FIR with complainant name
    res = client.post(
        "/fir/continue",
        json={"session_id": session_id, "answer": "Rajesh Kumar"},
        headers=headers,
    )
    assert res.status_code == 200
    print("  [OK] POST /fir/continue step 1 passed")

    # 3. Check status
    res = client.get(f"/fir/status/{session_id}")
    assert res.status_code == 200
    status_data = res.json()
    assert status_data["success"] is True
    print("  [OK] GET /fir/status passed")

    # 4. Check user's FIRs list
    res = client.get("/fir/my-firs", headers=headers)
    assert res.status_code == 200
    firs = res.json()
    assert any(f["session_id"] == session_id for f in firs)
    print("  [OK] GET /fir/my-firs verified")

    # 5. Download PDF
    res = client.get(f"/fir/download-pdf/{session_id}", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("content-type") == "application/pdf"
    assert len(res.content) > 500  # valid PDF binary stream
    print(f"  [OK] GET /fir/download-pdf generated valid PDF ({len(res.content)} bytes)")


if __name__ == "__main__":
    print("=" * 60)
    print("Starting CyberSahay Integration Verification")
    print("=" * 60)

    test_system_endpoints()
    token, email = test_auth_workflow()
    test_emergency_suite()
    test_chat_persistence(token)
    test_fir_workflow_and_pdf(token)

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY! [PASSED]")
    print("=" * 60)
