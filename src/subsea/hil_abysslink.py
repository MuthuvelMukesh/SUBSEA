"""Hardware-in-the-Loop (HIL) AbyssLink Bridge.

Bridges real AbyssLink ESP32 serial telemetry into the Subsea research pipeline,
synthesizing 50 Hz accelerometer data from binary vibration flags while mapping
ultrasonic distance to vessel observations.

Scientific Integrity Notice:
Data processed by this bridge is tagged with data_kind="HIL_SIMULATED_ACCEL".
Accelerometer data is synthesized and does not represent subsea acoustic physics.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
import datetime
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any

import numpy as np
import yaml

from .models import DecisionResult, DecisionState, SensorObservation, VesselObservation
from .pipeline import run_pipeline


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

@dataclass
class DistanceConfig:
    scale_factor: float = 0.1        # 80 cm -> 8.0 m
    smoothing_window: int = 5        # packets for speed estimation
    min_valid_cm: float = 2.0        # below this -> unavailable


@dataclass
class SignalConfig:
    ldr_debounce_packets: int = 2
    vibration_debounce_packets: int = 2
    grace_period_s: float = 0.5      # ignore LDR after START_TRANSMISSION
    packet_timeout_s: float = 1.0


@dataclass
class PipelineConfig:
    sampling_rate: float = 50.0
    window_size: int = 256
    baseline_rms: float = 1.0
    disturbance_rms: float = 1.8
    interaction_radius: float = 10.0
    temporal_tolerance: float = 5.0
    expected_interval: float = 0.02


@dataclass
class AccelConfig:
    baseline_amplitude: float = 0.15
    disturbance_amplitude: float = 1.8
    frequency_hz: float = 8.0
    noise_std: float = 0.03


@dataclass
class MockConfig:
    approach_start_cm: float = 120.0
    approach_end_cm: float = 20.0
    retreat_end_cm: float = 150.0
    link_break_duration_s: float = 3.0
    no_echo_duration_s: float = 2.0


@dataclass
class HILConfig:
    distance: DistanceConfig = field(default_factory=DistanceConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    accel: AccelConfig = field(default_factory=AccelConfig)
    mock: MockConfig = field(default_factory=MockConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> HILConfig:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Config file not found: {p}")
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls(
            distance=DistanceConfig(**raw.get("distance", {})),
            signal=SignalConfig(**raw.get("signal", {})),
            pipeline=PipelineConfig(**raw.get("pipeline", {})),
            accel=AccelConfig(**raw.get("accel", {})),
            mock=MockConfig(**raw.get("mock", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# Packet Data Structures & Parsing
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class AbyssLinkPacket:
    type: str                         # "sensor" or "ack"
    transmission: bool
    ldr: int = 0                      # 0 = light detected, 1 = interrupted
    vibration: int = 0                # 0 = normal, 1 = vibration
    distance_cm: float | None = None
    distance_valid: bool = False
    laser: str = "OFF"                # "ON" or "OFF"
    buzzer: str = "OFF"               # "ON" or "OFF"
    alert: str = "SAFE"
    command: str | None = None        # for ack
    success: bool | None = None       # for ack
    raw_line: str = ""
    timestamp: float = 0.0


def parse_abysslink_line(line: str, timestamp: float | None = None) -> AbyssLinkPacket | None:
    """Parse a single newline-delimited JSON line from AbyssLink serial stream.

    Returns an AbyssLinkPacket instance or None if the line is malformed/unrecognized.
    """
    clean = line.strip()
    if not clean or not clean.startswith("{") or not clean.endswith("}"):
        return None

    try:
        data = json.loads(clean)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    pkt_type = data.get("type")
    t = timestamp if timestamp is not None else 0.0

    if pkt_type == "sensor":
        raw_dist = data.get("distance_cm")
        dist_cm: float | None = None
        if raw_dist is not None:
            try:
                dist_cm = float(raw_dist)
            except (ValueError, TypeError):
                dist_cm = None

        dist_valid = bool(data.get("distance_valid", False))
        if dist_cm is not None and dist_cm < 2.0:
            dist_valid = False

        return AbyssLinkPacket(
            type="sensor",
            transmission=bool(data.get("transmission", False)),
            ldr=int(data.get("ldr", 0)),
            vibration=int(data.get("vibration", 0)),
            distance_cm=dist_cm,
            distance_valid=dist_valid,
            laser=str(data.get("laser", "OFF")),
            buzzer=str(data.get("buzzer", "OFF")),
            alert=str(data.get("alert", "SAFE")),
            raw_line=clean,
            timestamp=t,
        )

    if pkt_type == "ack":
        return AbyssLinkPacket(
            type="ack",
            transmission=bool(data.get("transmission", False)),
            command=str(data.get("command", "")),
            success=bool(data.get("success", False)),
            raw_line=clean,
            timestamp=t,
        )

    return None


# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

class MockAbyssLinkSource:
    """Deterministic simulated AbyssLink telemetry generator."""

    def __init__(
        self,
        seed: int = 42,
        scenario: str = "approach_vibration",
        config: HILConfig | None = None,
        total_packets: int = 100,
        start_time: float = 1000.0,
    ) -> None:
        self.seed = seed
        self.scenario = scenario
        self.config = config or HILConfig()
        self.total_packets = total_packets
        self.current_idx = 0
        self.rng = random.Random(seed)
        self.start_time = start_time
        self.interval = 0.3  # 300 ms telemetry interval

    def __iter__(self) -> Iterator[AbyssLinkPacket]:
        self.current_idx = 0
        while self.current_idx < self.total_packets:
            pkt = self._generate_packet(self.current_idx)
            self.current_idx += 1
            yield pkt

    def read_packet(self) -> AbyssLinkPacket | None:
        if self.current_idx >= self.total_packets:
            return None
        pkt = self._generate_packet(self.current_idx)
        self.current_idx += 1
        return pkt

    def _generate_packet(self, idx: int) -> AbyssLinkPacket:
        t = self.start_time + idx * self.interval
        transmission = True
        ldr = 0
        vibration = 0
        dist_cm: float | None = 120.0
        dist_valid = True
        alert = "SAFE"

        if self.scenario == "far_quiet":
            dist_cm = 150.0
            vibration = 0
            ldr = 0
            alert = "SAFE"

        elif self.scenario == "approach_vibration":
            # 0-20: approaching 120 -> 90 cm, quiet
            # 21-50: approaching 90 -> 20 cm, vibrating (contact/disturbance)
            # 51-70: close range 20 cm, vibrating
            # 71-100: retreating 20 -> 120 cm, quiet
            if idx <= 20:
                dist_cm = 120.0 - (idx / 20.0) * 30.0
                vibration = 0
                alert = "SAFE"
            elif idx <= 50:
                progress = (idx - 20) / 30.0
                dist_cm = 90.0 - progress * 70.0  # reaches 20 cm
                vibration = 1
                alert = "VIBRATION" if dist_cm > 50.0 else "PROXIMITY_DANGER"
            elif idx <= 70:
                dist_cm = 20.0
                vibration = 1
                alert = "PROXIMITY_DANGER"
            else:
                progress = (idx - 70) / 30.0
                dist_cm = 20.0 + progress * 100.0
                vibration = 0
                alert = "SAFE"

        elif self.scenario == "vibration_no_vessel":
            dist_cm = None
            dist_valid = False
            vibration = 1
            alert = "VIBRATION"

        elif self.scenario == "link_broken_transmitting":
            # Packets 0-5 normal, >= 6 laser blocked
            dist_cm = 80.0
            if idx >= 6:
                ldr = 1
                alert = "LASER_INTERRUPTION"

        elif self.scenario == "ldr_high_transmission_off":
            # Laser transmission is inactive, LDR = 1 is normal dark state
            transmission = False
            ldr = 1
            dist_cm = 80.0
            alert = "SAFE"

        elif self.scenario == "telemetry_gap":
            # Jump timestamp between idx 20 and 21 by 3 seconds
            if idx > 20:
                t += 3.0
            dist_cm = 80.0

        elif self.scenario == "no_echo":
            dist_cm = None
            dist_valid = False
            alert = "DISTANCE_UNAVAILABLE"

        # Format exact JSON representation matching firmware snprintf
        if dist_valid and dist_cm is not None:
            json_str = (
                f'{{"type":"sensor","transmission":{str(transmission).lower()},'
                f'"ldr":{ldr},"vibration":{vibration},"distance_cm":{dist_cm:.1f},'
                f'"distance_valid":true,"laser":"{"ON" if transmission else "OFF"}",'
                f'"buzzer":"{"ON" if alert != "SAFE" else "OFF"}","alert":"{alert}"}}'
            )
        else:
            json_str = (
                f'{{"type":"sensor","transmission":{str(transmission).lower()},'
                f'"ldr":{ldr},"vibration":{vibration},"distance_cm":null,'
                f'"distance_valid":false,"laser":"{"ON" if transmission else "OFF"}",'
                f'"buzzer":"{"ON" if alert != "SAFE" else "OFF"}","alert":"{alert}"}}'
            )

        return AbyssLinkPacket(
            type="sensor",
            transmission=transmission,
            ldr=ldr,
            vibration=vibration,
            distance_cm=dist_cm,
            distance_valid=dist_valid,
            laser="ON" if transmission else "OFF",
            buzzer="ON" if alert != "SAFE" else "OFF",
            alert=alert,
            raw_line=json_str,
            timestamp=t,
        )


class ReplayAbyssLinkSource:
    """Replay packets from a recorded JSONL file."""

    def __init__(self, path: str | Path, seed: int = 42) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"Replay file not found: {self.path}")
        self.seed = seed
        self._lines = [line.strip() for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def __iter__(self) -> Iterator[AbyssLinkPacket]:
        for line in self._lines:
            pkt = parse_abysslink_line(line)
            if pkt is not None:
                yield pkt


class SerialAbyssLinkSource:
    """Serial port connection to physical AbyssLink ESP32.

    pyserial is imported lazily inside __init__.
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0) -> None:
        try:
            import serial
        except ImportError as exc:
            raise ImportError(
                "pyserial is required for live serial connection. "
                "Install with: pip install pyserial or pip install -e .[hil]"
            ) from exc

        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)

    def read_line(self) -> str | None:
        raw = self.ser.readline()
        if not raw:
            return None
        return raw.decode("utf-8", errors="replace")

    def read_packet(self, timestamp: float | None = None) -> AbyssLinkPacket | None:
        line = self.read_line()
        if line is None:
            return None
        return parse_abysslink_line(line, timestamp=timestamp)

    def send_command(self, cmd: str) -> None:
        self.ser.write(f"{cmd}\n".encode("utf-8"))
        self.ser.flush()

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()


