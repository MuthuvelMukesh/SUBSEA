# Standalone Web Front End — Progress Log (`PROGRESS_WEB.md`)

## Summary Tracker

| Phase | Description | Deliverables | Test Count | AbyssLink Status | Commit | Status |
|-------|-------------|--------------|------------|------------------|--------|--------|
| **Phase 0** | Baseline & Plan | `PLAN_WEB.md`, `PROGRESS_WEB.md`, `dashboard/app.py` deprecation | 258 | VERIFIED UNCHANGED | `docs(web): phase 0 baseline, plan, and dashboard deprecation` | COMPLETED |
| **Phase 1** | Exporter & Data Layer | `src/subsea/web_export.py`, `scripts/export_web_data.py`, `tests/test_web_export.py`, `web/data/*.json` | 266 | VERIFIED UNCHANGED | `feat(web): phase 1 exporter, data layer, and tests` | COMPLETED |
| **Phase 2** | Site Shell & Components | `web/index.html`, `style.css`, Plotly vendored, `app.js`, `router.js`, `theme.js`, `banner.js`, `charts.js`, `components.js` | 266 | VERIFIED UNCHANGED | `feat(web): phase 2 site shell, styling, plotly vendoring, and router` | COMPLETED |
| **Phase 3** | Pages 1–5 | Overview, Scenarios, Signals, Geometry, Evidence Timeline | 266 | VERIFIED UNCHANGED | `feat(web): phase 3 pages 1-5 overview scenarios signals geometry timeline` | COMPLETED |
| **Phase 4** | Pages 6–10 | Decision Path, Hypotheses, Adversarial, Baselines, Robustness | 266 | VERIFIED UNCHANGED | `feat(web): phase 4 pages 6-10 decision_path hypotheses adversarial baselines robustness` | COMPLETED |
| **Phase 5** | Pages 11, 13, 14 | Real DAS, Provenance, Publications | 266 | VERIFIED UNCHANGED | `feat(web): phase 5 pages 11 13 14 real_das provenance publications` | COMPLETED |
| **Phase 6** | Page 12 (Live HIL) | Live HIL dashboard with polling, drag-and-drop, and disclaimer | 266 | VERIFIED UNCHANGED | `feat(web): phase 6 page 12 live hil dashboard` | COMPLETED |
| **Phase 7** | Documentation | `docs/WEB.md`, `README.md` update | 266 | VERIFIED UNCHANGED | `docs(web): phase 7 documentation and readme updates` | COMPLETED |
| **Phase 8** | Smoke & Tamper Tests | `tests/test_web_smoke.py`, Playwright automated browser tests across all 14 pages & tamper detection | 283 | VERIFIED UNCHANGED | `feat(web): phase 8 automated smoke and tamper tests` | COMPLETED |
| **Phase 9** | Pyodide Feasibility | In-browser Python assessment (Skipped per offline vendoring constraint) | 283 | VERIFIED UNCHANGED | `docs(web): phase 9 pyodide offline feasibility assessment` | COMPLETED |
| **Phase 10** | Direct ESP32 Web Serial | Direct USB serial link (`hardware_serial.js`, `hardware_adapter.js`, `serve_web.py`, real-time pipeline inference bridge, tests) | 292 | VERIFIED UNCHANGED | `feat(hil): direct esp32 hardware usb serial connectivity` | COMPLETED |
| **Phase A** | Verify & Repair What Exists | Verified `early_warning.js` and `hil.js` existence, added `playwright` to pyproject.toml test extra, documented `playwright install chromium`, verified 24/24 smoke tests and 8/8 export tests | 319 | VERIFIED UNCHANGED | `chore(web): phase a verify and repair existing pages and test suite` | COMPLETED |
| **Phase B** | Backend / API Fixes | Session isolation, twin heuristic state labeling, channel quality guard, export endpoint, input validation | 327 | VERIFIED UNCHANGED | `feat(api): session isolation, input validation, and digital twin export endpoint` | COMPLETED |
| **Phase C** | Early Warning Page Upgrade | State badge W0-WX, indicator groups, hold meters, dual timeline, controls, operator audit log | 327 | VERIFIED UNCHANGED | `feat(web): upgraded early warning experience with dual timeline, hold meters, and indicator groups` | COMPLETED |
| **Phase D** | Static/Offline Mode & Research | `twin_runs.json` export, offline replay fallback, Early Warning Benchmarks in research view | 329 | VERIFIED UNCHANGED | `feat(web): static twin replay and early warning benchmark research view` | COMPLETED |
| **Phase E** | Tests & Docs | Session tests, Playwright smoke tests (28), static fallback tests, tamper detection, documentation update | 333 | VERIFIED UNCHANGED | `test(web): playwright smoke tests, session isolation tests, and documentation` | COMPLETED |

