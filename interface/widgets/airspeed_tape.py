"""
airspeed_tape.py - EFIS-style vertical airspeed tape (left side).

Fixes applied:
  - Internal display-value smoother for stable scrolling
  - Text label Y-positions snapped to whole pixels (shimmer fix)
  - Only iterate at tick intervals instead of every integer knot
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter,
    QPen,
    QColor,
    QFont,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget

from flight_state import FlightData
from utils.colors import (
    PFD_BLACK,
    SCALE_WHITE,
    TAPE_BG,
    POINTER_BG,
    TEXT_GREEN,
)


class AirspeedTape(QWidget):
    """Vertical scrolling airspeed indicator — flicker-free."""

    TAPE_WIDTH_FRAC = 0.85
    MAJOR_INTERVAL = 10          # knots
    MINOR_INTERVAL = 5           # knots
    VISIBLE_RANGE_KTS = 80

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(70, 200)
        self._data = FlightData()
        self._display_spd = 250.0
        self._smooth_alpha = 0.22

    def set_data(self, data: FlightData) -> None:
        self._data = data
        self._display_spd += self._smooth_alpha * (data.airspeed - self._display_spd)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w, h = self.width(), self.height()
        spd = self._display_spd

        tape_w = w * self.TAPE_WIDTH_FRAC
        tape_x = w - tape_w
        ppu = 3.5 * max(1.0, h / 140.0) * 0.45

        # ── backgrounds ────────────────────────────────────────────────
        p.fillRect(self.rect(), PFD_BLACK)
        p.setBrush(TAPE_BG)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(tape_x, 0, tape_w, h))

        # ── clip ───────────────────────────────────────────────────────
        p.setClipRect(QRectF(tape_x, 0, tape_w, h))

        cy = h / 2.0
        font = QFont("Consolas", max(9, int(h / 35)))
        font.setBold(True)
        p.setFont(font)
        fm = p.fontMetrics()
        half_ascent = fm.ascent() * 0.38

        # Iterate only at tick intervals
        lo = (int((spd - self.VISIBLE_RANGE_KTS) / self.MINOR_INTERVAL) - 1) * self.MINOR_INTERVAL
        hi = (int((spd + self.VISIBLE_RANGE_KTS) / self.MINOR_INTERVAL) + 2) * self.MINOR_INTERVAL

        for v in range(max(0, lo), hi + 1, self.MINOR_INTERVAL):
            y_exact = cy - (v - spd) * ppu
            if y_exact < -20 or y_exact > h + 20:
                continue

            if v % self.MAJOR_INTERVAL == 0:
                p.setPen(QPen(SCALE_WHITE, 2))
                p.drawLine(QPointF(tape_x + tape_w - 14, y_exact),
                           QPointF(tape_x + tape_w, y_exact))
                lbl = str(v)
                tw = fm.horizontalAdvance(lbl)
                # Snap text to whole pixel
                label_y = round(y_exact + half_ascent)
                p.setPen(SCALE_WHITE)
                p.drawText(int(tape_x + tape_w - 18 - tw), label_y, lbl)
            else:
                p.setPen(QPen(SCALE_WHITE, 1))
                p.drawLine(QPointF(tape_x + tape_w - 8, y_exact),
                           QPointF(tape_x + tape_w, y_exact))

        p.setClipping(False)

        # ── right edge ─────────────────────────────────────────────────
        p.setPen(QPen(SCALE_WHITE, 1.5))
        p.drawLine(QPointF(tape_x + tape_w, 0), QPointF(tape_x + tape_w, h))

        # ── pointer box ────────────────────────────────────────────────
        box_h = max(24, h * 0.06)
        box_w = tape_w * 0.92
        bx = tape_x + (tape_w - box_w) / 2.0
        by = cy - box_h / 2.0
        ptr_arrow = 10

        pointer = QPolygonF([
            QPointF(bx + box_w, cy - box_h * 0.35),
            QPointF(bx + box_w + ptr_arrow, cy),
            QPointF(bx + box_w, cy + box_h * 0.35),
        ])
        p.setPen(QPen(SCALE_WHITE, 2))
        p.setBrush(POINTER_BG)
        p.drawRect(QRectF(bx, by, box_w, box_h))
        p.drawPolygon(pointer)

        # Raw airspeed in pointer
        raw_spd = self._data.airspeed
        spd_str = f"{raw_spd:.0f}"
        f2 = QFont("Consolas", max(11, int(h / 26)))
        f2.setBold(True)
        p.setFont(f2)
        fm2 = p.fontMetrics()
        tw2 = fm2.horizontalAdvance(spd_str)
        p.setPen(TEXT_GREEN)
        p.drawText(int(bx + box_w - tw2 - 6), int(cy + fm2.ascent() * 0.38), spd_str)

        p.end()
