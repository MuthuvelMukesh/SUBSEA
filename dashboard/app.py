from __future__ import annotations

import streamlit as st

from subsea.pipeline import run_pipeline
from subsea.simulation import generate_observations, make_scenario

st.set_page_config(page_title="Subsea Evidence Fusion", layout="wide")
st.title("Subsea Disturbance Assessment")
st.caption("Research prototype. Synthetic results are not operational evidence.")
scenario_id = st.sidebar.selectbox("Scenario", ["S01", "S02", "S04", "S05", "S07", "S17", "S18"])
seed = st.sidebar.number_input("Random seed", min_value=0, value=42, step=1)
scenario = make_scenario(scenario_id, int(seed))
observations, vessel = generate_observations(scenario)
result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)

columns = st.columns(5)
for column, label, value in zip(columns, ["Decision", "CP", "CA", "Reliability", "Uncertainty"], [result.decision, result.physical_confidence, result.association_confidence, result.reliability, result.uncertainty]):
    column.metric(label, f"{value:.3f}" if isinstance(value, float) else value)
st.subheader("Hypotheses")
st.bar_chart(result.hypothesis_scores)
st.subheader("Audit trail")
st.json({"positive_evidence": result.positive_evidence, "counter_evidence": result.counter_evidence, "missing_corroboration": result.missing_corroboration, "rationale": result.rationale})
