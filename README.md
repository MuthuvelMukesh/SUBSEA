# Subsea Cable Disturbance Assessment

> **An Uncertainty-Aware Multimodal Evidence Fusion Framework for Vessel-Associated Subsea Cable Disturbance Assessment under Adversarial Uncertainty**

[![Tests](https://img.shields.io/badge/tests-205%20passed%2C%202%20skipped-brightgreen)](#test-suite)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![Data Kind](https://img.shields.io/badge/data%20kind-SIMULATION%20(Synthetic)-orange)](#scientific-integrity--provenance)
[![Hardware](https://img.shields.io/badge/hardware-FUTURE%20WORK-lightgrey)](#hardware-status)

A reproducible research platform for uncertainty-aware multimodal evidence fusion under adversarial uncertainty. The framework integrates subsea vibration sensing (accelerometer/DAS acoustic), AIS vessel tracking kinematics, sensor health diagnostics, epistemic uncertainty quantification, and multi-hypothesis assessment to reliably distinguish vessel-caused cable disturbances (anchor dragging, bottom-trawling) from benign transit, sensor malfunctions, environmental confounding, and adversarial evasion (AIS spoofing, timestamp manipulation).

---

## Scientific Integrity & Provenance

- **SIMULATION (Synthetic Evaluation)**: Synthetic scenario results are computational experiment outputs generated from explicit mathematical and physical models; they are not operational real-world evidence and do not constitute causal ground truth.
- **REAL DAS/AIS DATA**: Real external datasets (such as Marlinks North Sea DAS or Paphos optical interferometry) require formal external data acquisition agreements. In this repository, real data loaders and association adapters are fully implemented and verified, but real-data evaluation is explicitly reported as **`NOT EXECUTED: Real external dataset required`**.
- **HARDWARE TESTBENCH**: Physical ESP32 / MPU6050 hardware validation is decoupled from the theoretical/fusion paper and is categorized as **`FUTURE WORK`**.
- **NO SILENT REPAIR / NO FABRICATION**: Experiment runners and report generators reject fabricated records, missing cohorts, out-of-range metrics, unverified manifests, and mismatched seeds.

---

## Repository Structure

```
├── config/
│   └── system.yaml                  # System configuration (weights, thresholds, uncertainty lambdas)
├── dashboard/
│   └── app.py                       # 21-panel interactive Streamlit research dashboard
├── scripts/
│   ├── generate_paper_results.py    # End-to-end generator for IEEE publication tables & figures
│   ├── run_simulation.py            # Single & all-scenario (S01–S22) simulation runner
│   ├── run_monte_carlo.py           # Multi-trial reproducible Monte Carlo experiment runner
│   ├── run_adversarial.py           # Adversarial attack evaluator (AER/FHER cohorts)
│   ├── run_attack_sweep.py          # Adversarial severity sweep generator
│   ├── run_robustness.py            # Noise, packet-loss, and position-uncertainty sweeps
│   └── run_baselines.py             # Baseline comparisons (ML & heuristics) and ablations
├── src/subsea/
│   ├── acquisition.py               # Sensor packet schema & receiver adapters (MQTT/HTTP/Serial)
│   ├── adversarial.py               # AIS spoofing, transponder suppression, timestamp/spatial manipulation
│   ├── ais.py                       # AIS trajectory loader, deduplication, interpolation
│   ├── association.py               # Spatial, temporal, and kinematic association
│   ├── baselines.py                 # Scikit-learn ML baselines (Random Forest, Decision Tree)
│   ├── behaviour.py                 # Vessel behaviour analysis & spectral feature extraction
│   ├── calibration.py               # Brier score, Expected Calibration Error (ECE), reliability curves
│   ├── cli.py                       # CLI entrypoints
│   ├── das.py                       # Read-only DAS HDF5 loader with SHA-256 validation
│   ├── das_ais_association.py       # DAS acoustic event to AIS track association pipeline
│   ├── decision.py                  # Decision state engine (T0, T1, T2, T3, TX)
│   ├── evaluation.py                # Evaluation harness & confusion matrix metrics
│   ├── experiments.py               # Experiment runners with append-only manifest guarantees
│   ├── features.py                  # Acceleration magnitude and spectral features
│   ├── fusion.py                    # Multimodal weighted evidence fusion & competing hypotheses
│   ├── geometry.py                  # Cable polyline geometry, CPA, dwell, crossing
│   ├── health.py                    # Sensor availability, freshness, constant-value detection
│   ├── metrics.py                   # Classification metrics, AER, FHER cohorts
│   ├── models.py                    # Typed Pydantic contracts
│   ├── pipeline.py                  # End-to-end decision pipelines (single/multi-node/multi-vessel)
│   ├── real_data.py                 # Read-only CSV/JSON/HDF5 data boundary loaders
│   ├── reporting.py                 # Publication figure (1–12) and table (I–IX) generators
│   ├── simulation.py                # Deterministic synthetic scenarios (S01–S22)
│   └── statistics.py                # Paired bootstrap, permutation tests, Cohen's d, McNemar
└── tests/                           # 21 test suites, 205 unit and regression tests
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

# Install dependencies
python -m pip install -r requirements.txt
# To install optional UI (Streamlit) and ML dependencies:
python -m pip install -e .[test,ui,ml]
```

---

## Test Suite

Run the full automated test suite:

```bash
python -m pytest tests/ -q
```

*Expected output: `205 passed, 2 skipped` (2 HDF5 tests skipped if `h5py` is not installed).*

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
- **Table IX**: Real-Data Association (`table_real_data_association.csv` / `.tex` — marked `NOT EXECUTED`)

### 8. Interactive Research Dashboard
Launch the 21-panel Streamlit dashboard:
```bash
streamlit run dashboard/app.py
```

---

## Hardware Status

Physical hardware experiments with ESP32 microcontrollers and MPU6050 vibration sensors are **`FUTURE WORK`** and are decoupled from the peer-reviewed paper's theoretical validation. All communication interfaces (`Mpu6050Packet`, MQTT receiver, HTTP receiver, Serial receiver, append-only packet logger) are implemented and unit tested.
