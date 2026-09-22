"""
judge.py — Step 5

Tier-2 fallback verifier. graph.py only calls this when
verifiers.run_tier1_verification() returns verdict="not_applicable" —
it must NEVER be used to override a Tier-1 "fail". Output is always
tagged tier="llm_judge" with a confidence < 1.0 so the ledger can render
it visibly differently from a deterministic pass.
"""

from pydantic import BaseModel
from config import call_llm_structured
from contracts import Evidence, PlannedStep


class _JudgeResponse(BaseModel):
    """Intermediate shape for the raw LLM output, before wrapping into Evidence."""
    verdict: str
    confidence: float
    cited_evidence: str

SYSTEM_PROMPT = """You are the last-resort judge in a zero-trust coding agent.
You are only called when NO deterministic check could apply to this step.

Evaluate whether the success_condition is met. You MUST cite specific
lines of code or output as evidence for your verdict — a vague impression
is not acceptable. Be conservative with confidence; only go above 0.85
if the evidence is unambiguous.

Respond with ONLY valid JSON:
{
  "verdict": "pass" | "fail",
  "confidence": <float 0.0-1.0>,
  "cited_evidence": "<specific lines/output you're basing this on>"
}
"""


def judge_step(step: PlannedStep, file_content: str) -> Evidence:
    user_prompt = (
        f"success_condition: {step.success_condition}\n"
        f"judge_justification (why no deterministic check applies): {step.judge_justification}\n"
        f"File content:\n{file_content}"
    )
    result = call_llm_structured(SYSTEM_PROMPT, user_prompt, _JudgeResponse)

    return Evidence(
        tier="llm_judge",
        verdict=result.verdict,
        confidence=result.confidence,
        raw={"cited_evidence": result.cited_evidence},
    )
