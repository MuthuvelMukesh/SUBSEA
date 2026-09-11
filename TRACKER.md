# Project Tracker

Last updated: 2026-09-11

This tracker distinguishes implemented software from results that require an executed experiment, real hardware, or an external dataset. A checked implementation item does not imply scientific validation.

## Status Legend

- `[x]` Implemented and covered by tests.
- `[~]` Partial prototype or adapter; more work is required.
- `[ ]` Not implemented.
- `PENDING` Experiment or dataset required; never treated as zero or success.

## Completed

- [x] Python package and reproducible source layout.
- [x] Typed sensor, vessel, evidence, hypothesis, health, and decision contracts.
- [x] MPU6050 acceleration magnitude and spectral features.
- [x] Spatial, temporal, and behaviour association outputs.
- [x] Sensor health, availability, stale-data handling, and fail-closed `TX` behavior.
- [x] Positive evidence, counter-evidence, missing corroboration, and competing hypotheses.
- [x] Interpretable weighted fusion with auditable intermediate values.
- [x] Deterministic synthetic scenarios and seeded experiment manifests.
- [x] Vessel-side AIS spoofing, transponder suppression, and timestamp manipulation hooks.
- [x] Explicit AER/FHER cohort metrics with `NOT EXECUTED` handling.
- [x] Baseline and ablation evaluator with aligned trials.
- [x] Streamlit prototype dashboard.
- [x] CLI commands for simulation, adversarial trials, and baseline comparisons.
- [x] Focused regression suite: 60 tests passing, with 2 optional HDF5 tests skipped when `h5py` is unavailable.

## Current Phase: Real Data, Metrics, and Paper Outputs

- [x] Real-data boundary contracts: read-only CSV/JSON/HDF5 loaders with source hashes and timestamp normalization.
- [~] DAS-specific HDF5 adapter reads configured signal, timestamp, and distance paths; Marlinks schema mapping remains dataset-specific.
- [x] AIS-like trajectory loader with ordering, timestamp normalization, uncertainty, and explicit interpolation policy.
- [ ] Real-data association validation without causal attribution claims.
- [x] Expanded classification metrics: precision, recall, F1, confusion matrix, and per-class support.
- [x] Brier score and calibration curve support with explicit binary/multiclass semantics.
- [x] ECE validation and bin-policy documentation.
- [x] Bootstrap confidence intervals with sample-size/status safeguards.
- [ ] Statistical comparison utilities selected by study design.
- [x] Publication-quality figure generation for method comparisons.
- [x] CSV and LaTeX table generation from executed manifests.
- [~] Paper-result manifest links source hash, seed, software version, scenarios, and methods; configuration capture remains.

## Hardware and Operations Gaps

- [~] ESP32/MPU6050 packet schema exists.
- [x] MQTT receiver adapter.
- [x] HTTP receiver adapter.
- [x] Serial receiver adapter.
- [x] Raw packet recorder with append-only behavior.
- [ ] LIVE, SIMULATION, and REPLAY mode coordinator.
- [ ] Hardware experiment workflows H01-H08.
- [ ] Hardware-in-the-loop latency measurement.
- [ ] ESP32 firmware source and wiring documentation.

## Simulation and Adversarial Gaps

- [~] S01-S22 scenario identifiers and explicit truth flags are supported; basic multi-vessel S22 evaluation exists, while multi-node generation remains partial.
- [ ] Remaining scenario matrix S03, S06, S08-S16, S20-S22.
- [ ] Multi-node and multi-vessel generation.
- [ ] Packet-loss/noise/position-uncertainty parameter sweeps.
- [~] Adversarial severity sweep with AER/FHER curves.
- [ ] FHER by benign operating condition.
- [ ] Monte Carlo result tables with explicit trial counts.

## Dashboard Gaps

- [~] Overview, scenario selection, hypothesis chart, and audit summary.
- [ ] Sensor-health timeline.
- [ ] Vibration waveform and FFT views.
- [ ] Vessel/cable spatial view.
- [ ] Evidence and uncertainty timelines.
- [ ] Adversarial severity and baseline comparison views.
- [ ] Paper figure browser.

## Scientific Integrity Gates

- [x] No fabricated experiment results in source or documentation.
- [x] Empty cohorts remain `NOT EXECUTED`.
- [x] Synthetic results are labeled and are not causal attribution ground truth.
- [ ] Real-data validation executed with a versioned dataset.
- [ ] Hardware experiments executed and archived.
- [ ] Thresholds and weights calibrated from documented experiments.
- [ ] Confidence intervals/statistical tests justified by study design.

## Iteration Log

### 2026-09-10

- Added this tracker as the project status source of truth.
- Recorded the next phase: real-data loaders, richer metrics/calibration, and paper outputs.
- Baseline/ablation phase completed with 23 passing tests.
- Added `subsea.real_data` loaders for CSV/JSON/HDF5 boundary validation; HDF5 execution is pending `h5py` installation.
- Added richer classification, Brier, calibration-curve, and seeded bootstrap metrics; insufficient samples remain `NOT EXECUTED`.
- Added executed-manifest paper CSV/LaTeX table and Matplotlib figure generation with provenance output.
- Hardened paper generation against unverified manifests, invalid metric ranges, ambiguous timestamps, and partial figure output.
- Added record-level summary recomputation and rejected unsupported/non-finite timestamp values.
- Added `subsea.das` and `subsea.ais` adapters with provenance and causal-ground-truth safeguards.
- Added polyline cable geometry, nearest-segment distance, CPA, dwell, crossing, and separated behaviour components.
- Added explicit S01-S22 scenario identifiers and deterministic condition flags; multi-node/multi-vessel generation remains partial.
- Added MQTT/HTTP/serial packet adapters, append-only raw recording, auditable trial components, latency records, and attack severity sweeps.
- Corrected DAS channel orientation, communication-failure simulation, AIS physical bounds, multi-segment crossing, and global timestamp ordering.
- Corrected zero-severity adversarial baselines, exercised S13-S15 conditions, hardened DAS/AIS boundaries, and made sweep paths collision-safe.
- Hardened severity/audit fields, DAS/recording timestamps, and malformed geometry rejection.
- Added explicit S22 two-vessel generation while retaining multi-node generation as partial.
- Added shared MQTT/HTTP/serial packet adapters and append-only raw packet recording.

## Next Smallest Deliverable

Implement multi-node/multi-vessel generation and full spatial/temporal manipulation experiments on top of the validated geometry and trajectory components. Preserve raw input files, record preprocessing parameters, and label unavailable metadata rather than infer causal truth.