# -----------------------------------------------------------------------------
# Signal Adaptation & Mapping
# -----------------------------------------------------------------------------

class LinkHealthTracker:
    """Tracks LDR debounce, grace period, and telemetry gaps."""

    def __init__(self, config: HILConfig | None = None) -> None:
        self.config = config or HILConfig()
        self.transmission_start_time: float | None = None
        self.last_transmission_state = False
        self.ldr_fault_count = 0
        self.vibration_active_count = 0
        self.last_packet_time: float | None = None
        self.is_link_fault = False
        self.is_vibrating = False

    def update(self, packet: AbyssLinkPacket) -> None:
        t = packet.timestamp

        # Detect transition to active transmission
        if packet.transmission and not self.last_transmission_state:
            self.transmission_start_time = t
        elif not packet.transmission:
            self.transmission_start_time = None
        self.last_transmission_state = packet.transmission

        # Check grace period after START_TRANSMISSION
        in_grace_period = False
        if packet.transmission and self.transmission_start_time is not None:
            if t - self.transmission_start_time < self.config.signal.grace_period_s:
                in_grace_period = True

        # Link fault condition: transmission == True AND ldr == 1 (after grace period)
        if packet.transmission and packet.ldr == 1 and not in_grace_period:
            self.ldr_fault_count += 1
        else:
            self.ldr_fault_count = 0

        self.is_link_fault = self.ldr_fault_count >= self.config.signal.ldr_debounce_packets

        # Vibration debounce
        if packet.vibration == 1:
            self.vibration_active_count += 1
        else:
            self.vibration_active_count = 0
        self.is_vibrating = self.vibration_active_count >= self.config.signal.vibration_debounce_packets

        self.last_packet_time = t

    def is_healthy(self) -> bool:
        return not self.is_link_fault


