"""
main_window.py - Full-HD (1920×1080) avionics dashboard layout.

State logic:
  - DISARMED: telemetry thread still runs but UI data updates are frozen.
    All panels keep showing last-seen values.
  - ARMED: data updates flow normally to all widgets.
  - Flight mode: propagated to mock telemetry + status panel.

Connection switching:
  - The status panel's CONNECTION TYPE dropdown lets the user switch
    between MOCK / TCP / SERIAL telemetry at runtime without restarting.
  - The SERIAL PORT dropdown selects the COM port for serial mode.
"""

from __future__ import annotations
import dataclasses
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
)

from flight_state import FlightState, FlightData
from telemetry.mock_telemetry import MockTelemetryThread
from utils.smoothing import EMAFilter, AngleEMAFilter
from utils.colors import ACCENT_BLUE, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_PURPLE

from widgets.attitude_indicator import AttitudeIndicator
from widgets.airspeed_tape import AirspeedTape
from widgets.altitude_tape import AltitudeTape
from widgets.heading_tape import HeadingTape
from widgets.mode_annunciator import ModeAnnunciator
from widgets.status_panel import StatusPanel
from widgets.telemetry_box import TelemetryBox
from widgets.one_dof_copter_widget import OneDofCopterWidget
from widgets.speed_panel import SpeedPanel
from widgets.comms_panel import CommsPanel
from widgets.logo_widget import LogoWidget


