"""
one_dof_copter_widget.py - Live 1-DOF copter rig indicator.

Draws the real test stand as a fixed pivot beam with two motor pods. The beam
uses the observer/control angle from STM32 telemetry, so it follows the same
signal that feeds the PID controller.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from flight_state import FlightData


class OneDofCopterWidget(QWidget):
    """Visualize the 1-DOF copter beam in sync with control telemetry."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data = FlightData()
        self.setMinimumHeight(180)

    def set_data(self, data: FlightData) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        rect = self.rect()

        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(18, 20, 26))
        bg.setColorAt(1.0, QColor(8, 9, 12))
        p.fillRect(rect, bg)

        cx = w * 0.5
        cy = h * 0.52
        beam_len = min(w * 0.72, h * 1.18)
        half = beam_len * 0.5
        angle = max(-45.0, min(45.0, self._data.control_angle))
        ref = max(-45.0, min(45.0, self._data.control_ref))

        self._draw_grid(p, w, h, cx, cy)
        self._draw_reference(p, cx, cy, half, ref)
        self._draw_beam(p, cx, cy, half, angle)
        self._draw_readouts(p, w, h)

        p.end()

    def _rotated_point(self, cx: float, cy: float, radius: float, angle_deg: float) -> QPointF:
        a = math.radians(angle_deg)
        return QPointF(cx + radius * math.cos(a), cy - radius * math.sin(a))

    def _draw_grid(self, p: QPainter, w: int, h: int, cx: float, cy: float) -> None:
        p.setPen(QPen(QColor(45, 48, 56), 1))
        p.drawLine(QPointF(w * 0.08, cy), QPointF(w * 0.92, cy))
        p.drawLine(QPointF(cx, h * 0.16), QPointF(cx, h * 0.88))

        p.setFont(QFont("Consolas", 8))
        p.setPen(QColor(95, 102, 116))
        for deg in (-30, -15, 15, 30):
            end = self._rotated_point(cx, cy, min(w, h) * 0.36, deg)
            p.drawLine(QPointF(cx, cy), end)
            label = f"{deg:+d}"
            p.drawText(QRectF(end.x() - 16, end.y() - 10, 32, 20),
                       Qt.AlignmentFlag.AlignCenter, label)

    def _draw_reference(self, p: QPainter, cx: float, cy: float, half: float, ref: float) -> None:
        left = self._rotated_point(cx, cy, -half * 0.92, ref)
        right = self._rotated_point(cx, cy, half * 0.92, ref)
        pen = QPen(QColor(0, 180, 255, 130), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(left, right)

    def _draw_beam(self, p: QPainter, cx: float, cy: float, half: float, angle: float) -> None:
        left = self._rotated_point(cx, cy, -half, angle)
        right = self._rotated_point(cx, cy, half, angle)

        shadow_pen = QPen(QColor(0, 0, 0, 180), 13)
        shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(shadow_pen)
        p.drawLine(left + QPointF(0, 3), right + QPointF(0, 3))

        beam_pen = QPen(QColor(222, 226, 235), 9)
        beam_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(beam_pen)
        p.drawLine(left, right)

        p.setPen(QPen(QColor(10, 12, 16), 2))
        p.setBrush(QColor(235, 190, 70))
        p.drawEllipse(QPointF(cx, cy), 13, 13)
        p.setBrush(QColor(35, 38, 45))
        p.drawEllipse(QPointF(cx, cy), 5, 5)

        self._draw_motor(p, left, "A2", QColor(0, 170, 255))
        self._draw_motor(p, right, "A3", QColor(0, 220, 120))

    def _draw_motor(self, p: QPainter, pos: QPointF, label: str, color: QColor) -> None:
        p.setPen(QPen(QColor(8, 9, 12), 2))
        p.setBrush(QColor(28, 31, 38))
        p.drawRoundedRect(QRectF(pos.x() - 24, pos.y() - 17, 48, 34), 5, 5)

        p.setBrush(color)
        p.drawEllipse(QPointF(pos.x(), pos.y()), 10, 10)
        p.setPen(QPen(QColor(230, 235, 240), 2))
        p.drawLine(QPointF(pos.x() - 18, pos.y()), QPointF(pos.x() + 18, pos.y()))
        p.drawLine(QPointF(pos.x(), pos.y() - 18), QPointF(pos.x(), pos.y() + 18))

        p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        p.setPen(color)
        p.drawText(QRectF(pos.x() - 20, pos.y() + 20, 40, 18),
                   Qt.AlignmentFlag.AlignCenter, label)

    def _draw_readouts(self, p: QPainter, w: int, h: int) -> None:
        p.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        p.setPen(QColor(210, 218, 230))
        p.drawText(QRectF(12, 8, w - 24, 22), Qt.AlignmentFlag.AlignLeft,
                   "1-DOF COPTER")

        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(145, 154, 170))
        text = (
            f"angle {self._data.control_angle:+.2f} deg   "
            f"ref {self._data.control_ref:+.1f} deg   "
            f"u {self._data.control_u_diff:+.0f} us"
        )
        p.drawText(QRectF(12, h - 30, w - 24, 22),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   text)
