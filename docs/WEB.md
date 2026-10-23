# SUBSEA Standalone Web Front End Documentation (`docs/WEB.md`)

## 1. Architectural Overview & Frontend Stack

The SUBSEA Standalone Web Front End replaces the deprecated Streamlit dashboard (`dashboard/app.py`) with a modern, high-performance, completely standalone static web application located in `web/`.

### Key Design Pillars
- **Zero Runtime Dependencies**: Pure HTML5, Vanilla ES Modules, and CSS3 custom design tokens. No Node.js runtime, no build step, no backend server, and no database required.
- **100% Offline Capability**: Vendored offline Plotly.js (`web/vendor/plotly.min.js`), native Web Crypto API hashing, and zero external CDNs, remote web fonts, or remote assets. Works completely air-gapped from local disk or static server.
- **Hash-Based Routing**: Clean client-side routing across 14 dedicated pages (`web/index.html#/overview`, `#/scenarios`, etc.), loading page modules dynamically.
- **Strict Data Integrity**: Every number shown originates from real Python pipeline runs, verified experimental manifests, or real Hardware-in-the-Loop (HIL) logs. Zero hardcoded results or synthetic verified flags.

---

## 2. Data Flow Architecture

The data flow is unidirectional, reproducible, and verifiable:

```
[ Python Research Framework: src/subsea/ ]
       │
       ├─ pipeline.py / decision.py / models.py / features.py / geometry.py / hil_abysslink.py
       ├─ config/system.yaml
       └─ artifacts/ (adversarial/, baselines/, ablation/, simulation/, real_data_evaluation/)
       │
       ▼
[ scripts/export_web_data.py ]
       │
       ▼ (Pure JSON Serialization + Validation)
[ web/data/*.json ] (17 Precomputed Manifest Files, ~1.5 MB Total)
       │
       ├─ scenarios.json, scenario_runs.json (S01–S22 sweeps across 6 attacks & 5 severities)
       ├─ signals.json, geometry.json, timelines.json
       ├─ config.json, decision_paths.json, hypotheses.json
       ├─ adversarial.json, baselines.json, ablation.json, robustness.json, calibration.json
       ├─ real_das.json, provenance.json, publications.json, overview.json
       │
       ▼
[ web/index.html & web/js/*.js ]
       │
       ▼
[ In-Browser Dynamic Rendering & Plotly Interactive Visualizations ]
```

To refresh all web data from current research code and manifests:
```powershell
$env:PYTHONPATH='src'
python scripts/export_web_data.py
```

---

## 3. Data-Kind Rules and Cohort Isolation

To maintain strict scientific integrity, three distinct experimental cohorts are recognized:

| Cohort Tag | Data Kind | Description & Scope |
|------------|-----------|---------------------|
| `SIMULATION` | `SIMULATION` | Controlled synthetic physics simulations (scenarios S01–S22, 2,200 trials, Monte Carlo adversarial sweeps). |
| `REAL_DAS` | `REAL_DAS` | Empirical field recordings from real submarine fiber optic cables (Marlinks North Sea, EMSO Ionian Sea, Dryad Oliktok Arctic Ocean). |
| `HIL_SIMULATED_ACCEL` | `HIL_SIMULATED_ACCEL` | ESP32 hardware bridge telemetry with synthesized 50 Hz MPU6050 accelerometer for timing/link integration testing. |

### Strict Cohort Isolation Rules:
1. **Prominent Data-Kind Banner on Every Page**: Driven dynamically by the loaded data model (`renderBanner(data_kind)`).
2. **Never Pool Cohorts**: Simulation metrics and Real DAS metrics are never averaged, combined, or plotted on the same chart axis.
3. **Preserved Disclaimers**:
   - No causal damage attribution on unlabelled environmental recordings.
   - Oliktok finding worded strictly: *"No T2/T3 vessel-escalation decisions occurred during the evaluated recording."* Never state "zero false alarms" (since benign T1 swell alarms naturally occur).
   - Marlinks gap clearly documented (1D proximity vs 2D AIS tracking).
   - No "attack-proof" claims.

---

## 4. Justification for Committing `web/data/*.json`

The precomputed JSON files in `web/data/` (~1.5 MB total) are **committed to version control**.

### Justification:
1. **Zero-Configuration Instant Deployment**: Allows immediate static hosting on platforms like GitHub Pages, Vercel, Netlify, or standard Apache/Nginx web servers without requiring a Python environment, pip packages, or build scripts.
2. **Deterministic Offline Auditing**: Anyone cloning the repository can immediately open `web/index.html` or run `python -m http.server` and inspect verified experimental results.
3. **Cryptographic Traceability**: All committed data files carry SHA-256 signatures, seed 42 metadata, software versions, and source manifest paths, auditable in-browser via Page 13 (Provenance).

