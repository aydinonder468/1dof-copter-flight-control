"""
flight_state.py - Central flight-state data model.

Includes battery fields and armed/mode state controlled by the UI.
"""

from __future__ import annotations
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal


@dataclass
class FlightData:
    # ── Attitude & Navigation ──────────────────────────────────────────────
    roll: float = 0.0
    pitch: float = 0.0
    heading: float = 0.0
    airspeed: float = 250.0
    altitude: float = 10000.0
    vertical_speed: float = 0.0
    ground_speed: float = 240.0
    pitot_airspeed: float = 248.0
    throttle: float = 0.5

    # 1-DOF controller telemetry
    control_ref: float = 0.0
    control_angle: float = 0.0
    control_rate: float = 0.0
    control_error: float = 0.0
    control_u_diff: float = 0.0
    pwm_left: float = 1000.0
    pwm_right: float = 1000.0

    # ── Autopilot / mode flags ─────────────────────────────────────────────
    ap1_active: bool = True
    ap2_active: bool = False
    autothrottle_active: bool = True
    speed_mode_active: bool = True
    heading_mode_active: bool = False
    lnav_active: bool = True
    appr_active: bool = False
    alt_hold_active: bool = True
    vs_active: bool = False

    # ── Communication / link ───────────────────────────────────────────────
    link_quality: float = 95.0
    interference: float = 5.0
    signal_strength: float = 85.0
    comm_band: str = "2.4 GHz"

    # ── Battery ────────────────────────────────────────────────────────────
    battery_percent: float = 100.0
    battery_voltage: float = 16.8

    # ── Operational status ─────────────────────────────────────────────────
    flight_mode: str = "STABILIZE"
    armed: bool = False
    ground_link: str = "CONNECTED"
    telemetry_status: str = "HEALTHY"
    autopilot_status: str = "ENGAGED"


class FlightState(QObject):
    state_updated = Signal(FlightData)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data = FlightData()

    @property
    def data(self) -> FlightData:
        return self._data

    def update(self, new_data: FlightData) -> None:
        self._data = new_data
        self.state_updated.emit(new_data)
