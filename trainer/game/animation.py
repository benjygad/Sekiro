"""
Animation Tracker
=================
Real-time character animation state tracking and analysis.

Provides attack timing windows, animation phase detection,
and prediction for the parry assistant.
"""

import time
import logging
from typing import Optional, Dict, List, Tuple
from collections import defaultdict, deque
from enum import Enum

from ..memory.structures import (
    AnimState, CharacterData, WorldState,
    AttackPhase, PerilousType
)

logger = logging.getLogger(__name__)


class ParryTiming(Enum):
    """Parry timing classification."""
    PERFECT = "perfect"      # Dead center of parry window
    EARLY = "early"          # Before perfect window
    LATE = "late"            # After perfect window
    MISS = "miss"            # Outside all windows
    PENDING = "pending"      # Attack incoming, window not yet reached


class AnimationTracker:
    """
    Tracks character animations with timing analysis.

    Maintains a database of known attack animations with their
    timing characteristics for accurate parry prediction.
    """

    # ── Known Attack Timing Database ──────────────────────
    # Maps animation category -> (windup_frames, active_frames, recovery_frames)
    # Based on frame data at 30fps (approximate)
    KNOWN_ATTACKS = {
        "attack_light": {
            "windup_ms": 300,
            "active_ms": 100,
            "recovery_ms": 200,
            "parry_window_ms": 50,
            "description": "Standard horizontal slash",
            "parry_offset_ms": 250,  # When to parry relative to windup end
        },
        "attack_heavy": {
            "windup_ms": 500,
            "active_ms": 150,
            "recovery_ms": 400,
            "parry_window_ms": 60,
            "description": "Overhead slam",
            "parry_offset_ms": 420,
        },
        "attack_thrust": {
            "windup_ms": 400,
            "active_ms": 120,
            "recovery_ms": 350,
            "parry_window_ms": 50,
            "description": "Forward thrust (Mikiri counterable)",
            "parry_offset_ms": 350,
        },
        "attack_sweep": {
            "windup_ms": 450,
            "active_ms": 200,
            "recovery_ms": 300,
            "parry_window_ms": 60,
            "description": "Low sweep (Jump counterable)",
            "parry_offset_ms": 380,
        },
        "attack_grab": {
            "windup_ms": 600,
            "active_ms": 150,
            "recovery_ms": 500,
            "parry_window_ms": 0,  # Cannot parry grabs
            "description": "Grab attack (Dodge/run away)",
            "parry_offset_ms": 0,
        },
        "attack_jump": {
            "windup_ms": 350,
            "active_ms": 200,
            "recovery_ms": 250,
            "parry_window_ms": 50,
            "description": "Jumping attack",
            "parry_offset_ms": 300,
        },
        "attack_perilous": {
            "windup_ms": 700,
            "active_ms": 200,
            "recovery_ms": 400,
            "parry_window_ms": 0,  # Cannot parry perilous
            "description": "Perilous (unblockable)",
            "parry_offset_ms": 0,
        },
    }

    def __init__(self):
        # Track individual attack instances with timing
        self._active_attacks: Dict[int, dict] = {}  # entity_addr -> attack info
        self._attack_timings: deque = deque(maxlen=200)  # Completed attack timings
        self._learned_timings: Dict[int, dict] = {}  # anim_id -> learned timings

        # Parry timing results
        self._parry_results: deque = deque(maxlen=100)

        # Configuration
        self.parry_early_ms = 150
        self.parry_perfect_ms = 50
        self.parry_late_ms = 100

    def update(self, world_state: WorldState):
        """Process animation state updates."""
        # Track enemy attacks
        if world_state.nearest_enemy:
            self._track_enemy_attack(world_state.nearest_enemy)

    def _track_enemy_attack(self, enemy: CharacterData):
        """Track an enemy's attack animation."""
        addr = enemy.address
        anim = enemy.animation

        if anim.is_attack:
            if addr not in self._active_attacks:
                # New attack started
                self._active_attacks[addr] = {
                    "start_time": time.time(),
                    "anim_id": anim.anim_id,
                    "category": anim.category,
                    "is_perilous": anim.is_perilous,
                    "predicted_hit_time": self._predict_hit_time(anim),
                    "parry_offset": self._get_parry_offset(anim),
                }
            else:
                # Update active attack progress
                attack_info = self._active_attacks[addr]
                attack_info["anim_time"] = anim.anim_time
                attack_info["anim_length"] = anim.anim_length
                attack_info["progress"] = anim.progress
        else:
            # Attack ended
            if addr in self._active_attacks:
                attack_info = self._active_attacks.pop(addr)
                attack_info["end_time"] = time.time()
                attack_info["total_duration"] = (
                    attack_info["end_time"] - attack_info["start_time"]
                )
                self._attack_timings.append(attack_info)

                # Learn timing for this specific animation
                self._learn_timing(attack_info)

    def _predict_hit_time(self, anim: AnimState) -> float:
        """Predict when the attack will land (active frame start)."""
        timing = self.KNOWN_ATTACKS.get(anim.category)
        learned = self._learned_timings.get(anim.anim_id)

        if learned:
            windup_ms = learned["windup_ms"]
        elif timing:
            windup_ms = timing["windup_ms"]
        else:
            windup_ms = 400  # Default estimate

        return time.time() + (windup_ms / 1000.0)

    def _get_parry_offset(self, anim: AnimState) -> float:
        """Get the optimal parry timing offset."""
        timing = self.KNOWN_ATTACKS.get(anim.category)
        learned = self._learned_timings.get(anim.anim_id)

        if learned:
            return learned["parry_offset_ms"] / 1000.0
        elif timing:
            return timing["parry_offset_ms"] / 1000.0
        return 0.350

    def _learn_timing(self, attack_info: dict):
        """Learn timing data from a completed attack."""
        anim_id = attack_info["anim_id"]
        duration = attack_info.get("total_duration", 0)

        if anim_id not in self._learned_timings:
            self._learned_timings[anim_id] = {
                "windup_ms": self.KNOWN_ATTACKS.get(
                    attack_info["category"], {}
                ).get("windup_ms", 400),
                "parry_offset_ms": self.KNOWN_ATTACKS.get(
                    attack_info["category"], {}
                ).get("parry_offset_ms", 350),
                "observations": 0,
                "avg_duration_ms": 0,
            }

        learned = self._learned_timings[anim_id]
        learned["observations"] += 1

        # Exponential moving average of duration
        alpha = 0.3
        if learned["avg_duration_ms"] == 0:
            learned["avg_duration_ms"] = duration * 1000
        else:
            learned["avg_duration_ms"] = (
                alpha * (duration * 1000)
                + (1 - alpha) * learned["avg_duration_ms"]
            )

        # Adjust windup estimate based on observed duration
        if learned["observations"] > 3:
            known = self.KNOWN_ATTACKS.get(attack_info["category"])
            if known:
                ratio = learned["avg_duration_ms"] / (
                    known["windup_ms"] + known["active_ms"] + known["recovery_ms"]
                )
                learned["windup_ms"] = known["windup_ms"] * ratio
                learned["parry_offset_ms"] = known["parry_offset_ms"] * ratio

    # ── Parry Timing API ──────────────────────────────────

    def get_parry_timing(self, enemy_addr: int) -> Optional[dict]:
        """
        Get current parry timing information for an active attack.

        Returns dict with:
            - time_to_hit: seconds until attack lands
            - parry_timing: ParryTiming classification
            - ms_until_perfect: ms until perfect parry window
            - progress: attack animation progress (0-1)
            - category: attack type
        """
        if enemy_addr not in self._active_attacks:
            return None

        attack = self._active_attacks[enemy_addr]
        now = time.time()
        time_to_hit = attack["predicted_hit_time"] - now
        parry_time = attack["predicted_hit_time"] - attack["parry_offset"]
        time_to_parry = parry_time - now

        # Classify timing
        if time_to_parry > self.parry_early_ms / 1000.0:
            timing = ParryTiming.PENDING
        elif time_to_parry > self.parry_perfect_ms / 1000.0:
            timing = ParryTiming.EARLY
        elif time_to_parry > -self.parry_perfect_ms / 1000.0:
            timing = ParryTiming.PERFECT
        elif time_to_parry > -self.parry_late_ms / 1000.0:
            timing = ParryTiming.LATE
        else:
            timing = ParryTiming.MISS

        return {
            "time_to_hit": time_to_hit,
            "time_to_parry": time_to_parry,
            "parry_timing": timing,
            "ms_until_perfect": time_to_parry * 1000,
            "progress": attack.get("progress", 0),
            "category": attack["category"],
            "is_perilous": attack["is_perilous"],
            "anim_id": attack["anim_id"],
        }

    def record_parry_result(self, timing: ParryTiming, ms_offset: float = 0):
        """Record a parry attempt result."""
        self._parry_results.append({
            "time": time.time(),
            "timing": timing,
            "ms_offset": ms_offset,
        })

    def get_parry_accuracy(self, last_n: int = 20) -> dict:
        """Get parry accuracy statistics over last N attempts."""
        results = list(self._parry_results)[-last_n:]
        if not results:
            return {"total": 0, "perfect": 0, "accuracy": 0}

        perfect = sum(1 for r in results if r["timing"] == ParryTiming.PERFECT)
        early = sum(1 for r in results if r["timing"] == ParryTiming.EARLY)
        late = sum(1 for r in results if r["timing"] == ParryTiming.LATE)
        miss = sum(1 for r in results if r["timing"] == ParryTiming.MISS)

        return {
            "total": len(results),
            "perfect": perfect,
            "early": early,
            "late": late,
            "miss": miss,
            "accuracy": (perfect / len(results)) * 100 if results else 0,
            "avg_offset_ms": (
                sum(r["ms_offset"] for r in results) / len(results)
                if results else 0
            ),
        }

    def get_countdown_info(self, enemy_addr: int) -> Optional[dict]:
        """
        Get countdown ring information for the overlay.

        Returns data for drawing a shrinking ring that hits
        zero at the perfect parry moment.
        """
        timing = self.get_parry_timing(enemy_addr)
        if not timing:
            return None

        # Ring shrinks from full to zero over the attack windup
        known = self.KNOWN_ATTACKS.get(timing["category"])
        total_windup = (known["windup_ms"] / 1000.0) if known else 0.4
        elapsed = total_windup - timing["time_to_hit"]
        progress = max(0, min(1, elapsed / total_windup))

        return {
            "progress": progress,
            "time_remaining": timing["time_to_hit"],
            "ms_remaining": timing["time_to_hit"] * 1000,
            "timing_class": timing["parry_timing"],
            "is_perilous": timing["is_perilous"],
            "category": timing["category"],
        }

    @property
    def active_attack_count(self) -> int:
        return len(self._active_attacks)

    @property
    def learned_animations(self) -> int:
        return len(self._learned_timings)

    def get_attack_info_display(self, enemy_addr: int) -> Optional[str]:
        """Get a human-readable attack info string."""
        if enemy_addr not in self._active_attacks:
            return None

        attack = self._active_attacks[enemy_addr]
        category = attack["category"]
        known = self.KNOWN_ATTACKS.get(category, {})
        desc = known.get("description", category)

        if attack.get("is_perilous"):
            return f"⚠ PERILOUS: {desc}"
        return f"⚔ {desc}"
