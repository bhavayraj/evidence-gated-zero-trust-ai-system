"""
executor.py — Step 3

The Executor is deliberately dumb: it runs a command and hands back raw
stdout/stderr/returncode. It never decides whether that output means
success — that's verifiers.py's job, called by graph.py, never by this file.

SANDBOX_MODE toggles isolation:
    "local"  -> plain subprocess, fastest for dev iteration
    "docker" -> runs inside a disposable container with --network=none

Flip to "docker" before the demo. Keep "local" while you're building —
don't let container setup slow down Steps 1-8.
"""

import subprocess
from contracts import PlannedStep

SANDBOX_MODE = "local"  # change to "docker" once Docker is confirmed working
SCRATCH_DIR = "./scratch"


def _run_local(cmd: list[str]) -> dict:
    result = subprocess.run(
        cmd, cwd=SCRATCH_DIR, capture_output=True, text=True, timeout=15
    )
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


DOCKER_IMAGE = "agent-sandbox:latest"  # build via: docker build -t agent-sandbox .


def _run_docker(cmd: list[str]) -> dict:
    docker_cmd = [
        "docker", "run", "--rm", "--network=none",
        "-v", f"{SCRATCH_DIR}:/scratch", "-w", "/scratch",
        DOCKER_IMAGE,
    ] + cmd
    result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=30)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _run(cmd: list[str]) -> dict:
    return _run_docker(cmd) if SANDBOX_MODE == "docker" else _run_local(cmd)


def execute(step: PlannedStep) -> dict:
    """
    Runs the action described by a PlannedStep and returns a raw evidence dict.
    graph.py passes this straight into verifiers.run_tier1_verification().
    """
    if step.action_type == "run_lint":
        result = _run(["ruff", "check", step.target_file])

    elif step.action_type == "run_tests":
        result = _run(["pytest", step.target_file, "-v"])

    elif step.action_type == "run_script":
        result = _run(["python", step.target_file])
        # Carry the Planner's pattern through so verifiers.run_tier1_verification
        # can actually reach the regex-check branch — it dispatches on
        # evidence_kwargs.get("pattern"), which only exists if we put it here.
        result["pattern"] = step.pattern
        # if the success_condition implies checking a written file, read it back
        if "report.txt" in step.success_condition or "file" in step.success_condition.lower():
            try:
                with open(f"{SCRATCH_DIR}/report.txt") as f:
                    result["file_content"] = f.read()
            except FileNotFoundError:
                result["file_content"] = ""

    elif step.action_type == "apply_patch":
        # Used for judge-only steps (e.g. "improve readability") where there's
        # nothing to run — the Tier-2 judge evaluates the file content directly.
        try:
            with open(f"{SCRATCH_DIR}/{step.target_file}") as f:
                content = f.read()
            result = {"returncode": 0, "stdout": content, "file_content": content}
        except FileNotFoundError:
            result = {"returncode": 1, "stdout": "", "stderr": f"{step.target_file} not found"}

    else:
        result = {"returncode": 1, "stdout": "", "stderr": f"unknown action_type {step.action_type}"}

    return result


def apply_patch(target_file: str, new_content: str, editable_files: list[str]) -> None:
    """
    Writes a patch to disk. Raises PatchRejected if target_file isn't in
    the allowlist for this step — this is what stops Recovery from ever
    editing a spec/test file to force a pass.
    """
    from contracts import PatchRejected

    if target_file not in editable_files:
        raise PatchRejected(f"{target_file} is a frozen spec file — Recovery cannot edit it")

    with open(f"{SCRATCH_DIR}/{target_file}", "w") as f:
        f.write(new_content)
