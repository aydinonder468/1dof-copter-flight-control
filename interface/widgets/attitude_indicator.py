"""
attitude_indicator.py - EFIS-style artificial horizon / attitude indicator.

All drawing is performed with QPainter — no images or external assets.
The widget shows sky/ground halves, a pitch ladder, roll-arc scale,
and a fixed aircraft reference symbol.

Rendering pipeline
------------------
1. Translate painter to widget centre
2. Clip to a circular region
3. Rotate by -roll
4. Shift vertically by pitch × (pixels-per-degree)
5. Draw oversized sky & ground rectangles
6. Draw pitch ladder lines & labels
7. Restore clip / transform
8. Draw roll arc, roll pointer, and fixed aircraft symbol
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainterPath,
    QPolygonF,
    QConicalGradient,
)
from PySide6.QtWidgets import QWidget

from flight_state import FlightData
from utils.colors import (
    SKY_BLUE,
    SKY_BLUE_LIGHT,
    GROUND_BROWN,
    GROUND_DARK,
    HORIZON_WHITE,
    AIRCRAFT_YELLOW,
    SCALE_WHITE,
    SCALE_DIM,
    PFD_BLACK,
)


class AttitudeIndicator(QWidget):
    """Custom-drawn EFIS attitude indicator widget."""

    # ── Pitch-ladder layout ────────────────────────────────────────────────
    PITCH_LINE_INTERVAL = 5          # degrees between ladder lines
    PITCH_RANGE = 30                 # draw ±30 ° on the ladder
    MAJOR_PITCH_INTERVAL = 10        # wider lines + labels every 10 °

    # ── Roll-arc tick layout ───────────────────────────────────────────────
    ROLL_TICKS = [0, 10, 20, 30, 45, 60, 90]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._data = FlightData()

    # ── Public update ──────────────────────────────────────────────────────
    def set_data(self, data: FlightData) -> None:
        self._data = data
        self.update()

    # ── Painting ───────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        side = min(w, h)
        cx, cy = w / 2.0, h / 2.0
        radius = side / 2.0 - 4          # small margin
        ppd = side / 45.0                 # pixels per degree of pitch

        # ── 1. background ──────────────────────────────────────────────────
        painter.fillRect(self.rect(), PFD_BLACK)

        # ── 2. clip to circular area ───────────────────────────────────────
        clip_path = QPainterPath()
        clip_path.addEllipse(QPointF(cx, cy), radius, radius)
        painter.setClipPath(clip_path)

        # ── 3. save, translate to centre, rotate by -roll ──────────────────
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._data.roll)

        pitch_offset = self._data.pitch * ppd   # positive pitch → horizon moves down

        self._draw_sky_ground(painter, radius, pitch_offset)
        self._draw_horizon_line(painter, radius, pitch_offset)
        self._draw_pitch_ladder(painter, radius, pitch_offset, ppd)

        painter.restore()

        # ── 4. draw roll arc (in widget space, not rotated) ────────────────
        painter.setClipPath(clip_path)
        self._draw_roll_arc(painter, cx, cy, radius)

        # ── 5. draw fixed aircraft symbol ──────────────────────────────────
        painter.setClipping(False)
        self._draw_aircraft_symbol(painter, cx, cy, side)

        # ── 6. outer bezel ring ────────────────────────────────────────────
        painter.setClipping(False)
        pen = QPen(QColor(50, 50, 50), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        painter.end()

    # ── Sky / Ground ───────────────────────────────────────────────────────
    def _draw_sky_ground(self, p: QPainter, r: float, pitch_off: float) -> None:
        big = r * 4  # oversize so rotation doesn't expose corners

        # Sky gradient
        sky_grad = QLinearGradient(0, -big + pitch_off, 0, pitch_off)
        sky_grad.setColorAt(0.0, SKY_BLUE)
        sky_grad.setColorAt(1.0, SKY_BLUE_LIGHT)
        p.setBrush(QBrush(sky_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(-big, -big + pitch_off, 2 * big, big))

        # Ground gradient
        gnd_grad = QLinearGradient(0, pitch_off, 0, big + pitch_off)
        gnd_grad.setColorAt(0.0, GROUND_BROWN)
        gnd_grad.setColorAt(1.0, GROUND_DARK)
        p.setBrush(QBrush(gnd_grad))
        p.drawRect(QRectF(-big, pitch_off, 2 * big, big))

    # ── Horizon line ───────────────────────────────────────────────────────
    def _draw_horizon_line(self, p: QPainter, r: float, pitch_off: float) -> None:
        pen = QPen(HORIZON_WHITE, 2)
        p.setPen(pen)
        big = r * 4
        p.drawLine(QPointF(-big, pitch_off), QPointF(big, pitch_off))

    # ── Pitch ladder ───────────────────────────────────────────────────────
    def _draw_pitch_ladder(
        self, p: QPainter, r: float, pitch_off: float, ppd: float
    ) -> None:
        font = QFont("Consolas", max(8, int(r / 14)))
        font.setBold(True)
        p.setFont(font)

        step = self.PITCH_LINE_INTERVAL
        for deg in range(-self.PITCH_RANGE, self.PITCH_RANGE + 1, step):
            if deg == 0:
                continue
            y = pitch_off - deg * ppd
            is_major = deg % self.MAJOR_PITCH_INTERVAL == 0
            half_w = r * 0.28 if is_major else r * 0.14
            pen_w = 2.0 if is_major else 1.2

            p.setPen(QPen(HORIZON_WHITE, pen_w))
            p.drawLine(QPointF(-half_w, y), QPointF(half_w, y))

            # Small downward ticks at line ends
            tick_len = r * 0.04
            if deg < 0:
                # Below horizon – ticks point up (toward horizon)
                p.drawLine(QPointF(-half_w, y), QPointF(-half_w, y - tick_len))
                p.drawLine(QPointF(half_w, y), QPointF(half_w, y - tick_len))
            else:
                # Above horizon – ticks point down (toward horizon)
                p.drawLine(QPointF(-half_w, y), QPointF(-half_w, y + tick_len))
                p.drawLine(QPointF(half_w, y), QPointF(half_w, y + tick_len))

            if is_major:
                lbl = str(abs(deg))
                fm = p.fontMetrics()
                tw = fm.horizontalAdvance(lbl)
                th = fm.ascent()
                p.setPen(HORIZON_WHITE)
                p.drawText(QPointF(-half_w - tw - 6, y + th / 2.5), lbl)
                p.drawText(QPointF(half_w + 6, y + th / 2.5), lbl)

    # ── Roll arc & ticks ───────────────────────────────────────────────────
    def _draw_roll_arc(self, p: QPainter, cx: float, cy: float, r: float) -> None:
        arc_r = r * 0.92
        pen = QPen(SCALE_WHITE, 1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Arc from -60 to +60 (Qt angles in 1/16th degree, 0 = 3 o'clock)
        # We want the arc centred at the top: span from 150° to 30° in QPainter's system
        start_angle = int(30 * 16)
        span_angle = int(120 * 16)
        rect = QRectF(cx - arc_r, cy - arc_r, 2 * arc_r, 2 * arc_r)
        p.drawArc(rect, start_angle, span_angle)

        # Ticks
        for deg in self.ROLL_TICKS:
            for sign in (-1, 1):
                angle_rad = math.radians(90 + sign * deg)
                is_major = deg in (0, 30, 60, 90)
                tick_len = r * 0.07 if is_major else r * 0.04
                tick_w = 2.0 if is_major else 1.2
                p.setPen(QPen(SCALE_WHITE, tick_w))
                x0 = cx + arc_r * math.cos(angle_rad)
                y0 = cy - arc_r * math.sin(angle_rad)
                x1 = cx + (arc_r - tick_len) * math.cos(angle_rad)
                y1 = cy - (arc_r - tick_len) * math.sin(angle_rad)
                p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

        # Roll pointer (small triangle at top, rotated by roll)
        roll_rad = math.radians(self._data.roll)
        ptr_r = arc_r + r * 0.01
        ptr_cx = cx - ptr_r * math.sin(roll_rad)
        ptr_cy = cy - ptr_r * math.cos(roll_rad)
        tri_size = r * 0.05
        # Build triangle pointing inward
        angle_base = math.radians(self._data.roll)
        pts = QPolygonF([
            QPointF(
                ptr_cx + tri_size * math.sin(angle_base + math.pi),
                ptr_cy + tri_size * math.cos(angle_base + math.pi),
            ),
            QPointF(
                ptr_cx + tri_size * 0.6 * math.sin(angle_base + math.pi / 2),
                ptr_cy + tri_size * 0.6 * math.cos(angle_base + math.pi / 2),
            ),
            QPointF(
                ptr_cx + tri_size * 0.6 * math.sin(angle_base - math.pi / 2),
                ptr_cy + tri_size * 0.6 * math.cos(angle_base - math.pi / 2),
            ),
        ])
        p.setPen(QPen(AIRCRAFT_YELLOW, 1))
        p.setBrush(AIRCRAFT_YELLOW)
        p.drawPolygon(pts)

    # ── Fixed aircraft reference symbol ────────────────────────────────────
    def _draw_aircraft_symbol(
        self, p: QPainter, cx: float, cy: float, side: float
    ) -> None:
        pen = QPen(AIRCRAFT_YELLOW, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        wing = side * 0.16
        inner = side * 0.025

        # Left wing
        p.drawLine(QPointF(cx - wing, cy), QPointF(cx - inner, cy))
        p.drawLine(QPointF(cx - inner, cy), QPointF(cx - inner, cy + side * 0.02))

        # Right wing
        p.drawLine(QPointF(cx + inner, cy), QPointF(cx + wing, cy))
        p.drawLine(QPointF(cx + inner, cy), QPointF(cx + inner, cy + side * 0.02))

        # Centre dot
        p.setBrush(AIRCRAFT_YELLOW)
        p.drawEllipse(QPointF(cx, cy), 4, 4)

        # Small top triangle (fixed reference at 12 o'clock on the roll arc)
        p.setPen(QPen(SCALE_WHITE, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        tr_h = side * 0.04
        tr_w = side * 0.03
        top_y = cy - (side / 2.0 - 4) * 0.92 - side * 0.01
        pts = QPolygonF([
            QPointF(cx, top_y + tr_h),
            QPointF(cx - tr_w / 2, top_y),
            QPointF(cx + tr_w / 2, top_y),
        ])
        p.drawPolygon(pts)
