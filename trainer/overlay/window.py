"""
Transparent Overlay Window
===========================
Frameless, click-through, always-on-top window using PyQt5.

Renders over the game at the monitor's native refresh rate.
All drawing goes through QPainter for smooth, anti-aliased graphics.
"""

import sys
import logging
import threading
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)

try:
    from PyQt5.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QLabel,
        QFrame, QHBoxLayout, QPushButton, QSlider,
        QCheckBox, QGroupBox, QSpinBox, QComboBox,
        QGraphicsDropShadowEffect, QSizePolicy
    )
    from PyQt5.QtCore import (
        Qt, QTimer, QPoint, QRect, QSize, pyqtSignal, QThread
    )
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QFontDatabase,
        QPainterPath, QRadialGradient, QLinearGradient,
        QPalette, QIcon, QPixmap
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    logger.warning("PyQt5 not available - overlay will not render")


# ── Color Palette ──────────────────────────────────────────

class Colors:
    """Sekiro-themed color palette."""

    # Core colors
    BG_TRANSPARENT = QColor(0, 0, 0, 0)
    BG_DARK = QColor(15, 15, 20, 200)
    BG_PANEL = QColor(20, 22, 30, 180)
    BG_HIGHLIGHT = QColor(30, 32, 45, 220)

    # Health & resource bars
    HP_GREEN = QColor(80, 200, 80)
    HP_YELLOW = QColor(220, 200, 60)
    HP_RED = QColor(220, 60, 60)
    HP_BG = QColor(40, 40, 40, 150)

    POSTURE_ORANGE = QColor(240, 160, 40)
    POSTURE_RED = QColor(240, 60, 40)
    POSTURE_BG = QColor(40, 30, 20, 150)

    STAMINA_GREEN = QColor(60, 180, 120)
    STAMINA_BG = QColor(20, 40, 30, 150)

    # Parry timing colors
    PARRY_PERFECT = QColor(255, 215, 0)      # Gold
    PARRY_EARLY = QColor(60, 200, 60)        # Green
    PARRY_LATE = QColor(220, 60, 60)         # Red
    PARRY_PENDING = QColor(100, 140, 220)    # Blue
    PARRY_MISS = QColor(80, 80, 80)          # Gray
    PARRY_BG = QColor(40, 40, 50, 100)

    # Text
    TEXT_WHITE = QColor(240, 240, 245)
    TEXT_DIM = QColor(160, 160, 170)
    TEXT_GOLD = QColor(255, 215, 0)
    TEXT_RED = QColor(255, 80, 80)
    TEXT_GREEN = QColor(80, 255, 120)

    # Attack types
    ATTACK_LIGHT = QColor(180, 180, 220)
    ATTACK_HEAVY = QColor(255, 140, 60)
    ATTACK_THRUST = QColor(100, 180, 255)
    ATTACK_SWEEP = QColor(180, 100, 255)
    ATTACK_GRAB = QColor(255, 80, 80)
    ATTACK_PERILOUS = QColor(255, 40, 40)

    # UI elements
    BORDER = QColor(60, 65, 80, 180)
    ACCENT = QColor(200, 160, 80)
    SHADOW = QColor(0, 0, 0, 120)

    @classmethod
    def hp_color(cls, percent: float) -> QColor:
        """Get HP bar color based on percentage."""
        if percent > 60:
            return cls.HP_GREEN
        elif percent > 30:
            return cls.HP_YELLOW
        return cls.HP_RED

    @classmethod
    def parry_color(cls, timing_class) -> QColor:
        """Get color for parry timing class."""
        from ..game.animation import ParryTiming
        colors = {
            ParryTiming.PERFECT: cls.PARRY_PERFECT,
            ParryTiming.EARLY: cls.PARRY_EARLY,
            ParryTiming.LATE: cls.PARRY_LATE,
            ParryTiming.PENDING: cls.PARRY_PENDING,
            ParryTiming.MISS: cls.PARRY_MISS,
        }
        return colors.get(timing_class, cls.TEXT_DIM)

    @classmethod
    def attack_color(cls, category: str) -> QColor:
        """Get color for attack category."""
        colors = {
            "attack_light": cls.ATTACK_LIGHT,
            "attack_heavy": cls.ATTACK_HEAVY,
            "attack_thrust": cls.ATTACK_THRUST,
            "attack_sweep": cls.ATTACK_SWEEP,
            "attack_grab": cls.ATTACK_GRAB,
            "attack_perilous": cls.ATTACK_PERILOUS,
        }
        return colors.get(category, cls.TEXT_WHITE)


