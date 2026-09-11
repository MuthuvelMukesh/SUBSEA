from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DecisionState(StrEnum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    TX = "TX"


class Hypothesis(StrEnum):
    VESSEL_DISTURBANCE = "vessel_associated_disturbance"
    ENVIRONMENTAL = "environmental_disturbance"
    MECHANICAL = "non_vessel_mechanical_disturbance"
    SENSOR_FAULT = "sensor_system_fault"


@dataclass(frozen=True)
class SensorObservation:
    node_id: str
    timestamp: float
    acceleration: tuple[float, ...]
    position: tuple[float, float]
    packet_received: bool = True
    source: str = "simulation"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VesselObservation:
    vessel_id: str
    timestamp: float
    position: tuple[float, float]
    speed: float
    heading: float
    reported: bool = True
    position_uncertainty: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SensorHealth:
    node_id: str
    health: float
    availability: float
    stale: bool
    constant_value: bool
    communication_ok: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Association:
    spatial_confidence: float
    temporal_confidence: float
    behaviour_confidence: float
    distance: float
    time_offset: float
    explanation: tuple[str, ...] = ()

    @property
    def confidence(self) -> float:
        return (self.spatial_confidence + self.temporal_confidence + self.behaviour_confidence) / 3.0


@dataclass(frozen=True)
class Evidence:
    name: str
    value: float
    weight: float
    health: float
    availability: float
    supports: Hypothesis | None
    explanation: str


@dataclass(frozen=True)
class DecisionResult:
    decision: DecisionState
    physical_confidence: float
    association_confidence: float
    reliability: float
    uncertainty: float
    hypothesis_scores: dict[str, float]
    positive_evidence: tuple[str, ...]
    counter_evidence: tuple[str, ...]
    missing_corroboration: tuple[str, ...]
    rationale: tuple[str, ...]
    audit: dict[str, Any]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    seed: int
    vessel_present: bool
    disturbance_present: bool
    environmental_event: bool = False
    sensor_failure: bool = False
    packet_loss: float = 0.0
    spoofing: bool = False
    timestamp_manipulation: bool = False
    mechanical_event: bool = False
    communication_failure: bool = False
    noise_stress: bool = False
    spatial_mismatch: bool = False
    temporal_mismatch: bool = False
    conflicting_evidence: bool = False
    counter_evidence: bool = False
    absence_corroboration: bool = False
    multiple_targets: bool = False
