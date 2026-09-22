from config import call_llm, call_llm_structured
from pydantic import BaseModel

# Test 1: raw call
result = call_llm("You are a test assistant.", "Reply with exactly: OK")
print("RAW RESPONSE:", result)

# Test 2: structured call (exercises JSON mode + Pydantic validation + retry wrapper)
class Ping(BaseModel):
    status: str
    number: int

parsed = call_llm_structured(
    "Respond with ONLY valid JSON, no prose, no code fences.",
    'Return JSON: {"status": "ok", "number": 42}',
    Ping,
)
print("PARSED:", parsed)
assert parsed.status == "ok" and parsed.number == 42
print("STRUCTURED CALL WORKS")