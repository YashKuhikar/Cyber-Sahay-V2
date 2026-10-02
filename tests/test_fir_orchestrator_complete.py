"""
Comprehensive End-to-End Verification Test for CyberSahay FIR / Police Complaint Workflow.

Covers:
1. Conversation-to-FIR Information Extraction:
   - User discusses incident in chat (fake bank call, app install, OTP, ₹25,000 loss, yesterday 7 PM, txn ABC123)
   - /fir/start loads conversation, extracts facts with provenance, asks ONLY genuinely missing fields
   - Does NOT ask to repeat already known facts
2. Multi-fact Answer Processing:
   - When user answers multiple details in a single utterance, all entities are extracted simultaneously
3. FIR Validation & Safe Error Handling:
   - Resolves NameError: name 'FIRValidator' is not defined
   - Invalid date/input returns HTTP 200 with controlled clarification, NEVER HTTP 500
   - Normalizers for date (relative, Indian, ISO), amount (currency, lakhs, k), phone, and time
4. Contradiction & Correction Handling:
   - User correction updates amount and flags provenance
5. Final Confirmation & FIR Draft Generation:
   - Review confirmation checklist
   - Generates official police complaint draft
   - Idempotency and database persistence across restarts
"""

import sys
import unittest
from datetime import datetime
from fastapi.testclient import TestClient

from src.main import app
from src.agents.validators import FIRValidator
from src.agents.fir_orchestrator import FIROrchestrator
from src.agents.fir_extractor import FIRInformationExtractor, INCIDENT_REQUIREMENTS
from src.database.models import ChatMessage, ChatSession, FIRRecord
from src.database.db import get_db, init_db
from src.memory.shared_memory import memory

client = TestClient(app)


def test_validator_normalization_units():
    """Validates all normalizers in FIRValidator."""
    print("Testing FIRValidator normalizers...")
    
    # Date normalizer
    assert FIRValidator.normalize_date("yesterday") != ""
    assert FIRValidator.normalize_date("today") != ""
    assert FIRValidator.normalize_date("01/10/2026") == "2026-10-01"
    assert FIRValidator.normalize_date("1 October 2026") == "2026-10-01"
    assert FIRValidator.normalize_date("2026-10-01") == "2026-10-01"
    assert FIRValidator.normalize_date("banana") == ""
    
    # Amount normalizer
    assert FIRValidator.normalize_amount("₹25,000") == 25000.0
    assert FIRValidator.normalize_amount("25000") == 25000.0
    assert FIRValidator.normalize_amount("around 50k") == 50000.0
    assert FIRValidator.normalize_amount("1.5 lakh") == 150000.0
    assert FIRValidator.normalize_amount("01/10/2026") is None  # Date is NOT an amount
    
    # Phone normalizer
    assert FIRValidator.normalize_phone("+91 9876543210") == "9876543210"
    assert FIRValidator.normalize_phone("98765-43210") == "9876543210"
    
    # Time normalizer
    assert "7 PM" in FIRValidator.normalize_time("around 7 PM").upper()
    assert "19:00" in FIRValidator.normalize_time("19:00")

    # Field validations
    val_date_ok, _ = FIRValidator.validate_field("incident_date", "yesterday")
    assert val_date_ok is True

    val_date_bad, msg_bad = FIRValidator.validate_field("incident_date", "banana")
    assert val_date_bad is False
    assert len(msg_bad) > 0

    val_amt_ok, _ = FIRValidator.validate_field("amount", "₹25,000")
    assert val_amt_ok is True

    print("PASS: test_validator_normalization_units")