class AccelSynthesizer:
    """Synthesizes continuous 50 Hz MPU6050 accelerometer observations."""

    def __init__(self, seed: int = 42, config: HILConfig | None = None) -> None:
        self.config = config or HILConfig()
        self.seed = seed
        self.rng = np.random.RandomState(seed)
        self.current_t = 0.0

    def synthesize(
        self,
        start_t: float,
        end_t: float,
        *,
        vibration: int,
        packet_received: bool = True,
        environmental: bool = False,
        node_id: str = "abysslink_node_1",
    ) -> list[SensorObservation]:
        """Synthesize 50 Hz observations from start_t to end_t with continuous phase."""
        fs = self.config.pipeline.sampling_rate
        dt = 1.0 / fs
        n_samples = max(1, int(round((end_t - start_t) / dt)))

        timestamps = [start_t + i * dt for i in range(n_samples)]
        amplitude = (
            self.config.accel.disturbance_amplitude
            if vibration == 1
            else self.config.accel.baseline_amplitude
        )
        f0 = self.config.accel.frequency_hz
        noise_std = self.config.accel.noise_std

        observations: list[SensorObservation] = []
        for t in timestamps:
            # 1.0g gravity bias + sine wave vibration + noise
            sine_val = amplitude * math.sin(2.0 * math.pi * f0 * t)
            if environmental:
                sine_val += 0.55 * math.sin(2.0 * math.pi * 2.0 * t)

            noise = self.rng.normal(0.0, noise_std, size=3)
            ax = float(1.0 + sine_val + noise[0])
            ay = float(noise[1])
            az = float(noise[2])

            obs = SensorObservation(
                node_id=node_id,
                timestamp=float(t),
                acceleration=(ax, ay, az),
                position=(0.0, 0.0),
                packet_received=packet_received,
                source="hil_simulated_accel",
                metadata={
                    "data_kind": "HIL_SIMULATED_ACCEL",
                    "hardware": "AbyssLink_ESP32",
                    "synthetic_accel": True,
                    "vibration_flag": vibration,
                },
            )
            observations.append(obs)

        return observations


