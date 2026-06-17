"""
telemetry_box.py - Bottom-row telemetry value card.

Fixed layout zones so title, value, and unit never overlap.
Consistent naming: HEADING (not YAW / HEADING).
"""

from __future__ import annotations
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QLinearGradient
from PySide6.QtWidgets import QWidget


class TelemetryBox(QWidget):
    """Single telemetry value display card with colored accent."""

    def __init__(
        self, title: str, unit: str, accent: QColor,
        fmt: str = ".1f", parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._accent = accent
        self._fmt = fmt
        self._value: float = 0.0
        self.setMinimumSize(90, 60)

    def set_value(self, value: float) -> None:
        self._value = value
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        accent_w = 4
        pad_l = accent_w + 12
        pad_r = 10

        # ── Card background ────────────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 22, 26))
        p.drawRoundedRect(QRectF(0, 0, w, h), 5, 5)

        # Left accent bar
        p.setBrush(self._accent)
        p.drawRoundedRect(QRectF(0, 0, accent_w + 2, h), 5, 5)
        p.drawRect(QRectF(accent_w, 0, 2, h))

        # Border
        p.setPen(QPen(QColor(40, 42, 48), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 5, 5)

        # ── Layout zones (strict, no overlap) ──────────────────────────
        title_h = 18
        unit_h = 16
        value_h = h - title_h - unit_h - 4  # remaining space

        title_rect = QRectF(pad_l, 4, w - pad_l - pad_r, title_h)
        value_rect = QRectF(pad_l, 4 + title_h, w - pad_l - pad_r, value_h)
        unit_rect  = QRectF(pad_l, h - unit_h - 2, w - pad_l - pad_r, unit_h)

        # ── Title ──────────────────────────────────────────────────────
        tf = QFont("Segoe UI", 8)
        tf.setBold(True)
        p.setFont(tf)
        p.setPen(QColor(140, 145, 155))
        p.drawText(title_rect,
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._title)

        # ── Value ──────────────────────────────────────────────────────
        val_str = f"{self._value:{self._fmt}}"
        # Adaptive font size: shrink if string is long
        base_size = max(12, int(value_h * 0.65))
        if len(val_str) > 7:
            base_size = int(base_size * 0.82)
        vf = QFont("Consolas", base_size)
        vf.setBold(True)
        p.setFont(vf)
        p.setPen(QColor(255, 255, 255))
        p.drawText(value_rect,
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   val_str)

        # ── Unit ───────────────────────────────────────────────────────
        uf = QFont("Segoe UI", 7)
        p.setFont(uf)
        p.setPen(QColor(90, 95, 105))
        p.drawText(unit_rect,
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._unit)

        p.end()
