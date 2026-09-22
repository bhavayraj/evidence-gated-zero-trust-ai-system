"""
contracts.py — Step 1

Shared data models for the entire pipeline. Every other file imports from here.

The one rule that makes this "zero-trust" in code, not just in prose:
    StepState.status and StepState.evidence are only ever assigned inside
    verifiers.py. Planner, Executor, and Recovery never touch these fields
    directly — they can only produce the INPUTS that verifiers.py consumes.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


ActionType = Literal["run_script", "run_tests", "run_lint", "apply_patch"]
VerifierTier = Literal["deterministic", "llm_judge"]
Verdict = Literal["pass", "fail", "not_applicable"]
StepStatus = Literal["pending", "executed", "verified_pass", "verified_fail", "recovered"]


class PlannedStep(BaseModel):
    """One link in the multi-step chain. Produced by the Planner."""
    step_id: str
    action_type: ActionType
    target_file: str                       # file the action runs/patches
    spec_file: Optional[str] = None         # file that DEFINES success (e.g. test_utils.py) — never patchable
    success_condition: str                  # human-readable, e.g. "pytest exit code == 0"
    pattern: Optional[str] = None           # regex checked against file_content — only used when
                                             # action_type == "run_script" and success_condition is
                                             # about file content rather than plain exit code. This is
                                             # what verifiers.file_content_regex_check actually matches
                                             # against; without it that check path is unreachable.
    requires_llm_judge: bool = False
    judge_justification: Optional[str] = None


class Plan(BaseModel):
    task: str
    steps: list[PlannedStep]


class Evidence(BaseModel):
    """Raw, immutable proof behind a verdict. Never a bare boolean."""
    tier: VerifierTier
    confidence: float = 1.0                 # 1.0 for deterministic; variable for llm_judge
    verdict: Verdict
    raw: dict = Field(default_factory=dict) # returncode, stdout, stderr, file_content, cited_evidence, etc.


class Patch(BaseModel):
    """Output of Recovery. target_file is checked against editable_files before it's ever applied."""
    step_id: str
    target_file: str
    diff: str                               # unified diff or full replacement content
    reasoning: str                          # must reference the Evidence it saw


class StepState(BaseModel):
    """Travels through the graph. status/evidence are write-once-per-attempt, verifier-only."""
    step_id: str
    action: PlannedStep
    status: StepStatus = "pending"
    evidence: Optional[Evidence] = None
    attempt: int = 1
    max_attempts: int = 3


class LedgerRow(BaseModel):
    """One append-only row. This is what the frontend polls and renders."""
    step_id: str
    timestamp: str
    tier: VerifierTier
    verdict: Verdict
    evidence: dict
    attempt: int


class PatchRejected(Exception):
    """Raised when Recovery tries to touch a frozen spec_file. Never caught silently."""
    pass
