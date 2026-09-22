"""
app.py — Step 9

Two views, one page:

  "Try It Yourself" — upload your code file and its test file separately,
  hit Run, and get back the corrected code file. No Planner call: with an
  explicit code file + test file, the step is unambiguous (run the test
  file, the test file is the frozen spec), so this constructs the
  PlannedStep directly instead of asking an LLM to guess file roles —
  fewer tokens spent, and it can't repeat the target_file mix-up we hit
  earlier when the Planner was inferring that from free text.

  "Live Ledger" — the original view: auto-refreshes off ledger.jsonl, meant
  to be left open while you trigger a run from a second terminal
  (`python run_full.py`) for a rehearsed demo.

Both tabs go through the exact same graph.py / ledger.py the rest of the
system uses — nothing here bypasses or duplicates the zero-trust pipeline,
it's just a second way to drive it besides a terminal script.

Run with: streamlit run app.py
"""

import difflib
import os

import pandas as pd
import streamlit as st

from contracts import PlannedStep
from executor import SCRATCH_DIR
from graph import run_step
from ledger import read_all_rows, reset_ledger

st.set_page_config(page_title="Evidence-Gated Agent", layout="wide")
st.title("🔒 Evidence-Gated Self-Healing Agent")

tab_try, tab_ledger = st.tabs(["🧪 Try It Yourself", "📜 Live Ledger"])


# ============================================================== Try It Yourself
with tab_try:
    st.caption(
        "Upload your code file and its test file. The agent runs the test "
        "for real, and if it fails, tries to fix your code — never the "
        "test — and re-runs until it passes or runs out of attempts."
    )

    col1, col2 = st.columns(2)
    with col1:
        code_file = st.file_uploader("Your code file", key="code_upload")
    with col2:
        test_file = st.file_uploader("Your test file (defines correctness — never modified)", key="test_upload")

    ready = bool(code_file and test_file)
    if code_file and test_file and code_file.name == test_file.name:
        st.error("Code file and test file can't be the same file.")
        ready = False

    run_clicked = st.button("▶ Run Agent", type="primary", disabled=not ready)

    if run_clicked:
        os.makedirs(SCRATCH_DIR, exist_ok=True)

        # Isolated per run — old uploads from a previous try don't linger
        # and confuse this one.
        for existing in os.listdir(SCRATCH_DIR):
            path = os.path.join(SCRATCH_DIR, existing)
            if os.path.isfile(path):
                os.remove(path)

        code_content = code_file.getvalue().decode("utf-8", errors="replace")
        test_content = test_file.getvalue().decode("utf-8", errors="replace")
        with open(os.path.join(SCRATCH_DIR, code_file.name), "w") as f:
            f.write(code_content)
        with open(os.path.join(SCRATCH_DIR, test_file.name), "w") as f:
            f.write(test_content)

        reset_ledger()  # this run's ledger view starts clean

        step = PlannedStep(
            step_id="user_test",
            action_type="run_tests",
            target_file=test_file.name,   # the literal pytest argument
            spec_file=test_file.name,     # frozen — Recovery is blocked from touching this
            success_condition="pytest exit code == 0",
        )
        all_files = [code_file.name, test_file.name]

        st.subheader("Execution")

        with st.spinner("Running your test..."):
            state = run_step(step, all_files)

        # Every attempt got appended to ledger.jsonl by run_step() itself, via
        # the same append_row() call the terminal flow uses — not something
        # this UI constructs after the fact. Since reset_ledger() ran right
        # before this, every row here belongs to THIS run. Show all of them,
        # each with its raw pytest stdout/stderr, so "attempts: N" isn't a
        # number you have to take on faith.
        attempt_rows = [r for r in read_all_rows() if r["step_id"] == "user_test"]
        st.dataframe(
            pd.DataFrame([
                {"attempt": r["attempt"], "tier": r["tier"], "verdict": r["verdict"], "timestamp": r["timestamp"]}
                for r in attempt_rows
            ]),
            use_container_width=True, hide_index=True,
        )
        for r in attempt_rows:
            with st.expander(f"Raw evidence — attempt {r['attempt']} ({r['verdict']})"):
                st.code(r["evidence"].get("stdout", "") + r["evidence"].get("stderr", ""), language="text")

        if state.status == "verified_pass":
            if state.attempt > 1:
                st.success(f"Passed after {state.attempt} attempt(s) — the agent fixed your code.")
            else:
                st.success("Passed on the first try — your code already satisfied the test.")
        else:
            st.warning(
                "Didn't reach a verified pass (see status above) — this can "
                "mean the fix attempts were exhausted, or Recovery tried to "
                "touch the test file and got blocked, flagging it for "
                "human review instead."
            )

        st.subheader("Your corrected file")
        path = os.path.join(SCRATCH_DIR, code_file.name)
        with open(path) as f:
            after = f.read()

        if after == code_content:
            st.markdown(f"**`{code_file.name}`** — unchanged")
            st.code(after, language="python")
        else:
            st.markdown(f"**`{code_file.name}`** — patched by Recovery")
            diff = "\n".join(difflib.unified_diff(
                code_content.splitlines(), after.splitlines(),
                fromfile=f"{code_file.name} (before)", tofile=f"{code_file.name} (after)", lineterm="",
            ))
            st.code(diff, language="diff")

        st.download_button(f"Download {code_file.name}", data=after, file_name=code_file.name)


# ================================================================== Live Ledger
with tab_ledger:
    st.caption(
        "Auto-refreshing view of ledger.jsonl. Leave this open and trigger a "
        "run from a second terminal (e.g. `python run_full.py`) to watch it live."
    )

    @st.fragment(run_every="1s")
    def live_ledger():
        rows = read_all_rows()
        if not rows:
            st.info("Waiting for the agent to start executing steps...")
            return

        df = pd.DataFrame(rows)

        def verdict_badge(row):
            if row["verdict"] == "pass" and row["tier"] == "deterministic":
                return "✅ PASS (deterministic)"
            elif row["verdict"] == "pass" and row["tier"] == "llm_judge":
                return f"🟡 PASS (LLM-judged, conf {row['confidence']:.2f})"
            elif row["verdict"] == "fail":
                return "❌ FAIL"
            return "⏳ N/A"

        df["display"] = df.apply(verdict_badge, axis=1)
        st.dataframe(
            df[["step_id", "attempt", "tier", "display", "timestamp"]],
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Raw evidence (most recent row)"):
            st.json(rows[-1]["evidence"])

    live_ledger()