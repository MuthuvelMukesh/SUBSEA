/**
 * Hardware Telemetry Adapter & Pipeline Bridge for AbyssLink ESP32
 * Validates hardware packets, manages raw telemetry buffering/JSONL export,
 * tracks state transitions, and routes telemetry to the Python pipeline backend.
 */

export const BENCHTOP_DISCLAIMERS = {
  ultrasonic: "HC-SR04 ultrasonic sensor operates in air for benchtop proximity testing. It is not an underwater acoustic transducer.",
  vibration: "MPU6050 vibration flag is a binary digital trigger. The pipeline synthesizes continuous 50 Hz acceleration to test logic, not subsea physics.",
};

export class TelemetryBuffer {
  constructor(maxRecords = 5000) {
    this.maxRecords = maxRecords;
    this.rawPackets = [];
    this.processedDecisions = [];
    this.events = [];
    this.maxEvents = 50;
  }

  addRawPacket(packet, rawLine = "") {
    const entry = {
      timestamp: Date.now() / 1000.0,
      sequence: this.rawPackets.length + 1,
      packet: { ...packet },
      raw_line: rawLine,
      data_kind: "HIL_SIMULATED_ACCEL",
    };
    this.rawPackets.push(entry);
    if (this.rawPackets.length > this.maxRecords) {
      this.rawPackets.shift();
    }
    return entry;
  }

  addProcessedDecision(decisionRecord) {
    this.processedDecisions.push(decisionRecord);
    if (this.processedDecisions.length > this.maxRecords) {
      this.processedDecisions.shift();
    }
  }

  addEvent(category, message, level = "info") {
    const d = new Date();
    const timeStr = d.toTimeString().split(" ")[0] + "." + Math.floor(d.getMilliseconds() / 100);
    const event = {
      timestamp: timeStr,
      category,
      message,
      level, // 'safe', 'warning', 'danger', 'info'
    };
    this.events.unshift(event);
    if (this.events.length > this.maxEvents) {
      this.events.pop();
    }
    return event;
  }

  clear() {
    this.rawPackets = [];
    this.processedDecisions = [];
    this.events = [];
  }

  exportRawJSONL(filename = "abysslink_raw_telemetry.jsonl") {
    if (this.rawPackets.length === 0) return false;
    const lines = this.rawPackets.map((r) => JSON.stringify(r.packet)).join("\n");
    const blob = new Blob([lines + "\n"], { type: "application/x-ndjson" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return true;
  }
}

/**
 * Validates and normalizes an AbyssLink sensor packet according to the firmware contract.
 * Returns null if packet is invalid or missing required telemetry fields.
 */
export function validateSensorPacket(raw) {
  if (!raw || typeof raw !== "object") return null;

  const isSensor = raw.type === "sensor" || (raw.type === undefined && ("transmission" in raw || "ldr" in raw));
  if (!isSensor) return null;

  // Validate fields without inventing fabricated metrics
  const transmission = Boolean(raw.transmission);
  const ldr = raw.ldr !== undefined ? Number(raw.ldr) : null;
  const vibration = raw.vibration !== undefined ? Number(raw.vibration) : null;

  let distance_cm = null;
  let distance_valid = false;
  if (raw.distance_cm !== undefined && raw.distance_cm !== null) {
    const parsedDist = parseFloat(raw.distance_cm);
    if (!isNaN(parsedDist) && parsedDist >= 2.0) {
      distance_cm = parsedDist;
      distance_valid = Boolean(raw.distance_valid !== undefined ? raw.distance_valid : true);
    }
  }

  const laser = String(raw.laser || (transmission ? "ON" : "OFF")).toUpperCase();
  const buzzer = String(raw.buzzer || "OFF").toUpperCase();
  const alert = String(raw.alert || "SAFE").toUpperCase();

  return {
    type: "sensor",
    transmission,
    ldr: isNaN(ldr) ? null : ldr,
    vibration: isNaN(vibration) ? null : vibration,
    distance_cm,
    distance_valid,
    laser,
    buzzer,
    alert,
    data_kind: "HIL_SIMULATED_ACCEL",
  };
}

/**
 * Validates an acknowledgement packet from ESP32.
 */
export function validateAckPacket(raw) {
  if (!raw || typeof raw !== "object" || raw.type !== "ack") return null;
  return {
    type: "ack",
    command: String(raw.command || ""),
    success: Boolean(raw.success),
    transmission: Boolean(raw.transmission),
  };
}

/**
 * Communicates with the local Python Subsea pipeline bridge if available.
 */
export class PipelineBridgeClient {
  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
    this.isOnline = null;
    this.lastCheck = 0;
  }

  async checkHealth() {
    const now = Date.now();
    if (this.isOnline !== null && now - this.lastCheck < 5000) {
      return this.isOnline;
    }

    try {
      const resp = await fetch("api/status.json");
      if (resp.ok) {
        const data = await resp.json();
        this.isOnline = data.mode === "live_pipeline";
      } else {
        this.isOnline = false;
      }
    } catch (_) {
      this.isOnline = false;
    }
    this.lastCheck = now;
    return this.isOnline;
  }

  async processPacket(packet) {
    const healthy = await this.checkHealth();
    if (!healthy) {
      return null;
    }

    try {
      const resp = await fetch(`${this.baseUrl}/api/hil/process_packet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(packet),
      });

      if (!resp.ok) return null;
      return await resp.json();
    } catch (e) {
      console.warn("Pipeline bridge process error:", e);
      return null;
    }
  }

  async resetSession() {
    try {
      const resp = await fetch(`${this.baseUrl}/api/hil/reset`, { method: "POST" });
      if (resp.ok) return await resp.json();
    } catch (_) {}
    return null;
  }
}
