# Evidence-Gated Self-Healing Agent Workflow

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your real Gemini key in place of your_key_here
# get one at https://aistudio.google.com/apikey
```
`.env` is gitignored — it will never get committed even if you push this repo. `.env.example` is the safe, key-less template that's fine to commit so teammates know what variable to set (`GEMINI_API_KEY`).

## File map (build/run order)
| File | Step | Purpose |
|---|---|---|
| `contracts.py` | 1 | Shared Pydantic models. Only `verifiers.py` may set `status`/`evidence`. |
| `verifiers.py` | 2 | Tier-1 deterministic checks. Zero LLM calls. The credibility center. |
| `executor.py` | 3 | Runs commands (local subprocess or Docker sandbox). Also enforces the spec-file allowlist in `apply_patch`. |
| `ledger.py` | 4 | Append-only proof log at `ledger.jsonl`. |
| `judge.py` | 5 | Tier-2 LLM fallback — only fires on Tier-1 `not_applicable`. |
| `planner.py` | 6 | LLM turns a task into a multi-step `Plan`. |
| `recovery.py` | 7 | LLM proposes a `Patch`. Blocked from ever touching `spec_file`. |
| `graph.py` | 8 | Wires it all together — the actual multi-step loop with per-step recovery. |
| `app.py` | 9 | Streamlit dashboard, polls `ledger.jsonl` only. |
| `scratch/utils.py` | — | Demo file with an intentional case/space bug. |
| `scratch/test_utils.py` | — | Frozen spec file. Recovery must never write here. |

## Manual checkpoint (run this before touching any LLM code)
```bash
python3 -c "
from contracts import PlannedStep
from executor import execute
from verifiers import run_tier1_verification
from ledger import append_row, read_all_rows

step = PlannedStep(step_id='s1', action_type='run_tests', target_file='test_utils.py',
                    spec_file='test_utils.py', success_condition='pytest exit code == 0')
raw = execute(step)
ev = run_tier1_verification(step.action_type, raw)
append_row(step.step_id, ev, attempt=1)
print(ev.verdict, ev.raw.get('stderr', '')[:200])
"
```
Expect `fail` with an `AssertionError` from `test_case_and_spaces` — this proves Steps 2+3+4 compose correctly with zero LLM involvement.

## Full run (once LLM files are wired up)
```bash
python3 -c "
from planner import make_plan
from graph import run_plan
import os

files = os.listdir('scratch')
plan = make_plan('Lint utils.py, then make it pass test_utils.py', files)
results = run_plan(plan, files)
for r in results:
    print(r.step_id, r.status)
"
```
In a second terminal: `streamlit run app.py` to watch the ledger live.

## Before the demo
- Build the sandbox image (needs network, do this ahead of time): `docker build -t agent-sandbox .`
- Flip `SANDBOX_MODE = "docker"` in `executor.py` (currently `"local"` for fast iteration).
- Run `python3 -c "from ledger import reset_ledger; reset_ledger()"` between rehearsal runs.
- Confirm `scratch/test_utils.py` never changes across a run — that's your zero-trust guarantee, visibly holding.

## Notes on the four hardening fixes applied
1. **LLM JSON parsing** — `config.call_llm_structured()` strips code fences and retries once with the actual parse/validation error fed back to the model before giving up loudly. `planner.py`, `recovery.py`, `judge.py` all go through this now.
2. **Docker image** — `python:3.11-slim` has no `pytest`/`ruff`. Build `agent-sandbox` from the included `Dockerfile` *before* the demo (it needs network to build; containers then run with `--network=none`).
3. **`apply_patch` action type** — now actually executes (reads the target file back) instead of falling into the "unknown action_type" branch — this is what makes the Tier-2 readability demo runnable.
4. **Validation retry** — folded into `call_llm_structured()` above; a malformed model response gets one corrective retry instead of crashing the whole run immediately.

## LLM provider
All LLM calls go through `config.py`, which now wraps the Gemini API (`google-genai` SDK) instead of Anthropic. `call_llm_structured()` also turns on Gemini's native JSON mode (`response_mime_type="application/json"`) so malformed output should be rarer than before, though the retry loop stays as a safety net. Set `GEMINI_API_KEY` in `.env`; the model id lives in one place, `config.MODEL` (currently `gemini-2.5-flash`) — bump it to `gemini-2.5-pro` there if `judge.py`'s verdicts need more reasoning headroom than `-flash` gives you.

## Two robustness fixes applied post-migration
1. **Transient API failures no longer crash a live run.** `config._generate()` is now the single choke point for the actual `generate_content` call — both `call_llm()` and `call_llm_structured()` go through it. It retries up to twice, with backoff, but only on the failure modes retrying can actually fix: HTTP 429/500/502/503/504. A 400 (bad request) or 403 (auth) fails immediately instead of wasting demo time retrying something that won't change. This is separate from, and sits underneath, the existing JSON-validity retry loop — that one handles "the API answered but the content was malformed," this one handles "the API call itself didn't come back cleanly."
2. **`run_script`'s regex verifier is now reachable.** Previously `verifiers.run_tier1_verification()` checked `evidence_kwargs.get("pattern")` to decide whether to do a content-regex check or fall back to a plain exit-code check — but nothing ever put a `"pattern"` key into that dict, so the regex branch was dead code and every `run_script` step silently fell back to exit-code-only. Fixed by adding an optional `pattern` field to `contracts.PlannedStep`, having `planner.py`'s system prompt fill it in whenever a `run_script` step's success genuinely depends on file *content* (not just exit code), and having `executor.py` carry `step.pattern` through into the result dict verifiers actually reads. If your demo task never needs content-based checking (the palindrome demo doesn't), this won't change what you see — it just means the capability the code already claimed to have now actually works if you reach for it.
