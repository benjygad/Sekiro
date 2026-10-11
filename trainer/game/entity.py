"""
Entity Manager
==============
Tracks game entities with history and pattern analysis.

Maintains rolling histories of character states for
animation prediction and attack pattern recognition.
"""

import time
import logging
from typing import Optional, Dict, List
from collections import defaultdict

from ..memory.structures import (
    CharacterData, GameEntity, WorldState,
    AnimState, CombatState, TeamType
)

logger = logging.getLogger(__name__)


class EntityManager:
    """
    Manages tracked game entities with state history.

    Provides entity lookup by address, attack history,
    and pattern recognition data.
    """

    def __init__(self, max_history: int = 300):
        self._entities: Dict[int, GameEntity] = {}
        self.max_history = max_history
        self._attack_log: List[dict] = []
        self._max_attack_log = 1000

    def update(self, world_state: WorldState):
        """Update all entities from current world state."""
        # Update player
        if world_state.player:
            self._update_entity(world_state.player)

        # Update enemies
        for enemy in world_state.enemies:
            self._update_entity(enemy)

        # Cleanup stale entities (not seen for 10 seconds)
        cutoff = time.time() - 10.0
        stale = [
            addr for addr, entity in self._entities.items()
            if entity.current.timestamp < cutoff
        ]
        for addr in stale:
            del self._entities[addr]

    def _update_entity(self, data: CharacterData):
        """Update or create an entity record."""
        addr = data.address
        if addr not in self._entities:
            self._entities[addr] = GameEntity(
                address=addr,
                name=data.name,
                max_history=self.max_history,
            )

        entity = self._entities[addr]

        # Log attack transitions
        prev_anim = entity.current.animation
        curr_anim = data.animation
        if not prev_anim.is_attack and curr_anim.is_attack:
            self._log_attack_start(data)
        elif prev_anim.is_attack and not curr_anim.is_attack:
            self._log_attack_end(data)

        entity.update(data)

    def _log_attack_start(self, data: CharacterData):
        """Log the start of an attack animation."""
        self._attack_log.append({
            "time": time.time(),
            "source_addr": data.address,
            "source_name": data.name,
            "anim_id": data.animation.anim_id,
            "category": data.animation.category,
            "is_perilous": data.animation.is_perilous,
            "start": True,
        })
        if len(self._attack_log) > self._max_attack_log:
            self._attack_log = self._attack_log[-self._max_attack_log:]

    def _log_attack_end(self, data: CharacterData):
        """Log the end of an attack animation."""
        self._attack_log.append({
            "time": time.time(),
            "source_addr": data.address,
            "source_name": data.name,
            "anim_id": data.animation.anim_id,
            "category": data.animation.category,
            "start": False,
        })

    def get_entity(self, address: int) -> Optional[GameEntity]:
        """Get a tracked entity by address."""
        return self._entities.get(address)

    def get_player_entity(self) -> Optional[GameEntity]:
        """Get the player entity."""
        for entity in self._entities.values():
            if entity.current.is_player:
                return entity
        return None

    def get_enemy_entities(self) -> List[GameEntity]:
        """Get all enemy entities."""
        return [
            e for e in self._entities.values()
            if e.current.is_enemy
        ]

    def get_attack_history(self, address: int) -> List[AnimState]:
        """Get attack animation history for an entity."""
        entity = self._entities.get(address)
        if not entity:
            return []
        return entity.attack_history

    def get_attack_patterns(self, address: int) -> Dict[str, int]:
        """
        Analyze attack patterns for an entity.

        Returns dict mapping attack categories to their frequency.
        """
        entity = self._entities.get(address)
        if not entity:
            return {}

        pattern_counts: Dict[str, int] = defaultdict(int)
        for anim in entity.attack_history:
            if anim.is_attack:
                pattern_counts[anim.category] += 1

        return dict(pattern_counts)

    def predict_next_attack(self, address: int) -> Optional[str]:
        """
        Predict the next attack type based on patterns.

        Uses Markov chain analysis of attack transitions.
        """
        entity = self._entities.get(address)
        if not entity or len(entity.attack_history) < 3:
            return None

        history = entity.attack_history
        last_attack = history[-1].category

        # Count transitions from last_attack to each next attack
        transitions: Dict[str, int] = defaultdict(int)
        for i in range(1, len(history)):
            if history[i-1].category == last_attack:
                transitions[history[i].category] += 1

        if not transitions:
            return None

        # Return most likely next attack
        return max(transitions, key=transitions.get)

    @property
    def attack_log(self) -> List[dict]:
        """Get the full attack event log."""
        return self._attack_log

    def get_combat_summary(self) -> dict:
        """Get a summary of all tracked combat data."""
        summary = {
            "entities_tracked": len(self._entities),
            "enemies_tracked": len(self.get_enemy_entities()),
            "total_attacks_logged": len(self._attack_log),
            "attack_types": defaultdict(int),
        }
        for entry in self._attack_log:
            if entry.get("start"):
                summary["attack_types"][entry["category"]] += 1
        summary["attack_types"] = dict(summary["attack_types"])
        return summary
