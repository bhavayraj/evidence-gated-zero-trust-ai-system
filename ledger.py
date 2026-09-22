"""
ledger.py — Step 4

Append-only JSON-lines log. This is what the frontend (Step 9) polls and
renders live. Rows are never edited or deleted after being written —
that immutability is what makes the ledger a credible audit trail rather
than just a status field the LLM could theoretically influence.
"""

import json
from datetime import datetime, timezone
from contracts import Evidence

LEDGER_PATH = "./ledger.jsonl"


def append_row(step_id: str, evidence: Evidence, attempt: int) -> None:
    row = {
        "step_id": step_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tier": evidence.tier,
        "verdict": evidence.verdict,
        "confidence": evidence.confidence,
        "evidence": evidence.raw,
        "attempt": attempt,
    }
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(row) + "\n")


def read_all_rows() -> list[dict]:
    """Used by the Streamlit/React frontend to render the live table."""
    try:
        with open(LEDGER_PATH) as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def reset_ledger() -> None:
    """Only call this between demo runs, never mid-run."""
    open(LEDGER_PATH, "w").close()
