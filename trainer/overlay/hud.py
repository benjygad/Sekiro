"""
Enhanced HUD
=============
Full heads-up display overlay with all game data elements.

Draws player/enemy health bars, posture bars, combat stats,
coordinates, animation info, and training statistics.
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
from .widgets import HealthBar, PostureBar, TextWidget, PhaseIndicator
from ..memory.structures import WorldState

if HAS_QT:

    class EnhancedHUD:
        """
        Full enhanced HUD overlay.

        Renders:
        - Player HP/Posture/Stamina bars
        - Enemy HP/Posture bars with name
        - Combat phase indicator
        - Attack pattern info
        - Coordinates and debug info
        - Training session statistics
        """

        def __init__(self, screen_width: int = 1920, screen_height: int = 1080,
                     scale: float = 1.0):
            self.screen_width = screen_width
            self.screen_height = screen_height
            self.scale = scale
            self.enabled = True

            # Toggle individual elements
            self.show_player_bars = True
            self.show_enemy_bars = True
            self.show_combat_stats = True
            self.show_coordinates = False
            self.show_animation_debug = False
            self.show_training_stats = True

            # Create widgets
            self.player_hp = HealthBar(20, 20, 280, 18)
            self.player_posture = PostureBar(20, 42, 280, 10)
            self.enemy_hp = HealthBar(20, 70, 280, 18)
            self.enemy_posture = PostureBar(20, 92, 280, 10)

            self.phase_indicator = PhaseIndicator(20, 115)
            self.debug_text = TextWidget(20, 145, 280)
            self.stats_text = TextWidget(screen_width - 220, 20, 200)

            # Connection status
            self._connected = False
            self._connect_msg_timer = 0

        def draw(self, painter: QPainter, overlay_window,
                 world_state: Optional[WorldState] = None,
                 combat_stats: Optional[dict] = None,
                 session_stats: Optional[dict] = None,
                 connected: bool = False):
            """Draw the full HUD overlay."""
            if not self.enabled or not world_state:
                return

            s = self.scale

            # Connection status
            self._draw_connection_status(painter, connected, s)

            # Player bars
            if self.show_player_bars and world_state.player:
                player = world_state.player
                self.player_hp.draw(
                    painter,
                    player.combat.hp,
                    player.combat.hp_max,
                    label="HP",
                    scale=s
                )
                self.player_posture.draw(
                    painter,
                    player.combat.posture,
                    player.combat.posture_max,
                    label="Posture",
                    scale=s
                )

            # Enemy bars
            if self.show_enemy_bars and world_state.nearest_enemy:
                enemy = world_state.nearest_enemy
                enemy_y = int(70 * s)
                self.enemy_hp.y = enemy_y // s
                self.enemy_hp.draw(
                    painter,
                    enemy.combat.hp,
                    enemy.combat.hp_max,
                    label="Enemy HP",
                    scale=s
                )
                self.enemy_posture.y = (enemy_y + 22) // s
                self.enemy_posture.draw(
                    painter,
                    enemy.combat.posture,
                    enemy.combat.posture_max,
                    label="Enemy Posture",
                    scale=s
                )

                # Enemy name and distance
                if world_state.player:
                    dist = world_state.player.position.distance_to(
                        enemy.position
                    )
                    font = QFont("Segoe UI", int(9 * s))
                    painter.setFont(font)
                    painter.setPen(Colors.TEXT_DIM)
                    painter.drawText(
                        int(22 * s), int(65 * s),
                        f"Enemy - {dist:.1f}m"
                    )

            # Combat stats panel
            if self.show_combat_stats and combat_stats:
                self._draw_combat_stats(painter, combat_stats, s)

            # Debug info
            if self.show_animation_debug and world_state.player:
                self._draw_debug_info(painter, world_state, s)

            # Training stats (right side)
            if self.show_training_stats and session_stats:
                self._draw_training_stats(painter, session_stats, s)

        def _draw_connection_status(self, painter: QPainter, connected: bool,
                                     s: float):
            """Draw connection status indicator."""
            status_color = Colors.HP_GREEN if connected else Colors.HP_RED
            status_text = "● Connected" if connected else "○ Searching..."

            # Top-right corner
            font = QFont("Segoe UI", int(9 * s))
            painter.setFont(font)

            x = int((self.screen_width - 150) * s)
            y = int(8 * s)

            # Background pill
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(status_text) + 16
            th = metrics.height() + 8

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(20, 20, 25, 180)))
            painter.drawRoundedRect(x, y, tw, th, th // 2, th // 2)

            painter.setPen(status_color)
            painter.drawText(x + 8, y + th - 6, status_text)

        def _draw_combat_stats(self, painter: QPainter, stats: dict, s: float):
            """Draw combat statistics panel."""
            x = int(20 * s)
            y = int(140 * s)
            w = int(200 * s)

            lines = []
            lines.append(("COMBAT STATS", Colors.TEXT_GOLD))

            phase = stats.get("phase", "idle")
            lines.append((f"Phase: {phase}", Colors.TEXT_WHITE))

            total = stats.get("total_exchanges", 0)
            lines.append((f"Exchanges: {total}", Colors.TEXT_DIM))

            guard_rate = stats.get("guard_rate", 0)
            lines.append((f"Guard Rate: {guard_rate:.0f}%", Colors.TEXT_DIM))

            combo = stats.get("current_combo", 0)
            if combo > 0:
                lines.append((f"Combo: {combo}x", Colors.TEXT_GREEN))

            self.debug_text.x = 20
            self.debug_text.y = 140
            self.debug_text.draw(painter, lines, scale=s, font_size=9)

        def _draw_debug_info(self, painter: QPainter, state: WorldState,
                             s: float):
            """Draw debug/animation info."""
            player = state.player
            if not player:
                return

            x = int(20 * s)
            y = int(250 * s)

            font = QFont("Consolas", int(8 * s))
            painter.setFont(font)
            painter.setPen(Colors.TEXT_DIM)

            lines = [
                f"Pos: ({player.position.x:.1f}, {player.position.y:.1f}, {player.position.z:.1f})",
                f"Anim: {player.animation.anim_id} ({player.animation.category})",
                f"AnimT: {player.animation.anim_time:.2f}/{player.animation.anim_length:.2f}",
                f"FPS: {state.fps:.0f}",
            ]

            for i, line in enumerate(lines):
                painter.drawText(x, y + (i + 1) * int(12 * s), line)

        def _draw_training_stats(self, painter: QPainter, stats: dict,
                                  s: float):
            """Draw training statistics panel (right side)."""
            x = int((self.screen_width - 210) * s)
            y = int(35 * s)
            w = int(195 * s)

            # Panel background
            panel_h = int(180 * s)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(Colors.BG_PANEL))
            painter.drawRoundedRect(x, y, w, panel_h, 6, 6)

            # Title
            font = QFont("Segoe UI", int(10 * s))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(Colors.TEXT_GOLD)
            painter.drawText(
                QRectF(x + 8, y + 6, w - 16, 20 * s),
                Qt.AlignLeft, "📊 Training"
            )

            # Stats
            font_sm = QFont("Consolas", int(8 * s))
            painter.setFont(font_sm)

            stat_y = y + int(30 * s)
            line_h = int(14 * s)

            stat_items = [
                ("Deaths", stats.get("deaths", 0), Colors.TEXT_RED),
                ("Session", self._format_time(stats.get("session_time", 0)),
                 Colors.TEXT_DIM),
                ("Best Streak", stats.get("best_streak", 0), Colors.TEXT_GOLD),
                ("Parry Rate", f"{stats.get('parry_rate', 0):.0f}%",
                 Colors.PARRY_PERFECT),
                ("Total Parries", stats.get("total_parries", 0), Colors.TEXT_WHITE),
                ("Perfect", stats.get("perfect_parries", 0), Colors.TEXT_GOLD),
                ("Avg Offset", f"{stats.get('avg_offset', 0):.0f}ms",
                 Colors.TEXT_DIM),
            ]

            for i, (label, value, color) in enumerate(stat_items):
                ly = stat_y + i * line_h
                painter.setPen(Colors.TEXT_DIM)
                painter.drawText(x + 10, ly, label)
                painter.setPen(color)
                painter.drawText(
                    QRectF(x + 10, ly - line_h + 2, w - 20, line_h),
                    Qt.AlignRight, str(value)
                )

        def _format_time(self, seconds: float) -> str:
            """Format seconds as MM:SS."""
            m = int(seconds) // 60
            s = int(seconds) % 60
            return f"{m:02d}:{s:02d}"

else:
    class EnhancedHUD:
        def __init__(self, *a, **kw): pass
        def draw(self, *a, **kw): pass