---

## 5. Primary Modules and Route Map

The application interface is structured into three primary operational modules, followed by detailed research deep-dives:

### Primary Operational Modules
1. **Module 1: Detection (`#/detection`) [Default Landing Page]**: Primary operational console integrating direct ESP32 hardware Web Serial streaming, real-time pipeline classification ($T0-TX$), continuous fusion metrics ($C_P, C_A, R, U$), and telemetry event audit trail.
2. **Module 2: Early Warning (`#/early-warning`)**: Multi-sensor early warning state machine ($W0-WX$), 6-group corroboration panel with quantitative thresholds, escalation persistence and de-escalation hold meters (seconds/frames), dual-strip timeline (W-state with lead-time calculation vs T-state twin heuristic), 7-scenario digital twin runner, client-side operator alert acknowledgment, and bounded audit log.
3. **Module 3: Research & Validation (`#/research`)**: Centralized scientific benchmarking laboratory hub featuring 6 interactive sub-tabs:
   - *1. Framework & Hypotheses (H1–H4)*
   - *2. Baselines & Ablations*
   - *3. Adversarial & Robustness*
   - *4. Real Submarine DAS (Marlinks, EMSO, Oliktok)*
   - *5. Cryptographic Provenance (In-browser SHA-256 verifier)*
   - *6. Early Warning Benchmarks (Monte Carlo scorecard, latency/lead-time distributions, flapping rate, ablation comparison, ROC operating curve)*

### Detailed Route Map (14 Pages)

| Page # | View Title | Route | Primary Data File(s) | Key Visualizations & Tables |
|---|---|---|---|---|
| - | Detection (Landing) | `#/detection` | Hardware Web Serial / `/api/hil` | Physical sensors, $T0-TX$ states, $C_P, C_A, R, U$ fusion metrics, telemetry buffer |
| - | Early Warning | `#/early-warning` | `data/twin_runs.json`, `/api/twin` | $W0-WX$ states, indicator groups, hold meters, dual timeline, twin runner, operator audit log |
| - | Research Hub | `#/research` | `data/*.json`, `data/early_warning_eval.json` | 6 sub-tabs, benchmark scorecards, latency error-bar plots, ROC curve |
| 1 | Overview & Architecture | `#/overview` | `data/overview.json`, `data/provenance.json` | System KPIs, Decision State semantics table, Cohort breakdown, Scientific disclaimers |
| 2 | Scenario Explorer | `#/scenarios` | `data/scenarios.json`, `data/scenario_runs.json` | S01–S22 ground-truth selector, Attack & Severity sweeps, Metric bar charts, Kinematics |
| 3 | Signals & Spectrum | `#/signals` | `data/signals.json` | 3-axis acceleration waveforms, Magnitude, Packet loss markers, FFT spectrum, Spectral CSV export |
| 4 | Geometry & Kinematics | `#/geometry` | `data/geometry.json` | 2D Metric Cartesian map, 10m interaction corridor, Vessel track, CPA, Dwell time, Crossing detection |
| 5 | Evidence Timeline | `#/timeline` | `data/timelines.json` | Sliding-window traces ($C_P, C_A, R, U$), Decision state sequence, Window table & CSV export |
| 6 | Decision Path Explainer | `#/decision-path` | `data/decision_paths.json`, `data/config.json` | 5-stage sequential gating engine, Deciding gate highlight, Exploratory what-if sliders |
| 7 | Hypotheses & Audit | `#/hypotheses` | `data/hypotheses.json`, `data/scenario_runs.json` | Hypothesis enum scores bar chart, Positive/counter evidence audit trail, Component breakdowns |
| 8 | Adversarial Lab | `#/adversarial` | `data/adversarial.json` | Severity sweeps [0.0, 1.0], AER & FHER curves, Stacked decision distributions, AER=0.0 finding |
| 9 | Baselines & Ablations | `#/baselines` | `data/baselines.json`, `data/ablation.json` | Proposed vs baselines bar chart with paired bootstrap 95% CIs, McNemar tests, Ablation hierarchy |
| 10 | Robustness & Calibration | `#/robustness` | `data/robustness.json`, `data/calibration.json` | Sensor failure stress matrix, Reliability diagram (ECE, Brier score), Sensitivity curve |
| 11 | Real DAS Deployments | `#/real-das` | `data/real_das.json` | Marlinks $1/\text{dist}$ correlation, EMSO noise floor, Oliktok 27.6-day recording & wave correlations |
| 12 | Live Hardware-in-the-Loop | `#/hil` | `web/hil/latest.json`, `web/hil/decisions.jsonl` | Direct Web Serial ESP32 connection (115200 baud), live hardware sensor cards, Start/Stop laser transmission controls, raw JSONL export, Python pipeline bridge, 2s polling stream, Drag-and-drop loader |
| 13 | Provenance Verification | `#/provenance` | `data/provenance.json`, Shipped web assets | In-browser Web Crypto API SHA-256 live verification, Match/Mismatch tamper detection |
| 14 | Publication Artifacts | `#/publications` | `data/publications.json`, `assets/figures/*.png` | Publication figure gallery with PNG downloads, Publication tables list with CSV downloads |

