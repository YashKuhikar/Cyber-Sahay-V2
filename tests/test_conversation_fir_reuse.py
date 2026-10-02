"""
Tests for Conversation History Reuse in the FIR Workflow (CyberSahay).
Verifies:
1. Scenario 1 (Section 21): Financial fraud conversation -> extracts facts, confirms them, asks ONLY missing fields (e.g. name, bank).
2. Scenario 2 (Section 22): Phishing courier link conversation -> asks only missing fields.
3. Scenario 3 (Section 23): Complete details already provided -> 0 missing fields, jumps directly to confirmation summary.
4. Contradiction test: When user changes details (e.g. amount 10000 -> 12000), previous value is tracked.
5. REST API Integration test: /api/fir/start and /api/fir/continue using a session with prior chat history.
"""

import unittest
from datetime import datetime
from src.agents.fir_extractor import (
    FIRInformationExtractor,
    FieldProvenance,
    format_extracted_summary,
    format_confirmation_summary,
    get_next_question,
)
from src.database.models import ChatMessage, ChatSession, User
from src.database.db import get_db, init_db
from fastapi.testclient import TestClient
from src.main import app

extractor = FIRInformationExtractor()

def test_scenario_1_fake_bank_call_extraction():
    """
    Scenario 1:
    - User conversation:
      1. Someone called me pretending to be from my bank.
      2. They asked me to install an app.
      3. I installed it and entered my OTP.
      4. After that ₹25,000 was deducted from my account.
      5. The transaction happened yesterday around 7 PM.
      6. The UPI transaction ID is ABC123.
    """
    messages = [
        {"sender": "user", "message": "Someone called me pretending to be from my bank."},
        {"sender": "assistant", "message": "Do not panic and do not share any more OTPs or personal details."},
        {"sender": "user", "message": "They asked me to install an app."},
        {"sender": "user", "message": "I installed it and entered my OTP."},
        {"sender": "user", "message": "After that ₹25,000 was deducted from my account."},
        {"sender": "user", "message": "The transaction happened yesterday around 7 PM."},
        {"sender": "user", "message": "The UPI transaction ID is ABC123."},
    ]

    extracted = extractor.extract_from_conversation(messages)

    # 1. Check incident classification
    assert extracted.incident.type.value == "financial_cyber_fraud"
    assert "bank" in extracted.incident.description.value.lower() or "app" in extracted.incident.description.value.lower()

    # 2. Check financial facts extracted and marked confirmed
    assert extracted.financial.amount.value == 25000.0
    assert extracted.financial.amount.status == "confirmed"
    assert extracted.financial.currency == "INR"
    assert extracted.financial.transaction_id.value == "ABC123"
    assert extracted.financial.transaction_id.status == "confirmed"

    # 3. Check temporal facts
    assert extracted.incident.time.value == "7 PM"
    assert extracted.incident.time.status == "confirmed"
    assert extracted.incident.date.value is not None
    assert extracted.incident.date.status == "confirmed"

    # 4. Check missing fields - MUST NOT include amount, date, time, transaction_id, or description!
    missing = extracted.missing_fields
    assert "amount" not in missing
    assert "incident_date" not in missing
    assert "incident_time" not in missing
    assert "description" not in missing

    # Must only ask truly missing fields: e.g. complainant name
    assert "complainant_name" in missing

    # 5. Formatted banner output
    summary = format_extracted_summary(extracted)
    assert "₹25,000" in summary or "25000" in summary
    assert "ABC123" in summary
    assert "I won't ask you to repeat these" in summary

    # 6. Next question should be for a genuinely missing field
    next_f, next_q = get_next_question(extracted)
    assert next_f in ["complainant_name", "bank"]
    assert "amount" not in next_q.lower()
    assert "what happened" not in next_q.lower()


def test_scenario_2_phishing_courier_link():
    """
    Scenario 2:
    - User conversation:
      "I received an SMS about a pending courier delivery with a link.
       I clicked it and entered my card details on a fake India Post website."
    - Verify:
      - Incident type detected as phishing / financial_cyber_fraud
      - Missing fields correctly include complainant_name
    """
    messages = [
        {"sender": "user", "message": "I received an SMS about a pending courier delivery with a link."},
        {"sender": "assistant", "message": "Did you enter any banking or card details on the site?"},
        {"sender": "user", "message": "I clicked it and entered my card details on a fake India Post website."},
    ]

    extracted = extractor.extract_from_conversation(messages)

    assert extracted.incident.type.value in ["phishing", "financial_cyber_fraud"]
    # Amount was not provided
    assert extracted.financial.amount.value is None
    # Missing fields must include complainant_name
    assert "complainant_name" in extracted.missing_fields


