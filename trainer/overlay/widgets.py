"""
Overlay Widgets
===============
Custom-drawn UI widgets for the overlay.

All widgets draw using QPainter for smooth, anti-aliased rendering.
Designed to be lightweight and efficient for high-FPS updates.
"""

import math
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from PyQt5.QtCore import Qt, QRect, QRectF, QPointF, QPoint
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont,
        QPainterPath, QRadialGradient, QLinearGradient,
        QConicalGradient
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False

from .window import Colors


if HAS_QT:

    class HealthBar:
        """
        Animated health bar with color transitions.

        Shows current HP with a trailing "damage" effect
        that shows recent HP loss.
        """

        def __init__(self, x: int, y: int, width: int = 250, height: int = 16):
            self.x = x
            self.y = y
            self.width = width
            self.height = height
            self._display_hp = 0.0
            self._trailing_hp = 0.0
            self._last_update = time.time()

        def draw(self, painter: QPainter, current_hp: float, max_hp: float,
                 label: str = "", scale: float = 1.0):
            """Draw the health bar."""
            w = int(self.width * scale)
            h = int(self.height * scale)
            x, y = int(self.x * scale), int(self.y * scale)

            # Calculate percentage
            percent = (current_hp / max_hp * 100) if max_hp > 0 else 0

            # Animate trailing HP (damage indicator)
            now = time.time()
            dt = now - self._last_update
            self._last_update = now

            if current_hp < self._display_hp:
                self._display_hp = current_hp
            else:
                self._display_hp = current_hp

            # Trailing HP catches up slowly
            trail_speed = 50.0 * dt  # HP per second
            if self._trailing_hp > self._display_hp:
                self._trailing_hp = max(
                    self._display_hp,
                    self._trailing_hp - trail_speed
                )
            else:
                self._trailing_hp = self._display_hp

            trail_percent = (self._trailing_hp / max_hp * 100) if max_hp > 0 else 0

            # Background
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(Colors.HP_BG))
            painter.drawRoundedRect(x, y, w, h, 3, 3)

            # Trailing damage (red/orange)
            if trail_percent > percent:
                trail_w = int(w * trail_percent / 100)
                painter.setBrush(QBrush(QColor(200, 80, 40, 180)))
                painter.drawRoundedRect(x, y, trail_w, h, 3, 3)

            # Current HP bar
            hp_w = int(w * percent / 100)
            if hp_w > 0:
                color = Colors.hp_color(percent)

                # Gradient effect
                gradient = QLinearGradient(x, y, x, y + h)
                gradient.setColorAt(0, QColor(
                    min(255, color.red() + 40),
                    min(255, color.green() + 40),
                    min(255, color.blue() + 40)
                ))
                gradient.setColorAt(1, color)

                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(x, y, hp_w, h, 3, 3)

            # Border
            painter.setPen(QPen(Colors.BORDER, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(x, y, w, h, 3, 3)

            # Label
            if label:
                font = QFont("Segoe UI", int(9 * scale))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(Colors.TEXT_WHITE)
                painter.drawText(
                    x + 4, y + h - 3,
                    f"{label}: {int(current_hp)}/{int(max_hp)}"
                )


    class PostureBar:
        """
        Posture/stamina bar with break indicator.

        Shows posture accumulation with a visual warning
        when approaching posture break.
        """

        def __init__(self, x: int, y: int, width: int = 250, height: int = 10):
            self.x = x
            self.y = y
            self.width = width
            self.height = height

        def draw(self, painter: QPainter, current: float, maximum: float,
                 label: str = "", scale: float = 1.0):
            """Draw the posture bar."""
            w = int(self.width * scale)
            h = int(self.height * scale)
            x, y = int(self.x * scale), int(self.y * scale)

            percent = (current / maximum * 100) if maximum > 0 else 0

            # Background
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(Colors.POSTURE_BG))
            painter.drawRoundedRect(x, y, w, h, 2, 2)

            # Posture fill
            fill_w = int(w * min(100, percent) / 100)
            if fill_w > 0:
                if percent > 80:
                    color = Colors.POSTURE_RED
                else:
                    color = Colors.POSTURE_ORANGE

                gradient = QLinearGradient(x, y, x + w, y)
                gradient.setColorAt(0, Colors.POSTURE_ORANGE)
                gradient.setColorAt(1, color)

                painter.setBrush(QBrush(gradient))
                painter.drawRoundedRect(x, y, fill_w, h, 2, 2)

            # Break line at 100%
            painter.setPen(QPen(QColor(255, 40, 40, 200), 2))
            painter.drawLine(x + w - 1, y, x + w - 1, y + h)

            # Border
            painter.setPen(QPen(Colors.BORDER, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(x, y, w, h, 2, 2)

            # Label
            if label:
                font = QFont("Segoe UI", int(8 * scale))
                painter.setFont(font)
                painter.setPen(Colors.TEXT_DIM)
                painter.drawText(x + 4, y + h - 2, label)


    class ParryRing:
        """
        Circular countdown ring for parry timing.

        Shrinks from full to zero, hitting zero at the
        perfect parry moment. Changes color based on timing.
        """

        def __init__(self, center_x: int, center_y: int, radius: int = 60):
            self.center_x = center_x
            self.center_y = center_y
            self.radius = radius
            self._flash_alpha = 0
            self._flash_color = Colors.PARRY_PERFECT
            self._flash_decay = 3.0

        def draw(self, painter: QPainter, progress: float,
                 timing_class, scale: float = 1.0,
                 show_text: bool = True, label: str = ""):
            """
            Draw the parry timing ring.

            Args:
                progress: 0.0 (just started) to 1.0 (perfect timing)
                timing_class: ParryTiming enum value
                scale: UI scale factor
            """
            cx = int(self.center_x * scale)
            cy = int(self.center_y * scale)
            r = int(self.radius * scale)
            now = time.time()

            # Decay flash effect
            self._flash_alpha = max(0, self._flash_alpha - 255 * 3.0 / 60)

            # Outer ring (background)
            painter.setPen(QPen(Colors.PARRY_BG, 4 * scale))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(cx, cy), r, r)

            # Progress ring
            color = Colors.parry_color(timing_class)
            pen = QPen(color, 5 * scale)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)

            # Draw arc from top, clockwise
            start_angle = 90 * 16  # Qt uses 1/16th of a degree
            span_angle = int(360 * 16 * progress)
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            painter.drawArc(rect, start_angle, -span_angle)

            # Inner indicator circle
            inner_r = int(r * 0.3)
            if progress > 0.85:
                # Getting close - pulse effect
                pulse = 1.0 + 0.1 * math.sin(now * 15)
                inner_r = int(inner_r * pulse)

            painter.setPen(QPen(color, 2 * scale))
            painter.setBrush(QBrush(QColor(
                color.red(), color.green(), color.blue(), 40
            )))
            painter.drawEllipse(QPoint(cx, cy), inner_r, inner_r)

            # Center dot
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPoint(cx, cy), 4 * scale, 4 * scale)

            # Flash effect for result
            if self._flash_alpha > 0:
                flash_color = QColor(
                    self._flash_color.red(),
                    self._flash_color.green(),
                    self._flash_color.blue(),
                    int(self._flash_alpha)
                )
                painter.setBrush(QBrush(flash_color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPoint(cx, cy), r + 10, r + 10)

            # Timing text
            if show_text:
                font = QFont("Segoe UI", int(14 * scale))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(color)

                timing_text = {
                    "perfect": "PERFECT",
                    "early": "EARLY",
                    "late": "LATE",
                    "pending": f"{int(progress * 100)}%",
                    "miss": "MISS",
                }
                text = timing_text.get(
                    timing_class.value if hasattr(timing_class, 'value') else 'pending',
                    ""
                )
                if text:
                    text_rect = QRectF(
                        cx - r - 20, cy + r + 8,
                        (r + 20) * 2, 30 * scale
                    )
                    painter.drawText(text_rect, Qt.AlignCenter, text)

            # Attack label
            if label:
                font = QFont("Segoe UI", int(10 * scale))
                painter.setFont(font)
                painter.setPen(Colors.TEXT_DIM)
                text_rect = QRectF(
                    cx - r - 20, cy - r - 28,
                    (r + 20) * 2, 24 * scale
                )
                painter.drawText(text_rect, Qt.AlignCenter, label)

        def flash(self, color: QColor):
            """Trigger a flash effect."""
            self._flash_color = color
            self._flash_alpha = 200


    class TextWidget:
        """Multi-line text display with optional background."""

        def __init__(self, x: int, y: int, width: int = 300):
            self.x = x
            self.y = y
            self.width = width

        def draw(self, painter: QPainter, lines: list,
                 scale: float = 1.0, with_bg: bool = True,
                 font_size: int = 10):
            """Draw text lines."""
            x = int(self.x * scale)
            y = int(self.y * scale)
            w = int(self.width * scale)
            line_h = int((font_size + 4) * scale)

            # Background
            if with_bg:
                bg_h = line_h * len(lines) + 8
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(Colors.BG_PANEL))
                painter.drawRoundedRect(x - 4, y - 4, w + 8, bg_h + 8, 4, 4)

            font = QFont("Consolas", int(font_size * scale))
            painter.setFont(font)

            for i, line in enumerate(lines):
                if isinstance(line, tuple):
                    text, color = line
                else:
                    text, color = line, Colors.TEXT_WHITE

                painter.setPen(color)
                painter.drawText(x, y + (i + 1) * line_h, text)


    class PhaseIndicator:
        """Combat phase indicator badge."""

        PHASE_COLORS = {
            "idle": Colors.TEXT_DIM,
            "approaching": Colors.PARRY_PENDING,
            "engaged": Colors.TEXT_WHITE,
            "pressure": Colors.HP_GREEN,
            "defensive": Colors.POSTURE_ORANGE,
            "recovery": Colors.TEXT_DIM,
            "retreating": Colors.HP_RED,
        }

        def __init__(self, x: int, y: int):
            self.x = x
            self.y = y

        def draw(self, painter: QPainter, phase: str, scale: float = 1.0):
            """Draw phase badge."""
            x = int(self.x * scale)
            y = int(self.y * scale)

            color = self.PHASE_COLORS.get(phase, Colors.TEXT_DIM)

            # Badge background
            font = QFont("Segoe UI", int(9 * scale))
            font.setBold(True)
            painter.setFont(font)

            text = phase.upper()
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(text) + 16
            text_h = metrics.height() + 8

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(
                color.red(), color.green(), color.blue(), 40
            )))
            painter.drawRoundedRect(x, y, text_w, text_h, 4, 4)

            painter.setPen(QPen(color, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(x, y, text_w, text_h, 4, 4)

            painter.setPen(color)
            painter.drawText(
                QRect(x, y, text_w, text_h),
                Qt.AlignCenter, text
            )

else:
    # Stub classes when Qt not available
    class HealthBar:
        def __init__(self, *a, **kw): pass
        def draw(self, *a, **kw): pass

    class PostureBar:
        def __init__(self, *a, **kw): pass
        def draw(self, *a, **kw): pass

    class ParryRing:
        def __init__(self, *a, **kw): pass
        def draw(self, *a, **kw): pass
        def flash(self, *a, **kw): pass

    class TextWidget:
        def __init__(self, *a, **kw): pass
        def draw(self, *a, **kw): pass

    class PhaseIndicator:
        def __init__(self, *a, **kw): pass
        def draw(self, *a, **kw): pass
