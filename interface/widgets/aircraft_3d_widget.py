"""
aircraft_3d_widget.py - Procedural 3D Cessna 172 orientation viewer.

Uses PySide6 QOpenGLWidget with fixed-function OpenGL to render a
procedural low-poly Cessna 172 that rotates with roll/pitch/yaw.

Falls back to a QPainter placeholder if OpenGL is unavailable.
"""

from __future__ import annotations
import math
import numpy as np
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QSurfaceFormat
from PySide6.QtWidgets import QWidget, QVBoxLayout

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from OpenGL.GL import *        # noqa: F403,F401
    from OpenGL.GLU import gluPerspective
    _HAS_GL = True
except ImportError:
    _HAS_GL = False


# ═══════════════════════════════════════════════════════════════════════
#  Cessna 172 geometry (procedural, all code, no external files)
# ═══════════════════════════════════════════════════════════════════════

def _cessna_parts():
    """Return list of (vertices_Nx3x3, color_RGB) for triangulated parts."""
    parts = []

    def _box(x0, x1, y0, y1, z0, z1):
        """8 verts of an axis-aligned box → 12 triangles (36 verts)."""
        v = [
            [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
            [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
        ]
        idx = [
            (0,1,2),(0,2,3),  (4,6,5),(4,7,6),
            (0,1,5),(0,5,4),  (2,3,7),(2,7,6),
            (0,4,7),(0,7,3),  (1,5,6),(1,6,2),
        ]
        return [[v[a], v[b], v[c]] for a, b, c in idx]

    def _add(box_args, color):
        tris = _box(*box_args)
        parts.append((np.array(tris, dtype=np.float32), color))

    # Colors (R, G, B)
    white  = (0.85, 0.85, 0.90)
    wing_c = (0.78, 0.78, 0.83)
    dark   = (0.35, 0.35, 0.40)
    glass  = (0.25, 0.50, 0.85)
    red_t  = (0.75, 0.15, 0.15)
    accent = (0.15, 0.25, 0.65)

    # Fuselage main
    _add((-2.8, 2.5, -0.35, 0.35, -0.30, 0.35), white)
    # Nose cowling
    _add((2.5, 3.4, -0.28, 0.28, -0.22, 0.28), dark)
    # Spinner / prop hub
    _add((3.4, 3.7, -0.10, 0.10, -0.10, 0.10), (0.3, 0.3, 0.3))
    # Cockpit glass
    _add((1.2, 2.5, -0.34, 0.34, 0.35, 0.58), glass)
    # Rear fuselage taper
    _add((-3.8, -2.8, -0.22, 0.22, -0.18, 0.22), white)

    # Wing - high mount (Cessna style)
    _add((-0.4, 1.2, -5.5, 5.5, 0.36, 0.44), wing_c)
    # Wing tips (red/green)
    _add((-0.2, 0.6, -5.8, -5.5, 0.37, 0.42), red_t)
    _add((-0.2, 0.6,  5.5,  5.8, 0.37, 0.42), (0.15, 0.75, 0.15))

    # Wing struts
    _add((0.2, 0.35, -2.2, -2.1, -0.20, 0.38), dark)
    _add((0.2, 0.35,  2.1,  2.2, -0.20, 0.38), dark)

    # Horizontal stabilizer
    _add((-4.0, -3.0, -1.8, 1.8, 0.02, 0.08), wing_c)
    # Vertical stabilizer
    _add((-4.0, -2.8, -0.04, 0.04, 0.08, 1.35), wing_c)
    # Rudder accent
    _add((-4.0, -3.6, -0.05, 0.05, 0.5, 1.35), accent)

    # Main gear legs
    _add((0.4, 0.55, -1.2, -1.10, -0.90, -0.30), dark)
    _add((0.4, 0.55,  1.10,  1.2, -0.90, -0.30), dark)
    # Main wheels
    _add((0.3, 0.65, -1.25, -1.05, -1.05, -0.85), (0.2, 0.2, 0.2))
    _add((0.3, 0.65,  1.05,  1.25, -1.05, -0.85), (0.2, 0.2, 0.2))
    # Nose gear
    _add((2.2, 2.35, -0.06, 0.06, -0.75, -0.30), dark)
    _add((2.1, 2.45, -0.10, 0.10, -0.90, -0.75), (0.2, 0.2, 0.2))

    # Blue stripe on fuselage
    _add((-2.7, 2.5, -0.36, -0.34, -0.02, 0.12), accent)
    _add((-2.7, 2.5,  0.34,  0.36, -0.02, 0.12), accent)

    return parts


# ═══════════════════════════════════════════════════════════════════════
#  OpenGL widget
# ═══════════════════════════════════════════════════════════════════════

if _HAS_GL:
    class _GLAircraftView(QOpenGLWidget):
        def __init__(self, parent=None):
            fmt = QSurfaceFormat()
            fmt.setSamples(4)
            fmt.setDepthBufferSize(24)
            QSurfaceFormat.setDefaultFormat(fmt)
            super().__init__(parent)
            self._roll = 0.0
            self._pitch = 0.0
            self._yaw = 0.0
            self._parts = _cessna_parts()

        def set_orientation(self, roll, pitch, yaw):
            self._roll = roll
            self._pitch = pitch
            self._yaw = yaw
            self.update()

        def initializeGL(self):
            glClearColor(0.04, 0.045, 0.06, 1.0)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            glLightfv(GL_LIGHT0, GL_POSITION, [5.0, 5.0, 10.0, 0.0])
            glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.25, 0.25, 0.30, 1.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.85, 0.85, 0.90, 1.0])
            glShadeModel(GL_FLAT)
            glEnable(GL_NORMALIZE)

        def resizeGL(self, w, h):
            glViewport(0, 0, w, h)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            aspect = w / max(1, h)
            gluPerspective(35, aspect, 0.5, 200.0)
            glMatrixMode(GL_MODELVIEW)

        def paintGL(self):
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glLoadIdentity()

            # Camera: 3/4 rear view
            glTranslatef(0, 0, -22)
            glRotatef(20, 1, 0, 0)     # slight top-down
            glRotatef(-150, 0, 1, 0)   # rear-quarter view

            # Aircraft rotation: yaw → pitch → roll (ZYX aerospace)
            glRotatef(self._yaw,   0, 0, 1)
            glRotatef(self._pitch, 0, 1, 0)
            glRotatef(self._roll,  1, 0, 0)

            # Draw aircraft
            for verts, color in self._parts:
                glColor3f(*color)
                glBegin(GL_TRIANGLES)
                for tri in verts:
                    # Flat normal (cross product of edges)
                    e1 = tri[1] - tri[0]
                    e2 = tri[2] - tri[0]
                    n = np.cross(e1, e2)
                    ln = np.linalg.norm(n)
                    if ln > 1e-8:
                        n /= ln
                    glNormal3f(*n)
                    for v in tri:
                        glVertex3f(*v)
                glEnd()

            # Reference ground grid
            glDisable(GL_LIGHTING)
            glColor4f(0.15, 0.18, 0.22, 0.5)
            glBegin(GL_LINES)
            for i in range(-10, 11, 2):
                glVertex3f(i, -10, -4)
                glVertex3f(i,  10, -4)
                glVertex3f(-10, i, -4)
                glVertex3f( 10, i, -4)
            glEnd()
            glEnable(GL_LIGHTING)


