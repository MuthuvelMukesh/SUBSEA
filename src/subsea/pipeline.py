from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .association import associate
from .decision import decide
from .features import physical_confidence, spectral_features
from .fusion import score_hypotheses, weighted_fusion
from .geometry import distance_to_polyline
from .health import estimate_health
from .models import DecisionResult, Evidence, Hypothesis, SensorObservation, VesselObservation


def run_pipeline(
    observations: Sequence[SensorObservation],
    vessel: VesselObservation | None,
    *,
    sampling_rate: float = 50.0,
    baseline_rms: float = 1.0,
    disturbance_rms: float = 1.8,
    interaction_radius: float = 10.0,
    temporal_tolerance: float = 5.0,
    expected_interval: float = 0.02,
    packet_timeout: float = 1.0,
    environmental_event: bool = False,
    now: float | None = None,
    cable_geometry: tuple[tuple[float, float], ...] | None = None,
) -> DecisionResult:
    if not observations:
        raise ValueError("at least one observation is required")
    ordered = tuple(sorted(observations, key=lambda item: item.timestamp))
    if any(not np.isfinite(item.timestamp) or not np.all(np.isfinite(item.acceleration)) for item in ordered):
        raise ValueError("observations must contain finite timestamps and acceleration values")
    if vessel is not None and (not np.isfinite(vessel.timestamp) or not np.all(np.isfinite(vessel.position)) or not np.isfinite(vessel.speed) or not np.isfinite(vessel.heading) or vessel.position_uncertainty < 0):
        raise ValueError("vessel observation contains invalid numeric values")
    usable = tuple(item for item in ordered if item.packet_received)
    health = estimate_health(ordered, expected_interval=expected_interval, packet_timeout=packet_timeout, now=now)
    features = spectral_features([item.acceleration for item in usable], sampling_rate) if usable else {}
    cp = physical_confidence(features, baseline_rms=baseline_rms, disturbance_rms=disturbance_rms) if usable else 0.0
    evidence = [Evidence("physical disturbance", cp, 1.0, health.health, health.availability, Hypothesis.VESSEL_DISTURBANCE, "MPU6050 acceleration features")]
    counter: list[str] = []
    missing: list[str] = []
    if vessel is None or not vessel.reported:
        association_confidence = 0.0
        association_components = {"spatial": 0.0, "temporal": 0.0, "behaviour": 0.0}
        missing.append("reported vessel corroboration")
        counter.append("no AIS-like corroboration")
    else:
        if cable_geometry is not None:
            distance = distance_to_polyline(vessel.position, cable_geometry)
        else:
            distance = float(np.linalg.norm(np.asarray(vessel.position) - np.asarray(ordered[-1].position)))
        association = associate(vessel, ordered[-1].timestamp, distance, interaction_radius=interaction_radius, temporal_tolerance=temporal_tolerance)
        association_confidence = association.confidence
        association_components = {"spatial": association.spatial_confidence, "temporal": association.temporal_confidence, "behaviour": association.behaviour_confidence}
        evidence.extend([
            Evidence("spatial association", association.spatial_confidence, 1.0, health.health, health.availability, Hypothesis.VESSEL_DISTURBANCE, "distance to cable path origin"),
            Evidence("temporal association", association.temporal_confidence, 1.0, health.health, health.availability, Hypothesis.VESSEL_DISTURBANCE, "timestamp alignment"),
            Evidence("vessel behaviour", association.behaviour_confidence, 1.0, health.health, health.availability, Hypothesis.VESSEL_DISTURBANCE, "proximity and motion"),
        ])
        counter.extend(association.explanation)
    fused, reliability = weighted_fusion(evidence)
    counter_penalty = min(0.6, 0.15 * len(counter))
    scores = score_hypotheses(cp, association_confidence, reliability, environmental=0.7 if environmental_event else 0.0, counter_evidence=counter_penalty)
    missing_component = min(1.0, len(missing) / 2)
    health_component = 1.0 - health.health
    conflict_component = float(np.std(list(scores.values())))
    association_component = 1.0 - association_confidence
    uncertainty_components = {"missing": missing_component, "health": health_component, "conflict": conflict_component, "association": association_component}
    uncertainty = float(np.clip(0.25 * sum(uncertainty_components.values()), 0, 1))
    scores_without_counter = score_hypotheses(cp, association_confidence, reliability, environmental=0.7 if environmental_event else 0.0, counter_evidence=0.0)
    uncertainty_without_counter = float(np.clip(0.25 * (missing_component + health_component + float(np.std(list(scores_without_counter.values()))) + association_component), 0, 1))
    decision = decide(physical_confidence=cp, association_confidence=association_confidence, reliability=reliability, uncertainty=uncertainty)
    rationale = (f"CP={cp:.3f}", f"CA={association_confidence:.3f}", f"reliability={reliability:.3f}", f"U={uncertainty:.3f}")
    return DecisionResult(decision, cp, association_confidence, reliability, uncertainty, scores, tuple(item.name for item in evidence), tuple(counter), tuple(missing), rationale, {"features": features, "health": health.__dict__, "fused_score": fused, "counter_penalty": counter_penalty, "association_components": association_components, "uncertainty_components": uncertainty_components, "uncertainty_without_counter_evidence": uncertainty_without_counter, "environmental_event": environmental_event, "cable_geometry": cable_geometry})
