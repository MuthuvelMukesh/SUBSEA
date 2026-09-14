from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

from subsea.models import Hypothesis, Decision
from subsea.pipeline import run_pipeline, run_multi_node_pipeline, run_multi_vessel_pipeline
from subsea.simulation import (
    make_scenario,
    generate_observations,
    generate_multi_node_observations,
    generate_multi_vessel_scenario,
    SUPPORTED_SCENARIOS,
    _DEFINITIONS,
)
from subsea.behaviour import compute_spectral_features
from subsea.adversarial import SUPPORTED_ATTACKS, apply_attack

st.set_page_config(
    page_title="Subsea Disturbance Assessment — Evidence Fusion",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Top Banner / Header
st.title("🌊 Subsea Cable Disturbance Assessment")
st.markdown(
    "**An Uncertainty-Aware Multimodal Evidence Fusion Framework for Vessel-Associated Subsea Cable Disturbance Assessment under Adversarial Uncertainty**"
)

# Provenance and Data Kind Disclaimer Badges
col_banner1, col_banner2, col_banner3 = st.columns([2, 1, 1])
with col_banner1:
    st.info("🔬 **Data Kind: SIMULATION (Synthetic Evaluation)** — Synthetic results are not operational evidence and do not constitute causal ground truth.")
with col_banner2:
    st.warning("⚠️ **Real DAS/AIS: PENDING / NOT EXECUTED** — Pending external field acquisition (Marlinks/Paphos).")
with col_banner3:
    st.secondary_status = "🛠️ **Hardware: FUTURE WORK** (Decoupled from paper validation)."
    st.caption("Hardware: FUTURE WORK | Protocol: Synthetic Causal Proof")

st.divider()

# Sidebar Navigation
st.sidebar.title("Navigation & Controls")
nav_section = st.sidebar.radio(
    "Select Dashboard View:",
    [
        "1. Overview & Architecture",
        "2. Scenario Explorer (S01–S22)",
        "3. Sensor Waveforms & FFT",
        "4. Spatial Trajectory & Kinematics",
        "5. Evidence & Uncertainty Timelines",
        "6. Hypotheses & Counter-Evidence",
        "7. Adversarial Severity & Evasion",
        "8. Baselines & Ablation Studies",
        "9. Experiment Manifests & Provenance",
        "10. Publication Figures & Tables",
    ],
)

# Scenario Selector
st.sidebar.subheader("Scenario Configuration")
selected_scenario_id = st.sidebar.selectbox(
    "Scenario Identifier",
    sorted(list(SUPPORTED_SCENARIOS)),
    index=sorted(list(SUPPORTED_SCENARIOS)).index("S01"),
)
random_seed = st.sidebar.number_input("Simulation Random Seed", min_value=0, max_value=999999, value=42, step=1)
attack_selection = st.sidebar.selectbox("Adversarial Attack", ["none"] + sorted(SUPPORTED_ATTACKS))
attack_severity = st.sidebar.slider("Attack Severity", min_value=0.0, max_value=1.0, value=0.5, step=0.05) if attack_selection != "none" else 0.0

# Generate scenario data
scenario = make_scenario(selected_scenario_id, int(random_seed))
observations, vessel = generate_observations(scenario)

# Apply adversarial attack if selected
if attack_selection != "none":
    observations, vessel = apply_attack(observations, vessel, attack_selection, attack_severity, int(random_seed))

result = run_pipeline(observations, vessel, environmental_event=scenario.environmental_event)

# ---------------------------------------------------------------------------
# VIEW 1: Overview & Architecture
# ---------------------------------------------------------------------------
if nav_section == "1. Overview & Architecture":
    st.header("1. Framework Overview & Architecture")
    
    st.markdown("""
    This research platform evaluates multimodal evidence fusion for detecting subsea cable disturbances 
    (anchor dragging, bottom-trawl gear interactions, dropped objects) in the presence of 
    adversarial AIS spoofing, sensor dropouts, noise, and environmental confounding.
    """)
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pipeline Decision", result.decision.value, help="T0=Normal, T1=Low, T2=High, T3=Urgent, TX=Fail-Closed")
    c2.metric("Physical Confidence (CP)", f"{result.physical_confidence:.3f}")
    c3.metric("Association Confidence (CA)", f"{result.association_confidence:.3f}")
    c4.metric("Sensor Reliability (CR)", f"{result.reliability:.3f}")
    c5.metric("Epistemic Uncertainty (U)", f"{result.uncertainty:.3f}")
    
    st.subheader("Decision Semantics & State Machine")
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        st.markdown("""
        - **`T0` (Normal Transit / Ambient)**: No disturbance detected or normal benign transit.
        - **`T1` (Low Advisory)**: Weak association or minor vibration anomaly below escalation threshold.
        - **`T2` (High Escalation)**: Corroborated physical disturbance with confirmed spatial-temporal vessel co-occurrence.
        - **`T3` (Urgent Intervention)**: Critical disturbance confirmed with severe dwell/speed anomaly and high reliability.
        - **`TX` (Indeterminate Fail-Closed)**: Epistemic uncertainty exceeds tolerance ($U > \tau_{TX}$) or sensor failure detected.
        """)
    with col_stat2:
        st.markdown("""
        **Competing Hypotheses Evaluated:**
        - **`H0`**: Normal ambient acoustic/vibrational state; no vessel interaction.
        - **`H1`**: Vessel-associated subsea cable disturbance (drag/trawl/strike).
        - **`H2`**: Environmental or non-vessel event (seismic, current, marine fauna).
        - **`H3`**: Benign vessel transit without cable contact/interaction.
        """)
    
    st.subheader("System Status Legend")
    st.table(pd.DataFrame([
        {"Category": "Synthetic Simulation", "Coverage": "S01–S22 Full Suite", "Status": "EXECUTED", "Ground Truth": "Synthetic (not causal operational truth)"},
        {"Category": "Multi-Node Sensing", "Coverage": "5-node spatial array (nodes N01-N05)", "Status": "EXECUTED", "Ground Truth": "Synthetic"},
        {"Category": "Multi-Vessel Disambiguation", "Coverage": "Candidate ranking & association", "Status": "EXECUTED", "Ground Truth": "Synthetic"},
        {"Category": "Adversarial Robustness", "Coverage": "Spoofing, timestamp manipulation, evasion", "Status": "EXECUTED", "Ground Truth": "Synthetic"},
        {"Category": "Real DAS/AIS Field Data", "Coverage": "Marlinks/Paphos external datasets", "Status": "NOT EXECUTED / PENDING", "Ground Truth": "External benchmark required"},
        {"Category": "Physical Hardware Testbench", "Coverage": "ESP32/MPU6050 physical testbench", "Status": "FUTURE WORK", "Ground Truth": "Hardware decoupled from paper"},
    ]))

# ---------------------------------------------------------------------------
# VIEW 2: Scenario Explorer
# ---------------------------------------------------------------------------
elif nav_section == "2. Scenario Explorer (S01–S22)":
    st.header(f"2. Scenario Explorer: {selected_scenario_id}")
    st.markdown(f"**Description**: {scenario.description}")
    
    st.caption("Ground Truth Attributes (Synthetic):")
    gt_cols = st.columns(6)
    gt_cols[0].checkbox("Vessel Present", value=scenario.vessel_present, disabled=True)
    gt_cols[1].checkbox("Disturbance Present", value=scenario.disturbance_present, disabled=True)
    gt_cols[2].checkbox("Environmental Event", value=scenario.environmental_event, disabled=True)
    gt_cols[3].checkbox("Sensor Failure", value=scenario.sensor_failure, disabled=True)
    gt_cols[4].checkbox("AIS Spoofing", value=scenario.spoofing, disabled=True)
    gt_cols[5].checkbox("Time Manipulation", value=scenario.timestamp_manipulation, disabled=True)
    
    st.subheader("All Scenarios Matrix (S01–S22)")
    scenario_summary_list = []
    for sid in sorted(SUPPORTED_SCENARIOS):
        sc_obj = make_scenario(sid, 42)
        scenario_summary_list.append({
            "Scenario": sid,
            "Description": sc_obj.description,
            "Vessel": "Yes" if sc_obj.vessel_present else "No",
            "Disturbance": "Yes" if sc_obj.disturbance_present else "No",
            "Environmental": "Yes" if sc_obj.environmental_event else "No",
            "Adversarial / Failure": "Yes" if (sc_obj.sensor_failure or sc_obj.spoofing or sc_obj.timestamp_manipulation or sc_obj.spatial_manipulation) else "No",
        })
    st.dataframe(pd.DataFrame(scenario_summary_list), use_container_width=True)

# ---------------------------------------------------------------------------
# VIEW 3: Sensor Waveforms & FFT
# ---------------------------------------------------------------------------
elif nav_section == "3. Sensor Waveforms & FFT":
    st.header(f"3. Sensor Waveforms & FFT Spectral Analysis: {selected_scenario_id}")
    
    times = [obs.timestamp for obs in observations]
    t_rel = [t - times[0] for t in times]
    ax_vals = [obs.ax for obs in observations]
    ay_vals = [obs.ay for obs in observations]
    az_vals = [obs.az for obs in observations]
    mag_vals = [np.sqrt(a**2 + b**2 + c**2) for a, b, c in zip(ax_vals, ay_vals, az_vals)]
    
    st.subheader("Tri-axial Acceleration & Total Magnitude")
    df_acc = pd.DataFrame({
        "Time (s)": t_rel,
        "Ax (m/s²)": ax_vals,
        "Ay (m/s²)": ay_vals,
        "Az (m/s²)": az_vals,
        "Magnitude (m/s²)": mag_vals,
    }).set_index("Time (s)")
    st.line_chart(df_acc[["Ax (m/s²)", "Ay (m/s²)", "Az (m/s²)"]])
    st.line_chart(df_acc[["Magnitude (m/s²)"]])
    
    st.subheader("Fast Fourier Transform (FFT) Power Spectrum")
    spec = compute_spectral_features(observations)
    st.write(f"**Energy**: `{spec['energy']:.4f}` | **Peak Frequency**: `{spec['peak_frequency']:.2f} Hz` | **Spectral Entropy**: `{spec['spectral_entropy']:.4f}`")
    
    # Compute FFT for visual display
    signal = np.array(mag_vals) - np.mean(mag_vals)
    n = len(signal)
    if n > 1:
        dt = np.mean(np.diff(t_rel)) if len(t_rel) > 1 else 0.1
        freqs = np.fft.rfftfreq(n, d=dt)
        fft_mags = np.abs(np.fft.rfft(signal))
        df_fft = pd.DataFrame({"Frequency (Hz)": freqs, "Power Spectral Amplitude": fft_mags}).set_index("Frequency (Hz)")
        st.bar_chart(df_fft)

# ---------------------------------------------------------------------------
# VIEW 4: Spatial Trajectory & Kinematics
# ---------------------------------------------------------------------------
elif nav_section == "4. Spatial Trajectory & Kinematics":
    st.header(f"4. Spatial Cable Geometry & Vessel Kinematics: {selected_scenario_id}")
    
    if vessel and vessel.trajectory:
        traj_df = pd.DataFrame([
            {
                "Time (s)": p.timestamp - vessel.trajectory[0].timestamp,
                "Longitude": p.longitude,
                "Latitude": p.latitude,
                "Speed (knots)": p.speed_knots,
                "Course (deg)": p.course_degrees,
                "Distance to Cable (m)": p.distance_to_cable_m,
            }
            for p in vessel.trajectory
        ])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Closest Point of Approach (CPA)", f"{min(p.distance_to_cable_m for p in vessel.trajectory):.1f} m")
        c2.metric("Mean Speed", f"{np.mean([p.speed_knots for p in vessel.trajectory]):.1f} knots")
        c3.metric("Transponder Status", "Enabled" if vessel.transponder_enabled else "Suppressed / Disabled")
        
        st.subheader("Vessel Distance to Cable over Time")
        st.line_chart(traj_df.set_index("Time (s)")[["Distance to Cable (m)"]])
        
        st.subheader("Spatial Position Coordinates")
        st.dataframe(traj_df, use_container_width=True)
    else:
        st.warning("No vessel trajectory present in this scenario (e.g. ambient normal or environmental-only condition).")

# ---------------------------------------------------------------------------
# VIEW 5: Evidence & Uncertainty Timelines
# ---------------------------------------------------------------------------
elif nav_section == "5. Evidence & Uncertainty Timelines":
    st.header(f"5. Evidence Confidence & Uncertainty Breakdown: {selected_scenario_id}")
    
    ev_df = pd.DataFrame({
        "Dimension": ["Physical Evidence (CP)", "Association Evidence (CA)", "Sensor Reliability (CR)", "Epistemic Uncertainty (U)"],
        "Value": [result.physical_confidence, result.association_confidence, result.reliability, result.uncertainty],
    })
    st.bar_chart(ev_df.set_index("Dimension"))
    
    st.subheader("Uncertainty Decomposition")
    st.markdown(f"""
    - **Total Epistemic Uncertainty ($U$)**: `{result.uncertainty:.4f}`
    - **Physical Confidence ($C_P$)**: `{result.physical_confidence:.4f}`
    - **Spatial-Temporal Association ($C_A$)**: `{result.association_confidence:.4f}`
    - **Sensor Health & Reliability ($C_R$)**: `{result.reliability:.4f}`
    - **Fail-Closed TX Trigger Condition**: $U > \\tau_{{TX}}$ or $C_R < \\tau_{{fail}}$
    """)

# ---------------------------------------------------------------------------
# VIEW 6: Hypotheses & Counter-Evidence
# ---------------------------------------------------------------------------
elif nav_section == "6. Hypotheses & Counter-Evidence":
    st.header(f"6. Competing Hypotheses & Audit Trail: {selected_scenario_id}")
    
    st.subheader("Hypothesis Probabilities / Scores")
    st.bar_chart(result.hypothesis_scores)
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Positive Evidence")
        if result.positive_evidence:
            for item in result.positive_evidence:
                st.write(f"✅ {item}")
        else:
            st.caption("None reported.")
            
        st.subheader("Counter-Evidence")
        if result.counter_evidence:
            for item in result.counter_evidence:
                st.write(f"❌ {item}")
        else:
            st.caption("None reported.")
            
    with c2:
        st.subheader("Missing Corroboration")
        if result.missing_corroboration:
            for item in result.missing_corroboration:
                st.write(f"⚠️ {item}")
        else:
            st.caption("All expected corroborating modalities satisfied.")
            
        st.subheader("Decision Rationale")
        st.info(result.rationale)

# ---------------------------------------------------------------------------
# VIEW 7: Adversarial Severity & Evasion
# ---------------------------------------------------------------------------
elif nav_section == "7. Adversarial Severity & Evasion":
    st.header("7. Adversarial Attacks & Severity Sweeps")
    st.markdown("""
    Evaluates adversarial evasion and manipulation targeting multimodal fusion:
    - **AIS Spoofing**: Fabricating ghost positions away from the disturbance zone.
    - **Timestamp Manipulation**: Desynchronizing vibration and AIS clocks to break temporal correlation.
    - **Spatial Manipulation**: Shifting trajectory coordinates perpendicularly to the subsea cable.
    - **Combined Evasion**: Coordinated multi-vector spoofing + timestamp skew.
    """)
    
    st.write(f"Current Active Attack: **`{attack_selection}`** at Severity: **`{attack_severity:.2f}`**")
    
    # Run a quick 5-point severity preview
    sweep_data = []
    for sev in [0.0, 0.25, 0.5, 0.75, 1.0]:
        sc_t = make_scenario(selected_scenario_id, int(random_seed))
        obs_t, ves_t = generate_observations(sc_t)
        if attack_selection != "none":
            obs_t, ves_t = apply_attack(obs_t, ves_t, attack_selection, sev, int(random_seed))
        res_t = run_pipeline(obs_t, ves_t, environmental_event=sc_t.environmental_event)
        sweep_data.append({
            "Severity": sev,
            "Decision": res_t.decision.value,
            "Uncertainty": res_t.uncertainty,
            "Association Conf": res_t.association_confidence,
        })
    st.dataframe(pd.DataFrame(sweep_data), use_container_width=True)

# ---------------------------------------------------------------------------
# VIEW 8: Baselines & Ablation Studies
# ---------------------------------------------------------------------------
elif nav_section == "8. Baselines & Ablation Studies":
    st.header("8. Comparative Baselines & Ablation Analysis")
    st.markdown("""
    **Architectural Ablations:**
    - `no_behavior`: Disables vessel kinematic dwelling/course deviation analysis.
    - `equal_weights`: Replaces calibrated evidence weights with equal 1/3 weighting.
    - `no_health`: Ignores sensor failure and missing packet indicators.
    - `no_uncertainty`: Omits epistemic uncertainty penalty ($U=0$).
    - `uncalibrated`: Uses arbitrary default decision thresholds.
    """)
    
    st.info("To generate full ablation and baseline manifests, run `python scripts/run_baselines.py`.")

# ---------------------------------------------------------------------------
# VIEW 9: Experiment Manifests & Provenance
# ---------------------------------------------------------------------------
elif nav_section == "9. Experiment Manifests & Provenance":
    st.header("9. Experiment Manifests & Reproducibility Audits")
    st.markdown("""
    Every experiment produces a deterministic, machine-readable JSON manifest 
    capturing seeds, configurations, Git commit hash, software version, and raw cohort records.
    """)
    
    st.json({
        "framework_version": "0.1.0",
        "current_scenario": selected_scenario_id,
        "seed": int(random_seed),
        "attack": attack_selection,
        "attack_severity": attack_severity,
        "data_kind": "synthetic",
        "provenance_verified": True,
        "causal_ground_truth": False,
        "decision": result.decision.value,
    })

# ---------------------------------------------------------------------------
# VIEW 10: Publication Figures & Tables
# ---------------------------------------------------------------------------
elif nav_section == "10. Publication Figures & Tables":
    st.header("10. Publication Figures & LaTeX / CSV Tables")
    st.markdown("""
    Publication artifacts conform to IEEE standard formats, traceable directly to reproducible experiment manifests.
    """)
    
    st.subheader("Available Publication Figures (IEEE Format)")
    st.markdown("""
    - **Figure 1**: Multimodal fusion architecture and threat model.
    - **Figure 2**: End-to-end evidence fusion state transition pipeline.
    - **Figure 3**: Scenario-wise accuracy across S01–S22 synthetic benchmarks.
    - **Figure 4**: Baseline comparison against Random Forest, Decision Tree, Heuristic.
    - **Figure 5**: Systematic ablation study across 5 architectural variants.
    - **Figure 6**: Adversarial Error Rate (AER) vs. attack severity curves.
    - **Figure 7**: False High Escalation Rate (FHER) under adversarial spoofing.
    - **Figure 8**: Uncertainty degradation under noise, packet loss, and position uncertainty.
    - **Figure 9**: Empirical reliability diagram & calibration curve (ECE & Brier score).
    - **Figure 10**: DAS/AIS spatio-temporal association geometry demonstration.
    - **Figure 11**: Competing hypothesis score distributions across scenarios.
    - **Figure 12**: Decision-state distributions across synthetic cohorts.
    """)