# ═══════════════════════════════════════════════════════════════════════
#  Fallback QPainter placeholder
# ═══════════════════════════════════════════════════════════════════════

class _FallbackView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._roll = self._pitch = self._yaw = 0.0

    def set_orientation(self, roll, pitch, yaw):
        self._roll, self._pitch, self._yaw = roll, pitch, yaw
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(12, 14, 18))
        p.setPen(QColor(80, 85, 95))
        f = QFont("Consolas", 10)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   f"3D View requires PyOpenGL\n\n"
                   f"Roll {self._roll:.1f}°  Pitch {self._pitch:.1f}°  Yaw {self._yaw:.1f}°")
        p.end()


# ═══════════════════════════════════════════════════════════════════════
#  Public wrapper
# ═══════════════════════════════════════════════════════════════════════

class Aircraft3DWidget(QWidget):
    """3D Cessna 172 orientation viewer with titled frame."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._title = _TitleBar("3D AIRCRAFT ORIENTATION")
        layout.addWidget(self._title)

        if _HAS_GL:
            self._view = _GLAircraftView()
        else:
            self._view = _FallbackView()
        layout.addWidget(self._view, stretch=1)

        self.setStyleSheet(
            "Aircraft3DWidget { border: 1px solid #24272e; border-radius: 4px; }"
        )

    def set_data(self, data):
        self._view.set_orientation(data.roll, data.pitch, data.heading)


class _TitleBar(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(22)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(18, 19, 23))
        f = QFont("Segoe UI", 7)
        f.setBold(True)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.8)
        p.setFont(f)
        p.setPen(QColor(80, 85, 95))
        p.drawText(QRectF(0, 0, w, h - 2), Qt.AlignmentFlag.AlignCenter, self._text)
        # Bottom separator
        p.setPen(QColor(30, 33, 38))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()