---

## Phase Details


### Phase 0: Baseline & Plan
- **Baseline Test Suite**: 258 passed, 0 failures in 52.01s.
- **AbyssLink Hashes**: Recorded in `$env:TEMP\abysslink_hashes_baseline.txt` and scratch backup. Verified 5 files matching baseline.
- **Files Touched**: `dashboard/app.py` (deprecation note added), `PLAN_WEB.md`, `PROGRESS_WEB.md`.
- **Status**: COMPLETED.

### Phase 1: Exporter & Data Layer
- **Test Suite**: 266 passed, 0 failures in 26.24s (8 new tests in `tests/test_web_export.py`).
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created/Modified**: `src/subsea/web_export.py`, `scripts/export_web_data.py`, `tests/test_web_export.py`, `web/data/*.json` (17 JSON files), `web/assets/figures/*.png` (copied static figures).
- **Status**: COMPLETED.

### Phase 2: Site Shell & Components
- **Test Suite**: 266 passed, 0 failures in 32.07s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created**: `web/index.html`, `web/assets/style.css`, `web/vendor/plotly.min.js`, `web/js/app.js`, `web/js/router.js`, `web/js/theme.js`, `web/js/banner.js`, `web/js/charts.js`, `web/js/components.js`.
- **Status**: COMPLETED.

### Phase 3: Pages 1–5
- **Test Suite**: 266 passed, 0 failures in 67.53s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created**:
  - `web/js/pages/overview.js` (Page 1: System KPI cards, decision state definitions, cohort breakdown, scientific disclaimers)
  - `web/js/pages/scenarios.js` (Page 2: S01–S22 selector, 6 attack types, 5 severities, metric comparison charts)
  - `web/js/pages/signals.js` (Page 3: Triaxial acceleration waveform, magnitude, packet loss markers, FFT spectrum, spectral features table & CSV download)
  - `web/js/pages/geometry.js` (Page 4: 2D metric coordinate map, 10m interaction corridor, vessel trajectory, distance vs time, CPA, dwell time, crossing detection)
  - `web/js/pages/timeline.js` (Page 5: Sliding-window multi-trace chart of C_P, C_A, R, U, discrete decision state sequence, window table & CSV export)
- **Status**: COMPLETED.

### Phase 4: Pages 6–10
- **Test Suite**: 266 passed, 0 failures in 27.91s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created**:
  - `web/js/pages/decision_path.js` (Page 6: 5-stage sequential decision gating engine, deciding gate highlighting, interactive exploratory what-if sandbox)
  - `web/js/pages/hypotheses.js` (Page 7: Real Hypothesis enum names, candidate evidence scoring, positive/counter evidence audit trail, audit breakdown table)
  - `web/js/pages/adversarial.js` (Page 8: 6-level severity sweeps, AER & FHER curves, stacked decision distributions, scientific statement display)
  - `web/js/pages/baselines.js` (Page 9: Proposed vs single-modality baselines, paired bootstrap 95% CIs, McNemar tests, multi-modal ablation hierarchy)
  - `web/js/pages/robustness.js` (Page 10: Sensor degradation/fault stress matrix, probability calibration curves, Brier score, ECE, reliability diagnostics)
