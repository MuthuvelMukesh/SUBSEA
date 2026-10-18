# Hardware-in-the-Loop (HIL) AbyssLink Bridge

## 1. Overview and Scientific Integrity Statement

The Subsea HIL AbyssLink Bridge connects real AbyssLink ESP32 sensor telemetry into Subsea's multimodal evidence fusion pipeline.

> **SCIENTIFIC INTEGRITY NOTICE**
>
> Data generated and processed by this bridge is strictly categorized under `data_kind: "HIL_SIMULATED_ACCEL"`.
> 
> The AbyssLink benchtop hardware platform provides:
> 1. A binary piezo vibration sensor (0 = normal, 1 = vibration)
> 2. An HC-SR04 ultrasonic distance sensor (2 cm to 450 cm)
> 3. An optical link via visible laser and light-dependent resistor (LDR)
>
> **The Subsea pipeline expects high-rate triaxial accelerometer data (50 Hz MPU6050) and AIS vessel kinematics.** Because the benchtop hardware measures only binary vibration and proximity, the bridge **synthesizes** 50 Hz accelerometer observations conditioned on the binary vibration flag and maps ultrasonic distance to scaled vessel coordinates.
>
> **This bridge validates software-firmware integration, protocol decoding, streaming adaptation, and real-time decision pipeline latency. It does NOT validate subsea acoustic or elastodynamic wave propagation physics.** HIL results form an independent validation cohort and are never pooled with real seabed DAS or simulated physical datasets.

---

## 2. Telemetry and Model Mapping Contract

The AbyssLink ESP32 transmits newline-delimited JSON over UART at 115200 baud every 300 ms (`TELEMETRY_INTERVAL_MS = 300`).

| AbyssLink Telemetry Field | AbyssLink Type | Subsea Target Model | Mapping / Transformation Logic |
|---------------------------|----------------|---------------------|--------------------------------|
| `type` | `"sensor" \| "ack"` | Internal Dispatch | `"sensor"` routes to pipeline; `"ack"` logs command receipt |
| `transmission` | `bool` | `LinkHealthTracker` | Indicates active laser telemetry; used with LDR for fault detection |
| `ldr` | `int (0 \| 1)` | `SensorHealth` | `0` = light received, `1` = interrupted. Fault flagged only when `transmission == true && ldr == 1` after grace period |
| `vibration` | `int (0 \| 1)` | `SensorObservation.acceleration` | Drives 50 Hz sinusoidal synthesis: `0` -> baseline (0.15g RMS), `1` -> disturbance (1.8g RMS at 8.0 Hz) |
| `distance_cm` | `float \| null` | `VesselObservation.position` | Scaled by `scale_factor` (0.1): e.g., 80.0 cm -> 8.0 m along X-axis. `null` -> `reported=False` |
| `distance_valid` | `bool` | `VesselObservation.reported` | `false` maps vessel position to (999.0, 999.0) with `reported=False` |
| `laser` | `"ON" \| "OFF"` | Telemetry Audit | Logged in raw audit records |
| `buzzer` | `"ON" \| "OFF"` | Telemetry Audit | Logged in raw audit records |
| `alert` | `string` | Audit / Rationale | Preserved in raw and decision audit logs |

---

## 3. Architecture

```
+--------------------+
|  AbyssLink ESP32   |
| (115200 baud UART) |
+---------+----------+
          | Serial JSON (300 ms interval)
          v
+---------+-------------------------------------------------------------+
| Subsea HIL Bridge (`src/subsea/hil_abysslink.py`)                     |
|                                                                       |
|  [JSON Parser] ---------> raw.jsonl                                   |
|       |                                                               |
|  [LinkHealthTracker] ---> LDR debounce, grace period, gap detection   |
|       |                                                               |
|  [AccelSynthesizer] ----> 50 Hz MPU6050 stream (phase-continuous)    |
|       |                                                               |
|  [DistanceToVessel] ----> Scaled coordinates & speed estimation       |
|       |                                                               |
|  [ScheduleInjector] ----> Injected faults / AIS evasions (optional)   |
|       |                                                               |
|  [Sliding Window Buffer (256 samples)]                                |
|       |                                                               |
|       v                                                               |
|  run_pipeline(observations, vessel) ===> decide()                     |
|       |                                                               |
|       +-----------------> decisions.jsonl                             |
|       +-----------------> manifest.json                               |
|       +-----------------> web/hil/latest.json (pointer)               |
+-----------------------------------------------------------------------+
```

