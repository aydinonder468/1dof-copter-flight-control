"""
tcp_telemetry_client.py - TCP client for receiving real-time JSON telemetry.

Designed for future integration with MATLAB (or any source) that sends
newline-delimited JSON packets over TCP.

Usage (future)::

    client = TcpTelemetryClient(host="127.0.0.1", port=5005)
    client.new_data.connect(flight_state.update)
    client.start()

Protocol
--------
Each line received on the socket is a complete JSON object terminated by '\\n'.
The keys map directly to FlightData fields; unknown keys are silently ignored.
"""

from __future__ import annotations

import json
import socket
import time

from PySide6.QtCore import QThread, Signal

from flight_state import FlightData


# Map from MATLAB JSON key names → FlightData field names
_KEY_MAP: dict[str, str] = {
    "roll":     "roll",
    "pitch":    "pitch",
    "yaw":      "heading",        # MATLAB sends "yaw", PFD uses "heading"
    "heading":  "heading",
    "airspeed": "airspeed",
    "altitude": "altitude",
    "vertical_speed": "vertical_speed",
    "throttle": "throttle",
    "ap1":   "ap1_active",
    "ap2":   "ap2_active",
    "athr":  "autothrottle_active",
    "spd":   "speed_mode_active",
    "hdg":   "heading_mode_active",
    "lnav":  "lnav_active",
    "appr":  "appr_active",
    "alt":   "alt_hold_active",
    "vs":    "vs_active",
    # ── New dashboard fields ───────────────────────────────────────────
    "ground_speed":     "ground_speed",
    "pitot_airspeed":   "pitot_airspeed",
    "link_quality":     "link_quality",
    "interference":     "interference",
    "signal_strength":  "signal_strength",
    "band":             "comm_band",
    "flight_mode":      "flight_mode",
    "armed":            "armed",
    "ground_link":      "ground_link",
    "telemetry_status": "telemetry_status",
    "autopilot_status": "autopilot_status",
    # ── Battery ────────────────────────────────────────────────────────
    "battery_percent":  "battery_percent",
    "battery_voltage":  "battery_voltage",
}


class TcpTelemetryClient(QThread):
    """Connects to a TCP server and converts JSON packets into FlightData.

    Parameters
    ----------
    host : str
        IP address or hostname of the telemetry server.
    port : int
        TCP port number.
    reconnect_delay : float
        Seconds to wait before retrying a failed connection.
    """

    new_data = Signal(FlightData)
    connection_status = Signal(str)      # "connected" / "disconnected" / error text

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5005,
        reconnect_delay: float = 2.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._host = host
        self._port = port
        self._reconnect_delay = reconnect_delay
        self.is_armed = False
        self._running = True

    # ── Thread entry point ─────────────────────────────────────────────────
    def run(self) -> None:
        while self._running:
            try:
                self._connect_and_receive()
            except (OSError, ConnectionError) as exc:
                self.connection_status.emit(f"disconnected: {exc}")
                if self._running:
                    time.sleep(self._reconnect_delay)

    def _connect_and_receive(self) -> None:
        with socket.create_connection((self._host, self._port), timeout=5) as sock:
            self.connection_status.emit("connected")
            sock.settimeout(1.0)           # allow periodic checks of _running
            buffer = ""
            while self._running:
                try:
                    chunk = sock.recv(4096).decode("utf-8")
                except socket.timeout:
                    continue
                if not chunk:
                    break                  # server closed
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._parse_line(line)

        self.connection_status.emit("disconnected")

    def _parse_line(self, line: str) -> None:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return                         # silently skip malformed lines

        kwargs: dict[str, object] = {}
        for src_key, dst_field in _KEY_MAP.items():
            if src_key in obj:
                kwargs[dst_field] = obj[src_key]

        if kwargs:
            # Start from defaults, override with received values
            data = FlightData(**kwargs)     # type: ignore[arg-type]
            self.new_data.emit(data)

    # ── Arm state (no outbound command yet) ─────────────────────────────────
    def set_armed(self, armed: bool) -> None:
        self.is_armed = armed
        print(f"[TCP] ARM state set to {armed} (no outbound command)")

    # ── Graceful shutdown ──────────────────────────────────────────────────
    def stop(self) -> None:
        self._running = False
        self.wait(3000)
