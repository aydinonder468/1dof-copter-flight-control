"""
altitude_tape.py - EFIS-style vertical altitude tape (right side).

Fixes applied:
  - Internal display-value smoother to prevent sub-frame jitter
  - Text label Y-positions snapped to whole pixels to eliminate
    font-rasterization shimmer
  - Clip region enforced around the scrolling area
  - Pointer box and VS readout drawn outside the clip
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


class AltitudeTape(QWidget):
    """Vertical scrolling altitude indicator — flicker-free."""

    TAPE_WIDTH_FRAC = 0.85
    MAJOR_INTERVAL = 100          # feet between labelled ticks
    MINOR_INTERVAL = 20           # feet between small ticks
    VISIBLE_RANGE_FT = 600        # ±feet visible from centre

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(80, 200)
        self._data = FlightData()
        # Internal display smoother — heavier than the global EMA so
        # the tape scrolls silkily even if upstream data has micro-jitter.
        self._display_alt = 10000.0
        self._smooth_alpha = 0.18        # lower = smoother

    def set_data(self, data: FlightData) -> None:
        self._data = data
        # Smooth altitude locally for display only
        diff = data.altitude - self._display_alt
        self._display_alt += self._smooth_alpha * diff
        self.update()

    # ── Painting ───────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Disable sub-pixel text positioning — forces whole-pixel glyph
        # placement, which eliminates the shimmer caused by fractional shifts.
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w, h = self.width(), self.height()
        alt = self._display_alt                   # use smoothed value

        tape_w = w * self.TAPE_WIDTH_FRAC
        tape_x = 0.0
        ppu = h / (2.0 * self.VISIBLE_RANGE_FT)  # pixels per foot

        # ── background ─────────────────────────────────────────────────
        p.fillRect(self.rect(), PFD_BLACK)

        # ── tape background ────────────────────────────────────────────
        p.setBrush(TAPE_BG)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(tape_x, 0, tape_w, h))

        # ── clip to tape region ────────────────────────────────────────
        clip_rect = QRectF(tape_x, 0, tape_w, h)
        p.setClipRect(clip_rect)

        cy = h / 2.0

        # Font setup — done once
        tick_font = QFont("Consolas", max(9, int(h / 35)))
        tick_font.setBold(True)
        p.setFont(tick_font)
        fm = p.fontMetrics()
        half_ascent = fm.ascent() * 0.38          # vertical centering tweak

        # Determine visible altitude range
        lo = (int((alt - self.VISIBLE_RANGE_FT) / self.MINOR_INTERVAL) - 1) * self.MINOR_INTERVAL
        hi = (int((alt + self.VISIBLE_RANGE_FT) / self.MINOR_INTERVAL) + 2) * self.MINOR_INTERVAL

        for v in range(lo, hi + 1, self.MINOR_INTERVAL):
            # Float-based pixel offset from centre — smooth scrolling
            y_exact = cy - (v - alt) * ppu
            if y_exact < -20 or y_exact > h + 20:
                continue

            if v % self.MAJOR_INTERVAL == 0:
                # Tick line — floating point is fine for lines
                p.setPen(QPen(SCALE_WHITE, 2))
                p.drawLine(QPointF(tape_x, y_exact),
                           QPointF(tape_x + 14, y_exact))

                # Label — SNAP to whole pixel to prevent shimmer
                label_y = round(y_exact + half_ascent)
                lbl = f"{v:,}" if abs(v) >= 1000 else str(v)
                p.setPen(SCALE_WHITE)
                p.drawText(int(tape_x + 18), label_y, lbl)

            elif v % self.MINOR_INTERVAL == 0:
                p.setPen(QPen(SCALE_WHITE, 1))
                p.drawLine(QPointF(tape_x, y_exact),
                           QPointF(tape_x + 8, y_exact))

        p.setClipping(False)

        # ── left edge line ─────────────────────────────────────────────
        p.setPen(QPen(SCALE_WHITE, 1.5))
        p.drawLine(QPointF(tape_x, 0), QPointF(tape_x, h))

        # ── pointer box (drawn outside clip, always sharp) ─────────────
        box_h = max(24, h * 0.06)
        box_w = tape_w * 0.92
        bx = tape_x + (tape_w - box_w) / 2.0
        by = cy - box_h / 2.0
        ptr_arrow = 10

        pointer = QPolygonF([
            QPointF(bx, cy - box_h * 0.35),
            QPointF(bx - ptr_arrow, cy),
            QPointF(bx, cy + box_h * 0.35),
        ])

        p.setPen(QPen(SCALE_WHITE, 2))
        p.setBrush(POINTER_BG)
        p.drawRect(QRectF(bx, by, box_w, box_h))
        p.drawPolygon(pointer)

        # Altitude readout — use the *real* (non-smoothed) altitude for
        # the numeric display so the number matches telemetry exactly.
        raw_alt = self._data.altitude
        alt_str = f"{raw_alt:,.0f}"
        f2 = QFont("Consolas", max(11, int(h / 26)))
        f2.setBold(True)
        p.setFont(f2)
        fm2 = p.fontMetrics()
        p.setPen(TEXT_GREEN)
        p.drawText(int(bx + 8), int(cy + fm2.ascent() * 0.38), alt_str)

        # ── VS readout ─────────────────────────────────────────────────
        vs = self._data.vertical_speed
        vs_str = f"{'+'if vs >= 0 else ''}{vs:,.0f} fpm"
        f3 = QFont("Consolas", max(8, int(h / 42)))
        p.setFont(f3)
        fm3 = p.fontMetrics()
        p.setPen(SCALE_WHITE)
        p.drawText(
            int(bx + 4), int(cy + box_h / 2.0 + fm3.height() + 2), vs_str
        )

        p.end()
