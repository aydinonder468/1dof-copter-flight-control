"""
logo_widget.py - Branding area: extracted red emblem + "AVIS" text.

Image processing approach:
  1. Load source JPEG (dark background with red emblem + white text)
  2. Convert to ARGB32 numpy array
  3. Crop to emblem zone (upper ~55% of image)
  4. Create alpha mask: keep only RED-DOMINANT pixels
     - Pixel is red if: R > 30 AND R > G×1.3 AND R > B×1.3
     - Alpha is proportional to red intensity for smooth anti-aliased edges
  5. Near-black background pixels become fully transparent
  6. White text at bottom is excluded by the crop
  7. Render the processed emblem centred with aspect-ratio preservation
  8. Draw "AVIS" in white below the emblem using an elegant serif font
"""

from __future__ import annotations
import os
import numpy as np
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QImage, QPixmap, QColor, QFont
from PySide6.QtWidgets import QWidget


def _extract_red_emblem(src: QImage) -> QImage:
    """Isolate the red emblem from a dark-background logo JPEG.

    Pipeline:
      - Crop to upper 55 % (emblem area, discard text below)
      - For each pixel, compute red-dominance score
      - Set alpha based on that score so near-black → transparent
        and red → opaque (with smooth anti-aliased edges)
    """
    src = src.convertToFormat(QImage.Format.Format_ARGB32)
    sw, sh = src.width(), src.height()

    # Crop: keep only the top 55 % where the emblem lives
    crop_h = int(sh * 0.55)
    cropped = src.copy(0, 0, sw, crop_h)
    cw, ch = cropped.width(), cropped.height()

    # Access pixel data as numpy array
    # QImage Format_ARGB32 on little-endian: byte order is B, G, R, A
    # PySide6 on Python 3.13+ returns memoryview from .bits()
    bits = cropped.bits()
    raw = bytes(bits)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape((ch, cw, 4)).copy()

    b = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    r = arr[:, :, 2].astype(np.float32)

    # Red-dominant mask: R must be noticeably higher than G and B
    g_safe = np.maximum(g, 1.0)
    b_safe = np.maximum(b, 1.0)

    red_ratio_g = r / g_safe
    red_ratio_b = r / b_safe

    # Core red detection: R > 25 AND dominates both G and B by at least 1.3×
    is_red = (r > 25) & (red_ratio_g > 1.3) & (red_ratio_b > 1.3)

    # Compute smooth alpha:
    #   - Base alpha from red intensity (0–255)
    #   - Scale up slightly so the bright red core is fully opaque
    #   - Dimmer red-glow pixels get proportionally lower alpha → smooth edges
    alpha = np.zeros((ch, cw), dtype=np.float32)
    alpha[is_red] = np.clip(r[is_red] * 1.6, 0, 255)

    # Feather: pixels that are very weakly red get extra attenuation
    #   (prevents harsh cut-off at the glow boundary)
    weak_red = is_red & (r < 60)
    alpha[weak_red] *= 0.6

    arr[:, :, 3] = alpha.astype(np.uint8)

    # Build output QImage from the modified array
    result = QImage(arr.data, cw, ch, cw * 4,
                    QImage.Format.Format_ARGB32).copy()
    return result


class LogoWidget(QWidget):
    """Top-right branding: extracted red emblem + white AVIS text."""

    # Vertical split: emblem takes top 68 %, AVIS text takes bottom 32 %
    _EMBLEM_FRAC = 0.68

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self._emblem_pix: QPixmap | None = None
        self._load_and_process(image_path)

    def _load_and_process(self, path: str) -> None:
        if not os.path.isfile(path):
            return
        src = QImage(path)
        if src.isNull():
            return
        emblem_img = _extract_red_emblem(src)
        if not emblem_img.isNull():
            self._emblem_pix = QPixmap.fromImage(emblem_img)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        # Dark background
        p.fillRect(self.rect(), QColor(10, 10, 12))

        emblem_h = int(h * self._EMBLEM_FRAC)
        text_h = h - emblem_h

        # ── Emblem ─────────────────────────────────────────────────────
        if self._emblem_pix and not self._emblem_pix.isNull():
            pw = self._emblem_pix.width()
            ph = self._emblem_pix.height()
            img_aspect = pw / max(1, ph)

            pad = 8
            avail_w = w - pad * 2
            avail_h = emblem_h - pad

            if avail_w > 0 and avail_h > 0:
                avail_aspect = avail_w / max(1, avail_h)
                if img_aspect > avail_aspect:
                    draw_w = avail_w
                    draw_h = draw_w / img_aspect
                else:
                    draw_h = avail_h
                    draw_w = draw_h * img_aspect

                draw_x = (w - draw_w) / 2.0
                draw_y = (emblem_h - draw_h) / 2.0

                p.drawPixmap(
                    QRectF(draw_x, draw_y, draw_w, draw_h),
                    self._emblem_pix,
                    QRectF(0, 0, pw, ph),
                )

        # ── AVIS text ──────────────────────────────────────────────────
        text_y = emblem_h
        # Use Georgia or Times New Roman for an elegant serif feel;
        # fall back chain handles missing fonts gracefully.
        font = QFont("Georgia", 13)
        font.setBold(False)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5.0)
        p.setFont(font)
        p.setPen(QColor(240, 240, 245))
        p.drawText(QRectF(0, text_y, w, text_h),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "AVIS")

        p.end()
