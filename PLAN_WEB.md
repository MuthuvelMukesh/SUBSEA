# Standalone Web Front End for SUBSEA — Master Build Plan (`PLAN_WEB.md`)

> **Status**: PHASE 0 (Baseline Established & Verified)  
> **Target**: Replace broken `dashboard/app.py` with standalone static web platform in `SUBSEA/web/`

---

## 1. Verified Facts & Interfaces

All facts below were verified by reading source files and runtime manifests:

### 1.1 Python API Signatures
- **`DecisionState`**: Enum in `src/subsea/models.py` with members `T0`, `T1`, `T2`, `T3`, `TX`. (Note: `Decision` does not exist; old dashboard failed on import).
- **`Hypothesis`**: Enum in `src/subsea/models.py`:
  - `VESSEL_DISTURBANCE = "vessel_associated_disturbance"`
  - `ENVIRONMENTAL = "environmental_disturbance"`
  - `MECHANICAL = "non_vessel_mechanical_disturbance"`
  - `SENSOR_FAULT = "sensor_system_fault"`
- **`SensorObservation`**: Frozen dataclass (`node_id`, `timestamp`, `acceleration`, `position`, `packet_received=True`, `source="simulation"`, `metadata={}`).
- **`VesselObservation`**: Frozen dataclass (`vessel_id`, `timestamp`, `position`, `speed`, `heading`, `reported=True`, `position_uncertainty=0.0`, `metadata={}`).
- **`run_pipeline()`** (`src/subsea/pipeline.py`):
  `run_pipeline(observations, vessel, *, sampling_rate=50.0, baseline_rms=1.0, disturbance_rms=1.8, interaction_radius=10.0, temporal_tolerance=5.0, expected_interval=0.02, packet_timeout=1.0, environmental_event=False, now=None, cable_geometry=None) -> DecisionResult`
- **`decide()`** (`src/subsea/decision.py`):
  `decide(*, physical_confidence, association_confidence, reliability, uncertainty, thresholds=None) -> DecisionState`
  Hierarchy:
  1. `reliability <= tx_reliability (0.35) -> TX`
  2. `physical_confidence < physical (0.55) -> T0`
  3. `uncertainty >= tx_uncertainty (0.65) -> TX`
  4. `association_confidence < association (0.60) -> T1`
  5. `score >= t3 (0.85) and uncertainty < t3_uncertainty (0.35) -> T3; else T2`
- **`apply_attack()`** (`src/subsea/adversarial.py`):
  `apply_attack(vessel: VesselObservation, attack: str, severity: float = 1.0) -> VesselObservation`. (Does not take observations or return a tuple; old dashboard failed here). Supported attacks: `"none"`, `"ais_spoofing"`, `"transponder_suppression"`, `"timestamp_manipulation"`, `"spatial_manipulation"`, `"combined_evasion"`.
- **`spectral_features()`** (`src/subsea/features.py`):
  `spectral_features(samples, sampling_rate)` returns dict with `mean`, `rms`, `variance`, `std`, `peak`, `peak_to_rms`, `spectral_energy`, `dominant_frequency`, `spectral_entropy`.
- **`trajectory.py`**:
  `closest_point_of_approach(trajectory, cable)`, `dwell_time(trajectory, timestamps, cable, radius=radius)`, `crossing_detected(trajectory, cable)`.
- **`make_scenario()`, `generate_observations()`** (`src/subsea/simulation.py`):
  Generates deterministic observations for 22 scenarios (S01–S22). Descriptions from `_DEFINITIONS` are source of truth.

