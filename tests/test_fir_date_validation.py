"""
Comprehensive test suite verifying FIR continue endpoint, date validation, normalization,
and conversation state preservation.

Covers Section 12 criteria:
- Test 1: Valid ISO date (2026-10-01) -> successful normalization
- Test 2: Indian date format (01/10/2026) -> successful normalization
- Test 3: Natural language date (1 October 2026) -> successful normalization
- Test 4: Invalid date ("not a date" / "banana") -> validation response, NOT HTTP 500
- Test 5: FIR continue endpoint via POST /fir/continue with date answer -> returns 200 with valid workflow status
- Test 6: Existing conversation data preserved when updating date field
"""

import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from src.main import app
from src.agents.validators import FIRValidator
from src.database.models import ChatMessage, ChatSession
from src.database.db import get_db, init_db
from src.memory.shared_memory import memory


client = TestClient(app)


def test_date_normalization_units():
    """Unit tests for FIRValidator.normalize_date and validate_incident_date."""
    # Test 1: Valid ISO date
    assert FIRValidator.normalize_date("2026-10-01") == "2026-10-01"
    valid, msg = FIRValidator.validate_field("incident_date", "2026-10-01")
    assert valid is True
    assert msg == ""

    # Test 2: Indian date format
    assert FIRValidator.normalize_date("01/10/2026") == "2026-10-01"
    valid, msg = FIRValidator.validate_field("incident_date", "01/10/2026")
    assert valid is True
    assert msg == ""

    # Test 3: Natural language date
    assert FIRValidator.normalize_date("1 October 2026") == "2026-10-01"
    assert FIRValidator.normalize_date("October 1, 2026") == "2026-10-01"
    assert FIRValidator.normalize_date("1st October 2026") == "2026-10-01"
    valid, msg = FIRValidator.validate_field("incident_date", "1 October 2026")
    assert valid is True

    # Test 4: Invalid date inputs
    assert FIRValidator.normalize_date("not a date") == ""
    assert FIRValidator.normalize_date("banana") == ""
    valid_bad, msg_bad = FIRValidator.validate_field("incident_date", "banana")
    assert valid_bad is False
    assert "couldn't understand that date" in msg_bad.lower()


def test_fir_continue_date_workflow():
    """Integration test for POST /fir/continue with date field, invalid input, and state preservation."""
    init_db()
    session_id = f"test-date-sess-{datetime.now().timestamp()}"

    # Setup session with complainant name and amount already known, missing incident_date
    with next(get_db()) as db:
        chat_sess = ChatSession(session_id=session_id, title="Test Date Session")
        db.add(chat_sess)
        db.commit()

        # Conversation providing name and loss, but no date
        db.add(ChatMessage(
            session_id=session_id,
            sender="user",
            message="My name is Amit Roy. I lost ₹45,000 to a phishing website."
        ))
        db.commit()

    # Step 1: Start FIR
    start_resp = client.post("/fir/start", json={"session_id": session_id})
    assert start_resp.status_code == 200, f"Error: {start_resp.text}"
    start_data = start_resp.json().get("data", start_resp.json())

    assert start_data["form"].get("complainant_name") == "Amit Roy"
    assert start_data["form"].get("amount_lost") == "45000"

    # Ensure current_field is incident_date
    current_field = start_data["current_field"]
    assert current_field == "incident_date"

    # Step 2: Test invalid date input ("banana") -> Must return HTTP 200 with controlled validation error (NOT 500)
    bad_resp = client.post("/fir/continue", json={
        "session_id": session_id,
        "answer": "banana"
    })
    assert bad_resp.status_code == 200, f"Error: {bad_resp.text}"
    bad_data = bad_resp.json().get("data", bad_resp.json())
    assert bad_data["status"] == "incomplete"
    assert bad_data["current_field"] == "incident_date"
    assert "couldn't understand that date" in bad_data["next_question"].lower()

    # Verify existing conversation data was not lost
    assert bad_data["form"].get("complainant_name") == "Amit Roy"
    assert bad_data["form"].get("amount_lost") == "45000"

    # Step 3: Test valid date input ("01/10/2026" - Indian format) -> Must normalize and proceed
    good_resp = client.post("/fir/continue", json={
        "session_id": session_id,
        "answer": "01/10/2026"
    })
    assert good_resp.status_code == 200, f"Error: {good_resp.text}"
    good_data = good_resp.json().get("data", good_resp.json())

    # Verify incident_date is normalized to ISO YYYY-MM-DD
    assert good_data["form"].get("incident_date") == "2026-10-01"
    # Verify prior data remains intact
    assert good_data["form"].get("complainant_name") == "Amit Roy"
    assert good_data["form"].get("amount_lost") == "45000"


if __name__ == "__main__":
    print("Running test_date_normalization_units...")
    test_date_normalization_units()
    print("PASS: test_date_normalization_units")

    print("Running test_fir_continue_date_workflow...")
    test_fir_continue_date_workflow()
    print("PASS: test_fir_continue_date_workflow")

    print("\nALL FIR DATE & VALIDATION TESTS PASSED!")