---

## 4. Execution Modes and CLI Usage

The CLI script is located at `scripts/run_abysslink_hil.py`.

### 4.1 Mock Mode (Deterministic Emulator)
Runs the deterministic emulator without requiring hardware:
```bash
python scripts/run_abysslink_hil.py --mock --seed 42
```
Supported mock scenarios:
- `approach_vibration` (default): Vessel approaches from 120 cm to 20 cm with vibration disturbance.
- `far_quiet`: Vessel remains distant (150 cm) with no vibration (pure T0).
- `vibration_no_vessel`: Vibration without vessel proximity (evaluates to T1).
- `link_broken_transmitting`: Laser path interrupted during transmission (fails closed to TX).
- `ldr_high_transmission_off`: Inactive transmission with dark LDR (normal state, T0).
- `telemetry_gap`: Telemetry timeout gap > 1.0 s.
- `no_echo`: Ultrasonic sensor out of range or echo lost.

### 4.2 Live Serial Hardware Mode
Live communication with physical ESP32. By default, the bridge is **PASSIVE** (read-only):
```bash
python scripts/run_abysslink_hil.py --port COM3
```
To enable sending start and stop commands over serial, pass the `--send-commands` flag:
```bash
python scripts/run_abysslink_hil.py --port COM3 --send-commands
```

### 4.3 Replay Mode
Replays previously captured raw JSONL telemetry:
```bash
python scripts/run_abysslink_hil.py --replay artifacts/hil/run-20261018T063607Z/raw.jsonl
```

### 4.4 Fault Injection Schedules
Inject controlled adversarial AIS manipulations or link faults during a run:
```bash
python scripts/run_abysslink_hil.py --mock --schedule data/hil_schedules/adversarial_spoof.json
```

### 4.5 Baseline Comparison
Evaluate incoming telemetry against ablation baseline methods:
```bash
python scripts/run_abysslink_hil.py --mock --replay-baselines
```

---

## 5. Configuration Tunables (`config/hil_abysslink.yaml`)

- `distance.scale_factor`: Conversion multiplier from centimeters to meters (default: 0.1).
- `distance.smoothing_window`: Number of packets for speed and heading estimation (default: 5).
- `distance.min_valid_cm`: Threshold below which ultrasonic echo is treated as invalid (default: 2.0).
- `signal.ldr_debounce_packets`: Consecutive fault packets required before declaring link failure (default: 2).
- `signal.grace_period_s`: Initial settlement period following START_TRANSMISSION (default: 0.5 s).
- `signal.packet_timeout_s`: Maximum expected inter-packet delay before stale alert (default: 1.0 s).
- `pipeline.sampling_rate`: Acceleration synthesis sampling frequency (default: 50.0 Hz).
- `pipeline.window_size`: Observation window length for spectral FFT analysis (default: 256).

---

## 6. Artifact Specifications

All HIL executions generate isolated run directories under `artifacts/hil/run-<UTC>/`:
- `decisions.jsonl`: Line-by-line decision records including physical and association confidences, uncertainty, reliability, and hypothesis scores.
- `raw.jsonl`: Raw incoming packet telemetry and parsed fields.
- `manifest.json`: Cryptographic audit record containing SHA-256 hashes of input config, raw log, and decisions log.
- `web/hil/latest.json`: Pointer referencing the most recent execution directory for dashboard integration.
