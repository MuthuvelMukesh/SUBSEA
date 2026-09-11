from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class RawPacketRecorder:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, packet: dict[str, Any], *, transport: str, received_timestamp: float, sequence: int | None = None) -> None:
        if isinstance(received_timestamp, bool) or not transport or not math.isfinite(received_timestamp) or received_timestamp < 0:
            raise ValueError("transport and non-negative received_timestamp are required")
        record = {"received_timestamp": received_timestamp, "transport": transport, "sequence": sequence, "packet": dict(packet)}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
