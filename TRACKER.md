# Project Tracker

Last updated: 2026-09-14

This tracker distinguishes implemented software from results that require an executed experiment, real hardware, or an external dataset. A checked implementation item does not imply scientific validation.

## Status Legend

- `[x]` Implemented and covered by tests.
- `[~]` Partial prototype or adapter; more work is required.
- `[ ]` Not implemented.
- `EXECUTED` Experiment executed with reproducible manifest and verified provenance.
- `PENDING / NOT EXECUTED` Real external dataset required; never treated as zero or fabricated success.
- `FUTURE WORK` Hardware decoupled from paper validation.

---

## Phase 1 — Repository Audit & Scientific Integrity Gates
- [x] Python package and reproducible source layout (`src/subsea/`).
- [x] Strict provenance enforcement: manifests reject unverified records, duplicates, out-of-range metrics.
- [x] Synthetic results explicitly labeled as simulation; never claimed as causal ground truth.
- [x] Transparent decision state machine: `T0` (Normal), `T1` (Low), `T2` (High), `T3` (Urgent), `TX` (Fail-Closed Indeterminate).
- [x] Auditable evidence triplet: Physical Confidence ($C_P$), Association Confidence ($C_A$), Reliability ($C_R$), Epistemic Uncertainty ($U$).

## Phase 2 — Multi-Node & Multi-Vessel Simulation
- [x] Multi-node spatial array generation (`generate_multi_node_observations` with spatial attenuation across nodes N01–N05).
- [x] Multi-node spatial consensus pipeline (`run_multi_node_pipeline`).
- [x] Multi-vessel trajectory generation (`generate_multi_vessel_scenario` for candidate vessels).
- [x] Multi-vessel association and candidate ranking pipeline (`run_multi_vessel_pipeline`).
- [x] Comprehensive test coverage (`test_multi_node.py`, `test_multi_vessel.py`).

## Phase 3 — Complete Benchmark Scenarios (S01–S22)
- [x] S01: Benign transit at cruising speed.
- [x] S02: Benign loitering outside cable zone.
- [x] S03: Normal cable crossing without contact.
- [x] S04: Anchor dragging (low speed, high vibration, spatial proximity).
- [x] S05: Bottom-trawling gear interaction.
- [x] S06: Dropped object / acute impact.
- [x] S07: Legitimate maintenance vessel operation.
- [x] S08: Benign transit in shallow water.
- [x] S09: Heavy vessel displacement wash without physical cable contact.
- [x] S10: Bad weather and sea-state turbulence.
- [x] S11: Natural seismic / seismic survey acoustic anomaly.
- [x] S12: Marine fauna / biological acoustic disturbance.
- [x] S13: Single sensor intermittent packet loss.
- [x] S14: Multiple sensor spatial node failure.
- [x] S15: Sensor drift and calibration offset.
- [x] S16: Communication backhaul outage.
- [x] S17: Adversarial AIS transponder intentional shutdown.
- [x] S18: Adversarial AIS spoofing (ghost trajectory injection).
- [x] S19: Adversarial AIS timestamp manipulation.
- [x] S20: Coordinated spatial offset manipulation.
- [x] S21: Multi-vector combined evasion (spoofing + timestamp desynchronization).
- [x] S22: Multi-vessel ambiguous association and spatial-temporal conflict.
- [x] Comprehensive test coverage (`test_all_scenarios.py`, `test_scenarios.py`).

## Phase 4 — Robustness Sweeps
- [x] Noise sweep: evaluated across noise ratios [0.0, 0.05, 0.10, 0.20, 0.30, 0.50] (`run_noise_sweep`).
- [x] Packet-loss sweep: evaluated across drop rates [0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70] (`run_packet_loss_sweep`).
- [x] Position-uncertainty sweep: evaluated across uncertainty levels [0, 50, 100, 200, 500m] (`run_position_uncertainty_sweep`).
- [x] CLI script: `scripts/run_robustness.py`.
- [x] Test coverage: `tests/test_robustness.py`.

## Phase 5 — Adversarial Severity & Evasion
- [x] Extended attacks: AIS spoofing, transponder suppression, timestamp manipulation, spatial manipulation, combined evasion.
- [x] Severity sweep with explicit baseline at $\text{severity}=0$ (`run_attack_severity_sweep`).
- [x] Adversarial Error Rate (AER) and False High Escalation Rate (FHER) cohorts.
- [x] CLI script: `scripts/run_adversarial.py`, `scripts/run_attack_sweep.py`.
- [x] Test coverage: `tests/test_adversarial_extended.py`.

## Phase 6 — Monte Carlo Reproducibility
- [x] Multi-trial seeded Monte Carlo experiment runner (`run_monte_carlo`).
- [x] JSON manifest capturing seed, trial count, software version, data kind, and raw records.
- [x] CLI script: `scripts/run_monte_carlo.py`.
- [x] Test coverage: `tests/test_monte_carlo.py`.

## Phase 7 — Comparative Baselines & Ablations
- [x] Baseline methods: `physical_only`, `vessel_only`, `weighted`, `without_behaviour`, `without_counter_evidence`, `without_health`, `without_spatial_temporal_association`, `without_uncertainty`.
- [x] Machine learning baseline wrappers (`RandomForestBaseline`, `DecisionTreeBaseline`).
- [x] Ablation study runner evaluating all architectural variants (`run_ablation_study`).
- [x] CLI script: `scripts/run_baselines.py`.
- [x] Test coverage: `tests/test_baselines.py`, `tests/test_ablation.py`.