class DistanceToVessel:
    """Maps AbyssLink ultrasonic distance_cm to Subsea VesselObservation."""

    def __init__(self, config: HILConfig | None = None) -> None:
        self.config = config or HILConfig()
        self.history: deque[tuple[float, float]] = deque(maxlen=self.config.distance.smoothing_window)

    def map_packet(self, packet: AbyssLinkPacket, vessel_id: str = "hil_vessel_1") -> VesselObservation:
        t = packet.timestamp
        is_valid = packet.distance_valid and packet.distance_cm is not None and packet.distance_cm >= self.config.distance.min_valid_cm

        if not is_valid:
            return VesselObservation(
                vessel_id=vessel_id,
                timestamp=t,
                position=(999.0, 999.0),
                speed=0.0,
                heading=0.0,
                reported=False,
                position_uncertainty=1.0,
                metadata={
                    "data_kind": "HIL_SIMULATED_ACCEL",
                    "raw_distance_cm": packet.distance_cm,
                    "distance_valid": False,
                },
            )

        assert packet.distance_cm is not None
        dist_m = packet.distance_cm * self.config.distance.scale_factor
        self.history.append((t, dist_m))

        speed = 0.0
        heading = 0.0
        if len(self.history) >= 2:
            dt = self.history[-1][0] - self.history[0][0]
            if dt > 1e-4:
                dist_change = self.history[-1][1] - self.history[0][1]
                speed = abs(dist_change) / dt
                # heading 180 = approaching cable at (0,0), 0 = moving away
                heading = 180.0 if dist_change < 0 else 0.0

        return VesselObservation(
            vessel_id=vessel_id,
            timestamp=t,
            position=(float(dist_m), 0.0),
            speed=float(speed),
            heading=float(heading),
            reported=True,
            position_uncertainty=0.05,
            metadata={
                "data_kind": "HIL_SIMULATED_ACCEL",
                "raw_distance_cm": packet.distance_cm,
                "distance_valid": True,
            },
        )


# -----------------------------------------------------------------------------
# Schedule Injection
# -----------------------------------------------------------------------------

