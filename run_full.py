from planner import make_plan
from graph import run_plan
import os

files = os.listdir('scratch')
plan = make_plan('Lint utils.py, then make it pass test_utils.py', files)

print("PLAN:")
for step in plan.steps:
    print(" ", step.step_id, step.action_type, step.target_file, "| judge:", step.requires_llm_judge)

results = run_plan(plan, files)

print("\nRESULTS:")
for r in results:
    print(" ", r.step_id, r.status, "| verdict:", r.evidence.verdict if r.evidence else None, "| attempts:", r.attempt)