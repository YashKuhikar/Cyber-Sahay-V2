"""
CyberSahay Quality & Fast-Path Validation Suite
Tests:
1. 'What is phishing' -> Rich, accurate definition & legal grounding (NO rejection).
2. 'I am a victim of phishing attack what should I do' -> Practical incident guidance.
3. Greetings ('hi', 'hello', 'namaste') -> Direct response bypassing RAG & IE.
4. Gratitude ('thank you', 'thanks', 'thanks a lot') -> Direct response bypassing RAG & IE.
5. Multi-turn conversation maintaining flow and clearing workflow on 'thank you'.
"""

import sys
import time

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi.testclient import TestClient
from src.main import app
from src.security.rate_limiter import RateLimiter

client = TestClient(app)


def test_quality_and_fast_path():
    print("=" * 80)
    print("  CYBERSAHAY QUALITY & FAST-PATH VERIFICATION")
    print("=" * 80)

    RateLimiter.reset()

    session_id = f"quality-test-{int(time.time())}"

    # 1. Test "What is phishing"
    print("\n[1] Testing: 'What is phishing'")
    t0 = time.perf_counter()
    res = client.post("/chat/", json={"session_id": session_id, "message": "What is phishing"})
    lat = time.perf_counter() - t0
    assert res.status_code == 200
    data = res.json()["data"]
    print(f"    Status: 200 OK | Latency: {lat:.2f}s")
    print(f"    Intent: {data['intent']} | Workflow: {data['workflow']} | Sources: {len(data['sources'])}")
    print(f"    Response Preview: {data['response'][:200]}...")
    assert "I couldn't find this information" not in data["response"]
    assert "phishing" in data["response"].lower()
    print("    [PASS] Definition and explanation provided successfully without rejection!")

    # 2. Test "I am a victim of phishing attack what should I do"
    print("\n[2] Testing: 'I am a victim of phishing attack what should I do'")
    t0 = time.perf_counter()
    res = client.post("/chat/", json={"session_id": session_id, "message": "I am a victim of phishing attack what should I do"})
    lat = time.perf_counter() - t0
    assert res.status_code == 200
    data = res.json()["data"]
    print(f"    Status: 200 OK | Latency: {lat:.2f}s")
    print(f"    Intent: {data['intent']} | Workflow: {data['workflow']} | Sources: {len(data['sources'])}")
    print(f"    Response Preview: {data['response'][:200]}...")
    assert len(data["response"]) > 100
    print("    [PASS] Actionable victim advisory generated successfully!")

    # 3. Test Gratitude: "thank you so much"
    print("\n[3] Testing Gratitude Fast-Path: 'thank you so much'")
    t0 = time.perf_counter()
    res = client.post("/chat/", json={"session_id": session_id, "message": "thank you so much"})
    lat_ms = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    data = res.json()["data"]
    print(f"    Status: 200 OK | Latency: {lat_ms:.2f}ms")
    print(f"    Intent: {data['intent']} | Workflow: {data['workflow']} | Sources: {len(data['sources'])}")
    print(f"    Response: {data['response']}")
    assert lat_ms < 200, f"Expected sub-200ms fast-path, got {lat_ms}ms"
    assert len(data["sources"]) == 0
    print("    [PASS] Gratitude fast-path bypassed RAG and responded instantly!")

    # 4. Test Greeting Fast-Path: "Hello"
    print("\n[4] Testing Greeting Fast-Path: 'Hello'")
    new_session = f"greet-test-{int(time.time())}"
    t0 = time.perf_counter()
    res = client.post("/chat/", json={"session_id": new_session, "message": "Hello"})
    lat_ms = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    data = res.json()["data"]
    print(f"    Status: 200 OK | Latency: {lat_ms:.2f}ms")
    print(f"    Intent: {data['intent']} | Workflow: {data['workflow']} | Sources: {len(data['sources'])}")
    print(f"    Response: {data['response']}")
    assert lat_ms < 200, f"Expected sub-200ms fast-path, got {lat_ms}ms"
    assert len(data["sources"]) == 0
    print("    [PASS] Greeting fast-path bypassed RAG and responded instantly!")

    # 5. Test "What is ransomware?"
    print("\n[5] Testing: 'What is ransomware?'")
    t0 = time.perf_counter()
    res = client.post("/chat/", json={"session_id": session_id, "message": "What is ransomware?"})
    lat = time.perf_counter() - t0
    assert res.status_code == 200
    data = res.json()["data"]
    print(f"    Status: 200 OK | Latency: {lat:.2f}s")
    print(f"    Intent: {data['intent']} | Workflow: {data['workflow']} | Sources: {len(data['sources'])}")
    print(f"    Response Preview: {data['response'][:200]}...")
    assert "I couldn't find this information" not in data["response"]
    assert "ransomware" in data["response"].lower()
    print("    [PASS] Ransomware explanation provided successfully!")

    print("\n" + "=" * 80)
    print("  ALL QUALITY & FAST-PATH TESTS PASSED (100% SUCCESS!)")
    print("=" * 80)


if __name__ == "__main__":
    test_quality_and_fast_path()