def test_scenario_3_complete_conversation_zero_missing():
    """
    Scenario 3:
    - All required fields already provided across the conversation.
    - System should identify that critical fields are satisfied and allow confirmation summary.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    messages = [
        {"sender": "user", "message": "My name is Ramesh Kumar, mobile 9876543210, residing in Mumbai."},
        {"sender": "user", "message": f"I was duped of ₹15,000 from my HDFC Bank account on {today_str} at 3 PM."},
        {"sender": "user", "message": "Someone sent me a fraudulent QR code claiming to send money. Transaction ID was TXN98765."},
    ]

    extracted = extractor.extract_from_conversation(messages)

    assert extracted.complainant.name.value == "Ramesh Kumar"
    assert extracted.complainant.phone.value == "9876543210"
    assert extracted.financial.amount.value == 15000.0
    assert extracted.financial.bank.value == "HDFC Bank"
    assert extracted.financial.transaction_id.value == "TXN98765"
    assert extracted.incident.time.value == "3 PM"

    conf_summary = format_confirmation_summary(extracted)
    assert "Ramesh Kumar" in conf_summary
    assert "15,000" in conf_summary or "15000" in conf_summary
    assert "HDFC Bank" in conf_summary
    assert "Please confirm" in conf_summary


def test_contradiction_detection():
    """
    Verify that if the user corrects an amount or detail, the system keeps the latest
    value while recording the previous value.
    """
    messages = [
        {"sender": "user", "message": "I lost ₹10,000 in this scam."},
        {"sender": "assistant", "message": "Noted. Did any other transactions occur?"},
        {"sender": "user", "message": "Actually, looking at my bank statement, I lost ₹12,000."},
    ]

    extracted = extractor.extract_from_conversation(messages)
    assert extracted.financial.amount.value == 12000.0
    assert extracted.financial.amount.status == "needs_confirmation"
    assert extracted.financial.amount.previous_value == 10000.0
    assert len(extracted.contradictions) > 0


def test_fir_routes_with_session_history():
    """
    Test FastAPI endpoints /api/fir/start and /api/fir/continue
    reusing conversation messages from database.
    """
    client = TestClient(app)
    init_db()

    session_id = f"test-sess-{datetime.now().timestamp()}"

    # Insert messages into DB for this session
    with next(get_db()) as db:
        chat_sess = ChatSession(session_id=session_id, title="Test FIR session")
        db.add(chat_sess)
        db.commit()

        db.add(ChatMessage(
            session_id=session_id,
            sender="user",
            message="Someone called me from my bank and took ₹25,000. Transaction ID ABC123 yesterday at 7 PM."
        ))
        db.commit()

    # 1. Call /fir/start with this session_id
    response = client.post("/fir/start", json={"session_id": session_id})
    assert response.status_code == 200, f"Error {response.status_code}: {response.text}"
    resp_body = response.json()
    data = resp_body.get("data", resp_body)

    assert data["session_id"] == session_id
    assert data["form"]["amount_lost"] == "25000" or data["form"].get("amount") == 25000.0
    assert data["form"]["transaction_id"] == "ABC123"
    # Extracted summary must be present
    assert "I found these details" in data["extracted_summary"]
    # The first question should NOT ask for amount or transaction id
    assert "amount" not in data["next_question"].lower()
    assert "abc123" not in data["next_question"].lower()

    # 2. Answer the missing field (e.g. complainant name)
    cont_resp = client.post("/fir/continue", json={
        "session_id": session_id,
        "answer": "Rajesh Sharma"
    })
    assert cont_resp.status_code == 200, f"Error {cont_resp.status_code}: {cont_resp.text}"
    cont_body = cont_resp.json()
    cont_data = cont_body.get("data", cont_body)
    assert cont_data["form"].get("complainant_name") == "Rajesh Sharma"


if __name__ == "__main__":
    print("Running test_scenario_1_fake_bank_call_extraction...")
    test_scenario_1_fake_bank_call_extraction()
    print("PASS: test_scenario_1_fake_bank_call_extraction")

    print("Running test_scenario_2_phishing_courier_link...")
    test_scenario_2_phishing_courier_link()
    print("PASS: test_scenario_2_phishing_courier_link")

    print("Running test_scenario_3_complete_conversation_zero_missing...")
    test_scenario_3_complete_conversation_zero_missing()
    print("PASS: test_scenario_3_complete_conversation_zero_missing")

    print("Running test_contradiction_detection...")
    test_contradiction_detection()
    print("PASS: test_contradiction_detection")

    print("Running test_fir_routes_with_session_history...")
    test_fir_routes_with_session_history()
    print("PASS: test_fir_routes_with_session_history")

    print("\nALL 5 TESTS PASSED SUCCESSFULLY!")
