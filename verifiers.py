"""
verifiers.py — Step 2

Deterministic (Tier-1) verifiers. Each takes raw execution output and a
success_condition, and returns an Evidence object. No LLM calls in this file.

This is the ONLY place in the whole codebase allowed to produce a
verdict of "pass" or "fail" — every other node treats these functions'
output as ground truth.
"""

import re
from contracts import Evidence


def exit_code_check(returncode: int, expected: int = 0) -> Evidence:
    verdict = "pass" if returncode == expected else "fail"
    return Evidence(
        tier="deterministic",
        verdict=verdict,
        raw={"returncode": returncode, "expected": expected},
    )


def pytest_runner_check(returncode: int, stdout: str, stderr: str) -> Evidence:
    verdict = "pass" if returncode == 0 else "fail"
    return Evidence(
        tier="deterministic",
        verdict=verdict,
        raw={"returncode": returncode, "stdout": stdout, "stderr": stderr},
    )


def ruff_lint_check(returncode: int, stdout: str) -> Evidence:
    verdict = "pass" if returncode == 0 else "fail"
    return Evidence(
        tier="deterministic",
        verdict=verdict,
        raw={"returncode": returncode, "stdout": stdout},
    )


def file_content_regex_check(file_content: str, pattern: str) -> Evidence:
    match = re.search(pattern, file_content)
    verdict = "pass" if match else "fail"
    return Evidence(
        tier="deterministic",
        verdict=verdict,
        raw={"file_content": file_content, "pattern": pattern, "matched": bool(match)},
    )


def file_exists_check(path_exists: bool, path: str) -> Evidence:
    verdict = "pass" if path_exists else "fail"
    return Evidence(
        tier="deterministic",
        verdict=verdict,
        raw={"path": path, "exists": path_exists},
    )


# Dispatch table — graph.py calls this, never the individual functions directly.
# Returns verdict="not_applicable" only when no deterministic check fits,
# which is the ONLY legitimate trigger for the Tier-2 judge fallback.
def run_tier1_verification(action_type: str, evidence_kwargs: dict) -> Evidence:
    dispatch = {
        "run_lint": lambda kw: ruff_lint_check(kw["returncode"], kw.get("stdout", "")),
        "run_tests": lambda kw: pytest_runner_check(kw["returncode"], kw.get("stdout", ""), kw.get("stderr", "")),
        "run_script": lambda kw: (
            file_content_regex_check(kw["file_content"], kw["pattern"])
            if kw.get("pattern")
            else exit_code_check(kw["returncode"])
        ),
    }
    fn = dispatch.get(action_type)
    if fn is None:
        return Evidence(tier="deterministic", verdict="not_applicable", raw={"reason": f"no Tier-1 verifier for {action_type}"})
    return fn(evidence_kwargs)
