# Subsea Cable Disturbance Assessment

> **An Uncertainty-Aware Multimodal Evidence Fusion Framework for Vessel-Associated Subsea Cable Disturbance Assessment under Adversarial Uncertainty**

[![Tests](https://img.shields.io/badge/tests-266%20passed-brightgreen)](#test-suite)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![Data Kind](https://img.shields.io/badge/data%20kind-SIMULATION%20%2B%20REAL%20DATA-brightgreen)](#scientific-integrity--provenance)
[![Web Front End](https://img.shields.io/badge/web%20front%20end-14%20pages%20%7C%20static-blue)](web/index.html)

A reproducible research platform for uncertainty-aware multimodal evidence fusion under adversarial uncertainty. The framework integrates subsea vibration sensing (accelerometer/DAS acoustic), AIS vessel tracking kinematics, sensor health diagnostics, epistemic uncertainty quantification, and multi-hypothesis assessment to reliably distinguish vessel-caused cable disturbances (anchor dragging, bottom-trawling) from benign transit, sensor malfunctions, environmental confounding, and adversarial evasion (AIS spoofing, timestamp manipulation).

---

## Scientific Integrity & Provenance

- **SIMULATION (Synthetic Evaluation)**: Synthetic scenario results (S01–S22) are computational experiment outputs generated from explicit mathematical and physical models; they are not operational real-world evidence and do not constitute causal ground truth.
- **REAL DAS EVALUATION (EXECUTED)**: Three real subsea DAS datasets are integrated with verified SHA-256 cryptographic provenance and strictly defined scientific roles:
  1. **Marlinks Demo DAS (North Sea)**: Validates high-frequency DAS spectral acoustic energy and 1D vessel proximity correlation ($\rho = +0.9482, p < 10^{-30}$) during a container ship transit. Does not provide 2D AIS polyline reconstruction or causal damage ground truth.
  2. **EMSO Western Ionian Observatory DAS**: Validates abyssal deep-sea ambient baseline noise floor stability ($\text{CV}_{\text{temporal}} = 0.0008$) and spatial inter-channel variance across 2,963 channels. Unperturbed baseline recording.
  3. **Dryad Oliktok Submarine DAS (Beaufort Sea, Arctic Ocean)**: Validates multi-week environmental noise stability ($\text{CV}_{\text{temporal}} = 0.1239$), oceanographic wave/pressure hydrodynamic coupling ($p < 10^{-14}$), and physical detector false-escalation avoidance (no T2/T3 vessel alarms across 27.6 days of Arctic storm variations). Does not contain vessel or AIS labels.
- **HARDWARE TESTBENCH**: Physical ESP32 / MPU6050 hardware validation is decoupled from the theoretical/fusion paper and is categorized as **`FUTURE WORK`**.
- **NO SILENT REPAIR / NO FABRICATION**: Experiment runners and report generators reject fabricated records, missing cohorts, out-of-range metrics, unverified manifests, and mismatched seeds.

---

## Repository Structure

```
├── config/
│   └── system.yaml                  # System configuration (weights, thresholds, uncertainty lambdas)
├── dashboard/
│   └── app.py                       # (Deprecated) Streamlit research dashboard prototype
├── web/                             # Standalone static web front end (14 interactive pages)
│   ├── index.html                   # Shell & hash-based routing entrypoint
│   ├── assets/                      # CSS styling and static publication figures
│   ├── vendor/                      # Offline vendored Plotly.js (v6.4.0)
│   ├── data/                        # Exported precomputed research manifests & runs
│   └── js/                          # ES modules for 14 pages and components
├── data/
│   ├── PROVENANCE.json              # SHA-256 provenance records for real external datasets
│   ├── marlinks_demo/               # Reduced Marlinks North Sea DAS demo (channels 1440-1690)
│   ├── emso_ionian/                 # EMSO Western Ionian seafloor observatory DAS (10 Hz decimated)
│   └── Dryad_Oliktok/               # Dryad Oliktok Arctic seafloor telecommunication DAS & moorings
├── docs/
│   ├── OLITKOK_VALIDATION_REPORT.md # 19-point scientific validation report for Dryad Oliktok DAS
│   └── FINAL_PAPER_READINESS_REPORT.md # Forensic paper-readiness evaluation report
├── scripts/
│   ├── generate_paper_results.py    # End-to-end generator for IEEE publication tables & figures
│   ├── run_simulation.py            # Single & all-scenario (S01–S22) simulation runner
│   ├── run_monte_carlo.py           # Multi-trial reproducible Monte Carlo experiment runner
│   ├── run_adversarial.py           # Adversarial attack evaluator (AER/FHER cohorts)
│   ├── run_attack_sweep.py          # Adversarial severity sweep generator
│   ├── run_robustness.py            # Noise, packet-loss, and position-uncertainty sweeps
│   ├── run_baselines.py             # Baseline comparisons (ML & heuristics) and ablations
│   ├── run_real_evaluation.py       # Real-data evaluator for Marlinks and EMSO DAS datasets
│   └── run_oliktok_evaluation.py     # Real-data evaluator for Dryad Oliktok submarine DAS
├── src/subsea/
│   ├── acquisition.py               # Sensor packet schema & receiver adapters (MQTT/HTTP/Serial)
│   ├── adversarial.py               # AIS spoofing, transponder suppression, timestamp/spatial manipulation
│   ├── ais.py                       # AIS trajectory loader, deduplication, interpolation
│   ├── association.py               # Spatial, temporal, and kinematic association
│   ├── baselines.py                 # Scikit-learn ML baselines (Random Forest, Decision Tree)
│   ├── behaviour.py                 # Vessel behaviour analysis & spectral feature extraction
│   ├── calibration.py               # Note: calibration functions integrated in metrics.py & experiments.py
│   ├── cli.py                       # CLI entrypoints
│   ├── das.py                       # Read-only DAS HDF5 loader with SHA-256 validation
│   ├── das_ais_association.py       # DAS acoustic event to AIS track association pipeline
│   ├── decision.py                  # Decision state engine (T0, T1, T2, T3, TX) with reliability-first hierarchy
│   ├── evaluation.py                # Note: evaluation harnesses integrated in experiments.py & *_evaluation.py
│   ├── hil_abysslink.py             # Hardware-in-the-Loop bridge for AbyssLink ESP32 serial telemetry
│   ├── experiments.py               # Experiment runners with append-only manifest guarantees
│   ├── features.py                  # Acceleration magnitude and spectral features
│   ├── fusion.py                    # Multimodal weighted evidence fusion & competing hypotheses
│   ├── geometry.py                  # Cable polyline geometry, CPA, dwell, crossing
│   ├── health.py                    # Sensor availability, freshness, constant-value detection
│   ├── metrics.py                   # Classification metrics, AER, FHER cohorts
│   ├── models.py                    # Typed Pydantic contracts
│   ├── oliktok.py                   # Read-only NetCDF-4 adapter for Dryad Oliktok DAS dataset
│   ├── oliktok_evaluation.py        # Physical characterization & false-escalation evaluation engine
│   ├── pipeline.py                  # End-to-end decision pipelines (single/multi-node/multi-vessel)
│   ├── real_data.py                 # Read-only CSV/JSON/HDF5/NetCDF data boundary loaders
│   ├── real_evaluation.py           # Evaluation engines for Marlinks and EMSO real datasets
│   ├── reporting.py                 # Publication figure (1–12) and table (I–IX) generators
│   ├── simulation.py                # Deterministic synthetic scenarios (S01–S22)
│   └── statistics.py                # Paired bootstrap, permutation tests, Cohen's d, McNemar
└── tests/                           # 23 test suites, 240 unit and regression tests
```

---

## Installation & Setup

```bash
# Clone and enter directory
cd /path/to/SUBSEA

# Create virtual environment
python -m venv .venv
# On Linux/macOS: source .venv/bin/activate
# On Windows: .venv\Scripts\activate

# Install dependencies (includes test, ui, ml, realdata, and hil extras)
python -m pip install -r requirements.txt
# Or selectively:
python -m pip install -e .[test,ui,ml,realdata,hil]
```

---

## Test Suite

Run the full automated test suite:

```bash
python -m pytest tests/ -q
```

*Current test result: `240 passed, 0 failed, 0 skipped`.*

---

## Research Workflow & Execution Commands

### 1. Single Scenario Simulation
Run a single scenario (e.g. S04: anchor dragging) and inspect intermediate outputs:
```bash
python scripts/run_simulation.py --scenario S04 --seed 42 --output results/sim_s04.json
```

### 2. Full Scenario Benchmark (S01–S22)
Execute the complete suite of 22 benchmark scenarios:
```bash
python scripts/run_simulation.py --all-scenarios --seed 42 --output results/all_scenarios.json
```

### 3. Reproducible Monte Carlo Evaluation
Run 100 seeded Monte Carlo trials across all scenarios:
```bash
python scripts/run_monte_carlo.py --scenarios S01 S02 S03 S04 S05 S07 S11 S17 S18 S22 --trials 100 --seed 42 --output results/monte_carlo
```

### 4. Adversarial Attack Severity Sweeps
Evaluate evasion resistance under AIS spoofing and timestamp manipulation across severity levels [0.0, 1.0]:
```bash
python scripts/run_attack_sweep.py --scenario S04 --attack ais_spoofing --trials 50 --output results/adv_spoofing
python scripts/run_attack_sweep.py --scenario S04 --attack timestamp_manipulation --trials 50 --output results/adv_timestamp
```

### 5. Sensor Robustness Sweeps
Evaluate degradation under noise, packet loss, and position uncertainty:
```bash
python scripts/run_robustness.py --scenario S04 --sweep noise --trials 50 --output results/sweep_noise
python scripts/run_robustness.py --scenario S04 --sweep packet_loss --trials 50 --output results/sweep_packet_loss
python scripts/run_robustness.py --scenario S04 --sweep position_uncertainty --trials 50 --output results/sweep_pos_unc
```

### 6. Comparative Baseline & Ablation Evaluation
Evaluate comparative baselines (Random Forest, Decision Tree, Heuristic) and systematic architectural ablations:
```bash
python scripts/run_baselines.py --scenario S01 S04 S07 S11 S17 S18 --trials 50 --seed 42 --output results/baselines
```

### 7. End-to-End Publication Figures and Tables Generation
Generate all 12 IEEE publication figures and 9 LaTeX / CSV tables from executed data manifests:
```bash
python scripts/generate_paper_results.py --run-suite --trials 10 --seed 42 --output artifacts/paper_results
```
This produces in `artifacts/paper_results/core/`:
- **Figure 1**: Framework Architecture (`figure_architecture.png`)
- **Figure 2**: Evidence Fusion Pipeline Flowchart (`figure_fusion_pipeline.png`)
- **Figure 3**: Scenario-wise Classification Accuracy (`figure_scenario_performance.png`)
- **Figure 4**: Baseline Method Comparison (`figure_method_comparison.png`)
- **Figure 5**: Systematic Ablation Study (`figure_ablation_study.png`)
- **Figure 6**: Adversarial Error Rate (AER) vs Severity (`figure_aer_vs_severity.png`)
- **Figure 7**: False High Escalation Rate (FHER) vs Severity (`figure_fher_vs_severity.png`)
- **Figure 8**: Uncertainty Degradation under Noise & Packet Loss (`figure_noise_robustness.png`, `figure_packet_loss_robustness.png`)
- **Figure 9**: Empirical Calibration Reliability Diagram (`figure_calibration.png`)
- **Figure 10**: DAS/AIS Spatio-Temporal Association Demonstration (`figure_das_ais_association.png`)
- **Figure 11**: Competing Hypothesis Score Distributions (`figure_competing_hypotheses.png`)
- **Figure 12**: Decision-State Distribution (`figure_decision_distribution.png`)
- **Table I**: Scenario Definitions (`table_scenarios.csv`)
- **Table II**: Dataset Characteristics (`table_dataset_characteristics.csv` / `.tex`)
- **Table III**: Overall Method Comparison (`table_methods.csv` / `.tex`)
- **Table IV**: Scenario-wise Performance Breakdown (`table_scenario_performance.csv` / `.tex`)
- **Table V**: Ablation Study Results (`table_ablation.csv` / `.tex`)
- **Table VI**: Adversarial Attack Metrics (`table_adversarial.csv`)
- **Table VII**: Noise & Packet Loss Robustness (`table_robustness.csv`)
- **Table VIII**: Calibration Metrics & Brier Score (`table_calibration.csv` / `.tex`)
- **Table IX**: Real-Data Association (`table_real_data_association.csv` / `.tex`)

### 8. Real Submarine DAS Evaluation (Marlinks & EMSO)
Evaluate real-data spectral profiles, 1D vessel proximity correlation, and deep-sea noise floor stability:
```bash
python scripts/run_real_evaluation.py
```

### 9. Dryad Oliktok Arctic Submarine DAS & Environmental Mooring Evaluation
Evaluate 27.6 days of continuous Arctic seafloor DAS strain spectra, oceanographic wave/pressure cross-correlation, and false-escalation avoidance:
```bash
python scripts/run_oliktok_evaluation.py
```

### 10. Standalone Web Front End (14 Interactive Pages)
The research dashboard has been transitioned to a complete, standalone, static web application in `web/` featuring 14 dedicated interactive pages powered by vendored Plotly.js and Web Crypto API. No backend, node runtime, or build step required.

#### A. Export Web Data
Export precomputed pipeline runs, scenarios, real DAS campaigns, and manifests:
```bash
# Windows PowerShell:
$env:PYTHONPATH='src'
python scripts/export_web_data.py
```

#### B. Serve Locally
Launch any static HTTP server:
```bash
# Recommended:
python -m http.server 8000 --directory web

# Open in browser: http://localhost:8000/
```

#### C. The 14 Pages
1. **Overview & Architecture** (`#/overview`): System KPIs, Decision State definitions ($T0-T3, TX$), Cohort isolation breakdown.
2. **Scenario Explorer** (`#/scenarios`): Scenarios S01–S22 across 6 attack types and 5 severities.
3. **Signals & Spectrum** (`#/signals`): 3-axis acceleration waveforms, FFT spectrum, packet-loss gaps, spectral CSV export.
4. **Geometry & Kinematics** (`#/geometry`): 2D metric map, 10m corridor, vessel trajectory, distance vs time, CPA, dwell time, crossing detection.
5. **Evidence Timeline** (`#/timeline`): Sliding-window multi-trace chart ($C_P, C_A, R, U$), decision sequence, window table & CSV export.
6. **Decision Path Explainer** (`#/decision-path`): 5-stage sequential decision gating engine, deciding gate highlighting, exploratory what-if sandbox.
7. **Hypotheses & Audit** (`#/hypotheses`): Real Hypothesis enum names, candidate evidence scoring, positive/counter evidence audit trail.
8. **Adversarial Lab** (`#/adversarial`): Severity sweeps [0.0, 1.0], AER & FHER curves, stacked decision distributions, AER=0.0 finding.
9. **Baselines & Ablations** (`#/baselines`): Proposed vs single-modality baselines, paired bootstrap 95% CIs, McNemar tests, ablation hierarchy.
10. **Robustness & Calibration** (`#/robustness`): Sensor degradation/fault stress matrix, probability calibration curves, Brier score, ECE.
11. **Real DAS Deployments** (`#/real-das`): Marlinks North Sea ($1/\text{dist}$ correlation), EMSO deep-sea noise floor, Oliktok 27.6-day Arctic recording.
12. **Live Hardware-in-the-Loop** (`#/hil`): 2-second polling live stream, drag-and-drop JSONL loader, simulated accelerometer disclaimer.
13. **Provenance Verification** (`#/provenance`): In-browser Web Crypto API SHA-256 live audit against PROVENANCE.json records.
14. **Publication Artifacts** (`#/publications`): Publication figure gallery with PNG downloads and tables list with CSV downloads.

*(Note: The legacy Streamlit prototype in `dashboard/app.py` is deprecated. See [`docs/WEB.md`](docs/WEB.md) for full architecture and deployment documentation).*

---

## Hardware Status

Physical hardware experiments with ESP32 microcontrollers and MPU6050 vibration sensors are **`FUTURE WORK`** and are decoupled from the peer-reviewed paper's theoretical validation. All communication interfaces (`Mpu6050Packet`, MQTT receiver, HTTP receiver, Serial receiver, append-only packet logger) are implemented and unit tested.

---

## Hardware-in-the-Loop (HIL) AbyssLink Bridge

The HIL AbyssLink bridge (`src/subsea/hil_abysslink.py`, CLI `scripts/run_abysslink_hil.py`) connects real AbyssLink ESP32 telemetry (115200 baud UART, 300 ms interval) into the Subsea research pipeline:
- **Telemetry ingestion**: Line-buffered JSON parser supporting sensor telemetry and command acknowledgments.
- **Signal adaptation**: Optical link tracking with LDR debounce and startup grace period; 50 Hz MPU6050 accelerometer synthesis conditioned on binary vibration; ultrasonic distance to scaled vessel kinematic observation mapping.
- **Passive by default**: Zero serial transmission unless explicitly passed `--send-commands`.
- **Scientific integrity**: All outputs isolated under `artifacts/hil/` with `data_kind: "HIL_SIMULATED_ACCEL"`. Validates protocol, streaming adaptation, and decision latency—does not represent subsea acoustic wave propagation physics.

### Quick Start (HIL)
```bash
# Run deterministic mock emulator with summary table:
python scripts/run_abysslink_hil.py --mock --seed 42

# Run with baseline comparison:
python scripts/run_abysslink_hil.py --mock --replay-baselines

# Live passive serial read from ESP32:
python scripts/run_abysslink_hil.py --port COM3

# Run unit and integration tests:
pytest tests/test_hil_abysslink.py -v
```
See [`docs/HIL_ABYSSLINK.md`](docs/HIL_ABYSSLINK.md) for full architecture and protocol mapping details.