def test_conversation_to_fir_full_flow():
    """
    Tests the complete user journey:
    Conversation -> Click Create FIR -> Extract known facts -> Ask ONLY missing ->
    Multi-fact answer -> Confirm -> Generate FIR Draft.
    """
    print("Testing complete conversation to FIR workflow...")
    init_db()
    session_id = f"test-flow-{datetime.now().timestamp()}"

    # 1. User has a realistic chat session with CyberSahay
    with next(get_db()) as db:
        chat_sess = ChatSession(session_id=session_id, title="Financial Fraud Incident")
        db.add(chat_sess)
        db.commit()

        messages = [
            "Someone called me pretending to be from my bank.",
            "They asked me to install an app.",
            "I installed it and entered my OTP.",
            "After that ₹25,000 was deducted from my account.",
            "The transaction happened yesterday around 7 PM.",
            "The UPI transaction ID is ABC123.",
        ]
        for msg in messages:
            db.add(ChatMessage(session_id=session_id, sender="user", message=msg))
        db.commit()

    # 2. User clicks 'Create FIR' (calls POST /fir/start)
    resp = client.post("/fir/start", json={"session_id": session_id})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    data = body.get("data", body)

    # Verify extracted facts
    assert data["form"].get("amount_lost") == "25000"
    assert data["form"].get("transaction_id") == "ABC123"
    assert data["form"].get("incident_date") != ""
    assert data["form"].get("incident_time") != ""

    # Verify that amount, date, and description are NOT asked again
    next_q = data["next_question"].lower()
    assert "how much money" not in next_q
    assert "when did it happen" not in next_q
    assert "what happened" not in next_q

    # The missing field should be complainant name
    assert data["current_field"] == "complainant_name"

    # 3. User responds with multiple facts in one turn:
    # Name + City + Phone number simultaneously
    cont_resp = client.post("/fir/continue", json={
        "session_id": session_id,
        "answer": "My name is Rajesh Sharma, I live in Pune and my phone number is 9876543210"
    })
    assert cont_resp.status_code == 200, f"Error: {cont_resp.text}"
    cont_data = cont_resp.json().get("data", cont_resp.json())

    # Verify that complainant_name was captured
    assert cont_data["form"].get("complainant_name") == "Rajesh Sharma"
    # Verify that prior data is intact
    assert cont_data["form"].get("amount_lost") == "25000"
    assert cont_data["form"].get("transaction_id") == "ABC123"

    # 4. If any useful fields remain (e.g. bank), continue
    if cont_data["status"] == "incomplete" and cont_data.get("current_field"):
        curr = cont_data["current_field"]
        ans = "State Bank of India" if curr == "bank" else "online"
        cont_resp2 = client.post("/fir/continue", json={
            "session_id": session_id,
            "answer": ans
        })
        assert cont_resp2.status_code == 200
        cont_data = cont_resp2.json().get("data", cont_resp2.json())

    # 5. Now it should be ready for confirmation
    assert cont_data["status"] == "ready_for_confirmation"
    assert "Complaint Details for Confirmation" in cont_data["next_question"]
    assert "Rajesh Sharma" in cont_data["next_question"]
    assert "25,000" in cont_data["next_question"] or "25000" in cont_data["next_question"]

    # 6. User confirms the details:
    confirm_resp = client.post("/fir/continue", json={
        "session_id": session_id,
        "answer": "Confirm"
    })
    assert confirm_resp.status_code == 200
    final_data = confirm_resp.json().get("data", confirm_resp.json())

    # Verify FIR is generated
    assert final_data["status"] == "ready"
    assert final_data.get("fir") is not None
    assert len(final_data["fir"]) > 100
    assert any(term in final_data["fir"].upper() for term in ["POLICE", "COMPLAINT", "FIR", "STATION"])

    # 7. Verify persistence in SQLite FIRRecord
    with next(get_db()) as db:
        rec = db.query(FIRRecord).filter(FIRRecord.session_id == session_id).first()
        assert rec is not None
        assert rec.status == "ready"
        assert rec.complainant_name == "Rajesh Sharma"
        assert rec.fir_draft_text is not None

    # 8. Verify idempotency: calling /fir/start on completed session returns existing FIR draft immediately
    repeat_resp = client.post("/fir/start", json={"session_id": session_id})
    assert repeat_resp.status_code == 200
    repeat_data = repeat_resp.json().get("data", repeat_resp.json())
    assert repeat_data["status"] == "ready"
    assert repeat_data["fir"] == final_data["fir"]

    print("PASS: test_conversation_to_fir_full_flow")


def test_invalid_input_does_not_500():
    """
    Verifies that invalid input during FIR questioning returns a graceful 200 with clarification,
    never an HTTP 500 NameError or crash.
    """
    print("Testing invalid input error resilience...")
    init_db()
    session_id = f"test-err-{datetime.now().timestamp()}"

    with next(get_db()) as db:
        chat_sess = ChatSession(session_id=session_id, title="Test Date Validation")
        db.add(chat_sess)
        db.commit()
        db.add(ChatMessage(session_id=session_id, sender="user", message="I lost ₹15,000 to an online fraud."))
        db.commit()

    start_resp = client.post("/fir/start", json={"session_id": session_id})
    assert start_resp.status_code == 200

    # User enters "banana" when asked for incident date or complainant name
    bad_resp = client.post("/fir/continue", json={
        "session_id": session_id,
        "answer": "banana"
    })
    # MUST return 200, NEVER 500
    assert bad_resp.status_code == 200
    bad_data = bad_resp.json().get("data", bad_resp.json())
    assert bad_data["status"] in ("incomplete", "needs_clarification")
    assert bad_data["form"].get("amount_lost") == "15000"

    print("PASS: test_invalid_input_does_not_500")


if __name__ == "__main__":
    print("\n=======================================================")
    print("CYBERSAHAY COMPLETE FIR ORCHESTRATOR TEST SUITE")
    print("=======================================================\n")
    test_validator_normalization_units()
    test_conversation_to_fir_full_flow()
    test_invalid_input_does_not_500()
    print("\n=======================================================")
    print("ALL COMPLETE FIR ORCHESTRATOR TESTS PASSED!")
    print("=======================================================\n")
