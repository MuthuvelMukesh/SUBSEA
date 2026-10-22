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
    this.onBaudMismatch = callbacks.onBaudMismatch || (() => {});

    this.port = null;
    this.reader = null;
    this.writer = null;
    this.state = "DISCONNECTED"; // DISCONNECTED, CONNECTING, CONNECTED, ERROR
    this.keepReading = false;
    this.currentBaudRate = 115200;

    this._consecutiveGarbageFrames = 0;
    this._lastGarbageWarnTime = 0;

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
      this.currentBaudRate = baudRate;
      this._consecutiveGarbageFrames = 0;
      this._lastGarbageWarnTime = 0;

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

  async resetEsp() {
    if (!this.port || this.state !== "CONNECTED") {
      this.onLog("warning", "Cannot reset ESP32: Serial port is not connected.");
      return false;
    }
    try {
      this.onLog("warning", "Sending hardware reboot pulse (RTS) to ESP32...");
      if (this.port.setSignals) {
        await this.port.setSignals({ dataTerminalReady: false, requestToSend: true });
        await new Promise((r) => setTimeout(r, 120));
        await this.port.setSignals({ dataTerminalReady: false, requestToSend: false });
        this.onLog("safe", "ESP32 hardware rebooted via RTS signal.");
        return true;
      } else {
        this.onLog("warning", "Hardware signal control not supported by current USB-UART driver.");
        return false;
      }
    } catch (err) {
      this.onLog("warning", `Hardware reset signal failed: ${err.message}`);
      return false;
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

    // Check if frame contains replacement character \ufffd (indicates UART framing / baud error)
    const hasReplacementChars = rawClean.includes("\ufffd") || /[\x00-\x08\x0B\x0C\x0E-\x1F]/.test(rawClean);

    // 1. Try parsing JSON directly
    let packet = null;
    try {
      packet = JSON.parse(rawClean);
    } catch (_) {
      // 2. Resilient JSON extraction: look for valid substring between first '{' and last '}'
      const firstBrace = rawClean.indexOf("{");
      const lastBrace = rawClean.lastIndexOf("}");
      if (firstBrace !== -1 && lastBrace > firstBrace) {
        try {
          const candidate = rawClean.substring(firstBrace, lastBrace + 1);
          packet = JSON.parse(candidate);
        } catch (_) {}
      }
    }

    if (packet && typeof packet === "object") {
      this._consecutiveGarbageFrames = 0;
      this.stats.receivedCount++;
      if (packet.type === "ack") {
        this.onAck(packet);
      } else {
        this.onPacket(packet, rawClean);
      }
      return;
    }

    // If frame is NOT valid JSON:
    this.stats.malformedCount++;

    if (hasReplacementChars) {
      this._consecutiveGarbageFrames++;
      const suggestedBaud = this.currentBaudRate === 115200 ? 9600 : 115200;

      // Throttle warning log to once every 2.5 seconds to avoid flooding the log
      if (now - this._lastGarbageWarnTime > 2500) {
        this._lastGarbageWarnTime = now;
        this.onLog(
          "danger",
          `⚠️ Baud Rate Mismatch / Framing Error: Port received corrupt bytes (\\ufffd). Connected at ${this.currentBaudRate} baud. If your device uses ${suggestedBaud} baud, switch baud rate and reconnect, or verify Serial.begin(${this.currentBaudRate}) in your Arduino sketch.`
        );
      }

      this.onBaudMismatch({
        currentBaud: this.currentBaudRate,
        suggestedBaud: suggestedBaud,
        sample: rawClean.slice(0, 40),
      });
      return;
    }

    // Normal non-JSON string print (e.g. bootloader logs, user debug prints)
    this._consecutiveGarbageFrames = 0;
    this.onLog("info", `ESP32 Print: ${rawClean.slice(0, 80)}`);
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
