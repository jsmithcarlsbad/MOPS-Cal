"""
3D viewer for MT-102 orientation display.

Displays the MT-102 model centered within colored axis rings (X=red, Y=green, Z=blue),
with a dark grid background. Model rotation is driven by X, Y, Z slider values (0–359°).
"""

import time
from pathlib import Path

try:
    import pyvista as pv
    from pyvistaqt import QtInteractor
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

# Fade-in duration (seconds) when orientation changes
ORIENTATION_FADE_SECONDS = 1.0


RING_RADIUS = 1.0
RING_RESOLUTION = 64
AXIS_LENGTH = 1.2
MODEL_SCALE = 0.3  # Scale model to fit inside rings


def _make_ring(radius: float, plane: str, color: str) -> "pv.PolyData":
    """Create a circular ring in the given plane (xy, xz, yz)."""
    circle = pv.Circle(radius=radius, resolution=RING_RESOLUTION)
    if plane == "yz":  # Red - rotation around X
        circle.rotate_y(90)
    elif plane == "xz":  # Green - rotation around Y
        circle.rotate_x(90)
    # xy stays as-is for blue - rotation around Z
    return circle


def _make_placeholder_model() -> "pv.PolyData":
    """Placeholder sphere until MT-102 model is provided."""
    sphere = pv.Sphere(radius=0.15, theta_resolution=24, phi_resolution=24)
    sphere.point_data.clear()
    return sphere


class Viewer3D(QWidget):
    """
    3D viewer with colored axis rings and centered MT-102 model.
    Model rotation (degrees) is set via set_rotation(x, y, z).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        if not PYVISTA_AVAILABLE:
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("3D viewer requires pyvista and pyvistaqt.\n"
                                   "Install: pip install pyvista pyvistaqt"))
            self._plotter = None
            self._model_actor = None
            self._model_mesh = None
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = QtInteractor(self)
        layout.addWidget(self._plotter)

        self._model_actor = None
        self._model_mesh = None
        self._rotation = (0.0, 0.0, 0.0)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_start_rotation = None
        self._anim_target_rotation = None
        self._anim_start_time = 0.0

        self._setup_scene()

    def _setup_scene(self) -> None:
        if self._plotter is None:
            return
        p = self._plotter
        p.set_background("#2b2b2b")
        p.add_floor("-z", color="#1a1a1a", show_edges=True)
        p.add_axes()
        p.view_xy()
        p.reset_camera()

        # Colored axis rings (sphere-like structure around center)
        ring_xy = _make_ring(RING_RADIUS, "xy", "blue")
        ring_xz = _make_ring(RING_RADIUS, "xz", "green")
        ring_yz = _make_ring(RING_RADIUS, "yz", "red")

        p.add_mesh(ring_xy, color="blue", line_width=2, render_lines_as_tubes=True)
        p.add_mesh(ring_xz, color="green", line_width=2, render_lines_as_tubes=True)
        p.add_mesh(ring_yz, color="red", line_width=2, render_lines_as_tubes=True)

        # Central model: load from models/MT102_Case.obj if present, else placeholder
        model_path = Path(__file__).resolve().parent / "models" / "MT102_Case.obj"
        self.load_model(model_path)

        p.reset_camera()
        p.view_isometric()

    def load_model(self, path: Path | str | None) -> None:
        """
        Load MT-102 model from file (STL, OBJ, etc.) or use placeholder if path is None.
        """
        if self._plotter is None:
            return
        if self._model_actor is not None:
            self._plotter.remove_actor(self._model_actor)

        if path and Path(path).exists():
            try:
                self._model_mesh = pv.read(str(path))
            except Exception:
                self._model_mesh = _make_placeholder_model()
        else:
            self._model_mesh = _make_placeholder_model()

        # Scale and center
        self._model_mesh.scale([MODEL_SCALE] * 3, inplace=True)
        cx, cy, cz = self._model_mesh.center
        self._model_mesh.translate([-cx, -cy, -cz], inplace=True)

        self._model_actor = self._plotter.add_mesh(
            self._model_mesh,
            color="#F1E5AC",
            smooth_shading=True,
            metallic=0.3,
            roughness=0.7,
        )
        self._apply_rotation()

    def set_rotation_immediate(self, x_deg: float, y_deg: float, z_deg: float) -> None:
        """Set model rotation in degrees immediately (no animation). Use when driving from ramp."""
        self._rotation = (float(x_deg), float(y_deg), float(z_deg))
        self._apply_rotation()

    def set_rotation(self, x_deg: float, y_deg: float, z_deg: float) -> None:
        """Set model rotation in degrees. Fades in over 1 second when orientation changes."""
        target = (float(x_deg), float(y_deg), float(z_deg))
        if not hasattr(self, "_anim_timer") or self._anim_timer is None:
            self._rotation = target
            self._apply_rotation()
            return

        def _target_eq(a: tuple, b: tuple) -> bool:
            return (abs(a[0] - b[0]) < 0.1 and abs(a[1] - b[1]) < 0.1 and abs(a[2] - b[2]) < 0.1)

        # Already at target — no change
        if _target_eq(self._rotation, target):
            return
        # Already animating to this target — let it continue
        if self._anim_target_rotation is not None and _target_eq(self._anim_target_rotation, target):
            return

        self._anim_timer.stop()
        self._anim_start_rotation = self._rotation
        self._anim_target_rotation = target
        self._anim_start_time = time.monotonic()
        self._anim_timer.start(20)  # ~50 Hz

    def _anim_tick(self) -> None:
        """Interpolate rotation toward target over ORIENTATION_FADE_SECONDS."""
        elapsed = time.monotonic() - self._anim_start_time
        t = min(1.0, elapsed / ORIENTATION_FADE_SECONDS)
        # Ease-in-out for smoother feel
        t_smooth = t * t * (3.0 - 2.0 * t)
        s = self._anim_start_rotation
        g = self._anim_target_rotation

        def lerp_angle(a: float, b: float, u: float) -> float:
            diff = ((b - a + 540.0) % 360.0) - 180.0
            return a + diff * u

        rx = lerp_angle(s[0], g[0], t_smooth)
        ry = lerp_angle(s[1], g[1], t_smooth)
        rz = lerp_angle(s[2], g[2], t_smooth)
        self._rotation = (rx, ry, rz)
        self._apply_rotation()
        if t >= 1.0:
            self._anim_timer.stop()
            self._rotation = self._anim_target_rotation
            self._apply_rotation()

    def _apply_rotation(self) -> None:
        if self._model_actor is None or self._model_mesh is None:
            return
        rx, ry, rz = self._rotation
        mesh = self._model_mesh.copy()
        mesh.rotate_x(rx, inplace=True)
        mesh.rotate_y(ry, inplace=True)
        mesh.rotate_z(rz, inplace=True)
        self._plotter.remove_actor(self._model_actor)
        self._model_actor = self._plotter.add_mesh(
            mesh,
            color="#F1E5AC",
            smooth_shading=True,
            metallic=0.3,
            roughness=0.7,
        )
