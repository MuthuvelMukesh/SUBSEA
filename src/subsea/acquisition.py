from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, validator

from .models import SensorObservation


class Mpu6050Packet(BaseModel):
    node_id: str = Field(min_length=1)
    timestamp: datetime | float
    ax: float
    ay: float
    az: float
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0

    class Config:
        extra = "forbid"

    @validator("ax", "ay", "az", "gx", "gy", "gz")
    @classmethod
    def finite_value(cls, value: float) -> float:
        if not float("-inf") < value < float("inf"):
            raise ValueError("sensor values must be finite")
        return value

    def to_observation(self, position: tuple[float, float] = (0.0, 0.0)) -> SensorObservation:
        timestamp = self.timestamp.timestamp() if isinstance(self.timestamp, datetime) else float(self.timestamp)
        return SensorObservation(self.node_id, timestamp, (self.ax, self.ay, self.az), position, source="mpu6050")


def parse_packet(payload: str | bytes | dict[str, object]) -> SensorObservation:
    if isinstance(payload, (str, bytes)):
        packet = Mpu6050Packet.parse_raw(payload)
    else:
        packet = Mpu6050Packet.parse_obj(payload)
    return packet.to_observation()