## Phase 8 — Calibration & Statistical Comparisons
- [x] Brier score, Expected Calibration Error (ECE), and empirical reliability curves (`subsea.calibration`).
- [x] Threshold calibration protocol avoiding evaluation set contamination (`run_calibration_analysis`).
- [x] Rigorous statistical comparison utilities: paired bootstrap confidence intervals, permutation test, Cohen's $d$, McNemar's test (`subsea.statistics`).
- [x] Test coverage: `tests/test_statistics.py`, `tests/test_ablation.py`.

## Phase 9 & 10 — Real Data Boundary Adapters & DAS/AIS Association
- [x] Read-only DAS HDF5 loader with SHA-256 provenance hash verification (`subsea.das`).
- [x] AIS normalization: deduplication, chronologic ordering, gap detection, linear interpolation (`subsea.ais`).
- [x] DAS/AIS spatial-temporal association pipeline (`subsea.das_ais_association`).
- [x] Real-data results status: **`NOT EXECUTED: Real external dataset required (Marlinks / Paphos)`** (No fabricated real-data results).
- [x] Test coverage: `tests/test_das_ais.py`, `tests/test_real_adapters.py`, `tests/test_real_data.py`.

## Phase 11 — Interactive Research Dashboard
- [x] Comprehensive Streamlit dashboard (`dashboard/app.py`) implementing all 21 items from Section 39:
  1. Overview & architecture state machine
  2. Scenario explorer (S01–S22)
  3. Sensor health & telemetry
  4. Vibration waveforms (tri-axial & magnitude)
  5. FFT power spectral analysis
  6. Cable geometry layout
  7. Vessel trajectory & kinematics
  8. Vessel-to-cable distance profile
  9. Closest Point of Approach (CPA) calculation
  10. Dwell time monitoring
  11. Cable crossing detection
  12. Evidence timeline
  13. Uncertainty timeline
  14. Competing hypotheses scoring
  15. Counter-evidence audit
  16. Missing corroboration checks
  17. Adversarial severity sweep preview
  18. Comparative baselines & ablations
  19. Experiment manifest inspector
  20. Publication figures & LaTeX tables
  21. Clear provenance badges: `SIMULATION`, `REAL DATA: NOT EXECUTED`, `HARDWARE: FUTURE WORK`.

## Phase 12 — Publication Figures & Tables
- [x] Complete IEEE figure generator (`src/subsea/reporting.py`):
  - Figure 1: Framework Architecture (`figure_architecture.png`)
  - Figure 2: Evidence Fusion Pipeline (`figure_fusion_pipeline.png`)
  - Figure 3: Scenario-wise Performance (`figure_scenario_performance.png`)
  - Figure 4: Baseline Comparison (`figure_method_comparison.png`)
  - Figure 5: Ablation Study (`figure_ablation_study.png`)
  - Figure 6: Adversarial Error Rate (AER) vs Severity (`figure_aer_vs_severity.png`)
  - Figure 7: False High Escalation Rate (FHER) vs Severity (`figure_fher_vs_severity.png`)
  - Figure 8: Uncertainty Degradation under Noise / Packet Loss (`figure_noise_robustness.png`, `figure_packet_loss_robustness.png`)
  - Figure 9: Calibration Reliability Diagram (`figure_calibration.png`)
  - Figure 10: DAS/AIS Spatio-Temporal Association Example (`figure_das_ais_association.png`)
  - Figure 11: Competing Hypothesis Scores (`figure_competing_hypotheses.png`)
  - Figure 12: Decision-State Distribution (`figure_decision_distribution.png`)
- [x] Complete IEEE table generator (both CSV and LaTeX formats):
  - Table I: Scenario definitions (`table_scenarios.csv`)
  - Table II: Dataset characteristics (`table_dataset_characteristics.csv` / `.tex`)
  - Table III: Overall method comparison (`table_methods.csv` / `.tex`)
  - Table IV: Scenario-wise performance (`table_scenario_performance.csv` / `.tex`)
  - Table V: Ablation study (`table_ablation.csv` / `.tex`)
  - Table VI: Adversarial attack results (`table_adversarial.csv`)
  - Table VII: Noise & packet-loss robustness (`table_robustness.csv`)
  - Table VIII: Calibration metrics (`table_calibration.csv` / `.tex`)
  - Table IX: Real-data association results (`table_real_data_association.csv` / `.tex` — marked `NOT EXECUTED`)
- [x] CLI script: `scripts/generate_paper_results.py`.
- [x] Test coverage: `tests/test_reporting.py`.

## Phase 13 & 14 — Provenance, Test Suite, and Validation
- [x] Full regression test suite: **205 passed, 2 skipped** (optional HDF5 tests when `h5py` is not installed).
- [x] Reproducibility audit: verified end-to-end generation from seed to LaTeX tables and figures.
- [x] Documentation integrity: README and TRACKER updated with exact commands and provenance status.

---

## Hardware Testbench (ESP32 / MPU6050)
- **Status: `FUTURE WORK`**
- *Per research design decisions, physical hardware testbench is decoupled from the primary validation of the theoretical, evidence-fusion paper. Hardware experiments (H01–H08) are reserved for future work and are not missing experimental evidence.*
- Implemented software adapters:
  - `Mpu6050Packet` validation schema.
  - MQTT, HTTP, and Serial receiver adapters.
  - Append-only raw packet recorder.