class ScheduleInjector:
    """Applies scheduled fault and evasion injections at designated timestamps."""

    def __init__(self, schedule_path: str | Path | None = None) -> None:
        self.schedule_path = Path(schedule_path) if schedule_path else None
        self.injections: list[dict[str, Any]] = []
        if self.schedule_path and self.schedule_path.is_file():
            data = json.loads(self.schedule_path.read_text(encoding="utf-8"))
            self.injections = data.get("injections", [])

    def apply(
        self,
        t: float,
        packet: AbyssLinkPacket,
        vessel: VesselObservation,
    ) -> tuple[AbyssLinkPacket, VesselObservation, bool]:
        """Apply active injections at time t. Returns (packet, vessel, environmental_event)."""
        modified_packet = packet
        modified_vessel = vessel
        environmental = False

        for inj in self.injections:
            t_start = float(inj.get("timestamp_s", 0.0))
            duration = float(inj.get("duration_s", 1.0))
            if not (t_start <= t <= t_start + duration):
                continue

            itype = inj.get("type")
            if itype == "vibration":
                val = int(inj.get("value", 1))
                modified_packet = AbyssLinkPacket(
                    type=modified_packet.type,
                    transmission=modified_packet.transmission,
                    ldr=modified_packet.ldr,
                    vibration=val,
                    distance_cm=modified_packet.distance_cm,
                    distance_valid=modified_packet.distance_valid,
                    laser=modified_packet.laser,
                    buzzer=modified_packet.buzzer,
                    alert="VIBRATION" if val == 1 else modified_packet.alert,
                    raw_line=modified_packet.raw_line,
                    timestamp=modified_packet.timestamp,
                )

            elif itype == "link_fault":
                modified_packet = AbyssLinkPacket(
                    type=modified_packet.type,
                    transmission=True,
                    ldr=1,
                    vibration=modified_packet.vibration,
                    distance_cm=modified_packet.distance_cm,
                    distance_valid=modified_packet.distance_valid,
                    laser="ON",
                    buzzer="ON",
                    alert="LASER_INTERRUPTION",
                    raw_line=modified_packet.raw_line,
                    timestamp=modified_packet.timestamp,
                )

            elif itype == "ais_spoof":
                offset_m = float(inj.get("offset_m", 50.0))
                new_pos = (modified_vessel.position[0] + offset_m, modified_vessel.position[1])
                modified_vessel = VesselObservation(
                    vessel_id=modified_vessel.vessel_id,
                    timestamp=modified_vessel.timestamp,
                    position=new_pos,
                    speed=modified_vessel.speed,
                    heading=modified_vessel.heading,
                    reported=modified_vessel.reported,
                    position_uncertainty=modified_vessel.position_uncertainty,
                    metadata=modified_vessel.metadata,
                )

            elif itype == "ais_timestamp":
                delta_s = float(inj.get("delta_s", 30.0))
                modified_vessel = VesselObservation(
                    vessel_id=modified_vessel.vessel_id,
                    timestamp=modified_vessel.timestamp + delta_s,
                    position=modified_vessel.position,
                    speed=modified_vessel.speed,
                    heading=modified_vessel.heading,
                    reported=modified_vessel.reported,
                    position_uncertainty=modified_vessel.position_uncertainty,
                    metadata=modified_vessel.metadata,
                )

            elif itype == "ais_suppress":
                modified_vessel = VesselObservation(
                    vessel_id=modified_vessel.vessel_id,
                    timestamp=modified_vessel.timestamp,
                    position=modified_vessel.position,
                    speed=0.0,
                    heading=0.0,
                    reported=False,
                    position_uncertainty=1.0,
                    metadata=modified_vessel.metadata,
                )

            elif itype == "environmental":
                environmental = True

        return modified_packet, modified_vessel, environmental


# -----------------------------------------------------------------------------
# Manifest & Pointer Writers
# -----------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


