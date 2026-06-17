"""
mock_telemetry.py - Realistic mock telemetry with battery simulation.

Heading derived from coordinated-turn physics.
Battery drains slowly while running (simulates real flight).
"""

from __future__ import annotations
import math
import time
from PySide6.QtCore import QThread, Signal
from flight_state import FlightData

_BANDS = ["2.4 GHz", "915 MHz", "868 MHz"]
_G = 9.81
_KTS_TO_MS = 0.5144


class MockTelemetryThread(QThread):
    new_data = Signal(FlightData)

    def __init__(self, update_hz: float = 30.0, parent=None) -> None:
        super().__init__(parent)
        self._hz = update_hz
        self._running = True
        # Battery state (decreases over time)
        self._battery_pct = 100.0
        # These are set from outside by main_window
        self._flight_mode = "STABILIZE"
        self._armed = False

    def set_armed(self, armed: bool) -> None:
        self._armed = armed

    def set_flight_mode(self, mode: str) -> None:
        self._flight_mode = mode

    def run(self) -> None:
        t0 = time.monotonic()
        dt = 1.0 / self._hz
        heading_accum = 45.0
        prev_t = 0.0

        while self._running:
            t = time.monotonic() - t0
            elapsed = t - prev_t
            prev_t = t
            s = math.sin

            # ── Attitude ───────────────────────────────────────────────
            roll  = 25.0 * s(0.25 * t) + 5.0 * s(0.73 * t)
            pitch =  7.0 * s(0.18 * t) + 3.0 * s(0.47 * t)

            # ── Airspeed ───────────────────────────────────────────────
            airspeed = 250.0 + 30.0 * s(0.12 * t) + 10.0 * s(0.37 * t)
            airspeed = max(100.0, airspeed)

            # ── Heading from coordinated turn ──────────────────────────
            V = airspeed * _KTS_TO_MS
            clamped_roll = max(-60.0, min(60.0, roll))
            turn_rate_deg = math.degrees(
                _G * math.tan(math.radians(clamped_roll)) / max(30.0, V)
            )
            heading_accum += turn_rate_deg * elapsed
            heading_accum %= 360.0

            # ── Altitude ───────────────────────────────────────────────
            altitude = 10000.0 + 2000.0 * s(0.08 * t) + 500.0 * s(0.22 * t)
            vs_raw = (2000.0 * 0.08 * math.cos(0.08 * t)
                      + 500.0 * 0.22 * math.cos(0.22 * t))
            vertical_speed = vs_raw * 60.0 / (2 * math.pi)

            # ── Speeds ─────────────────────────────────────────────────
            ground_speed = max(80.0, airspeed * 0.96 + 5.0 * s(0.2 * t))
            pitot_airspeed = max(80.0, airspeed + 3.0 * s(0.5 * t) - 2.0)
            throttle = 0.5 + 0.3 * s(0.15 * t)

            # ── Battery simulation ─────────────────────────────────────
            # Drain ~0.5% per minute ≈ 0.000278% per frame at 30 Hz
            self._battery_pct = max(0.0, self._battery_pct - 0.000278)
            # Voltage: 4S LiPo: 16.8V full → 13.2V empty (linear approx)
            battery_voltage = 13.2 + (self._battery_pct / 100.0) * 3.6

            # ── Comm / link ────────────────────────────────────────────
            link_quality = 85.0 + 10.0 * s(0.05 * t) + 3.0 * s(0.15 * t)
            interference = 10.0 + 8.0 * s(0.07 * t) + 5.0 * s(0.23 * t)
            signal_strength = 80.0 + 12.0 * s(0.04 * t) + 4.0 * s(0.11 * t)

            # ── Mode toggles ──────────────────────────────────────────
            p10 = int(t / 10.0) % 2 == 0

            data = FlightData(
                roll=roll,
                pitch=pitch,
                heading=heading_accum,
                airspeed=airspeed,
                altitude=max(0.0, altitude),
                vertical_speed=vertical_speed,
                ground_speed=ground_speed,
                pitot_airspeed=pitot_airspeed,
                throttle=max(0.0, min(1.0, throttle)),
                ap1_active=True, ap2_active=False,
                autothrottle_active=True,
                speed_mode_active=p10,
                heading_mode_active=not p10,
                lnav_active=True, appr_active=False,
                alt_hold_active=p10, vs_active=not p10,
                link_quality=max(0, min(100, link_quality)),
                interference=max(0, min(100, interference)),
                signal_strength=max(0, min(100, signal_strength)),
                comm_band=_BANDS[int(t / 30) % len(_BANDS)],
                battery_percent=self._battery_pct,
                battery_voltage=battery_voltage,
                flight_mode=self._flight_mode,
                armed=self._armed,
                ground_link="CONNECTED" if s(0.03 * t) > -0.9 else "DEGRADED",
                telemetry_status="HEALTHY" if link_quality > 60 else "DEGRADED",
                autopilot_status="ENGAGED" if p10 else "MANUAL",
            )
            self.new_data.emit(data)
            time.sleep(dt)

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
