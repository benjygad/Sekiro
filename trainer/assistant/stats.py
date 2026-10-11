"""
Training Statistics
===================
Tracks and persists training progress over sessions.

Records parry accuracy, death counts, boss attempts,
and generates progress reports.
"""

import json
import time
import logging
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class TrainingSession:
    """A single training session with start/end and metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.deaths = 0
        self.total_parries = 0
        self.perfect_parries = 0
        self.early_parries = 0
        self.late_parries = 0
        self.missed_parries = 0
        self.best_streak = 0
        self.current_streak = 0
        self.boss_fights: Dict[str, dict] = defaultdict(lambda: {
            "attempts": 0,
            "wins": 0,
            "best_accuracy": 0,
            "total_parries": 0,
        })
        self.parry_offsets: List[float] = []

    @property
    def duration(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def accuracy(self) -> float:
        if self.total_parries == 0:
            return 0.0
        return (self.perfect_parries / self.total_parries) * 100

    @property
    def avg_offset(self) -> float:
        if not self.parry_offsets:
            return 0.0
        return sum(self.parry_offsets) / len(self.parry_offsets)

    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "deaths": self.deaths,
            "total_parries": self.total_parries,
            "perfect_parries": self.perfect_parries,
            "early_parries": self.early_parries,
            "late_parries": self.late_parries,
            "missed_parries": self.missed_parries,
            "best_streak": self.best_streak,
            "accuracy": self.accuracy,
            "avg_offset": self.avg_offset,
            "boss_fights": dict(self.boss_fights),
        }


class TrainingStats:
    """
    Comprehensive training statistics manager.

    Tracks progress across sessions, provides reports,
    and persists data to disk.
    """

    def __init__(self, history_file: str = "training_history.json"):
        self._history_file = history_file
        self._current_session = TrainingSession()
        self._all_sessions: List[dict] = []
        self._load_history()

    @property
    def current_session(self) -> TrainingSession:
        return self._current_session

    # ── Event Recording ──────────────────────────────────

    def record_death(self):
        """Record a player death."""
        self._current_session.deaths += 1
        self._current_session.current_streak = 0
        logger.debug(f"Death recorded (total: {self._current_session.deaths})")

    def record_parry(self, timing: str, offset_ms: float = 0):
        """
        Record a parry attempt.

        Args:
            timing: "perfect", "early", "late", or "miss"
            offset_ms: Milliseconds offset from perfect timing
        """
        self._current_session.total_parries += 1
        self._current_session.parry_offsets.append(offset_ms)

        if timing == "perfect":
            self._current_session.perfect_parries += 1
            self._current_session.current_streak += 1
            if self._current_session.current_streak > self._current_session.best_streak:
                self._current_session.best_streak = self._current_session.current_streak
        elif timing == "early":
            self._current_session.early_parries += 1
            self._current_session.current_streak = 0
        elif timing == "late":
            self._current_session.late_parries += 1
            self._current_session.current_streak = 0
        else:
            self._current_session.missed_parries += 1
            self._current_session.current_streak = 0

    def record_boss_fight(self, boss_name: str, won: bool = False):
        """Record a boss fight attempt."""
        fight = self._current_session.boss_fights[boss_name]
        fight["attempts"] += 1
        fight["total_parries"] += self._current_session.total_parries

        if won:
            fight["wins"] += 1

        accuracy = self._current_session.accuracy
        if accuracy > fight["best_accuracy"]:
            fight["best_accuracy"] = accuracy

    # ── Session Management ───────────────────────────────

    def start_session(self):
        """Start a new training session."""
        self._current_session = TrainingSession()
        logger.info("New training session started")

    def end_session(self):
        """End the current session and save."""
        self._current_session.end_time = time.time()
        session_data = self._current_session.to_dict()
        self._all_sessions.append(session_data)
        self._save_history()
        logger.info(
            f"Session ended: {session_data['accuracy']:.1f}% accuracy, "
            f"{session_data['deaths']} deaths"
        )

    # ── Statistics Queries ────────────────────────────────

    def get_session_stats(self) -> dict:
        """Get current session statistics."""
        s = self._current_session
        return {
            "deaths": s.deaths,
            "session_time": s.duration,
            "best_streak": s.best_streak,
            "current_streak": s.current_streak,
            "parry_rate": s.accuracy,
            "total_parries": s.total_parries,
            "perfect_parries": s.perfect_parries,
            "early_parries": s.early_parries,
            "late_parries": s.late_parries,
            "missed_parries": s.missed_parries,
            "avg_offset": s.avg_offset,
            "boss_fights": dict(s.boss_fights),
        }

    def get_alltime_stats(self) -> dict:
        """Get all-time statistics across all sessions."""
        if not self._all_sessions:
            return {
                "total_sessions": 0,
                "total_time": 0,
                "total_deaths": 0,
                "total_parries": 0,
                "avg_accuracy": 0,
                "best_accuracy": 0,
                "best_streak": 0,
            }

        total_time = sum(s.get("duration", 0) for s in self._all_sessions)
        total_deaths = sum(s.get("deaths", 0) for s in self._all_sessions)
        total_parries = sum(s.get("total_parries", 0) for s in self._all_sessions)
        total_perfect = sum(s.get("perfect_parries", 0) for s in self._all_sessions)

        accuracies = [
            s.get("accuracy", 0) for s in self._all_sessions
            if s.get("total_parries", 0) > 0
        ]

        return {
            "total_sessions": len(self._all_sessions),
            "total_time": total_time,
            "total_deaths": total_deaths,
            "total_parries": total_parries,
            "total_perfect": total_perfect,
            "avg_accuracy": (
                sum(accuracies) / len(accuracies) if accuracies else 0
            ),
            "best_accuracy": max(accuracies) if accuracies else 0,
            "best_streak": max(
                (s.get("best_streak", 0) for s in self._all_sessions),
                default=0
            ),
        }

    def get_progress_report(self) -> str:
        """Generate a text progress report."""
        session = self.get_session_stats()
        alltime = self.get_alltime_stats()

        lines = [
            "═══════════════════════════════════════",
            "       SEKIRO TRAINING REPORT",
            "═══════════════════════════════════════",
            "",
            "CURRENT SESSION:",
            f"  Duration:    {self._format_time(session['session_time'])}",
            f"  Deaths:      {session['deaths']}",
            f"  Parries:     {session['total_parries']}",
            f"  Accuracy:    {session['parry_rate']:.1f}%",
            f"  Best Streak: {session['best_streak']}",
            f"  Avg Offset:  {session['avg_offset']:.1f}ms",
            "",
            "ALL TIME:",
            f"  Sessions:    {alltime['total_sessions']}",
            f"  Total Time:  {self._format_time(alltime['total_time'])}",
            f"  Total Deaths:{alltime['total_deaths']}",
            f"  Total Parries:{alltime['total_parries']}",
            f"  Avg Accuracy: {alltime['avg_accuracy']:.1f}%",
            f"  Best Accuracy:{alltime['best_accuracy']:.1f}%",
            f"  Best Streak:  {alltime['best_streak']}",
            "",
        ]

        if session.get("boss_fights"):
            lines.append("BOSS FIGHTS:")
            for boss, data in session["boss_fights"].items():
                lines.append(
                    f"  {boss}: {data['attempts']} attempts, "
                    f"{data['wins']} wins"
                )
            lines.append("")

        lines.append("═══════════════════════════════════════")
        return "\n".join(lines)

    # ── Persistence ──────────────────────────────────────

    def _save_history(self):
        """Save training history to disk."""
        try:
            data = {
                "version": 1,
                "last_updated": datetime.now().isoformat(),
                "sessions": self._all_sessions,
            }
            with open(self._history_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save training history: {e}")

    def _load_history(self):
        """Load training history from disk."""
        try:
            path = Path(self._history_file)
            if not path.exists():
                return

            with open(path, "r") as f:
                data = json.load(f)

            self._all_sessions = data.get("sessions", [])
            logger.info(
                f"Loaded {len(self._all_sessions)} previous sessions"
            )
        except Exception as e:
            logger.warning(f"Could not load training history: {e}")

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        h = int(seconds) // 3600
        m = (int(seconds) % 3600) // 60
        s = int(seconds) % 60
        if h > 0:
            return f"{h}h {m:02d}m {s:02d}s"
        return f"{m:02d}:{s:02d}"

    def reset_all(self):
        """Reset all training data."""
        self._current_session = TrainingSession()
        self._all_sessions = []
        self._save_history()
        logger.info("All training data reset")