### 1.2 Real Artifacts and Manifests
- `artifacts/EXPERIMENT_MANIFEST.json`: Master manifest referencing real dataset scopes, scenario matrix, publication tables, and figures.
- `artifacts/real_data_evaluation/marlinks_manifest.json`: Real DAS vessel proximity correlation ($\rho = 0.9482$).
- `artifacts/real_data_evaluation/emso_manifest.json`: Real seafloor unperturbed noise baseline ($\text{CV} = 0.0008$).
- `artifacts/real_data_evaluation/oliktok_manifest.json`: 27.6 days Arctic seafloor DAS evaluation ($N=215$ hours, 183 channels). Exact escalation finding: *"No T2/T3 vessel-escalation decisions occurred during the evaluated recording."*
- `data/PROVENANCE.json`: Contains 3 provenance records with SHA-256 hashes and file metadata.
- `artifacts/hil/run-*/decisions.jsonl`: Real HIL log schema confirmed (`timestamp`, `sequence`, `decision`, `physical_confidence`, `association_confidence`, `reliability`, `uncertainty`, `hypothesis_scores`, `rationale`, `vessel_distance_m`, `vessel_speed`, `vibration_flag`, `ldr_flag`, `transmission`, `alert`, `data_kind`).

### 1.3 Offline Plotly Vendoring
- Plotly.js is available locally at:
  `C:\Users\MUTHUVEL\AppData\Local\Programs\Python\Python313\Lib\site-packages\plotly\package_data\plotly.min.js`
  Can be vendored directly into `web/vendor/plotly.min.js` without any external network dependency.

---

## 2. Assumptions

1. **Static Deployment**: The front end runs in any modern browser via static HTTP file serving (`python -m http.server`) or static hosting (Vercel, GitHub Pages).
2. **Browser Crypto Support**: `window.crypto.subtle.digest("SHA-256", buffer)` is universally supported across modern browsers for in-browser provenance verification.
3. **Committed vs Gitignored Data (`web/data/`)**:
   - `web/data/` contains pre-rendered JSON files (~3 MB total) exported from real manifests and simulations.
   - **Decision**: `web/data/` will be **committed to git**. This ensures that the web front end works out-of-the-box upon `git clone` or static deployment without requiring Python, NetCDF libraries, or running the exporter script first.

---

## 3. Page-to-Data Map (14 Pages)

| # | Page Name | Primary Route | Data Sources / Files | Cohort / Data Kind | Key Features & Metrics |
|---|-----------|---------------|----------------------|--------------------|------------------------|
| 1 | Overview | `#/overview` | `web/data/overview.json`, `web/data/provenance.json` | Mixed (Cohort-separated) | Decision cards, $C_P, C_A, R, U$ KPI badges, methodology boundary overview |
| 2 | Scenario Explorer | `#/scenarios` | `web/data/scenarios.json`, `web/data/scenario_runs.json` | `SIMULATION` | S01–S22 pickers, ground truth flags, attack & severity selector |
| 3 | Signals & Spectrum | `#/signals` | `web/data/signals.json` | `SIMULATION` | Triaxial acceleration waveforms ($a_x, a_y, a_z$), magnitude, FFT spectrum, packet-loss markers |
| 4 | Geometry & Kinematics | `#/geometry` | `web/data/geometry.json` | `SIMULATION` | 2D Cartesian metric cable & vessel trajectories, CPA, dwell time, cable crossing flag |
| 5 | Evidence Timeline | `#/timeline` | `web/data/timelines.json` | `SIMULATION` | Sliding-window timeline of $C_P, C_A, R, U$, and decision state sequence |
| 6 | Decision Path Explainer | `#/decision-path` | `web/data/config.json`, `web/data/decision_paths.json` | `SIMULATION` | Gate-by-gate decision flowchart, fired gate highlight, interactive what-if sandbox |
| 7 | Hypotheses & Audit | `#/hypotheses` | `web/data/hypotheses.json` | `SIMULATION` | Four real hypotheses scores, positive/counter evidence, missing corroboration list |
| 8 | Adversarial Lab | `#/adversarial` | `web/data/adversarial.json` | `SIMULATION` | Clean vs attacked comparisons, severity sweeps $[0, 1]$, AER and FHER tables |
| 9 | Baselines & Ablations | `#/baselines` | `web/data/baselines.json`, `web/data/ablation.json` | `SIMULATION` | Proposed vs ablation variants, accuracy/F1/TX-rate comparisons with CIs |
| 10 | Robustness & Calibration | `#/robustness` | `web/data/robustness.json`, `web/data/calibration.json` | `SIMULATION` | Noise, packet-loss, position-uncertainty sweeps, reliability curve, ECE, Brier score |
| 11 | Real DAS | `#/real-das` | `web/data/real_das.json` | `REAL_DAS` | Marlinks ($1/\text{dist}$, CPA, $\rho=0.948$), EMSO ($\text{CV}=0.0008$), Oliktok (27.6-day Arctic storm timeline, wave/pressure correlation) |
| 12 | Live HIL | `#/hil` | `web/hil/latest.json`, `artifacts/hil/run-*/` | `HIL_SIMULATED_ACCEL` | Drag-and-drop log viewer, 2s polling live mode, optical link fault indicator, event timeline |
| 13 | Provenance | `#/provenance` | `web/data/provenance.json` | Multi-Source | In-browser Web Crypto SHA-256 verification of shipped files against `PROVENANCE.json` |
| 14 | Publication Figures & Tables | `#/publications` | `web/data/publications.json`, `web/assets/figures/` | Multi-Source | Browser view and download for 12 publication figures and 10 publication tables |