- **Status**: COMPLETED.

### Phase 5: Pages 11, 13, 14
- **Test Suite**: 266 passed, 0 failures in 37.41s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created**:
  - `web/js/pages/real_das.js` (Page 11: Real DAS deployments for Marlinks, EMSO, Oliktok; exact wording of zero T2/T3 false escalation finding; autocorrelation caveats)
  - `web/js/pages/provenance.js` (Page 13: Live Web Crypto API SHA-256 auditing of shipped assets; match/mismatch indicators; PROVENANCE.json records)
  - `web/js/pages/publications.js` (Page 14: Publication figures browser with PNG downloads and tables browser with CSV downloads; cohort filters)
- **Status**: COMPLETED.

### Phase 6: Page 12 (Live HIL)
- **Test Suite**: 266 passed, 0 failures in 68.17s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created/Modified**:
  - `web/js/pages/hil.js` (Page 12: Live HIL streaming dashboard with 2s polling of `latest.json`, drag-and-drop JSONL loader, simulated accelerometer disclaimer, real schema from actual HIL run)
  - `scripts/export_web_data.py` (Synced latest HIL decisions to `web/hil/decisions.jsonl`)
  - Tested against real mock run log: `python scripts/run_abysslink_hil.py --mock --seed 42` (100 packets, 55 T0, 2 T1, 43 T2, 0 T3, 0 TX)
- **Status**: COMPLETED.

### Phase 7: Documentation
- **Test Suite**: 266 passed, 0 failures in 52.20s.
- **AbyssLink Hashes**: 5/5 verified unchanged.
- **Files Created/Modified**:
  - `docs/WEB.md` (Architecture, data flow, cohort isolation rules, justification for committing `web/data/*.json`, page-to-data mapping, local serving and Vercel/GitHub Pages deployment instructions)
  - `README.md` (Updated test badge to 266, updated tree structure, replaced Streamlit instructions with 14-page static web frontend guide)
- **Status**: COMPLETED.

### Phase 8: Smoke & Tamper Tests
- **Test Suite**: 283 passed (266 unit/pipeline + 17 Playwright browser tests), 0 failures in 52.92s.
- **AbyssLink Hashes**: 5/5 verified unchanged against baseline.
- **Automated Browser Coverage**:
  - Headless Chromium browser testing all 14 hash routes (`#/overview`, `#/scenarios`, `#/signals`, `#/geometry`, `#/timeline`, `#/decision-path`, `#/hypotheses`, `#/adversarial`, `#/baselines`, `#/robustness`, `#/real-das`, `#/hil`, `#/provenance`, `#/publications`).
  - Verified no unhandled JavaScript console errors or fatal page exceptions on any route.
  - Verified presence of cohort isolation banner on every page matching exact data kind tokens (`SIMULATION`, `REAL_DAS`, `HIL_SIMULATED_ACCEL`).
  - Verified tamper detection in `test_provenance_tamper_detection`: live payload interception triggers provenance mismatch reporting.
  - Verified graceful degradation in `test_missing_data_graceful_handling`: missing data files render without crashing the application shell.
- **Files Created/Modified**:
  - `tests/test_web_smoke.py` (17 headless Playwright smoke and tamper tests)
  - `web/js/banner.js` (cohort badges aligned to exact tokens)
  - `web/js/pages/adversarial.js` (fixed template literal syntax)
  - `web/js/pages/timeline.js` (ensured initial banner render)
- **Status**: COMPLETED.

### Phase 9: Optional Pyodide Phase Assessment
- **Assessment Finding**: Skipped per explicit prompt specification: *"If Pyodide cannot be vendored offline, skip this phase and report why."*
- **Technical Justification**:
  - The core architecture enforces a zero-external-CDN, fully air-gapped offline static site design.
  - Vendoring Pyodide + Emscripten WASM binary + Python standard library archive (`python_stdlib.zip`) + compiled NumPy wheels requires ~45–60 MB of third-party binary artifacts not pre-bundled in the workspace.
  - Fetching Pyodide at runtime from CDN (e.g. `cdn.jsdelivr.net`) violates Hard Rule 8 / Frontend Stack rules ("No CDN, no web fonts, no remote images, no analytics").
  - The 14 static pages already provide precomputed, deterministic pipeline runs for all 22 scenarios across 6 attack vectors and 5 severity levels, fully satisfying interactive exploration requirements without incurring heavy in-browser runtime penalties.
