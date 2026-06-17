"""
status_panel.py - Interactive operational status strip.

ARM box:          click to toggle armed / disarmed state.
MODE box:         click to open a popup flight-mode selector.
CONNECTION TYPE:  click to switch between Mock / TCP / Serial telemetry.
SERIAL PORT:      click to select COM port (COM1–COM14).
TELEMETRY:        passive read-only health indicator.
"""

from __future__ import annotations
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QCursor
from PySide6.QtWidgets import QWidget, QMenu
from flight_state import FlightData

try:
    import serial.tools.list_ports
except ImportError:
    serial = None  # type: ignore[assignment]


FLIGHT_MODES = [
    "MANUAL", "STABILIZE", "FBWA", "CRUISE", "AUTO", "RTL", "LOITER",
]

CONNECTION_TYPES = ["MOCK", "TCP", "SERIAL"]
REFERENCE_OPTIONS = ["-20.0", "-10.0", "0.0", "10.0", "20.0"]

SERIAL_PORTS = [f"COM{i}" for i in range(1, 15)]


def _available_serial_ports() -> list[str]:
    ports = set(SERIAL_PORTS)
    if serial is not None:
        ports.update(port.device.upper() for port in serial.tools.list_ports.comports())
    return sorted(ports, key=lambda p: int(p[3:]) if p.upper().startswith("COM") and p[3:].isdigit() else 999)

_GOOD = {"ARMED", "CONNECTED", "HEALTHY", "ENGAGED", "AUTO", "RTL",
         "LOITER", "CRUISE", "MOCK", "TCP", "SERIAL"}
_WARN = {"DEGRADED", "MANUAL", "STABILIZE", "FBWA"}
_BAD  = {"DISARMED", "DISCONNECTED", "ERROR", "LOST"}


def _status_color(value: str) -> QColor:
    v = value.upper()
    if v in _GOOD:
        return QColor(0, 200, 80)
    if v in _WARN:
        return QColor(255, 165, 0)
    if v in _BAD:
        return QColor(220, 40, 40)
    return QColor(0, 200, 80)


def _dropdown_style() -> str:
    """Shared dark-themed dropdown menu stylesheet."""
    return """
        QMenu {
            background-color: #1a1c22;
            border: 1px solid #2e3138;
            border-radius: 4px;
            padding: 4px 0;
        }
        QMenu::item {
            color: #c8cad0;
            padding: 6px 24px 6px 16px;
            font-family: 'Consolas';
            font-size: 10pt;
            font-weight: bold;
        }
        QMenu::item:selected {
            background-color: #2a3040;
            color: #ffffff;
        }
        QMenu::item:checked {
            color: #00c850;
        }
        QMenu::separator {
            height: 1px;
            background: #2a2c32;
            margin: 2px 8px;
        }
    """


