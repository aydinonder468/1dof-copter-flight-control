"""
heading_tape.py - EFIS-style horizontal heading tape (bottom).

Draws a scrolling horizontal compass tape with major/minor ticks,
cardinal labels, and a centred pointer triangle for the current heading.
Handles 359→0 wrap-around seamlessly.
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
    SCALE_CYAN,
    TAPE_BG,
    POINTER_BG,
    TEXT_GREEN,
    AIRCRAFT_YELLOW,
)


_CARDINAL = {
    0: "N", 45: "NE", 90: "E", 135: "SE",
    180: "S", 225: "SW", 270: "W", 315: "NW",
}


class HeadingTape(QWidget):
    """Horizontal scrolling heading/compass tape."""

    MAJOR_INTERVAL = 10       # degrees between labelled ticks
    MINOR_INTERVAL = 5        # degrees between small ticks
    VISIBLE_RANGE = 60        # ±degrees visible from centre

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 50)
        self._data = FlightData()

    def set_data(self, data: FlightData) -> None:
        self._data = data
        self.update()

    # ── Painting ───────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        hdg = self._data.heading % 360.0

        tape_h = h * 0.70
        tape_y = 0.0
        ppd = w / (2.0 * self.VISIBLE_RANGE)   # pixels per degree

        # ── background ─────────────────────────────────────────────────────
        painter.fillRect(self.rect(), PFD_BLACK)

        # ── tape bg ────────────────────────────────────────────────────────
        painter.setBrush(TAPE_BG)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(0, tape_y, w, tape_h))

        # ── clip ───────────────────────────────────────────────────────────
        painter.setClipRect(QRectF(0, tape_y, w, tape_h))

        cx = w / 2.0
        font = QFont("Consolas", max(9, int(h / 5.5)))
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        lo = int(hdg - self.VISIBLE_RANGE) - self.MAJOR_INTERVAL
        hi = int(hdg + self.VISIBLE_RANGE) + self.MAJOR_INTERVAL

        for v in range(lo, hi + 1):
            nv = v % 360
            if nv < 0:
                nv += 360
            # Only draw at tick intervals
            if v % self.MINOR_INTERVAL != 0:
                continue

            diff = v - hdg
            x = cx + diff * ppd
            if x < -30 or x > w + 30:
                continue

            is_major = v % self.MAJOR_INTERVAL == 0
            tick_h = tape_h * 0.35 if is_major else tape_h * 0.18
            tick_w = 2.0 if is_major else 1.0

            painter.setPen(QPen(SCALE_WHITE, tick_w))
            painter.drawLine(QPointF(x, tape_y + tape_h), QPointF(x, tape_y + tape_h - tick_h))

            if is_major:
                lbl = _CARDINAL.get(nv, f"{nv:03d}")
                tw = fm.horizontalAdvance(lbl)
                color = SCALE_CYAN if nv in _CARDINAL else SCALE_WHITE
                painter.setPen(color)
                painter.drawText(
                    QPointF(x - tw / 2.0, tape_y + tape_h - tick_h - 4), lbl
                )

        painter.setClipping(False)

        # ── bottom edge ────────────────────────────────────────────────────
        painter.setPen(QPen(SCALE_WHITE, 1.5))
        painter.drawLine(QPointF(0, tape_y + tape_h), QPointF(w, tape_y + tape_h))

        # ── centre pointer triangle ────────────────────────────────────────
        tri_h = h * 0.22
        tri_w = h * 0.18
        pts = QPolygonF([
            QPointF(cx, tape_y + tape_h + 2),
            QPointF(cx - tri_w / 2, tape_y + tape_h + 2 + tri_h),
            QPointF(cx + tri_w / 2, tape_y + tape_h + 2 + tri_h),
        ])
        painter.setPen(QPen(AIRCRAFT_YELLOW, 2))
        painter.setBrush(AIRCRAFT_YELLOW)
        painter.drawPolygon(pts)

        # ── digital heading readout ────────────────────────────────────────
        hdg_str = f"{hdg:05.1f}°"
        f2 = QFont("Consolas", max(10, int(h / 4.8)))
        f2.setBold(True)
        painter.setFont(f2)
        fm2 = painter.fontMetrics()
        tw2 = fm2.horizontalAdvance(hdg_str)
        box_w = tw2 + 14
        box_h = fm2.height() + 4
        bx = cx - box_w / 2
        by = tape_y + tape_h + 2 + tri_h + 2

        painter.setPen(QPen(SCALE_WHITE, 1.5))
        painter.setBrush(POINTER_BG)
        painter.drawRect(QRectF(bx, by, box_w, box_h))
        painter.setPen(TEXT_GREEN)
        painter.drawText(QPointF(bx + 7, by + fm2.ascent() + 1), hdg_str)

        painter.end()
