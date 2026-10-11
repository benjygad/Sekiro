"""
Combat Analyzer
===============
High-level combat analysis and pattern recognition.

Detects combat phases, combo sequences, and provides
strategic suggestions based on game state.
"""

import time
import logging
from typing import Optional, List, Dict, Tuple
from collections import deque, defaultdict
from enum import Enum

from ..memory.structures import (
    WorldState, CharacterData, CombatState, AnimState,
    AttackPhase, PerilousType
)

logger = logging.getLogger(__name__)


class CombatPhase(Enum):
    """High-level combat phases."""
    IDLE = "idle"
    APPROACHING = "approaching"
    ENGAGED = "engaged"
    PRESSURE = "pressure"        # Player is attacking
    DEFENSIVE = "defensive"      # Player is defending
    RECOVERY = "recovery"        # Between exchanges
    RETREATING = "retreating"    # Player is backing off


class CombatAnalyzer:
    """
    Analyzes combat patterns and provides strategic insights.
    """

    def __init__(self):
        self._combat_phase = CombatPhase.IDLE
        self._phase_history: deque = deque(maxlen=200)
        self._exchange_log: deque = deque(maxlen=100)
        self._combo_counter = 0
        self._last_exchange_time = 0.0
        self._posture_exchange: List[dict] = []

        # Enemy behavior tracking
        self._enemy_attack_sequences: Dict[int, List[str]] = defaultdict(list)
        self._current_sequence: List[str] = []
        self._sequence_timeout = 3.0

    def update(self, world_state: WorldState):
        """Analyze current combat state."""
        self._update_combat_phase(world_state)
        self._track_exchanges(world_state)
        self._track_combos(world_state)

    def _update_combat_phase(self, state: WorldState):
        """Determine current combat phase."""
        player = state.player
        enemy = state.nearest_enemy

        if not player or not enemy:
            new_phase = CombatPhase.IDLE
        elif not enemy.combat.is_alive:
            new_phase = CombatPhase.IDLE
        else:
            distance = player.position.distance_to(enemy.position)

            if distance > 8.0:
                new_phase = CombatPhase.APPROACHING
            elif distance < 2.0:
                if player.combat.is_attacking:
                    new_phase = CombatPhase.PRESSURE
                elif player.combat.is_guarding:
                    new_phase = CombatPhase.DEFENSIVE
                elif enemy.animation.is_attack:
                    new_phase = CombatPhase.DEFENSIVE
                else:
                    new_phase = CombatPhase.ENGAGED
            elif distance < 5.0:
                if player.combat.is_attacking:
                    new_phase = CombatPhase.PRESSURE
                else:
                    new_phase = CombatPhase.ENGAGED
            else:
                new_phase = CombatPhase.APPROACHING

        if new_phase != self._combat_phase:
            self._phase_history.append({
                "time": time.time(),
                "from": self._combat_phase,
                "to": new_phase,
            })
            self._combat_phase = new_phase

    def _track_exchanges(self, state: WorldState):
        """Track combat exchanges (hit/parry/dodge sequences)."""
        if not state.player or not state.nearest_enemy:
            return

        enemy = state.nearest_enemy
        now = time.time()

        # Detect when enemy starts and stops attacking
        if enemy.animation.is_attack:
            if enemy.animation.attack_phase == AttackPhase.ACTIVE:
                # Active hit frame - this is an exchange window
                if now - self._last_exchange_time > 0.5:
                    self._last_exchange_time = now
                    self._exchange_log.append({
                        "time": now,
                        "enemy_anim": enemy.animation.anim_id,
                        "enemy_category": enemy.animation.category,
                        "player_guarding": state.player.combat.is_guarding,
                        "distance": state.player.position.distance_to(
                            enemy.position
                        ),
                    })

    def _track_combos(self, state: WorldState):
        """Track player attack combos."""
        if not state.player:
            return

        if state.player.animation.is_attack:
            if state.player.animation.attack_phase == AttackPhase.WINDUP:
                self._combo_counter += 1
        else:
            if self._combo_counter > 0:
                # Combo ended
                if time.time() - self._last_exchange_time > 2.0:
                    self._combo_counter = 0

    @property
    def combat_phase(self) -> CombatPhase:
        return self._combat_phase

    def get_suggestion(self, world_state: WorldState) -> Optional[str]:
        """
        Get a strategic suggestion based on current combat state.

        Returns a short text suggestion, or None.
        """
        if not world_state.player or not world_state.nearest_enemy:
            return None

        enemy = world_state.nearest_enemy
        player = world_state.player
        distance = player.position.distance_to(enemy.position)

        # Perilous attack incoming
        if enemy.animation.is_perilous and enemy.animation.is_attack:
            category = enemy.animation.category
            if "thrust" in category:
                return "Mikiri Counter! (Forward + Deflect)"
            elif "sweep" in category:
                return "Jump over the sweep!"
            elif "grab" in category:
                return "Dodge or run away!"
            return "Perilous! Counter appropriately!"

        # Enemy posture nearly broken
        if enemy.combat.posture_percent > 80:
            return "Enemy posture breaking! Keep pressure!"

        # Player posture high
        if player.combat.posture_percent > 70:
            return "Your posture is high! Create distance!"

        # Low HP
        if player.combat.hp_percent < 25:
            return "Low HP! Play defensively and heal!"

        # Enemy attacking
        if enemy.animation.is_attack and not enemy.animation.is_perilous:
            return "Deflect incoming attack!"

        return None

    def get_enemy_combo_info(self) -> dict:
        """Get info about enemy's current attack combo."""
        recent = [
            e for e in self._exchange_log
            if time.time() - e["time"] < 5.0
        ]

        if not recent:
            return {"count": 0, "attacks": []}

        attacks = [e["enemy_category"] for e in recent]
        return {
            "count": len(recent),
            "attacks": attacks,
            "sequence": " → ".join(a.replace("attack_", "") for a in attacks),
        }

    def get_combat_stats(self) -> dict:
        """Get combat statistics for the current session."""
        total_exchanges = len(self._exchange_log)
        guarded_exchanges = sum(
            1 for e in self._exchange_log if e.get("player_guarding")
        )

        return {
            "total_exchanges": total_exchanges,
            "guarded_exchanges": guarded_exchanges,
            "guard_rate": (
                (guarded_exchanges / total_exchanges * 100)
                if total_exchanges > 0 else 0
            ),
            "current_combo": self._combo_counter,
            "phase": self._combat_phase.value,
            "avg_exchange_interval": self._get_avg_exchange_interval(),
        }

    def _get_avg_exchange_interval(self) -> float:
        """Average time between exchanges in seconds."""
        if len(self._exchange_log) < 2:
            return 0.0

        intervals = []
        log = list(self._exchange_log)
        for i in range(1, len(log)):
            intervals.append(log[i]["time"] - log[i-1]["time"])

        return sum(intervals) / len(intervals) if intervals else 0.0
