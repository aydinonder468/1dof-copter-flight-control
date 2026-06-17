"""
colors.py - Centralized avionics color palette for the Full-HD PFD dashboard.
"""

from PySide6.QtGui import QColor

# ── Background ────────────────────────────────────────────────────────────────
PFD_BLACK = QColor(10, 10, 10)
PANEL_BG  = QColor(18, 18, 22)
CARD_BG   = QColor(22, 24, 28)

# ── Attitude indicator ────────────────────────────────────────────────────────
SKY_BLUE       = QColor(0, 100, 210)
SKY_BLUE_LIGHT = QColor(30, 140, 255)
GROUND_BROWN   = QColor(140, 90, 30)
GROUND_DARK    = QColor(90, 55, 15)
HORIZON_WHITE  = QColor(255, 255, 255)

# ── Scale / tape colors ──────────────────────────────────────────────────────
SCALE_WHITE    = QColor(255, 255, 255)
SCALE_CYAN     = QColor(0, 255, 255)
SCALE_DIM      = QColor(140, 140, 140)
TAPE_BG        = QColor(20, 20, 20, 200)
TAPE_BG_SOLID  = QColor(20, 20, 20)
POINTER_BG     = QColor(10, 10, 10)

# ── Mode annunciator ─────────────────────────────────────────────────────────
MODE_GREEN     = QColor(0, 220, 80)
MODE_DIM       = QColor(80, 80, 80)
MODE_BOX_BG    = QColor(25, 25, 25)
MODE_BOX_ACTIVE_BG = QColor(15, 50, 20)

# ── Aircraft reference / FD ───────────────────────────────────────────────────
AIRCRAFT_YELLOW = QColor(255, 210, 0)
AIRCRAFT_MAGENTA = QColor(255, 0, 200)

# ── General UI ────────────────────────────────────────────────────────────────
TEXT_WHITE     = QColor(255, 255, 255)
TEXT_GREEN     = QColor(0, 220, 80)
WARNING_AMBER  = QColor(255, 165, 0)
ERROR_RED      = QColor(220, 40, 40)

# ── Telemetry box accent colors ──────────────────────────────────────────────
ACCENT_BLUE    = QColor(40, 140, 255)
ACCENT_GREEN   = QColor(0, 200, 100)
ACCENT_ORANGE  = QColor(255, 160, 40)
ACCENT_PURPLE  = QColor(160, 80, 255)
ACCENT_CYAN    = QColor(0, 220, 220)
ACCENT_MAGENTA = QColor(220, 50, 180)

# ── Status colors ────────────────────────────────────────────────────────────
STATUS_HEALTHY = QColor(0, 200, 80)
STATUS_DEGRADED = QColor(255, 165, 0)
STATUS_ERROR   = QColor(220, 40, 40)
STATUS_INACTIVE = QColor(80, 80, 80)
