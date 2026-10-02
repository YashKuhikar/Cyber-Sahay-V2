print("STEP 1: Script started")

from groq import Groq
from src.config import GROQ_API_KEY

print("STEP 2: Groq imported")
print("API key exists:", bool(GROQ_API_KEY))

client = Groq(api_key=GROQ_API_KEY)

print("STEP 3: Client created")

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant. Always respond with text."
        },
        {
            "role": "user",
            "content": "What is 2 + 2? Answer in one sentence."
        }
    ],
    temperature=0,
    max_completion_tokens=100,
)

print("FULL RESPONSE:")
print(response)
print("\nCONTENT:")
print(repr(response.choices[0].message.content))