class StatusPanel(QWidget):
    """Horizontal strip of operational status indicators.

    Emits:
        arm_toggled(bool)          — armed / disarmed
        mode_selected(str)         — flight mode
        connection_type_selected(str) — MOCK / TCP / SERIAL
        serial_port_selected(str)  — COM port string (e.g. "COM3")
    """

    arm_toggled = Signal(bool)
    mode_selected = Signal(str)
    connection_type_selected = Signal(str)
    serial_port_selected = Signal(str)
    reference_selected = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self._data = FlightData()
        self._box_rects: list[QRectF] = []
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Track current connection type & serial port independently
        # so they persist across FlightData updates.
        self._connection_type = "MOCK"
        self._serial_port = "COM3"

    def set_data(self, data: FlightData) -> None:
        self._data = data
        self.update()

    def set_connection_type(self, conn_type: str) -> None:
        self._connection_type = conn_type.upper()
        self.update()

    def set_serial_port(self, port: str) -> None:
        self._serial_port = port.upper()
        self.update()

    # ── Items definition ────────────────────────────────────────────────
    def _items(self):
        """Return list of (label, value, is_interactive)."""
        d = self._data
        return [
            ("ARM",             "ARMED" if d.armed else "DISARMED", True),
            ("MODE",            d.flight_mode,                      True),
            ("CONNECTION TYPE", self._connection_type,              True),
            ("SERIAL PORT",     self._serial_port,                  True),
            ("REF",             f"{d.control_ref:+.1f} DEG",        True),
            ("TELEMETRY",       d.telemetry_status,                 False),
        ]

    # ── Paint ───────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(14, 14, 18))

        items = self._items()
        n = len(items)
        gap = 5
        box_w = (w - gap * (n + 1)) / n
        box_h = h - 6
        self._box_rects = []

        for i, (label, value, interactive) in enumerate(items):
            color = _status_color(value)
            x = gap + i * (box_w + gap)
            y = 3.0
            rect = QRectF(x, y, box_w, box_h)
            self._box_rects.append(rect)

            border_color = QColor(55, 60, 70) if interactive else QColor(35, 38, 44)
            p.setPen(QPen(border_color, 1))
            p.setBrush(QColor(22, 24, 30) if interactive else QColor(20, 22, 26))
            p.drawRoundedRect(rect, 4, 4)

            if interactive:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(color.red(), color.green(), color.blue(), 60))
                p.drawRoundedRect(
                    QRectF(x + 2, y + box_h - 3, box_w - 4, 2), 1, 1
                )

            dot_r = 3
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(QRectF(x + 8, y + 8, dot_r * 2, dot_r * 2))

            lf = QFont("Segoe UI", 7)
            lf.setBold(True)
            p.setFont(lf)
            p.setPen(QColor(100, 105, 115))
            has_dropdown = interactive and label in ("MODE", "CONNECTION TYPE", "SERIAL PORT", "REF")
            suffix = " \u25BC" if has_dropdown else ""
            p.drawText(QRectF(x + 18, y + 1, box_w - 24, box_h * 0.45),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label + suffix)

            vf = QFont("Consolas", 8)
            vf.setBold(True)
            p.setFont(vf)
            p.setPen(color)
            p.drawText(QRectF(x + 8, y + box_h * 0.48, box_w - 14, box_h * 0.50),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       value)

        p.end()

    # ── Mouse interaction ───────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        pos = event.position()
        items = self._items()
        for i, (label, value, interactive) in enumerate(items):
            if not interactive:
                continue
            if i < len(self._box_rects) and self._box_rects[i].contains(pos):
                if label == "ARM":
                    self.arm_toggled.emit(not self._data.armed)
                elif label == "MODE":
                    self._show_menu(label, FLIGHT_MODES,
                                    self._data.flight_mode,
                                    self.mode_selected)
                elif label == "CONNECTION TYPE":
                    self._show_menu(label, CONNECTION_TYPES,
                                    self._connection_type,
                                    self._on_connection_type_chosen)
                elif label == "SERIAL PORT":
                    self._show_menu(label, _available_serial_ports(),
                                    self._serial_port,
                                    self._on_serial_port_chosen)
                elif label == "REF":
                    self._show_menu(label, REFERENCE_OPTIONS,
                                    f"{self._data.control_ref:.1f}",
                                    self._on_reference_chosen)
                return
        super().mousePressEvent(event)

    def _show_menu(self, label: str, options: list[str],
                   current: str, callback) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(_dropdown_style())

        for opt in options:
            action = menu.addAction(opt)
            action.setCheckable(True)
            action.setChecked(opt == current)

        chosen = menu.exec(QCursor.pos())
        if chosen and chosen.text() != current:
            callback(chosen.text())

    def _on_connection_type_chosen(self, conn_type: str) -> None:
        self._connection_type = conn_type
        self.connection_type_selected.emit(conn_type)

    def _on_serial_port_chosen(self, port: str) -> None:
        self._serial_port = port
        self.serial_port_selected.emit(port)

    def _on_reference_chosen(self, value: str) -> None:
        self.reference_selected.emit(float(value))
