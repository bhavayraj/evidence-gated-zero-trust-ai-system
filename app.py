"""
app.py — Step 9

Streamlit frontend. Reads ONLY from ledger.py's read_all_rows() — never
touches graph.py's internal state directly. This keeps the dashboard fully
decoupled: backend logic can keep changing without breaking the UI.

Run with: streamlit run app.py
"""

import time
import streamlit as st
import pandas as pd
from ledger import read_all_rows

st.set_page_config(page_title="Evidence-Gated Agent", layout="wide")
st.title("🔒 Evidence-Gated Self-Healing Agent — Live Ledger")

placeholder = st.empty()

while True:
    rows = read_all_rows()
    with placeholder.container():
        if not rows:
            st.info("Waiting for the agent to start executing steps...")
        else:
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

            with st.expander("Raw evidence (click a row's step_id to inspect)"):
                st.json(rows[-1]["evidence"])

    time.sleep(1)
