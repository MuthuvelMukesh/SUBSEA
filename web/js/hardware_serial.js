/**
 * Web Serial API Controller for AbyssLink ESP32 Hardware
 * Handles USB serial port selection, 115200 baud streaming, line buffering,
 * command transmission, and graceful error/disconnect recovery.
 */

export function isSerialSupported() {
  return typeof navigator !== "undefined" && "serial" in navigator;
}

export class HardwareSerialController {
  constructor(callbacks = {}) {
    this.onPacket = callbacks.onPacket || (() => {});
    this.onAck = callbacks.onAck || (() => {});
    this.onStateChange = callbacks.onStateChange || (() => {});
    this.onLog = callbacks.onLog || (() => {});
    this.onRawLine = callbacks.onRawLine || (() => {});

    this.port = null;
    this.reader = null;
    this.writer = null;
    this.state = "DISCONNECTED"; // DISCONNECTED, CONNECTING, CONNECTED, ERROR
    this.keepReading = false;

    this.stats = {
      receivedCount: 0,
      malformedCount: 0,
      lastTimestamp: null,
      updateRateHz: 0,
    };

    this._rateWindow = [];
    this._disconnectHandler = this._handleUsbDisconnect.bind(this);
  }

  getState() {
    return this.state;
  }

  getStats() {
    return { ...this.stats };
  }

  async connect(options = {}) {
    if (!isSerialSupported()) {
      const err = new Error("Web Serial API is not supported in this browser. Please use Chrome or Edge.");
      this._setState("ERROR", err.message);
      this.onLog("danger", err.message);
      throw err;
    }

    if (this.state === "CONNECTED" || this.state === "CONNECTING") {
      this.onLog("warning", "Serial connection is already active or connecting.");
      return;
    }

    this._setState("CONNECTING", "Requesting USB serial port from user...");
    this.onLog("info", "Requesting serial port selection...");

    try {
      this.port = await navigator.serial.requestPort();

      const baudRate = options.baudRate || 115200;
      this._setState("CONNECTING", `Opening port at ${baudRate} baud...`);
      await this.port.open({
        baudRate: baudRate,
        dataBits: 8,
        stopBits: 1,
        parity: "none",
        bufferSize: 8192,
        flowControl: "none",
      });

      // Release ESP32 from bootloader / reset via DTR/RTS signals
      if (this.port.setSignals) {
        try {
          await this.port.setSignals({ dataTerminalReady: false, requestToSend: false });
        } catch (sigErr) {
          console.warn("Unable to set DTR/RTS signals:", sigErr);
        }
      }

      this.keepReading = true;
      this._setState("CONNECTED", `Connected at ${baudRate} baud`);
      this.onLog("safe", `ESP32 connected successfully on USB serial (${baudRate} baud).`);

      // Listen for physical device unplugging
      navigator.serial.addEventListener("disconnect", this._disconnectHandler);

      // Launch continuous read loop in background
      this._readLoop().catch((err) => {
        if (this.keepReading) {
          console.error("Unexpected read loop termination:", err);
          this._handleUnexpectedDisconnect(err.message);
        }
      });
    } catch (err) {
      if (err.name === "NotFoundError") {
        // User dismissed the port selection prompt
        this._setState("DISCONNECTED", "Connection cancelled by user");
        this.onLog("info", "Port selection was cancelled by user.");
      } else {
        console.error("Serial connection error:", err);
        let detail = err.message;
        if (err.name === "NetworkError" || detail.toLowerCase().includes("failed to open")) {
          detail = "Port locked by another program (e.g. Arduino IDE Serial Monitor). Close other monitors and retry.";
        }
        this._setState("ERROR", detail);
        this.onLog("danger", `Connection failed: ${detail}`);
        this.port = null;
        throw err;
      }
    }
  }

  async disconnect() {
    this.onLog("info", "Disconnecting ESP32 serial link...");
    await this._teardownCleanly();
    this._setState("DISCONNECTED", "Disconnected");
    this.onLog("info", "ESP32 disconnected and serial resources released.");
  }

