"""
mode_annunciator.py - Flight Mode Annunciator (FMA) bar.

Renders a row of rectangular mode boxes at the top of the PFD.
Active modes glow green; inactive modes appear dim/outlined.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PySide6.QtWidgets import QWidget

from flight_state import FlightData
from utils.colors import (
    PFD_BLACK,
    MODE_GREEN,
    MODE_DIM,
    MODE_BOX_BG,
    MODE_BOX_ACTIVE_BG,
    SCALE_WHITE,
)


# Each entry: (label, attribute-name on FlightData)
_MODES = [
    ("AP1",   "ap1_active"),
    ("AP2",   "ap2_active"),
    ("A/THR", "autothrottle_active"),
    ("SPD",   "speed_mode_active"),
    ("HDG",   "heading_mode_active"),
    ("LNAV",  "lnav_active"),
    ("APPR",  "appr_active"),
    ("ALT",   "alt_hold_active"),
    ("VS",    "vs_active"),
]


class ModeAnnunciator(QWidget):
    """Top-bar flight mode annunciator strip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(32)
        self.setMaximumHeight(52)
        self._data = FlightData()

    def set_data(self, data: FlightData) -> None:
        self._data = data
        self.update()

    # ── Painting ───────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), PFD_BLACK)

        n = len(_MODES)
        gap = 4
        total_gap = gap * (n + 1)
        box_w = (w - total_gap) / n
        box_h = h - 8

        font = QFont("Consolas", max(9, int(box_h * 0.42)))
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        for i, (label, attr) in enumerate(_MODES):
            active = getattr(self._data, attr, False)
            x = gap + i * (box_w + gap)
            y = (h - box_h) / 2.0
            rect = QRectF(x, y, box_w, box_h)

            # Box fill
            bg = MODE_BOX_ACTIVE_BG if active else MODE_BOX_BG
            painter.setBrush(QBrush(bg))

            # Border
            border_color = MODE_GREEN if active else MODE_DIM
            painter.setPen(QPen(border_color, 1.5))
            painter.drawRoundedRect(rect, 3, 3)

            # Label
            text_color = MODE_GREEN if active else MODE_DIM
            painter.setPen(text_color)
            tw = fm.horizontalAdvance(label)
            tx = x + (box_w - tw) / 2.0
            ty = y + (box_h + fm.ascent()) / 2.0 - 2
            painter.drawText(tx, ty, label)

        painter.end()