- **AbyssLink Hashes**: 5/5 verified unchanged against baseline.
- **Status**: COMPLETED (Formally evaluated and skipped per offline constraint).

### Phase 10: Direct ESP32 Web Serial Hardware Integration
- **Deliverables**:
  - `web/js/hardware_serial.js`: Web Serial API controller supporting 115200 baud streaming, line buffering, TextDecoder/TextEncoder streams, command transmission (`START_TRANSMISSION\n`, `STOP_TRANSMISSION\n`), ACK handling, USB physical disconnect listener, and duplicate connection guards.
  - `web/js/hardware_adapter.js`: Telemetry parser, packet validator, bounded raw packet buffer, raw JSONL export, transition logger, and Python pipeline bridge client.
  - `scripts/serve_web.py`: Unified server serving static files from `web/` plus HTTP endpoints:
    - `GET /api/status` & `GET /api/status.json` (pipeline status indicator)
    - `POST /api/hil/process_packet` (routes live Web Serial packets directly into `HILBridge.process_packet()`, runs real `run_pipeline()` and `decide()`, and returns real `DecisionResult`)
    - `POST /api/hil/reset` (resets HIL run session)
  - `web/js/pages/hil.js`: Integrated direct USB serial connectivity, 4 live hardware cards (LDR, vibration, ultrasonic distance, actuators), Start/Stop transmission controls, raw JSONL telemetry export, bounded event audit log (50 events), and real pipeline inference display.
  - `web/api/status.json`: Static fallback status file ensuring zero 404 console errors on pure static hosts.
  - `tests/test_hardware_serial.py`: 9 comprehensive automated tests for packet validation, missing fields, buffer stream splitting, malformed recovery, adapter mapping, and real pipeline execution.
- **Test Suite**: 292 passed (258 baseline + 8 web export + 17 Playwright browser smoke + 9 hardware serial), 0 failures in 44.66s.
- **AbyssLink Hashes**: 5/5 verified unchanged against baseline.
- **Status**: COMPLETED.

### Phase A: Verify and Repair What Exists
- **Verification of Router and Pages**:
  - `web/js/router.js` maps `early-warning` -> `web/js/pages/early_warning.js` and `hil` -> `web/js/pages/hil.js`.
  - Both files exist and render properly without stubs or missing elements.
  - `hil.js` includes polling of `web/hil/latest.json`, JSONL drag-and-drop loader, simulated accelerometer disclaimer, and Web Serial controls using `hardware_serial.js` and `hardware_adapter.js`.
- **Dependencies & Tests**:
  - Updated `pyproject.toml` to include `"playwright>=1.40"` in `[project.optional-dependencies] test`.
  - Documented Playwright test execution and `playwright install chromium` in `docs/WEB.md`.
- **Status**: COMPLETED.

### Phase B: Backend/API Fixes
- **Session Isolation**:
  - Replaced module-global twin and early warning engine instances with per-session `TwinSession` state keyed by client UUID `session_id`.
  - Added support for extracting session ID from JSON body, `X-Session-ID` / `X-Session-Id` headers, or `?session=` query parameter.
  - Provided clean fallback to `"default"` session for backwards compatibility.
  - Added session TTL cleanup (1 hour TTL).
- **Twin Heuristic State Labeling**:
  - Formally renamed disturbance classification to `twin_heuristic_state` with clear labeling `"Twin heuristic (NOT the fusion classifier)"`, while maintaining `disturbance_classification` as an alias for backwards compatibility.
- **Channel Quality Guards**:
  - Safely guarded `frame.readings.get("das_rms")` against missing channel objects, preventing `AttributeError` when channels are missing or degraded.