  async sendCommand(commandName) {
    if (!this.port || !this.port.writable || this.state !== "CONNECTED") {
      const err = new Error(`Cannot send ${commandName}: Serial port is not connected or writable.`);
      this.onLog("danger", err.message);
      throw err;
    }

    try {
      const encoder = new TextEncoder();
      const data = encoder.encode(commandName.trim() + "\n");

      this.writer = this.port.writable.getWriter();
      await this.writer.write(data);
      this.writer.releaseLock();
      this.writer = null;

      this.onLog("info", `Command transmitted to ESP32: ${commandName}`);
    } catch (err) {
      if (this.writer) {
        try { this.writer.releaseLock(); } catch (_) {}
        this.writer = null;
      }
      this.onLog("danger", `Failed to send command ${commandName}: ${err.message}`);
      throw err;
    }
  }

  async _readLoop() {
    let textBuffer = "";
    const textDecoder = new TextDecoder();

    while (this.port && this.port.readable && this.keepReading) {
      try {
        this.reader = this.port.readable.getReader();

        while (this.keepReading) {
          const { value, done } = await this.reader.read();
          if (done) {
            break;
          }

          if (value) {
            const chunk = textDecoder.decode(value, { stream: true });
            textBuffer += chunk;

            // Process all newline-terminated lines
            let newlineIdx;
            while ((newlineIdx = textBuffer.indexOf("\n")) >= 0) {
              const rawLine = textBuffer.slice(0, newlineIdx).trim();
              textBuffer = textBuffer.slice(newlineIdx + 1);

              if (rawLine.length > 0) {
                this._processLine(rawLine);
              }
            }
          }
        }
      } catch (err) {
        if (this.keepReading) {
          console.error("Serial stream read error:", err);
          this.onLog("danger", `Serial read error: ${err.message}`);
          this._handleUnexpectedDisconnect("Stream Error: " + err.message);
        }
        break;
      } finally {
        if (this.reader) {
          try { this.reader.releaseLock(); } catch (_) {}
          this.reader = null;
        }
      }
    }
  }

  _processLine(line) {
    const rawClean = line.replace(/[\r\n]/g, "").trim();
    if (!rawClean) return;

    this.onRawLine(rawClean);

    // Track packet rate and timestamp
    const now = Date.now();
    this.stats.lastTimestamp = now;
    this._rateWindow.push(now);
    // Keep rate window over last 2 seconds
    this._rateWindow = this._rateWindow.filter((t) => now - t <= 2000);
    this.stats.updateRateHz = this._rateWindow.length > 1
      ? Math.round((this._rateWindow.length / 2) * 10) / 10
      : 0;

    // Check if line is valid JSON
    let packet;
    try {
      packet = JSON.parse(rawClean);
    } catch (_) {
      this.stats.malformedCount++;
      this.onLog("warning", `Non-JSON or malformed serial frame: ${rawClean.slice(0, 60)}`);
      return;
    }

    if (!packet || typeof packet !== "object") {
      this.stats.malformedCount++;
      return;
    }

    this.stats.receivedCount++;

    if (packet.type === "ack") {
      this.onAck(packet);
    } else {
      this.onPacket(packet, rawClean);
    }
  }

  _handleUsbDisconnect(event) {
    if (this.port && event.target === this.port) {
      this.onLog("danger", "ESP32 USB cable physically disconnected from computer.");
      this._handleUnexpectedDisconnect("DEVICE_UNPLUGGED");
    }
  }

  async _handleUnexpectedDisconnect(reason) {
    await this._teardownCleanly();
    this._setState("ERROR", `Device disconnected (${reason})`);
  }

  async _teardownCleanly() {
    this.keepReading = false;

    navigator.serial.removeEventListener("disconnect", this._disconnectHandler);

    if (this.reader) {
      try { await this.reader.cancel(); } catch (_) {}
      try { this.reader.releaseLock(); } catch (_) {}
      this.reader = null;
    }

    if (this.writer) {
      try { this.writer.releaseLock(); } catch (_) {}
      this.writer = null;
    }

    if (this.port) {
      try { await this.port.close(); } catch (e) {
        console.warn("Error closing port during teardown:", e);
      }
      this.port = null;
    }
  }

  _setState(state, detail = "") {
    this.state = state;
    this.onStateChange(state, detail);
  }
}
