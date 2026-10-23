"""
Parry Display
=============
Main parry assistant visual display component.

Combines the parry ring, attack info, and timing feedback
into a cohesive overlay element.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PyQt5.QtCore import Qt, QRectF, QPoint
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont,
        QPainterPath, QLinearGradient
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False

from .window import Colors
from .widgets import ParryRing, TextWidget


if HAS_QT:

    class ParryDisplay:
        """
        Complete parry assistant display.

        Shows:
        - Countdown ring for timing
        - Attack type and name
        - Timing result (PERFECT/EARLY/LATE)
        - Accuracy statistics
        """

        def __init__(self, x: int = 100, y: int = 400, scale: float = 1.0):
            self.x = x
            self.y = y
            self.scale = scale
            self.enabled = True

            # Sub-widgets
            self.parry_ring = ParryRing(80, 80, radius=55)
            self.info_text = TextWidget(10, 170, width=160)
            self.stats_text = TextWidget(10, 240, width=160)

            # Result flash state
            self._result_text = ""
            self._result_color = Colors.TEXT_DIM
            self._result_alpha = 0
            self._result_timer = 0

            # Perilous warning
            self._perilous_alpha = 0
            self._perilous_text = ""

        def draw(self, painter: QPainter, overlay_window,
                 parry_timing: Optional[dict] = None,
                 accuracy_stats: Optional[dict] = None,
                 suggestion: Optional[str] = None):
            """
            Draw the complete parry display.

            Args:
                painter: QPainter to draw with
                overlay_window: Reference to overlay window for size
                parry_timing: Current parry timing data from AnimationTracker
                accuracy_stats: Parry accuracy statistics
                suggestion: Combat suggestion text
            """
            if not self.enabled:
                return

            s = self.scale
            x = int(self.x * s)
            y = int(self.y * s)

            # Panel background
            panel_w = int(180 * s)
            panel_h = int(320 * s)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(Colors.BG_PANEL))
            painter.drawRoundedRect(x, y, panel_w, panel_h, 8, 8)

            # Title
            font = QFont("Segoe UI", int(11 * s))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(Colors.TEXT_GOLD)
            painter.drawText(
                QRectF(x + 10, y + 8, panel_w - 20, 24 * s),
                Qt.AlignCenter, "⚔ PARRY ASSISTANT"
            )

            # Divider
            painter.setPen(QPen(Colors.BORDER, 1))
            painter.drawLine(x + 10, y + 32 * s, x + panel_w - 10, y + 32 * s)

            # Draw parry ring
            if parry_timing:
                from ..game.animation import ParryTiming

                ring_cx = x + panel_w // 2
                ring_cy = y + int(105 * s)
                ring_r = int(50 * s)

                # Update ring position
                self.parry_ring.center_x = ring_cx
                self.parry_ring.center_y = ring_cy
                self.parry_ring.radius = ring_r

                timing_class = parry_timing.get("parry_timing", ParryTiming.PENDING)
                progress = parry_timing.get("progress", 0)
                category = parry_timing.get("category", "")
                is_perilous = parry_timing.get("is_perilous", False)

                # Attack label
                attack_label = ""
                if is_perilous:
                    attack_label = "⚠ PERILOUS"
                elif category:
                    attack_label = category.replace("attack_", "").upper()

                self.parry_ring.draw(
                    painter, progress, timing_class,
                    scale=1.0, label=attack_label
                )

                # Timing info below ring
                time_to_hit = parry_timing.get("time_to_hit", 0)
                font_sm = QFont("Consolas", int(9 * s))
                painter.setFont(font_sm)
                painter.setPen(Colors.TEXT_DIM)
                painter.drawText(
                    QRectF(x + 10, y + int(165 * s), panel_w - 20, 16 * s),
                    Qt.AlignCenter,
                    f"Hit in: {max(0, time_to_hit):.3f}s"
                )

                # Perilous warning flash
                if is_perilous:
                    self._perilous_alpha = 200
                    self._perilous_text = "⚠ PERILOUS - CANNOT PARRY ⚠"
                else:
                    self._perilous_alpha = max(0, self._perilous_alpha - 5)

                if self._perilous_alpha > 0:
                    font_warn = QFont("Segoe UI", int(10 * s))
                    font_warn.setBold(True)
                    painter.setFont(font_warn)
                    painter.setPen(QColor(
                        255, 40, 40, int(self._perilous_alpha)
                    ))
                    painter.drawText(
                        QRectF(x, y + int(185 * s), panel_w, 20 * s),
                        Qt.AlignCenter,
                        self._perilous_text
                    )
            else:
                # No active attack - show idle state
                font_idle = QFont("Segoe UI", int(11 * s))
                painter.setFont(font_idle)
                painter.setPen(Colors.TEXT_DIM)
                painter.drawText(
                    QRectF(x + 10, y + int(80 * s), panel_w - 20, 60 * s),
                    Qt.AlignCenter,
                    "Waiting for\nenemy attack..."
                )

            # Suggestion text
            if suggestion:
                font_sug = QFont("Segoe UI", int(9 * s))
                font_sug.setBold(True)
                painter.setFont(font_sug)
                painter.setPen(Colors.TEXT_GREEN)
                painter.drawText(
                    QRectF(x + 10, y + int(210 * s), panel_w - 20, 30 * s),
                    Qt.AlignCenter | Qt.TextWordWrap,
                    suggestion
                )

            # Accuracy stats
            if accuracy_stats:
                stats_y = y + int(245 * s)
                font_stat = QFont("Consolas", int(8 * s))
                painter.setFont(font_stat)

                total = accuracy_stats.get("total", 0)
                perfect = accuracy_stats.get("perfect", 0)
                accuracy = accuracy_stats.get("accuracy", 0)

                # Accuracy bar
                bar_x = x + 15
                bar_y = stats_y
                bar_w = panel_w - 30
                bar_h = int(8 * s)

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(Colors.HP_BG))
                painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 2, 2)

                if accuracy > 0:
                    fill_w = int(bar_w * accuracy / 100)
                    color = Colors.PARRY_PERFECT if accuracy > 70 else (
                        Colors.POSTURE_ORANGE if accuracy > 40 else Colors.HP_RED
                    )
                    painter.setBrush(QBrush(color))
                    painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 2, 2)

                painter.setPen(Colors.TEXT_DIM)
                painter.drawText(
                    QRectF(x + 10, stats_y + bar_h + 4, panel_w - 20, 14 * s),
                    Qt.AlignCenter,
                    f"Accuracy: {accuracy:.0f}% ({perfect}/{total})"
                )

                # Streak info
                early = accuracy_stats.get("early", 0)
                late = accuracy_stats.get("late", 0)
                painter.drawText(
                    QRectF(x + 10, stats_y + bar_h + 20 * s, panel_w - 20, 14 * s),
                    Qt.AlignCenter,
                    f"Early: {early} | Late: {late}"
                )

            # Result flash overlay
            if self._result_alpha > 0:
                font_result = QFont("Segoe UI", int(24 * s))
                font_result.setBold(True)
                painter.setFont(font_result)
                painter.setPen(QColor(
                    self._result_color.red(),
                    self._result_color.green(),
                    self._result_color.blue(),
                    int(self._result_alpha)
                ))
                painter.drawText(
                    QRectF(x, y + int(60 * s), panel_w, 40 * s),
                    Qt.AlignCenter,
                    self._result_text
                )
                self._result_alpha = max(0, self._result_alpha - 8)

        def show_result(self, text: str, color: QColor):
            """Show a result flash (PERFECT, EARLY, LATE, etc.)."""
            self._result_text = text
            self._result_color = color
            self._result_alpha = 255

else:
    class ParryDisplay:
        def __init__(self, *a, **kw): pass
        def draw(self, *a, **kw): pass
        def show_result(self, *a, **kw): pass
