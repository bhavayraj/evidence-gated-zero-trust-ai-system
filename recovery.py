"""
recovery.py — Step 7

Reads a FAILED step's Evidence and proposes a Patch. Two hard rules,
enforced in code, not just prompted for:

1. Recovery is only ever called with evidence.verdict == "fail" from
   verifiers.py (graph.py enforces this — Recovery never sees a
   not_applicable or pass).
2. The proposed patch's target_file is checked against editable_files
   BEFORE it is ever written to disk (executor.apply_patch does the
   actual enforcement) — this file only proposes, it cannot write.
"""

from config import call_llm_structured
from contracts import Evidence, PlannedStep, Patch, PatchRejected

SYSTEM_PROMPT = """You are the Recovery node in a zero-trust coding agent.

You will be given the raw evidence from a FAILED verification and the
step that failed. Propose a minimal patch to the IMPLEMENTATION file only.

You are FORBIDDEN from proposing changes to the spec/test file — it is
frozen and defines what "correct" means. If you believe the spec file
itself is wrong, say so in your reasoning but still target the
implementation file, or return target_file equal to the spec_file only
if you want the patch to be rejected and flagged for human review.

Respond with ONLY valid JSON, no prose:
{
  "step_id": "<step_id>",
  "target_file": "<file to patch — must NOT be the spec_file>",
  "diff": "<full replacement content of target_file>",
  "reasoning": "<must reference the specific evidence you saw>"
}
"""


def propose_patch(step: PlannedStep, evidence: Evidence) -> Patch:
    assert evidence.verdict == "fail", "Recovery must only be called on a verified failure"

    import json
    user_prompt = (
        f"Step: {step.model_dump_json()}\n"
        f"Evidence (raw failure output): {json.dumps(evidence.raw)}\n"
        f"Frozen spec_file (do not touch): {step.spec_file}"
    )
    patch = call_llm_structured(SYSTEM_PROMPT, user_prompt, Patch)

    if step.spec_file and patch.target_file == step.spec_file:
        raise PatchRejected(
            f"Recovery attempted to patch frozen spec_file '{step.spec_file}' — rejected, "
            f"flag step '{step.step_id}' for human review instead of retrying"
        )

    return patch