---

## 4. Numbered Build Tasks & Verification Workflow

- **Phase 0: Baseline & Audit**
  - Hash `AbyssLink\` to external temporary location.
  - Run full pytest test suite (Baseline: 258 passed).
  - Create `PLAN_WEB.md` and initialize `PROGRESS_WEB.md`.
  - Add deprecation banner to `dashboard/app.py`.
- **Phase 1: Exporter & Read-Only Helpers**
  - Implement `src/subsea/web_export.py` with read-only extraction helpers.
  - Implement `scripts/export_web_data.py` to write `web/data/*.json`.
  - Implement `tests/test_web_export.py` verifying export schema and determinism.
  - Acceptance: `python scripts/export_web_data.py && python -m pytest tests/test_web_export.py -v`.
- **Phase 2: Core Web Architecture & Shell**
  - Vendor `plotly.min.js` to `web/vendor/`.
  - Create `web/index.html`, `web/assets/style.css`, and modular JavaScript foundation (`web/js/app.js`, `web/js/router.js`, `web/js/theme.js`, `web/js/banner.js`, `web/js/charts.js`).
  - Acceptance: Open in headless browser/server, verify navigation and dark/light theme switching.
- **Phase 3: Pages 1–5 (Overview, Scenarios, Signals, Geometry, Timelines)**
  - Implement `web/js/pages/overview.js`, `scenarios.js`, `signals.js`, `geometry.js`, `timeline.js`.
  - Smoke-test each page rendering real exported data.
- **Phase 4: Pages 6–10 (Decision Path, Hypotheses, Adversarial, Baselines, Robustness)**
  - Implement `decision_path.js`, `hypotheses.js`, `adversarial.js`, `baselines.js`, `robustness.js`.
  - Verify interactive exploratory sliders and gate highlight logic.
- **Phase 5: Pages 11, 13, 14 (Real DAS, Provenance, Publications)**
  - Implement `real_das.js`, `provenance.js` (with Web Crypto SHA-256 hasher), `publications.js`.
  - Copy static figures into `web/assets/figures/`.
- **Phase 6: Page 12 (Live HIL)**
  - Implement `web/js/pages/hil.js` with polling of `web/hil/latest.json`, file upload, and simulated-accel disclaimer.
- **Phase 7: Documentation & Repo Cleanliness**
  - Create `docs/WEB.md` (data flow, serving, Vercel/GitHub Pages deployment guide).
  - Update `README.md` with true page count (14 pages) and running instructions.
- **Phase 8: Automated End-to-End Smoke Testing**
  - Run Python/Playwright smoke tests checking all 14 pages, console logs, banner presence, and tampering detection.
- **Phase 9: Pyodide Assessment**
  - Evaluate offline vendoring constraints for Pyodide; report feasibility.

---

## 5. Stop Conditions & Rules

- `AbyssLink\` remains 100% frozen (hashes verified after every phase).
- Result-producing logic in `src/subsea/` (`decide`, `pipeline`, etc.) must NOT be modified.
- No CDN, external font, or analytics requests.
- All numbers originate strictly from real code and real manifests.
- Python tests (`python -m pytest tests/ -q`) must pass with $\ge 258$ tests at every phase.
