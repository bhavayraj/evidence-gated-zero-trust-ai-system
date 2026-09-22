"""
graph.py — Step 8

Wires everything into the actual loop:

    Planner -> [per step: Executor -> Tier-1 Verifier -> (Judge if N/A)] -> Router
                    ^ FAIL                                                    | next step
                    +-------------------- Recovery (scoped to this step) -----+

Rules enforced HERE, not just documented:
  - A step only advances to the next step on verified_pass.
  - Recovery is only invoked on verified_fail, never on not_applicable.
  - editable_files for a step is EVERYTHING except that step's spec_file —
    this is what executor.apply_patch checks against.
  - Each step has its own attempt counter, capped by max_attempts.
"""

from contracts import Plan, PlannedStep, StepState
from executor import execute, apply_patch
from verifiers import run_tier1_verification
from judge import judge_step
from recovery import propose_patch
from ledger import append_row
from contracts import PatchRejected

SCRATCH_DIR = "./scratch"


def editable_files_for(step: PlannedStep, all_files: list[str]) -> list[str]:
    return [f for f in all_files if f != step.spec_file]


def run_step(step: PlannedStep, all_files: list[str]) -> StepState:
    state = StepState(step_id=step.step_id, action=step)

    while state.attempt <= state.max_attempts:
        raw = execute(step)
        state.status = "executed"

        evidence = run_tier1_verification(step.action_type, raw)

        # Tier-2 fallback — ONLY on not_applicable, never overrides a Tier-1 fail
        if evidence.verdict == "not_applicable" and step.requires_llm_judge:
            file_content = raw.get("file_content") or raw.get("stdout", "")
            evidence = judge_step(step, file_content)

        state.evidence = evidence
        append_row(step.step_id, evidence, state.attempt)

        if evidence.verdict == "pass":
            state.status = "verified_pass"
            return state

        if evidence.verdict == "not_applicable":
            # No Tier-1 check fired and no judge resolved it (either the step
            # didn't set requires_llm_judge, or judge_step still couldn't
            # reach pass/fail). recovery.propose_patch() asserts it is only
            # ever called on a verified "fail" — sending it a not_applicable
            # would crash that assert, so stop here instead and flag it.
            state.status = "verified_fail"
            print(f"[HUMAN REVIEW NEEDED] step '{step.step_id}' verdict is "
                  f"'not_applicable' — no deterministic check applied and no "
                  f"LLM judge resolved it. Check requires_llm_judge on this step.")
            return state

        # verdict == "fail" -> scoped recovery, retry same step only
        state.status = "verified_fail"
        if state.attempt >= state.max_attempts:
            return state  # exhausted retries, caller decides what to do

        try:
            editable = editable_files_for(step, all_files)
            patch = propose_patch(step, evidence)
            print(f"\n[RECOVERY] target={patch.target_file}\nreasoning: {patch.reasoning}\n--- new content ---\n{patch.diff}\n---\n")
            apply_patch(patch.target_file, patch.diff, editable)
            state.status = "recovered"
        except PatchRejected as e:
            # Recovery tried to touch the frozen spec file — stop retrying,
            # this needs a human, not another automated attempt.
            state.status = "verified_fail"
            append_row(step.step_id, evidence, state.attempt)
            print(f"[HUMAN REVIEW NEEDED] {e}")
            return state

        state.attempt += 1

    return state


def run_plan(plan: Plan, all_files: list[str]) -> list[StepState]:
    """Runs steps IN ORDER. Stops the chain if a step never recovers."""
    results = []
    for step in plan.steps:
        result = run_step(step, all_files)
        results.append(result)
        if result.status != "verified_pass":
            break  # don't advance the chain past an unresolved failure
    return results
