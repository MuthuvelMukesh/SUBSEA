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
    noise_level: float = 0.03
    n_nodes: int = 1
    position_uncertainty_level: float = 0.0
    high_uncertainty: bool = False
    spatial_manipulation: bool = False


@dataclass(frozen=True)
class MultiNodeResult:
    """Aggregated result from multiple sensor nodes along a cable."""
    node_results: tuple[DecisionResult, ...]
    fused_physical_confidence: float
    fused_uncertainty: float
    node_ids: tuple[str, ...]
    cable_positions: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class MultiVesselResult:
    """Result evaluating multiple candidate vessels."""
    vessel_results: tuple[tuple[str, DecisionResult], ...]
    selected_vessel_id: str | None
    selected_decision: DecisionResult
    competing_associations: dict[str, float]
