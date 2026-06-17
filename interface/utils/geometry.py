"""
geometry.py - Reusable geometry helpers for PFD widget drawing.

Provides conversions, clamping, and common drawing primitives that are
shared across multiple custom instruments.
"""

from __future__ import annotations
import math


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to the range [lo, hi]."""
    return max(lo, min(value, hi))


def normalize_heading(deg: float) -> float:
    """Return heading normalised to [0, 360)."""
    return deg % 360.0


def heading_diff(a: float, b: float) -> float:
    """Signed shortest-path difference *a - b* on the heading circle."""
    d = (a - b) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between *a* and *b* at fraction *t*."""
    return a + (b - a) * t


def deg_to_rad(deg: float) -> float:
    return math.radians(deg)


def rad_to_deg(rad: float) -> float:
    return math.degrees(rad)