class HILManifest:
    """Generates and writes execution audit manifest for a HIL run."""

    @staticmethod
    def generate(
        run_dir: Path,
        *,
        seed: int,
        config: HILConfig,
        packet_count: int,
        malformed_count: int,
        decision_counts: dict[str, int],
        duration_s: float,
    ) -> dict[str, Any]:
        cfg_str = json.dumps(config.to_dict(), sort_keys=True)
        cfg_hash = hashlib.sha256(cfg_str.encode("utf-8")).hexdigest()

        raw_path = run_dir / "raw.jsonl"
        dec_path = run_dir / "decisions.jsonl"

        manifest_data = {
            "data_kind": "HIL_SIMULATED_ACCEL",
            "run_id": run_dir.name,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "seed": seed,
            "config_hash": cfg_hash,
            "raw_log_sha256": sha256_file(raw_path),
            "decisions_log_sha256": sha256_file(dec_path),
            "packet_count": packet_count,
            "malformed_count": malformed_count,
            "decision_counts": decision_counts,
            "duration_s": float(duration_s),
            "scientific_statement": (
                "HIL evaluation validates software-firmware communication and telemetry adaptation. "
                "Accelerometer data is synthesized from binary vibration flags and does not represent subsea acoustic physics."
            ),
        }
        return manifest_data

    @classmethod
    def write(cls, run_dir: Path, **kwargs: Any) -> Path:
        data = cls.generate(run_dir, **kwargs)
        out_p = run_dir / "manifest.json"
        out_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return out_p


