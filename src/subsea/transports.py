from __future__ import annotations

from typing import Any

from .acquisition import parse_packet
from .models import SensorObservation


def receive_mqtt(payload: str | bytes | dict[str, Any]) -> SensorObservation:
    return parse_packet(payload)


def receive_http(payload: dict[str, Any] | str | bytes) -> SensorObservation:
    return parse_packet(payload)


def receive_serial(line: str | bytes) -> SensorObservation:
    return parse_packet(line)