---

## 6. Backend API & Session Isolation (`scripts/serve_web.py`)

The unified server `scripts/serve_web.py` serves static files and provides stateful, multi-session REST API endpoints:

### Endpoints
- `GET /api/status` & `GET /api/status.json`: Returns pipeline status, framework version, mode, config hash, and supported scenarios.
- `POST /api/twin/set_scenario`: Configures scenario (`normal_operation`, `approaching_vessel`, etc.), mode (`HYBRID_DEMO` or `PHYSICAL_ONLY`), and seed. Validates scenario (unknown -> 400).
- `POST /api/twin/step`: Steps simulation by clamped `dt` (`[0.05, 5.0]`). Returns readings, early warning decision, `twin_heuristic_state` (labeled *"Twin heuristic (NOT the fusion classifier)"*), indicator groups, hold progress, ground-truth `t_event`, and config hash.
- `POST /api/twin/reset`: Resets simulator and early warning engine for the active session.
- `GET /api/twin/export?session=<id>`: Streams recorded run as JSONL in `artifacts/digital_twin/*.jsonl` format.
- `POST /api/hil/process_packet`: Ingests AbyssLink hardware packets, running real physical pipeline inference.

### Multi-Tab Session Isolation
- State is isolated per client tab using client-generated UUID session keys (`session_id`).
- Sessions are supplied via `X-Session-ID` header, request body `{"session_id": "..."}`, or query param `?session=`.
- Inactive sessions are automatically cleaned up after 1 hour (TTL).
- Backwards compatible: requests without a session ID fall back to the `"default"` session.

### Static / Offline Replay Mode
- If `/api/status` reports mode `"static"` or if `/api` is unreachable, `early_warning.js` automatically falls back to replaying from `web/data/twin_runs.json` with a visible `STATIC REPLAY` badge (`#static-replay-badge`).
- Tamper detection validates `twin_runs.json` structure; corrupted payloads trigger a prominent `#twin-integrity-warning` alert.


---

## 7. Static Cloud Deployment Guide

### Deploying to GitHub Pages
1. In repository settings, navigate to **Pages**.
2. Select Source: **Deploy from a branch**.
3. Branch: `main`, Folder: `/web`.
4. Save. GitHub Pages will serve the site at `https://<user>.github.io/<repo>/`.

### Deploying to Vercel
1. Install or run Vercel CLI from `SUBSEA\web`:
   ```bash
   cd web
   npx vercel
   ```
2. Or in the Vercel Dashboard:
   - Root Directory: `SUBSEA/web`
   - Framework Preset: **Other**
   - Build Command: *(None / leave empty)*
   - Output Directory: *(None / leave empty)*
3. Deploy. Zero build configuration required.

---

## 8. In-Browser Python Execution (Pyodide Assessment)

As specified in the architecture roadmap, an optional in-browser Python execution panel via Pyodide was evaluated.

### Decision: Skipped per Offline Vendoring Constraint
- **Air-Gapped & Offline Requirement**: Hard rules mandate zero remote CDN dependencies, zero web fonts, and zero external network calls.
- **Payload Footprint**: Vendoring Pyodide offline requires bundling the Emscripten WASM runtime, the Python 3.11/3.12 standard library ZIP, and pre-compiled WebAssembly wheels (`numpy`, etc.), which totals ~45–60 MB.
- **Coverage Equivalence**: All 22 scenarios across 6 attack vectors and 5 severity levels (over 2,200 trials) are already precomputed with high fidelity and exported to `web/data/*.json`. Users can explore full multi-trace sensor signals, gating pathways, and adversarial sweeps instantly with zero browser lag or memory consumption.

---

## 9. Automated Testing & Smoke Tests

Automated E2E smoke and regression testing uses headless Playwright:

### Prerequisites:
```bash
pip install -e ".[test]"
playwright install chromium
```

### Running the Web Test Suite:
```bash
pytest tests/test_web_export.py -v
pytest tests/test_web_smoke.py -v
```

This verifies that:
1. All static routes render without unhandled JavaScript exceptions or console errors.
2. The cohort isolation / data-kind banner is displayed on every page.
3. Interactive visualizations, cards, badges, and controls are mounted properly.
4. Tamper detection correctly triggers warnings when assets are modified.


