"""
comms_panel.py - Left-column communication & link monitoring panel.

Redesigned for clarity:
  1. Four compact status cards at the top (Link, Signal, Interference, Band)
  2. Two clean, well-spaced real-time scrolling charts below
  3. No visual clutter — restrained palette, proper margins, no overlapping text
"""

from __future__ import annotations
import collections
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont, QBrush,
    QLinearGradient, QPainterPath,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout
from flight_state import FlightData


# ═══════════════════════════════════════════════════════════════════════
#  Compact status card (small icon-less info tile)
# ═══════════════════════════════════════════════════════════════════════
class _StatusCard(QWidget):
    """Small labelled value card for the top of the comms column."""

    def __init__(self, label: str, unit: str = "%", parent=None):
        super().__init__(parent)
        self._label = label
        self._unit = unit
        self._value: str = "—"
        self._color = QColor(0, 200, 80)
        self.setFixedHeight(48)

    def set_value(self, value: str, color: QColor | None = None):
        self._value = value
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Card background
        p.setPen(QPen(QColor(35, 38, 44), 1))
        p.setBrush(QColor(18, 19, 23))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 4, 4)

        pad = 8

        # Label — top portion
        lf = QFont("Segoe UI", 7)
        lf.setBold(True)
        p.setFont(lf)
        p.setPen(QColor(100, 105, 115))
        p.drawText(QRectF(pad, 3, w - pad * 2, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._label)

        # Value — bottom portion
        vf = QFont("Consolas", 11)
        vf.setBold(True)
        p.setFont(vf)
        p.setPen(self._color)
        p.drawText(QRectF(pad, 20, w - pad * 2, h - 24),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._value)
        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  Scrolling real-time chart — improved margins & readability
# ═══════════════════════════════════════════════════════════════════════
class _Chart(QWidget):
    """Clean real-time scrolling line chart with proper spacing."""

    def __init__(
        self, title: str, line_color: QColor,
        warn_threshold: float | None = None,
        y_min: float = 0, y_max: float = 100,
        buf_size: int = 120, parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._color = line_color
        self._warn = warn_threshold
        self._ymin = y_min
        self._ymax = y_max
        self._buf: collections.deque[float] = collections.deque(
            [y_min] * buf_size, maxlen=buf_size
        )
        self.setMinimumHeight(90)

    def push(self, value: float):
        self._buf.append(value)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Panel background ───────────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(16, 17, 20))
        p.drawRoundedRect(QRectF(0, 0, w, h), 5, 5)
        p.setPen(QPen(QColor(32, 35, 40), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 5, 5)

        # ── Layout zones ───────────────────────────────────────────────
        header_h = 22
        y_label_w = 28
        pad_r = 8
        pad_b = 6

        chart_x = y_label_w
        chart_y = header_h
        chart_w = w - y_label_w - pad_r
        chart_h = h - header_h - pad_b

        if chart_w < 10 or chart_h < 10:
            p.end()
            return

        # ── Header: title + live value ─────────────────────────────────
        tf = QFont("Segoe UI", 8)
        tf.setBold(True)
        p.setFont(tf)
        p.setPen(QColor(110, 115, 125))
        p.drawText(QRectF(8, 2, w * 0.6, header_h),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._title)

        if self._buf:
            cur = self._buf[-1]
            p.setPen(self._color)
            p.drawText(QRectF(w * 0.5, 2, w * 0.5 - 8, header_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{cur:.0f}%")

        # ── Clip to chart area ─────────────────────────────────────────
        chart_rect = QRectF(chart_x, chart_y, chart_w, chart_h)

        # ── Grid lines (subtle) ────────────────────────────────────────
        p.setPen(QPen(QColor(28, 30, 36), 1, Qt.PenStyle.DotLine))
        for frac in (0.25, 0.5, 0.75):
            gy = chart_y + chart_h * (1 - frac)
            p.drawLine(QPointF(chart_x, gy), QPointF(chart_x + chart_w, gy))

        # ── Warning threshold ──────────────────────────────────────────
        if self._warn is not None:
            rng = max(1, self._ymax - self._ymin)
            frac_w = (self._warn - self._ymin) / rng
            wy = chart_y + chart_h * (1 - frac_w)
            p.setPen(QPen(QColor(200, 50, 50, 70), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(chart_x, wy), QPointF(chart_x + chart_w, wy))

        # ── Data fill + line ───────────────────────────────────────────
        if len(self._buf) > 1:
            n = len(self._buf)
            dx = chart_w / max(1, n - 1)
            rng = max(1e-6, self._ymax - self._ymin)
            points = []
            for i, v in enumerate(self._buf):
                frac = max(0.0, min(1.0, (v - self._ymin) / rng))
                px = chart_x + i * dx
                py = chart_y + chart_h * (1 - frac)
                points.append(QPointF(px, py))

            # Gradient fill
            fill_path = QPainterPath()
            fill_path.moveTo(points[0].x(), chart_y + chart_h)
            for pt in points:
                fill_path.lineTo(pt)
            fill_path.lineTo(points[-1].x(), chart_y + chart_h)
            fill_path.closeSubpath()

            grad = QLinearGradient(0, chart_y, 0, chart_y + chart_h)
            r, g, b = self._color.red(), self._color.green(), self._color.blue()
            grad.setColorAt(0.0, QColor(r, g, b, 35))
            grad.setColorAt(1.0, QColor(r, g, b, 3))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.setClipRect(chart_rect)
            p.drawPath(fill_path)
            p.setClipping(False)

            # Line
            p.setPen(QPen(self._color, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setClipRect(chart_rect)
            for i in range(len(points) - 1):
                p.drawLine(points[i], points[i + 1])
            p.setClipping(False)

        # ── Y-axis labels (outside chart clip) ─────────────────────────
        lf = QFont("Consolas", 7)
        p.setFont(lf)
        p.setPen(QColor(60, 65, 75))
        fm = p.fontMetrics()

        # Max at top
        p.drawText(QRectF(2, chart_y - 2, y_label_w - 4, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                   f"{self._ymax:.0f}")
        # Min at bottom
        p.drawText(QRectF(2, chart_y + chart_h - 12, y_label_w - 4, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                   f"{self._ymin:.0f}")

        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  Section header
# ═══════════════════════════════════════════════════════════════════════
class _SectionLabel(QWidget):
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
#  Full comms panel (public)
# ═══════════════════════════════════════════════════════════════════════
class CommsPanel(QWidget):
    """Left-column communication & link monitoring panel.

    Structure:
        ┌─ COMM STATUS ──────────┐
        │ Link │ Signal │         │
        │ Noise│ Band   │         │
        ├─ LINK QUALITY ─────────┤
        │ [scrolling chart]      │
        ├─ INTERFERENCE ─────────┤
        │ [scrolling chart]      │
        └────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Top: 4 compact status cards in 2×2 grid ───────────────────
        layout.addWidget(_SectionLabel("COMM STATUS"))

        grid = QGridLayout()
        grid.setContentsMargins(2, 0, 2, 0)
        grid.setSpacing(3)

        self._card_link   = _StatusCard("LINK STATUS")
        self._card_signal = _StatusCard("SIGNAL")
        self._card_noise  = _StatusCard("INTERFERENCE")
        self._card_band   = _StatusCard("BAND", unit="")

        grid.addWidget(self._card_link,   0, 0)
        grid.addWidget(self._card_signal, 0, 1)
        grid.addWidget(self._card_noise,  1, 0)
        grid.addWidget(self._card_band,   1, 1)

        layout.addLayout(grid)

        # ── Charts ─────────────────────────────────────────────────────
        layout.addWidget(_SectionLabel("TELEMETRY CHARTS"))

        self._link_chart = _Chart(
            "LINK QUALITY", QColor(0, 190, 180), warn_threshold=50,
        )
        self._noise_chart = _Chart(
            "INTERFERENCE", QColor(220, 120, 50), warn_threshold=60,
        )

        layout.addWidget(self._link_chart, stretch=1)
        layout.addWidget(self._noise_chart, stretch=1)
        layout.addStretch()

    # ── Public update ──────────────────────────────────────────────────
    def set_data(self, data: FlightData):
        # Charts
        self._link_chart.push(data.link_quality)
        self._noise_chart.push(data.interference)

        # Status cards
        lq = data.link_quality
        lq_color = QColor(0, 200, 80) if lq > 70 else (
            QColor(255, 165, 0) if lq > 40 else QColor(220, 40, 40))
        self._card_link.set_value(f"{lq:.0f}%", lq_color)

        sig = data.signal_strength
        sig_color = QColor(0, 200, 80) if sig > 60 else (
            QColor(255, 165, 0) if sig > 30 else QColor(220, 40, 40))
        self._card_signal.set_value(f"{sig:.0f}%", sig_color)

        noise = data.interference
        noise_color = QColor(0, 200, 80) if noise < 30 else (
            QColor(255, 165, 0) if noise < 60 else QColor(220, 40, 40))
        self._card_noise.set_value(f"{noise:.0f}%", noise_color)

        self._card_band.set_value(data.comm_band, QColor(0, 200, 220))
