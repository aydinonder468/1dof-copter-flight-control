"""
speed_panel.py - Single airspeed card + battery panel for the right column.

Simplified: only one speed readout and a battery section with
horizontal charge bar + voltage readout.
"""

from __future__ import annotations
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QLinearGradient
from PySide6.QtWidgets import QWidget, QVBoxLayout
from flight_state import FlightData
from utils.colors import ACCENT_CYAN


# ═══════════════════════════════════════════════════════════════════════
#  Single speed card
# ═══════════════════════════════════════════════════════════════════════
class _SpeedCard(QWidget):
    """Prominent single airspeed readout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.setMinimumHeight(60)

    def set_value(self, v: float):
        self._value = v
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = 12

        # Card bg
        p.setPen(QPen(QColor(35, 38, 44), 1))
        p.setBrush(QColor(20, 22, 26))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 5, 5)

        # Top accent
        glow = QLinearGradient(0, 0, w, 0)
        glow.setColorAt(0.0, ACCENT_CYAN)
        glow.setColorAt(1.0, QColor(ACCENT_CYAN.red(), ACCENT_CYAN.green(),
                                     ACCENT_CYAN.blue(), 30))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRect(QRectF(1, 1, w - 2, 2))

        # Title
        tf = QFont("Segoe UI", 8)
        tf.setBold(True)
        p.setFont(tf)
        p.setPen(QColor(120, 125, 135))
        p.drawText(QRectF(pad, 6, w - pad * 2, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "AIRSPEED")

        # Value
        vf = QFont("Consolas", max(16, int(h * 0.30)))
        vf.setBold(True)
        p.setFont(vf)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(pad, 26, w * 0.65, h - 32),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._value:.1f}")

        # Unit
        uf = QFont("Segoe UI", 8)
        p.setFont(uf)
        p.setPen(QColor(80, 85, 95))
        p.drawText(QRectF(w * 0.62, 26, w * 0.36, h - 32),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "kts")
        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  Battery panel
# ═══════════════════════════════════════════════════════════════════════
class _BatteryPanel(QWidget):
    """Battery level bar + voltage readout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._percent = 100.0
        self._voltage = 16.8
        self.setMinimumHeight(70)

    def set_data(self, percent: float, voltage: float):
        self._percent = max(0.0, min(100.0, percent))
        self._voltage = voltage
        self.update()

    def _bar_color(self, pct: float) -> QColor:
        if pct > 50:
            return QColor(0, 200, 80)
        elif pct > 25:
            return QColor(255, 175, 0)
        else:
            return QColor(220, 45, 45)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = 12

        # Card bg
        p.setPen(QPen(QColor(35, 38, 44), 1))
        p.setBrush(QColor(20, 22, 26))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 5, 5)

        # Title
        tf = QFont("Segoe UI", 8)
        tf.setBold(True)
        p.setFont(tf)
        p.setPen(QColor(120, 125, 135))
        p.drawText(QRectF(pad, 6, w - pad * 2, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "BATTERY")

        # Percentage text (right of title)
        p.setPen(self._bar_color(self._percent))
        pf = QFont("Consolas", 9)
        pf.setBold(True)
        p.setFont(pf)
        p.drawText(QRectF(pad, 6, w - pad * 2, 16),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._percent:.0f}%")

        # Bar area
        bar_y = 28
        bar_h = 14
        bar_x = pad
        bar_w = w - pad * 2

        # Bar background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(30, 32, 38))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Filled bar
        fill_w = bar_w * (self._percent / 100.0)
        if fill_w > 2:
            color = self._bar_color(self._percent)
            bar_grad = QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_h)
            bar_grad.setColorAt(0.0, color.lighter(120))
            bar_grad.setColorAt(1.0, color)
            p.setBrush(QBrush(bar_grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 4, 4)

        # Battery bar segments (visual segmentation)
        p.setPen(QPen(QColor(20, 22, 26), 1))
        seg_count = 10
        for i in range(1, seg_count):
            sx = bar_x + bar_w * (i / seg_count)
            p.drawLine(int(sx), int(bar_y + 2), int(sx), int(bar_y + bar_h - 2))

        # Bar border
        p.setPen(QPen(QColor(50, 52, 58), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Voltage readout below bar
        volt_y = bar_y + bar_h + 6
        vf = QFont("Consolas", 12)
        vf.setBold(True)
        p.setFont(vf)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(pad, volt_y, w * 0.5, h - volt_y - 4),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._voltage:.1f} V")

        # Cell type label
        lf = QFont("Segoe UI", 7)
        p.setFont(lf)
        p.setPen(QColor(70, 75, 85))
        p.drawText(QRectF(w * 0.45, volt_y, w * 0.5, h - volt_y - 4),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "4S LiPo")
        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  Section header
# ═══════════════════════════════════════════════════════════════════════
class _PanelTitle(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(18)

    def paintEvent(self, event):
        p = QPainter(self)
        f = QFont("Segoe UI", 7)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.8)
        p.setFont(f)
        p.setPen(QColor(70, 75, 85))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  Composite right-side data panel
# ═══════════════════════════════════════════════════════════════════════
class SpeedPanel(QWidget):
    """Right-column data panel: single speed card + battery."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 2)
        layout.setSpacing(6)

        layout.addWidget(_PanelTitle("FLIGHT DATA"))
        self._speed = _SpeedCard()
        layout.addWidget(self._speed)

        layout.addWidget(_PanelTitle("BATTERY"))
        self._battery = _BatteryPanel()
        layout.addWidget(self._battery)

        layout.addStretch()

    def set_data(self, data: FlightData):
        self._speed.set_value(data.airspeed)
        self._battery.set_data(data.battery_percent, data.battery_voltage)
