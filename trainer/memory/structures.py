"""
Game Data Structures
====================
Typed dataclasses representing game entities and state.

These are snapshots of game data read from memory,
used throughout the trainer for clean data access.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
from enum import Enum, IntEnum


class TeamType(IntEnum):
    """Entity team affiliations."""
    PLAYER = 1
    ENEMY = 2
    NPC_FRIENDLY = 3
    NPC_NEUTRAL = 4
    BOSS = 5


class AttackPhase(IntEnum):
    """Phases of an attack animation."""
    NONE = 0
    WINDUP = 1        # Startup / telegraph
    ACTIVE = 2        # Hit window
    RECOVERY = 3      # Recovery frames
    CANCELLED = 4     # Attack was interrupted


class GuardType(IntEnum):
    """Types of defensive actions."""
    NONE = 0
    BLOCK = 1
    PARRY = 2
    PERFECT_PARRY = 3
    DODGE = 4


class PerilousType(Enum):
    """Types of perilous (unblockable) attacks."""
    NONE = "none"
    THRUST = "thrust"      # Mikiri counter
    SWEEP = "sweep"        # Jump
    GRAB = "grab"          # Run/dodge
    UNKNOWN = "unknown"


class GameState(IntEnum):
    """High-level game states."""
    LOADING = 0
    IN_GAME = 1
    PAUSED = 2
    MENU = 3
    CUTSCENE = 4
    DEATH_SCREEN = 5


@dataclass
class Position:
    """3D world position."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: "Position") -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx*dx + dy*dy + dz*dz) ** 0.5

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class AnimState:
    """
    Character animation state snapshot.

    Tracks the current animation, its progress, and derived
    combat-relevant information.
    """
    anim_id: int = 0
    anim_time: float = 0.0
    anim_length: float = 0.0
    anim_speed: float = 1.0
    category: str = "unknown"
    is_attack: bool = False
    is_perilous: bool = False
    attack_phase: AttackPhase = AttackPhase.NONE
    perilous_type: PerilousType = PerilousType.NONE

    @property
    def progress(self) -> float:
        """Animation progress as 0.0-1.0 fraction."""
        if self.anim_length <= 0:
            return 0.0
        return min(1.0, self.anim_time / self.anim_length)

    @property
    def time_remaining(self) -> float:
        """Seconds remaining in current animation."""
        return max(0.0, self.anim_length - self.anim_time)

    @property
    def time_in_phase(self) -> float:
        """Estimated time into current attack phase."""
        if self.attack_phase == AttackPhase.WINDUP:
            return self.anim_time
        elif self.attack_phase == AttackPhase.ACTIVE:
            return max(0, self.anim_time - self._windup_duration)
        return 0.0

    @property
    def _windup_duration(self) -> float:
        """Estimated windup duration (varies by attack type)."""
        # These are approximate values - actual values depend on the specific animation
        durations = {
            "attack_light": 0.3,
            "attack_heavy": 0.5,
            "attack_thrust": 0.4,
            "attack_sweep": 0.45,
            "attack_grab": 0.6,
            "attack_jump": 0.5,
            "attack_perilous": 0.7,
        }
        return durations.get(self.category, 0.4)


@dataclass
class CombatState:
    """
    Combat-related state for a character.
    """
    hp: float = 0.0
    hp_max: float = 0.0
    posture: float = 0.0
    posture_max: float = 0.0
    stamina: float = 0.0
    stamina_max: float = 0.0

    is_attacking: bool = False
    is_guarding: bool = False
    guard_type: GuardType = GuardType.NONE
    attack_phase: AttackPhase = AttackPhase.NONE
    super_armor: float = 0.0

    # Status effects
    burn: float = 0.0
    poison: float = 0.0

    @property
    def hp_percent(self) -> float:
        if self.hp_max <= 0:
            return 0.0
        return (self.hp / self.hp_max) * 100.0

    @property
    def posture_percent(self) -> float:
        if self.posture_max <= 0:
            return 0.0
        return (self.posture / self.posture_max) * 100.0

    @property
    def stamina_percent(self) -> float:
        if self.stamina_max <= 0:
            return 0.0
        return (self.stamina / self.stamina_max) * 100.0

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    @property
    def posture_broken(self) -> bool:
        return self.posture_max > 0 and self.posture >= self.posture_max


@dataclass
class CharacterData:
    """
    Complete character data snapshot.

    Combines position, combat, and animation data for one entity.
    """
    address: int = 0
    name: str = "Unknown"
    team_type: TeamType = TeamType.ENEMY
    position: Position = field(default_factory=Position)
    rotation_y: float = 0.0
    combat: CombatState = field(default_factory=CombatState)
    animation: AnimState = field(default_factory=AnimState)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_player(self) -> bool:
        return self.team_type == TeamType.PLAYER

    @property
    def is_enemy(self) -> bool:
        return self.team_type in (TeamType.ENEMY, TeamType.BOSS)


@dataclass
class GameEntity:
    """
    Tracked game entity with history.

    Maintains a rolling history of state changes for
    animation prediction and pattern analysis.
    """
    address: int = 0
    name: str = "Unknown"
    current: CharacterData = field(default_factory=CharacterData)
    history: List[CharacterData] = field(default_factory=list)
    max_history: int = 120  # ~2 seconds at 60fps

    def update(self, new_data: CharacterData):
        """Update entity with new data, maintaining history."""
        self.history.append(self.current)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self.current = new_data

    @property
    def attack_history(self) -> List[AnimState]:
        """Get animation history filtered to attack animations."""
        return [
            h.animation for h in self.history
            if h.animation.is_attack
        ]

    def get_anim_transition_count(self, from_cat: str, to_cat: str) -> int:
        """Count transitions between animation categories in history."""
        count = 0
        for i in range(1, len(self.history)):
            prev_cat = self.history[i-1].animation.category
            curr_cat = self.history[i].animation.category
            if prev_cat == from_cat and curr_cat == to_cat:
                count += 1
        return count


@dataclass
class WorldState:
    """
    Overall world/game state snapshot.

    Combines all entity data and global game information.
    """
    game_state: GameState = GameState.LOADING
    is_paused: bool = False
    is_loading: bool = False

    player: Optional[CharacterData] = None
    enemies: List[CharacterData] = field(default_factory=list)
    nearest_enemy: Optional[CharacterData] = None

    death_count: int = 0
    session_start: float = field(default_factory=time.time)
    frame_count: int = 0
    fps: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def in_combat(self) -> bool:
        """Whether the player is currently in combat."""
        if not self.player or not self.nearest_enemy:
            return False
        dist = self.player.position.distance_to(self.nearest_enemy.position)
        return dist < 5.0 and self.nearest_enemy.combat.is_alive

    @property
    def enemy_is_attacking(self) -> bool:
        """Whether the nearest enemy is currently attacking."""
        if not self.nearest_enemy:
            return False
        return (
            self.nearest_enemy.animation.is_attack
            and self.nearest_enemy.animation.attack_phase != AttackPhase.NONE
        )

    @property
    def session_duration(self) -> float:
        """Session duration in seconds."""
        return time.time() - self.session_start
