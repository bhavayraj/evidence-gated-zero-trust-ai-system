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

MINIMAL means minimal. You are FORBIDDEN from:
  - adding new functions, classes, or methods that were not there before,
    unless the failure evidence specifically requires one to exist
  - adding a __main__ block, self-written test cases, or any test/demo
    scaffolding of your own — you are fixing the file, not proving it, and
    the file's own test file (which you never see the contents of, and
    never touch) is what proves it, not you
  - adding print statements, logging, or comments beyond what's needed to
    explain the specific fix
  - changing the public interface (function/class names, parameter names,
    return types) unless the failure evidence specifically requires it
Change only what the evidence shows is actually broken. If you're tempted
to add anything beyond that fix, don't — a smaller correct patch beats a
larger "improved" one every time here.

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
