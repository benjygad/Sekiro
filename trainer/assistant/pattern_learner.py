"""
Pattern Learner
===============
Learns enemy attack patterns through observation.

Builds a model of each enemy's attack sequences to
predict upcoming attacks and suggest counters.
"""

import time
import json
import logging
from typing import Optional, Dict, List, Tuple
from collections import defaultdict, Counter
from pathlib import Path

logger = logging.getLogger(__name__)


class AttackSequence:
    """Represents a learned attack sequence."""

    def __init__(self, attacks: List[str]):
        self.attacks = attacks
        self.count = 1
        self.last_seen = time.time()

    @property
    def key(self) -> str:
        return " → ".join(self.attacks)

    def observe(self):
        """Record another observation of this sequence."""
        self.count += 1
        self.last_seen = time.time()


class PatternLearner:
    """
    Learns and predicts enemy attack patterns.

    Uses n-gram analysis of observed attack sequences
    to predict the most likely next attack.
    """

    def __init__(self, pattern_file: str = "learned_patterns.json"):
        self._pattern_file = pattern_file
        self._sequences: Dict[str, AttackSequence] = {}
        self._transitions: Dict[str, Counter] = defaultdict(Counter)
        self._current_sequence: List[str] = []
        self._sequence_timeout = 4.0  # Seconds between attacks to break sequence
        self._last_attack_time = 0.0
        self._ngram_sizes = [2, 3, 4]  # Analyze 2, 3, and 4-grams

        # Load existing patterns
        self._load_patterns()

    def observe_attack(self, enemy_id: str, attack_category: str):
        """
        Record an observed enemy attack.

        Args:
            enemy_id: Unique identifier for the enemy
            attack_category: Attack animation category
        """
        now = time.time()

        # Break sequence if too much time has passed
        if now - self._last_attack_time > self._sequence_timeout:
            self._current_sequence = []

        self._current_sequence.append(attack_category)
        self._last_attack_time = now

        # Record transitions
        if len(self._current_sequence) >= 2:
            prev = self._current_sequence[-2]
            self._transitions[f"{enemy_id}:{prev}"][attack_category] += 1

        # Record n-gram sequences
        for n in self._ngram_sizes:
            if len(self._current_sequence) >= n:
                seq = self._current_sequence[-n:]
                key = f"{enemy_id}:{'→'.join(seq)}"
                if key in self._sequences:
                    self._sequences[key].observe()
                else:
                    self._sequences[key] = AttackSequence(list(seq))

    def predict_next(self, enemy_id: str) -> Optional[Dict[str, float]]:
        """
        Predict the next attack based on learned patterns.

        Returns dict mapping attack categories to probabilities.
        """
        if not self._current_sequence:
            return None

        predictions: Counter = Counter()
        total_weight = 0

        # Check transitions from each recent context
        for n in self._ngram_sizes:
            if len(self._current_sequence) < n:
                continue

            context = self._current_sequence[-n:]
            key = f"{enemy_id}:{context[-1]}"

            if key in self._transitions:
                transitions = self._transitions[key]
                total = sum(transitions.values())
                weight = n  # Higher n-grams get more weight

                for attack, count in transitions.items():
                    predictions[attack] += (count / total) * weight
                    total_weight += weight

        if total_weight == 0:
            return None

        # Normalize to probabilities
        return {
            attack: score / total_weight
            for attack, score in predictions.most_common(5)
        }

    def get_suggested_counter(self, enemy_id: str) -> Optional[str]:
        """
        Suggest a counter based on predicted next attack.

        Returns a counter suggestion string.
        """
        prediction = self.predict_next(enemy_id)
        if not prediction:
            return None

        most_likely = max(prediction, key=prediction.get)
        confidence = prediction[most_likely]

        if confidence < 0.3:
            return None

        counters = {
            "attack_light": "Deflect (Parry timing ~250ms)",
            "attack_heavy": "Deflect (Parry timing ~420ms)",
            "attack_thrust": "Mikiri Counter (Forward + Deflect)",
            "attack_sweep": "Jump over, then counter",
            "attack_grab": "Dodge sideways or run",
            "attack_jump": "Deflect or step back",
            "attack_perilous": "Counter based on perilous type",
        }

        counter = counters.get(most_likely, "Stay defensive")
        return f"Likely: {most_likely.replace('attack_', '')} ({confidence:.0%}) → {counter}"

    def get_pattern_summary(self, enemy_id: str) -> dict:
        """Get a summary of learned patterns for an enemy."""
        enemy_seqs = {
            k: v for k, v in self._sequences.items()
            if k.startswith(f"{enemy_id}:")
        }

        if not enemy_seqs:
            return {"patterns": 0, "observations": 0}

        # Most common sequences
        sorted_seqs = sorted(
            enemy_seqs.values(), key=lambda s: s.count, reverse=True
        )

        return {
            "patterns": len(enemy_seqs),
            "observations": sum(s.count for s in enemy_seqs.values()),
            "top_sequences": [
                {"sequence": s.key, "count": s.count}
                for s in sorted_seqs[:5]
            ],
        }

    def save_patterns(self):
        """Save learned patterns to disk."""
        data = {
            "sequences": {
                k: {
                    "attacks": v.attacks,
                    "count": v.count,
                    "last_seen": v.last_seen,
                }
                for k, v in self._sequences.items()
            },
            "transitions": {
                k: dict(v) for k, v in self._transitions.items()
            },
        }

        try:
            with open(self._pattern_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self._sequences)} patterns")
        except Exception as e:
            logger.error(f"Failed to save patterns: {e}")

    def _load_patterns(self):
        """Load previously learned patterns from disk."""
        try:
            path = Path(self._pattern_file)
            if not path.exists():
                return

            with open(path, "r") as f:
                data = json.load(f)

            for key, seq_data in data.get("sequences", {}).items():
                seq = AttackSequence(seq_data["attacks"])
                seq.count = seq_data["count"]
                seq.last_seen = seq_data["last_seen"]
                self._sequences[key] = seq

            for key, trans in data.get("transitions", {}).items():
                self._transitions[key] = Counter(trans)

            logger.info(f"Loaded {len(self._sequences)} patterns")
        except Exception as e:
            logger.warning(f"Could not load patterns: {e}")

    def clear_patterns(self, enemy_id: str = None):
        """Clear learned patterns, optionally for a specific enemy."""
        if enemy_id:
            self._sequences = {
                k: v for k, v in self._sequences.items()
                if not k.startswith(f"{enemy_id}:")
            }
            self._transitions = {
                k: v for k, v in self._transitions.items()
                if not k.startswith(f"{enemy_id}:")
            }
        else:
            self._sequences.clear()
            self._transitions.clear()

    def reset_sequence(self):
        """Reset the current observed sequence."""
        self._current_sequence = []
