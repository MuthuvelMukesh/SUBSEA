import json
import math

import pytest

from subsea.acquisition import parse_packet
from subsea.recording import RawPacketRecorder
from subsea.transports import receive_http, receive_mqtt, receive_serial


PACKET = {"node_id": "n1", "timestamp": 1.0, "ax": 1.0, "ay": 0.0, "az": 0.0, "gx": 0.0, "gy": 0.0, "gz": 0.0}


def test_transports_share_packet_contract():
    payload = json.dumps(PACKET)
    assert receive_mqtt(payload).node_id == "n1"
    assert receive_http(PACKET).timestamp == 1.0
    assert receive_serial(payload.encode()).acceleration == (1.0, 0.0, 0.0)


def test_raw_recorder_appends_without_overwriting(tmp_path):
    path = tmp_path / "raw.jsonl"
    recorder = RawPacketRecorder(path)
    recorder.append(PACKET, transport="mqtt", received_timestamp=2.0, sequence=4)
    recorder.append(PACKET, transport="serial", received_timestamp=3.0, sequence=5)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["transport"] == "mqtt"
    assert json.loads(lines[1])["sequence"] == 5
    with pytest.raises(ValueError):
        recorder.append(PACKET, transport="mqtt", received_timestamp=math.nan)
