"""
Parry Trainer
=============
Core parry training assistant with timing analysis and feedback.

Provides real-time parry timing guidance, accuracy tracking,
and progressive difficulty adjustment.
"""

import time
import logging
from typing import Optional, Dict, List
from collections import deque
from enum import Enum

from ..memory.structures import WorldState, AttackPhase
from ..game.animation import AnimationTracker, ParryTiming

logger = logging.getLogger(__name__)


class TrainerMode(Enum):
    """Training difficulty modes."""
    PASSIVE = "passive"          # Just shows timing, no scoring
    GUIDED = "guided"            # Shows timing with feedback
    CHALLENGE = "challenge"      # Reduced timing windows
    MASTER = "master"            # Minimal UI, tightest windows


class ParryTrainer:
    """
    Perfect parry training assistant.

    Features:
    - Real-time parry timing visualization
    - Accuracy tracking and feedback
    - Progressive difficulty scaling
    - Attack pattern prediction
    - Session statistics
    """

    # Timing windows by difficulty (in milliseconds)
    DIFFICULTY_WINDOWS = {
        TrainerMode.PASSIVE: {
            "perfect": 80,
            "early": 200,
            "late": 150,
        },
        TrainerMode.GUIDED: {
            "perfect": 50,
            "early": 150,
            "late": 100,
        },
        TrainerMode.CHALLENGE: {
            "perfect": 30,
            "early": 100,
            "late": 60,
        },
        TrainerMode.MASTER: {
            "perfect": 15,
            "early": 60,
            "late": 40,
        },
    }

    def __init__(self, anim_tracker: AnimationTracker):
        self.anim_tracker = anim_tracker
        self.mode = TrainerMode.GUIDED
        self.enabled = True

        # Scoring
        self._current_streak = 0
        self._best_streak = 0
        self._total_attempts = 0
        self._perfect_count = 0
        self._early_count = 0
        self._late_count = 0
        self._miss_count = 0

        # Recent results for trend analysis
        self._recent_results: deque = deque(maxlen=50)

        # Auto-difficulty adjustment
        self._auto_difficulty = True
        self._difficulty_timer = time.time()

        # Sound feedback
        self._sound_enabled = True

        # Callbacks
        self._on_perfect_callback = None
        self._on_result_callback = None

    def set_callbacks(self, on_perfect=None, on_result=None):
        """Set callback functions for events."""
        self._on_perfect_callback = on_perfect
        self._on_result_callback = on_result

    def update(self, world_state: WorldState):
        """Process a game state update."""
        if not self.enabled:
            return

        # Update animation tracker
        self.anim_tracker.update(world_state)

        # Auto-difficulty adjustment
        if self._auto_difficulty:
            self._adjust_difficulty()

    def process_parry_input(self, enemy_addr: int) -> Optional[dict]:
        """
        Process a parry input (player pressed deflect).

        Returns timing analysis result.
        """
        if not self.enabled:
            return None

        timing = self.anim_tracker.get_parry_timing(enemy_addr)
        if not timing:
            return None

        now = time.time()
        time_to_parry = timing["time_to_parry"]
        windows = self.DIFFICULTY_WINDOWS[self.mode]

        # Classify the timing
        if abs(time_to_parry * 1000) <= windows["perfect"]:
            classification = ParryTiming.PERFECT
        elif time_to_parry > 0:
            classification = ParryTiming.EARLY
        elif abs(time_to_parry * 1000) <= windows["late"]:
            classification = ParryTiming.LATE
        else:
            classification = ParryTiming.MISS

        # Record result
        result = {
            "time": now,
            "timing": classification,
            "ms_offset": time_to_parry * 1000,
            "category": timing["category"],
            "is_perilous": timing["is_perilous"],
        }

        self._record_result(result)
        self.anim_tracker.record_parry_result(
            classification, time_to_parry * 1000
        )

        # Fire callbacks
        if classification == ParryTiming.PERFECT and self._on_perfect_callback:
            self._on_perfect_callback(result)
        if self._on_result_callback:
            self._on_result_callback(result)

        return result

    def _record_result(self, result: dict):
        """Record a parry result and update stats."""
        self._recent_results.append(result)
        self._total_attempts += 1

        timing = result["timing"]
        if timing == ParryTiming.PERFECT:
            self._perfect_count += 1
            self._current_streak += 1
            if self._current_streak > self._best_streak:
                self._best_streak = self._current_streak
        elif timing == ParryTiming.EARLY:
            self._early_count += 1
            self._current_streak = 0
        elif timing == ParryTiming.LATE:
            self._late_count += 1
            self._current_streak = 0
        else:
            self._miss_count += 1
            self._current_streak = 0

    def _adjust_difficulty(self):
        """Auto-adjust difficulty based on recent performance."""
        now = time.time()
        if now - self._difficulty_timer < 30:  # Check every 30 seconds
            return

        if len(self._recent_results) < 10:
            return

        # Calculate recent accuracy
        recent = list(self._recent_results)[-20:]
        perfect = sum(1 for r in recent if r["timing"] == ParryTiming.PERFECT)
        accuracy = perfect / len(recent)

        # Adjust difficulty
        if accuracy > 0.8 and self.mode != TrainerMode.MASTER:
            # Doing well - increase difficulty
            modes = list(TrainerMode)
            idx = modes.index(self.mode)
            if idx < len(modes) - 1:
                self.mode = modes[idx + 1]
                logger.info(f"Difficulty increased to {self.mode.value}")
        elif accuracy < 0.3 and self.mode != TrainerMode.PASSIVE:
            # Struggling - decrease difficulty
            modes = list(TrainerMode)
            idx = modes.index(self.mode)
            if idx > 0:
                self.mode = modes[idx - 1]
                logger.info(f"Difficulty decreased to {self.mode.value}")

        self._difficulty_timer = now

    def get_timing_data(self, world_state: WorldState) -> Optional[dict]:
        """Get current parry timing data for the overlay."""
        if not self.enabled or not world_state.nearest_enemy:
            return None

        enemy_addr = world_state.nearest_enemy.address
        return self.anim_tracker.get_parry_timing(enemy_addr)

    def get_countdown_data(self, world_state: WorldState) -> Optional[dict]:
        """Get countdown ring data for the overlay."""
        if not self.enabled or not world_state.nearest_enemy:
            return None

        enemy_addr = world_state.nearest_enemy.address
        return self.anim_tracker.get_countdown_info(enemy_addr)

    def get_accuracy_stats(self) -> dict:
        """Get current accuracy statistics."""
        return {
            "total": self._total_attempts,
            "perfect": self._perfect_count,
            "early": self._early_count,
            "late": self._late_count,
            "miss": self._miss_count,
            "accuracy": (
                (self._perfect_count / self._total_attempts * 100)
                if self._total_attempts > 0 else 0
            ),
            "current_streak": self._current_streak,
            "best_streak": self._best_streak,
            "mode": self.mode.value,
            "avg_offset_ms": (
                sum(r["ms_offset"] for r in self._recent_results)
                / len(self._recent_results)
                if self._recent_results else 0
            ),
        }

    def get_trend(self) -> str:
        """Get performance trend (improving/stable/declining)."""
        if len(self._recent_results) < 10:
            return "learning"

        results = list(self._recent_results)
        first_half = results[:len(results)//2]
        second_half = results[len(results)//2:]

        first_acc = sum(
            1 for r in first_half if r["timing"] == ParryTiming.PERFECT
        ) / len(first_half)
        second_acc = sum(
            1 for r in second_half if r["timing"] == ParryTiming.PERFECT
        ) / len(second_half)

        diff = second_acc - first_acc
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        return "stable"

    def reset_session(self):
        """Reset all session statistics."""
        self._current_streak = 0
        self._total_attempts = 0
        self._perfect_count = 0
        self._early_count = 0
        self._late_count = 0
        self._miss_count = 0
        self._recent_results.clear()
        logger.info("Training session reset")

    @property
    def timing_windows(self) -> dict:
        return self.DIFFICULTY_WINDOWS[self.mode]
