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
- [x] Real-data results status: **`EXECUTED`** (Real datasets ingested with verified SHA-256 provenance).
  - Marlinks Demo DAS: Executed (`artifacts/real_data_evaluation/marlinks_manifest.json`)
  - EMSO Western Ionian DAS: Executed (`artifacts/real_data_evaluation/emso_manifest.json`)
- [x] Test coverage: `tests/test_das_ais.py`, `tests/test_real_adapters.py`, `tests/test_real_data.py`, `tests/test_real_validation.py`.

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
  21. Clear provenance badges: `SIMULATION`, `REAL DATA: EXECUTED`, `HARDWARE: FUTURE WORK`.

## Phase 12 — Publication Figures & Tables
- [x] Complete IEEE figure generator (`src/subsea/reporting.py`):
  - Figures 1–12 generated and verified from executed experiment manifests.
- [x] Complete IEEE table generator (both CSV and LaTeX formats):
  - Tables I–IX generated and verified.
- [x] CLI scripts: `scripts/generate_paper_results.py`, `scripts/run_real_evaluation.py`.
- [x] Test coverage: `tests/test_reporting.py`.

## Phase 13 & 14 — Provenance, Test Suite, and Validation
- [x] Full regression test suite: **240 passed, 0 failed, 0 skipped**.
- [x] Reproducibility audit: verified end-to-end generation from seed to LaTeX tables and figures.
- [x] Documentation integrity: README and TRACKER updated with exact commands and provenance status.

## Phase 3.2 — Dryad Oliktok Real-Data Environmental Validation & Decision Hierarchy Fix
- [x] Read-only NetCDF-4 adapter: `src/subsea/oliktok.py` (`OliktokAdapter`, `OliktokDataset`).
- [x] Decision engine ordering defect resolved in `src/subsea/decision.py`:
  - Hardware reliability ($R \le 0.35 \implies \text{TX}$)
  - Normal quiet baseline ($C_p < 0.55 \implies \text{T0}$)
  - Disturbance ambiguity ($U \ge 0.65 \implies \text{TX}$)
  - Uncorroborated disturbance ($C_a < 0.60 \implies \text{T1}$)
  - Corroborated disturbance ($C_a \ge 0.60 \implies \text{T2/T3}$)
- [x] Scenario regression verification: all 22 benchmark scenarios ($S01\text{--}S22$) preserve 100% identical decisions (`artifacts/audit/decision_regression_report.json`).
- [x] Real Arctic DAS evaluation executed over 27.6 days ($N=215$ hours, 183 channels):
  - Hydrodynamic wave height correlation: Spearman $\rho = +0.3141$ ($p = 2.63 \times 10^{-6}$)
  - Seafloor bottom pressure variance correlation: Spearman $\rho = +0.4951$ ($p = 1.07 \times 10^{-14}$)
  - Environmental escalation rate: $0.0\%$ (No T2/T3 vessel escalations across 27.6 days of Arctic storms)
  - Manifest: `artifacts/real_data_evaluation/oliktok_manifest.json`
  - Tables: `artifacts/tables/table_oliktok_validation.csv` & `.tex`, `table_real_datasets_comparison.csv` & `.tex`
  - Figures: `oliktok_temporal_stability.png`, `oliktok_channel_statistics.png`, `oliktok_physical_confidence.png`
  - Consistency report: `artifacts/audit/oliktok_consistency_report.json` (23/23 checks PASS)
  - Reproducibility report: `artifacts/audit/oliktok_reproducibility_report.json` (PASS, 22/22 identical comparisons)
  - Scientific documentation: `docs/OLITKOK_VALIDATION_REPORT.md`
- [x] Cross-Dataset Triad:
  - Marlinks: 1D AIS-corroborated vessel proximity correlation ($\rho = 0.948$)
  - EMSO Western Ionian: Deep-sea unperturbed noise floor baseline ($\text{CV} = 0.0008$)
  - Dryad Oliktok: Multi-week shallow Arctic shelf environmental robustness ($p < 10^{-14}$, 0% false escalation)
- [~] Paper: Ready for final manuscript consistency review (`docs/FINAL_PAPER_READINESS_REPORT.md` created; IEEE manuscript files in `paper/` deliberately unedited until user review).

---

## Hardware Testbench (ESP32 / MPU6050)
- **Status: `FUTURE WORK`**
- *Per research design decisions, physical hardware testbench is decoupled from the primary validation of the theoretical, evidence-fusion paper. Hardware experiments (H01–H08) are reserved for future work and are not missing experimental evidence.*
- Implemented software adapters:
  - `Mpu6050Packet` validation schema.
  - MQTT, HTTP, and Serial receiver adapters.
  - Append-only raw packet recorder.
