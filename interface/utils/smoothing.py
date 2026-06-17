"""
smoothing.py - Value smoothing / interpolation helpers.

Provides exponential-moving-average (EMA) smoothing so that displayed
instrument values change fluidly instead of jumping between raw samples.
"""

from __future__ import annotations


class EMAFilter:
    """Exponential Moving Average filter for a single scalar channel.

    Parameters
    ----------
    alpha : float
        Smoothing factor in (0, 1].  Smaller values → heavier smoothing.
        Typical range for 30-60 Hz display updates: 0.10 – 0.40.
    """

    def __init__(self, alpha: float = 0.25, initial: float = 0.0) -> None:
        self._alpha = max(0.01, min(alpha, 1.0))
        self._value = initial

    @property
    def value(self) -> float:
        return self._value

    def update(self, raw: float) -> float:
        """Feed a new raw sample and return the smoothed output."""
        self._value += self._alpha * (raw - self._value)
        return self._value

    def reset(self, value: float = 0.0) -> None:
        self._value = value


class AngleEMAFilter(EMAFilter):
    """EMA filter that correctly handles angular wrap-around (0-360)."""

    def update(self, raw: float) -> float:
        diff = raw - self._value
        # Wrap difference into [-180, 180)
        while diff > 180.0:
            diff -= 360.0
        while diff < -180.0:
            diff += 360.0
        self._value += self._alpha * diff
        # Keep output in [0, 360)
        self._value %= 360.0
        return self._value
