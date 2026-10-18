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
| **Phase 9** | Pyodide Feasibility | In-browser Python assessment | Pending | Pending | - | PENDING |

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
