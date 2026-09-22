"""
planner.py — Step 6

Turns a task string into a Plan (ordered list of PlannedStep). This is the
FIRST place an LLM enters the pipeline. It only ever proposes — it cannot
set status or evidence, and its output is parsed into contracts.Plan, so
malformed output fails loudly rather than silently corrupting the state.
"""

from config import call_llm_structured
from contracts import Plan

SYSTEM_PROMPT = """You are the Planner in a zero-trust coding agent.

Break the task into an ORDERED list of steps. For EACH step you must:
1. Try to write a DETERMINISTIC success_condition first (exit code, pytest
   result, a regex the output must match, a lint check). Prefer this always.
2. If action_type is "run_script" AND success depends on the CONTENT of a
   file the script writes (not just its exit code), you MUST also set
   "pattern" to a regex that content has to match — e.g. a script that
   writes report.txt and should be checked for the substring "export
   complete" gets pattern: "export complete". Leave pattern null for any
   step judged by exit code alone (run_lint, run_tests, or a run_script
   step with no file-content requirement).
3. Only set requires_llm_judge=true if no deterministic check is possible
   (e.g. "improve readability" with no test file) — and you MUST fill in
   judge_justification explaining why no deterministic check applies.
4. If a step's success depends on a test/spec file, set spec_file to that
   file's name. spec_file is FROZEN — no step may ever target it for patching.
5. action_type "apply_patch" has NO deterministic Tier-1 check available —
   it can only ever be resolved by the Tier-2 judge. So any step with
   action_type "apply_patch" MUST set requires_llm_judge=true and fill in
   judge_justification, with no exceptions. Do not use "apply_patch" as a
   generic "fix this file" step — recovery.py already handles patching
   failed steps automatically. Only plan an explicit "apply_patch" step when
   the task is itself a judge-only evaluation of a file's current content
   (e.g. "improve readability" with no test to run).

Respond with ONLY valid JSON matching this shape, no prose, no markdown fences:
{
  "task": "<the task>",
  "steps": [
    {
      "step_id": "step_1",
      "action_type": "run_lint" | "run_tests" | "run_script" | "apply_patch",
      "target_file": "<file the action runs against>",
      "spec_file": "<frozen spec file, or null>",
      "success_condition": "<human-readable deterministic condition>",
      "pattern": "<regex against file content, or null — see rule 2>",
      "requires_llm_judge": false,
      "judge_justification": null
    }
  ]
}
"""


def make_plan(task: str, available_files: list[str]) -> Plan:
    user_prompt = f"Task: {task}\nFiles available in scratch/: {available_files}"
    return call_llm_structured(SYSTEM_PROMPT, user_prompt, Plan)