- **Rich Per-Step Metadata & Ground-Truth**:
  - Added per-group indicator status (`quiet`/`watch`/`urgent`), threshold definitions, source chips, and mixed-source warning flags.
  - Added hold/persistence progress metrics in seconds and frame counts for both escalation and de-escalation.
  - Added ground-truth `t_event` mapping to `TwinScenario` in `digital_twin.py`.
  - Included config hash and seed in every step payload.
- **Export Endpoint**:
  - Implemented `GET /api/twin/export?session=<id>` returning JSONL streaming records matching `artifacts/digital_twin/*.jsonl` format.
- **Validation**:
  - Unknown scenario returns HTTP 400 with a list of valid scenarios.
  - `dt` is clamped to safe range `[0.05, 5.0]`.
  - Request body size is capped at 64KB (HTTP 413).
- **Status**: COMPLETED.

### Phase C: Early Warning Page Upgrade (`web/js/pages/early_warning.js`)
- **State Badge W0-WX & Explainability**:
  - Rendered with icon + text + colour (`🟢 W0`, `🟡 W1`, `🟠 W2`, `🔴 W3`, `⚪ WX`), never colour alone.
  - Confidence displayed as heuristic score (`Score: 95%`).
  - Implemented expandable `<details>` panel "Why this state?" exposing primary explanation, triggering indicators, persistence reasons, and data quality integrity.
  - Kept critical DOM test identifiers `#early-warning-state-badge` and `#early-warning-quality-badge`.
- **Indicator Group Panel**:
  - Implemented 6 corroboration group rows: Vibration & Acoustics, Physical Proximity (Ultrasonic), Vessel Proximity (Corridor), Mechanical Cable Strain, Benthic Thermal, Cable Integrity & Optical Link.
  - Displayed current values vs quantitative thresholds, quiet/watch/urgent status badges, provenance chips (`SIMULATED`, `PHYSICAL`, `REAL-NOISE`), and mixed-source warning chips (`⚠️ MIXED SOURCES`).
- **Hold & Persistence Meters**:
  - Added visual progress meters for escalation persistence (seconds / target threshold seconds) and de-escalation hold (quiet seconds / target quiet seconds).
  - Clarified hysteresis state hold conditions in operator caption.
- **State Timeline Dual Strip**:
  - Created dual-strip Plotly chart in `#twin-timeline-strip`:
    - Top strip: Early Warning state ($W0 \to W1 \to W2 \to W3 \to WX$).
    - Bottom strip: Disturbance classification state ($T0 \to T1 \to T2 \to T3 \to TX$) explicitly labelled `"Twin heuristic (NOT the fusion classifier)"`.
    - Vertical marker at ground-truth `t_event` with dynamic advance lead time calculation.
- **Run Controls**:
  - Implemented scenario selector across 7 digital twin scenarios (`#select-twin-scenario`), seed input (`#input-twin-seed`), speed selector (0.5x, 1x, 2x, 5x), Play/Pause (`#btn-twin-run`), Step (`#btn-twin-step`), Reset (`#btn-twin-reset`), Replay (`#btn-twin-replay`), and Export Run JSONL (`#btn-twin-export`).
  - Enforced `PHYSICAL_ONLY` mode isolation: shows WX with honest disconnect explanation and zero simulated data.
- **Operator Basics**:
  - Added acknowledge button (`#btn-ack-alert`) for W2/W3 alerts.
  - Added bounded audit log (`<= 100` items) with search, filter, and CSV export.
  - Added `aria-live="polite"` element for assistive screen reader announcements.
- **Scientific Integrity**:
  - Embedded prominent notice: *"Digital-twin channels are simulated benchmark models, not field measurements."*
- **Verification**:
  - Automated Playwright smoke tests pass 100% (24/24 passed in 35.6s).

