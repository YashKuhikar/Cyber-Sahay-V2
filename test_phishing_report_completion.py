import sys
import time
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

session_id = f"test-complete-{int(time.time())}"
query = "Should I report the phishing attack to the police? How do I report it step by step?"

print("Sending query to /chat/ ...")
t0 = time.perf_counter()
res = client.post("/chat/", json={"session_id": session_id, "message": query})
elapsed = time.perf_counter() - t0

print(f"Status Code: {res.status_code} | Latency: {elapsed:.2f}s")
assert res.status_code == 200
data = res.json()["data"]

print("\n--- RESPONSE OUTPUT ---")
print(data["response"])
print("\n--- END OF RESPONSE ---")

# Verify it does not cut off mid-sentence
last_100_chars = data["response"].strip()[-100:]
print(f"\nLast 100 characters:\n{last_100_chars}")

# Check that the ending ends cleanly with punctuation (. or ! or ? or markdown list)
last_char = data["response"].strip()[-1]
assert last_char in {'.', '!', '?', ')', '*', '`'}, f"Response seems abruptly cut off at: '{last_100_chars}'"
print("\n[PASS] Response is complete, fully finished, and does NOT cut off mid-sentence!")