def write_pointer(run_dir: Path, web_dir: Path | None = None) -> Path:
    """Writes/overwrites web/hil/latest.json pointer to the latest run directory."""
    if web_dir is None:
        # Default: locate web directory relative to repo root
        root = Path(__file__).resolve().parent.parent.parent
        target_web = root / "web" / "hil"
    else:
        target_web = Path(web_dir)

    target_web.mkdir(parents=True, exist_ok=True)
    pointer_file = target_web / "latest.json"

    data = {
        "run_id": run_dir.name,
        "run_dir": str(run_dir).replace("\\", "/"),
        "decisions_path": str(run_dir / "decisions.jsonl").replace("\\", "/"),
        "raw_path": str(run_dir / "raw.jsonl").replace("\\", "/"),
        "manifest_path": str(run_dir / "manifest.json").replace("\\", "/"),
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    pointer_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return pointer_file


# -----------------------------------------------------------------------------
# Main Orchestrator: HILBridge
# -----------------------------------------------------------------------------

class HILBridge:
    """Main HIL bridge orchestrating telemetry intake, synthesis, and Subsea pipeline execution."""

    def __init__(
        self,
        source: Any,
        output_dir: str | Path,
        config: HILConfig | None = None,
        schedule_path: str | Path | None = None,
        seed: int = 42,
    ) -> None:
        self.source = source
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or HILConfig()
        self.seed = seed

        self.health_tracker = LinkHealthTracker(self.config)
        self.accel_synth = AccelSynthesizer(seed=seed, config=self.config)
        self.dist_mapper = DistanceToVessel(config=self.config)
        self.injector = ScheduleInjector(schedule_path)

        self.raw_log_path = self.output_dir / "raw.jsonl"
        self.dec_log_path = self.output_dir / "decisions.jsonl"

        self.packet_count = 0
        self.malformed_count = 0
        self.decision_counts: dict[str, int] = {"T0": 0, "T1": 0, "T2": 0, "T3": 0, "TX": 0}

        # Rolling observation buffer for 256-sample window
        self.window: deque[SensorObservation] = deque(maxlen=self.config.pipeline.window_size)
        self.last_packet_t: float | None = None

        # Warm up buffer with quiet baseline observations so window starts fully populated
        self._warmup_buffer()

    def _warmup_buffer(self) -> None:
        fs = self.config.pipeline.sampling_rate
        dt = 1.0 / fs
        w_size = self.config.pipeline.window_size
        t_start = -w_size * dt
        warmup_obs = self.accel_synth.synthesize(
            t_start,
            0.0,
            vibration=0,
            packet_received=True,
            environmental=False,
        )
        for obs in warmup_obs:
            self.window.append(obs)

    def process_packet(self, packet: AbyssLinkPacket) -> DecisionResult | None:
        """Process a single AbyssLink packet through synthesis and pipeline."""
        self.packet_count += 1

        # 1. Log raw packet
        raw_record = {
            "timestamp": packet.timestamp,
            "sequence": self.packet_count,
            "raw_line": packet.raw_line,
            "type": packet.type,
            "transmission": packet.transmission,
            "ldr": packet.ldr,
            "vibration": packet.vibration,
            "distance_cm": packet.distance_cm,
            "distance_valid": packet.distance_valid,
            "laser": packet.laser,
            "buzzer": packet.buzzer,
            "alert": packet.alert,
            "data_kind": "HIL_SIMULATED_ACCEL",
        }
        with open(self.raw_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(raw_record) + "\n")

        # Skip ACK packets from pipeline
        if packet.type == "ack":
            return None

        # 2. Map distance to vessel observation
        vessel_obs = self.dist_mapper.map_packet(packet)

        # 3. Apply schedule injections
        packet, vessel_obs, environmental = self.injector.apply(packet.timestamp, packet, vessel_obs)

        # 4. Update link health tracker
        self.health_tracker.update(packet)
        is_healthy = self.health_tracker.is_healthy()

        # 5. Determine synthesis time window
        if self.last_packet_t is None:
            t_prev = packet.timestamp - 0.3
        else:
            t_prev = self.last_packet_t
        self.last_packet_t = packet.timestamp

        # 6. Synthesize 50 Hz acceleration observations
        new_obs = self.accel_synth.synthesize(
            t_prev,
            packet.timestamp,
            vibration=packet.vibration,
            packet_received=is_healthy,
            environmental=environmental,
        )
        for obs in new_obs:
            self.window.append(obs)

        # 7. Run real Subsea pipeline
        result: DecisionResult = run_pipeline(
            observations=tuple(self.window),
            vessel=vessel_obs,
            sampling_rate=self.config.pipeline.sampling_rate,
            baseline_rms=self.config.pipeline.baseline_rms,
            disturbance_rms=self.config.pipeline.disturbance_rms,
            interaction_radius=self.config.pipeline.interaction_radius,
            temporal_tolerance=self.config.pipeline.temporal_tolerance,
            expected_interval=self.config.pipeline.expected_interval,
            packet_timeout=self.config.signal.packet_timeout_s,
            environmental_event=environmental,
            now=packet.timestamp,
        )

        dec_str = result.decision.value
        self.decision_counts[dec_str] = self.decision_counts.get(dec_str, 0) + 1

        # 8. Record decision record
        dec_record = {
            "timestamp": packet.timestamp,
            "sequence": self.packet_count,
            "decision": dec_str,
            "physical_confidence": round(result.physical_confidence, 4),
            "association_confidence": round(result.association_confidence, 4),
            "reliability": round(result.reliability, 4),
            "uncertainty": round(result.uncertainty, 4),
            "hypothesis_scores": {k: round(v, 4) for k, v in result.hypothesis_scores.items()},
            "rationale": result.rationale,
            "vessel_distance_m": round(vessel_obs.position[0], 2) if vessel_obs.reported else None,
            "vessel_speed": round(vessel_obs.speed, 2) if vessel_obs.reported else None,
            "vibration_flag": packet.vibration,
            "ldr_flag": packet.ldr,
            "transmission": packet.transmission,
            "alert": packet.alert,
            "data_kind": "HIL_SIMULATED_ACCEL",
        }
        with open(self.dec_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(dec_record) + "\n")

        return result

    def run(self, max_packets: int | None = None) -> dict[str, Any]:
        """Execute bridge run over the configured source until completion."""
        start_time = datetime.datetime.now(datetime.timezone.utc)
        count = 0

        # Handle iterator or line-based sources
        if hasattr(self.source, "__iter__") and not hasattr(self.source, "read_line"):
            for pkt in self.source:
                if max_packets is not None and count >= max_packets:
                    break
                self.process_packet(pkt)
                count += 1
        else:
            # Serial or line-based source
            while True:
                if max_packets is not None and count >= max_packets:
                    break
                if hasattr(self.source, "read_packet"):
                    pkt = self.source.read_packet()
                elif hasattr(self.source, "read_line"):
                    line = self.source.read_line()
                    if line is None:
                        break
                    pkt = parse_abysslink_line(line)
                    if pkt is None:
                        self.malformed_count += 1
                        continue
                else:
                    break

                if pkt is None:
                    break

                self.process_packet(pkt)
                count += 1

        end_time = datetime.datetime.now(datetime.timezone.utc)
        duration_s = (end_time - start_time).total_seconds()

        # Write manifest
        manifest = HILManifest.write(
            self.output_dir,
            seed=self.seed,
            config=self.config,
            packet_count=self.packet_count,
            malformed_count=self.malformed_count,
            decision_counts=self.decision_counts,
            duration_s=duration_s,
        )

        # Write web pointer
        write_pointer(self.output_dir)

        return json.loads(manifest.read_text(encoding="utf-8"))