### Phase D: Static/Offline Mode & Research View
- **Export Precomputed Twin Runs**:
  - Implemented `generate_twin_runs(seed=42)` in `src/subsea/web_export.py` precomputing deterministic runs across all 7 digital twin scenarios with frame summaries, readings, early warning decisions, and `t_event`.
  - Added export step in `scripts/export_web_data.py` producing `web/data/twin_runs.json`.
  - Added `"twin_runs.json"` to expected files in `tests/test_web_export.py` with determinism validation test.
- **Static Replay Fallback**:
  - `web/js/pages/early_warning.js` dynamically checks backend availability. If `/api/status` shows mode `"static"` or if live requests fail, it seamlessly falls back to replaying from `web/data/twin_runs.json` with a prominent `STATIC REPLAY` badge (`#static-replay-badge`).
  - Added integrity validation to `web/js/pages/early_warning.js`: corrupted or tampered `twin_runs.json` immediately triggers a visible warning card (`#twin-integrity-warning`).
- **Research Hub Early Warning Benchmarks Tab**:
  - Implemented `export_early_warning_eval()` in `src/subsea/web_export.py` exporting Monte Carlo scorecard, latency distributions (median, P5, P95), operational KPIs, engine vs baseline vs ablation comparisons, and ROC curve to `web/data/early_warning_eval.json`.
  - Added 6th sub-tab `6. Early Warning Benchmarks` to `web/js/pages/research.js` rendering:
    - Provenance banner with SIMULATION chip, 10 seeds evaluated, 700 trials, 40/60 calibration/test split.
    - False alarms/hr, flapping rate, advance lead time, and fail-safe isolation KPIs.
    - Latency distribution horizontal bar chart with P5-P95 error bars (SIMULATION).
    - ROC operating curve with AUC = 0.992 (SIMULATION).
    - Deterministic benchmark scorecard and ablation comparison table.
    - Explicit "not yet generated" card with generating instructions if artifacts are missing.
- **Verification**:
  - All 10 export tests passed.
  - All 24 Playwright smoke tests passed.
- **Status**: COMPLETED.

### Phase E: Tests and Docs
- **Automated Playwright Smoke Tests (`tests/test_web_smoke.py`)**:
  - Expanded test suite from 24 to 28 browser tests:
    - Early warning page renders with zero console errors.
    - Scenario switch resets state (`test_early_warning_scenario_switch_resets_state`).
    - `PHYSICAL_ONLY` mode shows `WX`, zero simulated telemetry, and explicit channel isolation rationale (`test_early_warning_physical_only_mode`).
    - Static replay fallback executes seamlessly when `/api` is intercepted and blocked (`test_early_warning_static_replay_fallback_when_api_blocked`).
    - Direct ESP32 Web Serial HIL page renders with hardware sensor cards, status badges, and controls.
    - Tamper warning appears on screen when `twin_runs.json` payload is corrupted (`test_early_warning_tamper_warning_on_corrupt_twin_runs`).
    - Route list and primary navigation order assertions hold (`#/detection` -> `#/early-warning` -> `#/research`).
- **Python Unit & API Tests**:
  - Per-session isolation verified across concurrent sessions in `tests/test_twin_session_api.py`.
  - Endpoint validation tested: unknown scenario returns 400, `dt` clamped to `[0.05, 5.0]`, body size limited to 64KB (413).
  - Export endpoint streaming JSONL schema verified against `artifacts/digital_twin/*.jsonl` format.
  - `twin_runs.json` determinism verified (seed 42 produces identical step states).
- **Documentation Updated**:
  - `docs/WEB.md`: Documented 3 primary navigation modules, Early Warning components, 6th research sub-tab (Early Warning Benchmarks), new digital twin REST API endpoints, session isolation keys, and offline static replay mode.
  - `docs/DIGITAL_TWIN.md`: Updated with heuristic state labeling rules, multi-session isolation architecture, endpoint parameters, and static replay fallback.
  - `README.md`: Updated test badge to 333 passed based strictly on actual pytest output.
- **Verification**:
  - 333/333 tests passed across full repository test suite in 75.87s.
- **Status**: COMPLETED.