if HAS_QT:

    class OverlayWindow(QWidget):
        """
        Transparent overlay window that renders on top of the game.

        Features:
        - Frameless, always-on-top
        - Click-through (doesn't intercept mouse)
        - Custom QPainter drawing
        - High-refresh-rate updates
        """

        # Signals for thread-safe updates
        update_signal = pyqtSignal()

        def __init__(self, opacity: float = 0.85, scale: float = 1.0):
            super().__init__()
            self._opacity = opacity
            self._scale = scale
            self._draw_callbacks: List[Callable] = []
            self._update_timer: Optional[QTimer] = None
            self._is_visible = True

            self._setup_window()
            self._setup_timer()

            # Connect signal for thread-safe updates
            self.update_signal.connect(self.update)

        def _setup_window(self):
            """Configure window flags for transparent overlay."""
            flags = (
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.Tool
                | Qt.WindowTransparentForInput
            )
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.setAttribute(Qt.WA_ShowWithoutActivating)

            # Make it click-through on Windows
            if sys.platform == "win32":
                self._set_click_through()

            # Set geometry to cover entire screen
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.geometry()
                self.setGeometry(geo)
            else:
                self.setGeometry(0, 0, 1920, 1080)

        def _set_click_through(self):
            """Set window to be click-through on Windows."""
            try:
                import ctypes
                from ctypes import wintypes

                hwnd = int(self.winId())
                GWL_EXSTYLE = -20
                WS_EX_LAYERED = 0x80000
                WS_EX_TRANSPARENT = 0x20

                user32 = ctypes.windll.user32
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                )
            except Exception as e:
                logger.warning(f"Could not set click-through: {e}")

        def _setup_timer(self):
            """Set up the render update timer."""
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self.update)
            # ~120 FPS update rate
            self._update_timer.start(8)

        def add_draw_callback(self, callback: Callable):
            """Register a callback to be called during paintEvent."""
            self._draw_callbacks.append(callback)

        def remove_draw_callback(self, callback: Callable):
            """Remove a draw callback."""
            try:
                self._draw_callbacks.remove(callback)
            except ValueError:
                pass

        def request_update(self):
            """Thread-safe update request."""
            self.update_signal.emit()

        def paintEvent(self, event):
            """Custom painting - calls all registered draw callbacks."""
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            # Set overall opacity
            painter.setOpacity(self._opacity)

            # Call all draw callbacks
            for callback in self._draw_callbacks:
                try:
                    callback(painter, self)
                except Exception as e:
                    logger.error(f"Draw callback error: {e}", exc_info=True)

            painter.end()

        def toggle_visibility(self):
            """Toggle overlay visibility."""
            self._is_visible = not self._is_visible
            if self._is_visible:
                self.show()
            else:
                self.hide()

        @property
        def visible(self) -> bool:
            return self._is_visible

        @visible.setter
        def visible(self, value: bool):
            self._is_visible = value
            if value:
                self.show()
            else:
                self.hide()

        @property
        def scale(self) -> float:
            return self._scale

        @scale.setter
        def scale(self, value: float):
            self._scale = max(0.5, min(2.0, value))

        @property
        def overlay_opacity(self) -> float:
            return self._opacity

        @overlay_opacity.setter
        def overlay_opacity(self, value: float):
            self._opacity = max(0.1, min(1.0, value))

        def closeEvent(self, event):
            """Handle window close."""
            if self._update_timer:
                self._update_timer.stop()
            event.accept()


    class OverlayApp:
        """
        Manages the PyQt5 application and overlay window.

        Runs the Qt event loop in a separate thread so it
        doesn't block the main application.
        """

        def __init__(self):
            self._app: Optional[QApplication] = None
            self._window: Optional[OverlayWindow] = None
            self._thread: Optional[QThread] = None
            self._running = False

        def start(self, opacity: float = 0.85, scale: float = 1.0) -> Optional[OverlayWindow]:
            """Start the overlay application."""
            if self._running:
                return self._window

            self._thread = OverlayThread(opacity, scale)
            self._thread.window_ready.connect(self._on_window_ready)
            self._thread.start()
            self._running = True
            return None  # Window available after signal

        def _on_window_ready(self, window: OverlayWindow):
            self._window = window

        @property
        def window(self) -> Optional[OverlayWindow]:
            return self._window

        def stop(self):
            """Stop the overlay application."""
            if self._thread:
                self._thread.quit()
                self._thread.wait(3000)
            self._running = False


    class OverlayThread(QThread):
        """Thread that runs the Qt event loop."""

        window_ready = pyqtSignal(object)

        def __init__(self, opacity: float = 0.85, scale: float = 1.0):
            super().__init__()
            self._opacity = opacity
            self._scale = scale
            self._window: Optional[OverlayWindow] = None

        def run(self):
            # Create QApplication in this thread
            self._app = QApplication.instance() or QApplication(sys.argv)
            self._window = OverlayWindow(self._opacity, self._scale)
            self._window.show()
            self.window_ready.emit(self._window)
            self._app.exec_()

else:
    # Stub implementations when PyQt5 is not available
    class OverlayWindow:
        def __init__(self, *args, **kwargs):
            logger.warning("Overlay window not available (PyQt5 missing)")
        def add_draw_callback(self, cb): pass
        def remove_draw_callback(self, cb): pass
        def request_update(self): pass
        def toggle_visibility(self): pass
        def show(self): pass
        def hide(self): pass

    class OverlayApp:
        def __init__(self): pass
        def start(self, *args, **kwargs): return None
        def stop(self): pass
        @property
        def window(self): return None