class PFDMainWindow(QMainWindow):
    """Full-HD avionics dashboard — 1920×1080 target."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flight Controller Interface — Primary Flight Display")
        self.setMinimumSize(1024, 600)
        self.resize(1920, 1080)
        self.setStyleSheet("background-color: #0a0a0a;")

        # ── App state ──────────────────────────────────────────────────
        self._armed = False
        self._flight_mode = "STABILIZE"
        self._connection_type = "MOCK"
        self._serial_port = "COM3"
        self._tcp_host = "127.0.0.1"
        self._tcp_port = 5005
        self._baud = 115200

        # ── Flight state ───────────────────────────────────────────────
        self._flight_state = FlightState(self)

        # ── Smoothing filters ──────────────────────────────────────────
        self._filters = {
            "roll":           EMAFilter(alpha=0.12),
            "pitch":          EMAFilter(alpha=0.12),
            "heading":        AngleEMAFilter(alpha=0.15),
            "airspeed":       EMAFilter(alpha=0.25),
            "altitude":       EMAFilter(alpha=0.18),
            "vertical_speed": EMAFilter(alpha=0.20),
            "ground_speed":   EMAFilter(alpha=0.25),
            "pitot_airspeed": EMAFilter(alpha=0.25),
            "control_angle":  EMAFilter(alpha=0.60),
            "control_error":  EMAFilter(alpha=0.60),
            "control_rate":   EMAFilter(alpha=0.45),
            "control_u_diff": EMAFilter(alpha=0.45),
            "link_quality":   EMAFilter(alpha=0.15),
            "interference":   EMAFilter(alpha=0.15),
            "signal_strength":EMAFilter(alpha=0.15),
        }

        # ── Create all widgets ─────────────────────────────────────────
        self._status   = StatusPanel()
        self._fma      = ModeAnnunciator()
        self._adi      = AttitudeIndicator()
        self._asi      = AirspeedTape()
        self._alt_tape = AltitudeTape()
        self._hdg      = HeadingTape()
        self._aircraft = OneDofCopterWidget()
        self._speed    = SpeedPanel()
        self._comms    = CommsPanel()

        self._box_roll  = TelemetryBox("ROLL",     "deg", ACCENT_BLUE,   fmt=".1f")
        self._box_pitch = TelemetryBox("PITCH",    "deg", ACCENT_GREEN,  fmt=".1f")
        self._box_hdg   = TelemetryBox("HEADING",  "deg", ACCENT_ORANGE, fmt=".1f")
        self._box_alt   = TelemetryBox("ALTITUDE", "ft",  ACCENT_PURPLE, fmt=".0f")
        self._box_ref   = TelemetryBox("REF",      "deg", ACCENT_BLUE,   fmt=".1f")
        self._box_ctrl  = TelemetryBox("CTRL",     "deg", ACCENT_GREEN,  fmt=".1f")
        self._box_err   = TelemetryBox("ERROR",    "deg", ACCENT_ORANGE, fmt=".1f")
        self._box_udiff = TelemetryBox("U DIFF",   "us",  ACCENT_PURPLE, fmt=".0f")
        self._box_pwm_l = TelemetryBox("PWM L",    "us",  ACCENT_BLUE,   fmt=".0f")
        self._box_pwm_r = TelemetryBox("PWM R",    "us",  ACCENT_GREEN,  fmt=".0f")

        # ── Build layout ───────────────────────────────────────────────
        self._build_layout()

        # ── Wire signals ───────────────────────────────────────────────
        self._flight_state.state_updated.connect(self._on_state_updated)
        self._status.arm_toggled.connect(self._on_arm_toggled)
        self._status.mode_selected.connect(self._on_mode_selected)
        self._status.connection_type_selected.connect(self._on_connection_type_selected)
        self._status.serial_port_selected.connect(self._on_serial_port_selected)
        self._status.reference_selected.connect(self._on_reference_selected)

        # ── Start telemetry ────────────────────────────────────────────
        self._telemetry = MockTelemetryThread(update_hz=30, parent=self)
        self._telemetry.set_armed(self._armed)
        self._telemetry.set_flight_mode(self._flight_mode)
        self._telemetry.new_data.connect(self._on_raw_telemetry)
        self._telemetry.start()

        # Push initial disarmed state to UI
        self._push_status_only()

    # ── Layout construction ────────────────────────────────────────────
    def _build_layout(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        # 1) Top status bar
        root.addWidget(self._status, stretch=0)

        # 2) Main content: [Comms | PFD Center | Right]
        main_h = QHBoxLayout()
        main_h.setSpacing(6)

        # Left column
        self._comms.setFixedWidth(280)
        main_h.addWidget(self._comms)

        # Center column
        center_v = QVBoxLayout()
        center_v.setSpacing(2)

        self._fma.setMaximumHeight(36)
        center_v.addWidget(self._fma, stretch=0)

        instr_h = QHBoxLayout()
        instr_h.setSpacing(3)
        self._asi.setFixedWidth(100)
        self._asi.setSizePolicy(QSizePolicy.Policy.Fixed,
                                QSizePolicy.Policy.Expanding)
        self._alt_tape.setFixedWidth(110)
        self._alt_tape.setSizePolicy(QSizePolicy.Policy.Fixed,
                                     QSizePolicy.Policy.Expanding)
        self._adi.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)

        instr_h.addWidget(self._asi)
        instr_h.addWidget(self._adi, stretch=1)
        instr_h.addWidget(self._alt_tape)
        center_v.addLayout(instr_h, stretch=1)

        self._hdg.setFixedHeight(68)
        center_v.addWidget(self._hdg, stretch=0)

        main_h.addLayout(center_v, stretch=1)

        # Right column: Logo → 3D Aircraft → Speed/Battery
        right_v = QVBoxLayout()
        right_v.setSpacing(4)

        # Logo at top-right
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "logo.jpg")
        self._logo = LogoWidget(logo_path)
        self._logo.setFixedHeight(204)
        right_v.addWidget(self._logo, stretch=0)

        # 1-DOF copter rig
        self._aircraft.setSizePolicy(QSizePolicy.Policy.Preferred,
                                     QSizePolicy.Policy.Expanding)
        right_v.addWidget(self._aircraft, stretch=3)

        # Speed + battery
        right_v.addWidget(self._speed, stretch=2)

        right_frame = QWidget()
        right_frame.setLayout(right_v)
        right_frame.setFixedWidth(320)
        main_h.addWidget(right_frame)

        root.addLayout(main_h, stretch=1)

        # 3) Bottom telemetry boxes
        bottom_h = QHBoxLayout()
        bottom_h.setSpacing(8)
        for box in (
            self._box_roll, self._box_pitch, self._box_hdg, self._box_alt,
            self._box_ref, self._box_ctrl, self._box_err, self._box_udiff,
            self._box_pwm_l, self._box_pwm_r,
        ):
            box.setFixedHeight(82)
            bottom_h.addWidget(box, stretch=1)
        root.addLayout(bottom_h, stretch=0)

    # ── ARM / MODE interaction handlers ────────────────────────────────
    def _on_arm_toggled(self, armed: bool) -> None:
        self._armed = armed
        self._telemetry.set_armed(armed)
        # If disarming, push one final state update with armed=False
        # so the status panel reflects it immediately.
        if not armed:
            self._push_status_only()

    def _on_mode_selected(self, mode: str) -> None:
        self._flight_mode = mode
        # Only MockTelemetryThread supports set_flight_mode
        if hasattr(self._telemetry, "set_flight_mode"):
            self._telemetry.set_flight_mode(mode)

    def _on_reference_selected(self, reference_deg: float) -> None:
        if hasattr(self._telemetry, "set_reference"):
            self._telemetry.set_reference(reference_deg)
        current = self._flight_state.data
        self._flight_state.update(
            dataclasses.replace(current, control_ref=reference_deg)
        )

    def _push_status_only(self) -> None:
        """Push a status-only update so ARM / MODE reflect in the UI
        even when flight data updates are frozen."""
        current = self._flight_state.data
        patched = dataclasses.replace(
            current,
            armed=self._armed,
            flight_mode=self._flight_mode,
        )
        self._flight_state.update(patched)

    # ── Telemetry slots ────────────────────────────────────────────────
    def _on_raw_telemetry(self, raw: FlightData) -> None:
        if self._connection_type == "SERIAL":
            self._armed = raw.armed

        # If disarmed, freeze flight data — only update status fields
        if not self._armed and self._connection_type != "SERIAL":
            # Still update comms / link / battery (they keep running)
            current = self._flight_state.data
            patched = dataclasses.replace(
                current,
                armed=self._armed,
                flight_mode=self._flight_mode,
                link_quality=self._filters["link_quality"].update(raw.link_quality),
                interference=self._filters["interference"].update(raw.interference),
                signal_strength=self._filters["signal_strength"].update(raw.signal_strength),
                battery_percent=raw.battery_percent,
                battery_voltage=raw.battery_voltage,
                ground_link=raw.ground_link,
                telemetry_status=raw.telemetry_status,
            )
            self._flight_state.update(patched)
            return

        # Armed: full update with smoothing
        smoothed = dataclasses.replace(
            raw,
            roll=self._filters["roll"].update(raw.roll),
            pitch=self._filters["pitch"].update(raw.pitch),
            heading=self._filters["heading"].update(raw.heading),
            airspeed=self._filters["airspeed"].update(raw.airspeed),
            altitude=self._filters["altitude"].update(raw.altitude),
            vertical_speed=self._filters["vertical_speed"].update(raw.vertical_speed),
            ground_speed=self._filters["ground_speed"].update(raw.ground_speed),
            pitot_airspeed=self._filters["pitot_airspeed"].update(raw.pitot_airspeed),
            control_angle=self._filters["control_angle"].update(raw.control_angle),
            control_error=self._filters["control_error"].update(raw.control_error),
            control_rate=self._filters["control_rate"].update(raw.control_rate),
            control_u_diff=self._filters["control_u_diff"].update(raw.control_u_diff),
            link_quality=self._filters["link_quality"].update(raw.link_quality),
            interference=self._filters["interference"].update(raw.interference),
            signal_strength=self._filters["signal_strength"].update(raw.signal_strength),
            armed=raw.armed if self._connection_type == "SERIAL" else self._armed,
            flight_mode=self._flight_mode,
        )
        self._flight_state.update(smoothed)

    def _on_state_updated(self, data: FlightData) -> None:
        self._fma.set_data(data)
        self._adi.set_data(data)
        self._asi.set_data(data)
        self._alt_tape.set_data(data)
        self._hdg.set_data(data)
        self._status.set_data(data)
        self._aircraft.set_data(data)
        self._speed.set_data(data)
        self._comms.set_data(data)
        self._box_roll.set_value(data.roll)
        self._box_pitch.set_value(data.pitch)
        self._box_hdg.set_value(data.heading)
        self._box_alt.set_value(data.altitude)
        self._box_ref.set_value(data.control_ref)
        self._box_ctrl.set_value(data.control_angle)
        self._box_err.set_value(data.control_error)
        self._box_udiff.set_value(data.control_u_diff)
        self._box_pwm_l.set_value(data.pwm_left)
        self._box_pwm_r.set_value(data.pwm_right)

    # ── Connection type & serial port handlers ──────────────────────────
    def _on_connection_type_selected(self, conn_type: str) -> None:
        conn_type = conn_type.upper()
        if conn_type == self._connection_type:
            return
        self._connection_type = conn_type
        self._status.set_connection_type(conn_type)
        self._switch_telemetry(conn_type)

    def _on_serial_port_selected(self, port: str) -> None:
        port = port.upper()
        self._serial_port = port
        self._status.set_serial_port(port)
        # If already in SERIAL mode, restart with the new port
        if self._connection_type == "SERIAL":
            self._switch_telemetry("SERIAL")

    def _switch_telemetry(self, conn_type: str) -> None:
        """Stop the current telemetry source and start the requested one."""
        # ── Stop old source ────────────────────────────────────────────
        self._telemetry.stop()

        # ── Create & start new source ──────────────────────────────────
        if conn_type == "MOCK":
            client = MockTelemetryThread(update_hz=30, parent=self)
            client.set_armed(self._armed)
            client.set_flight_mode(self._flight_mode)
            client.new_data.connect(self._on_raw_telemetry)
            client.start()
            self._telemetry = client
            self.setWindowTitle("Flight Controller Interface — MOCK")

        elif conn_type == "TCP":
            from telemetry.tcp_telemetry_client import TcpTelemetryClient
            client = TcpTelemetryClient(
                host=self._tcp_host, port=self._tcp_port, parent=self
            )
            client.new_data.connect(self._on_raw_telemetry)
            client.connection_status.connect(
                lambda s: self.setWindowTitle(f"PFD — TCP [{s}]")
            )
            client.start()
            self._telemetry = client
            self.setWindowTitle(f"PFD — TCP {self._tcp_host}:{self._tcp_port}")

        elif conn_type == "SERIAL":
            from telemetry.serial_telemetry_client import SerialTelemetryClient
            client = SerialTelemetryClient(
                port=self._serial_port, baud=self._baud, parent=self
            )
            client.new_data.connect(self._on_raw_telemetry)
            client.connection_status.connect(
                lambda s: self.setWindowTitle(f"PFD — SERIAL [{s}]")
            )
            client.start()
            self._telemetry = client
            self.setWindowTitle(f"PFD — SERIAL {self._serial_port} @ {self._baud}")

    def closeEvent(self, event):
        self._telemetry.stop()
        super().closeEvent(event)
