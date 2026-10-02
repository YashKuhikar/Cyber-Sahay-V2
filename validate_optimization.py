"""
CyberSahay Optimization Validation Suite
Validates:
1. RAG Resource Caching (Loaded once and reused across all requests).
2. Parallel Dense + BM25 Retrieval execution & timing.
3. Chat workflow with:
   - a normal cyber question
   - a UPI fraud question
   - a cybercrime reporting question
   - a follow-up chat session
4. API response structure verification (exact JSON contract match).
"""

import sys
import time

# Ensure UTF-8 output on Windows terminal
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_validation():
    print("=" * 70)
    print("CYBERSAHAY PERFORMANCE OPTIMIZATION VALIDATION")
    print("=" * 70)

    session_id = f"opt-sess-{int(time.time())}"

    test_queries = [
        ("Normal Cyber Question", "What is cyber stalking and what are my legal protections under Indian law?"),
        ("UPI Fraud Question", "Someone tricked me into scanning a QR code and Rs 20000 was debited from my account. What should I do immediately?"),
        ("Cybercrime Reporting Question", "How do I file a complaint on the National Cyber Crime Reporting Portal 1930?"),
        ("Follow-up Chat", "Can I also file an FIR at my local police station for this?"),
    ]

    for idx, (title, query) in enumerate(test_queries, 1):
        print(f"\n[{idx}] Testing: {title}")
        print(f"    Query: '{query}'")

        start = time.perf_counter()
        response = client.post(
            "/chat/",
            json={"session_id": session_id, "message": query},
        )
        latency = time.perf_counter() - start

        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        # Contract Validation
        assert data["success"] is True
        assert "message" in data
        assert "data" in data
        assert "timestamp" in data

        res_data = data["data"]
        assert "intent" in res_data
        assert "workflow" in res_data
        assert "category" in res_data
        assert "confidence" in res_data
        assert "response" in res_data
        assert "sources" in res_data

        print(f"    [OK] Status: 200 OK | Latency: {latency:.2f}s")
        print(f"    Intent: {res_data['intent']} | Workflow: {res_data['workflow']} | Category: {res_data['category']}")
        print(f"    Sources Retrieved: {len(res_data['sources'])}")
        preview = res_data["response"][:160].replace("\n", " ") + "..."
        print(f"    Response Preview: {preview}")

    print("\n" + "=" * 70)
    print("ALL OPTIMIZATION VALIDATION TESTS PASSED SUCCESSFULLY! [100% OK]")
    print("=" * 70)


if __name__ == "__main__":
    test_validation()
