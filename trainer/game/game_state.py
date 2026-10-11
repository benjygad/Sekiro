"""
Game State Manager
==================
Central coordinator for reading and maintaining game state.

Polls game memory at high frequency and distributes state
updates to all registered listeners (overlay, assistant, etc.)
"""

import time
import logging
import threading
from typing import Optional, Callable, List, Dict
from collections import deque

from ..memory.process_reader import ProcessReader
from ..memory.pattern_scanner import PatternScanner
from ..memory.pointers import GamePointers
from ..memory.structures import (
    WorldState, CharacterData, CombatState, AnimState,
    Position, AttackPhase, GuardType, PerilousType,
    TeamType, GameState
)

logger = logging.getLogger(__name__)


class GameStateManager:
    """
    Central game state coordinator.

    Runs a background polling loop that reads game memory and
    updates the WorldState. Supports listener callbacks for
    state change events.
    """

    def __init__(self, process_name: str = "sekiro.exe", poll_interval_ms: int = 8):
        self.reader = ProcessReader(process_name)
        self.scanner = PatternScanner(self.reader)
        self.pointers = GamePointers(self.reader, self.scanner)

        self.poll_interval_ms = poll_interval_ms
        self._poll_interval_sec = poll_interval_ms / 1000.0

        self.world_state = WorldState()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # FPS tracking
        self._frame_times: deque = deque(maxlen=120)
        self._last_frame_time = 0.0

        # Event listeners
        self._listeners: Dict[str, List[Callable]] = {
            "state_update": [],
            "enemy_attack": [],
            "player_death": [],
            "combat_start": [],
            "combat_end": [],
            "game_attached": [],
            "game_detached": [],
        }

        # Tracking
        self._prev_player_hp: float = 0.0
        self._prev_in_combat: bool = False
        self._prev_enemy_attacking: bool = False
        self._was_attached: bool = False

    # ── Event System ──────────────────────────────────────

    def on(self, event: str, callback: Callable):
        """Register an event listener."""
        if event in self._listeners:
            self._listeners[event].append(callback)
        else:
            logger.warning(f"Unknown event: {event}")

    def off(self, event: str, callback: Callable):
        """Unregister an event listener."""
        if event in self._listeners:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

    def _emit(self, event: str, *args, **kwargs):
        """Emit an event to all registered listeners."""
        for callback in self._listeners.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Event listener error ({event}): {e}")

    # ── Lifecycle ─────────────────────────────────────────

    def start(self):
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Game state manager started")

    def stop(self):
        """Stop the background polling thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.reader.disconnect()
        logger.info("Game state manager stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_attached(self) -> bool:
        return self.reader.is_attached

    # ── Polling Loop ──────────────────────────────────────

    def _poll_loop(self):
        """Main polling loop - runs in background thread."""
        scan_timer = 0.0

        while self._running:
            frame_start = time.perf_counter()

            try:
                if not self.reader.is_attached:
                    # Try to connect
                    if scan_timer <= 0:
                        if self.reader.connect():
                            self._was_attached = True
                            self._emit("game_attached")
                            self.pointers.invalidate_cache()
                            self.scanner.clear_cache()
                        scan_timer = 2.0  # Retry every 2 seconds
                    else:
                        scan_timer -= self._poll_interval_sec
                else:
                    # Check if still alive
                    if not self.reader.is_process_alive():
                        logger.warning("Game process died")
                        self._emit("game_detached")
                        self.reader.disconnect()
                        self.pointers.invalidate_cache()
                        scan_timer = 2.0
                    else:
                        self._update_state()

            except Exception as e:
                logger.error(f"Poll loop error: {e}", exc_info=True)
                try:
                    self.reader.disconnect()
                except Exception:
                    pass
                scan_timer = 2.0

            # FPS tracking
            now = time.perf_counter()
            if self._last_frame_time > 0:
                self._frame_times.append(now - self._last_frame_time)
            self._last_frame_time = now

            if self._frame_times:
                avg_frame = sum(self._frame_times) / len(self._frame_times)
                self.world_state.fps = 1.0 / avg_frame if avg_frame > 0 else 0

            self.world_state.frame_count += 1

            # Sleep to maintain target poll rate
            elapsed = time.perf_counter() - frame_start
            sleep_time = self._poll_interval_sec - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _update_state(self):
        """Read current game state from memory."""
        now = time.time()
        self.world_state.timestamp = now

        # Find player
        player_addr = self.pointers.find_player()
        if player_addr:
            player_data = self.pointers.read_character_data(player_addr)
            if player_data:
                self._update_player(player_data, player_addr)

        # Find enemies
        self._update_enemies()

        # Check for events
        self._check_events()

    def _update_player(self, data: dict, address: int):
        """Update player character data."""
        combat = CombatState(
            hp=data.get("hp", 0) or 0,
            hp_max=data.get("hp_max", 0) or 0,
            posture=data.get("posture", 0) or 0,
            posture_max=data.get("posture_max", 0) or 0,
            stamina=data.get("stamina", 0) or 0,
            stamina_max=data.get("stamina_max", 0) or 0,
            is_attacking=data.get("is_attacking", False),
            is_guarding=data.get("is_guarding", False),
            super_armor=data.get("super_armor", 0) or 0,
        )

        anim_id = data.get("anim_id", 0) or 0
        category = self.scanner.classify_animation(anim_id)
        animation = AnimState(
            anim_id=anim_id,
            anim_time=data.get("anim_time", 0) or 0,
            anim_length=data.get("anim_length", 0) or 0,
            anim_speed=data.get("anim_speed", 1.0) or 1.0,
            category=category,
            is_attack=self.scanner.is_attack_animation(anim_id),
            is_perilous=self.scanner.is_perilous_attack(anim_id),
            attack_phase=AttackPhase(data.get("attack_phase", 0) or 0),
        )

        position = Position(
            x=data.get("pos_x", 0) or 0,
            y=data.get("pos_y", 0) or 0,
            z=data.get("pos_z", 0) or 0,
        )

        char_data = CharacterData(
            address=address,
            name="Sekiro",
            team_type=TeamType.PLAYER,
            position=position,
            rotation_y=data.get("rot_y", 0) or 0,
            combat=combat,
            animation=animation,
        )

        self.world_state.player = char_data

    def _update_enemies(self):
        """Update all enemy entities."""
        enemy_addrs = self.pointers.find_enemies()
        self.world_state.enemies = []

        for addr in enemy_addrs:
            data = self.pointers.read_character_data(addr)
            if not data:
                continue

            combat = CombatState(
                hp=data.get("hp", 0) or 0,
                hp_max=data.get("hp_max", 0) or 0,
                posture=data.get("posture", 0) or 0,
                posture_max=data.get("posture_max", 0) or 0,
                stamina=data.get("stamina", 0) or 0,
                stamina_max=data.get("stamina_max", 0) or 0,
                is_attacking=data.get("is_attacking", False),
                is_guarding=data.get("is_guarding", False),
                super_armor=data.get("super_armor", 0) or 0,
            )

            anim_id = data.get("anim_id", 0) or 0
            category = self.scanner.classify_animation(anim_id)
            animation = AnimState(
                anim_id=anim_id,
                anim_time=data.get("anim_time", 0) or 0,
                anim_length=data.get("anim_length", 0) or 0,
                anim_speed=data.get("anim_speed", 1.0) or 1.0,
                category=category,
                is_attack=self.scanner.is_attack_animation(anim_id),
                is_perilous=self.scanner.is_perilous_attack(anim_id),
                attack_phase=AttackPhase(data.get("attack_phase", 0) or 0),
            )

            position = Position(
                x=data.get("pos_x", 0) or 0,
                y=data.get("pos_y", 0) or 0,
                z=data.get("pos_z", 0) or 0,
            )

            team = data.get("team_type", 2)
            team_type = TeamType.BOSS if team == 5 else TeamType.ENEMY

            char_data = CharacterData(
                address=addr,
                name=f"Enemy_{addr:#X}",
                team_type=team_type,
                position=position,
                rotation_y=data.get("rot_y", 0) or 0,
                combat=combat,
                animation=animation,
            )

            self.world_state.enemies.append(char_data)

        # Find nearest enemy
        if self.world_state.player and self.world_state.enemies:
            min_dist = float("inf")
            nearest = None
            for enemy in self.world_state.enemies:
                dist = self.world_state.player.position.distance_to(enemy.position)
                if dist < min_dist:
                    min_dist = dist
                    nearest = enemy
            self.world_state.nearest_enemy = nearest
        else:
            self.world_state.nearest_enemy = None

    def _check_events(self):
        """Check for state transitions and emit events."""
        # Combat start/end
        in_combat = self.world_state.in_combat
        if in_combat and not self._prev_in_combat:
            self._emit("combat_start", self.world_state)
        elif not in_combat and self._prev_in_combat:
            self._emit("combat_end", self.world_state)
        self._prev_in_combat = in_combat

        # Enemy attack detection
        enemy_attacking = self.world_state.enemy_is_attacking
        if enemy_attacking and not self._prev_enemy_attacking:
            self._emit("enemy_attack", self.world_state)
        self._prev_enemy_attacking = enemy_attacking

        # Player death
        if self.world_state.player:
            current_hp = self.world_state.player.combat.hp
            if self._prev_player_hp > 0 and current_hp <= 0:
                self.world_state.death_count += 1
                self._emit("player_death", self.world_state)
            self._prev_player_hp = current_hp

        # General update
        self._emit("state_update", self.world_state)

    # ── Public API ────────────────────────────────────────

    def get_state(self) -> WorldState:
        """Get the current world state snapshot."""
        return self.world_state

    def get_player(self) -> Optional[CharacterData]:
        """Get current player data."""
        return self.world_state.player

    def get_nearest_enemy(self) -> Optional[CharacterData]:
        """Get the nearest enemy."""
        return self.world_state.nearest_enemy

    def get_all_enemies(self) -> List[CharacterData]:
        """Get all tracked enemies."""
        return self.world_state.enemies

    def force_rescan(self):
        """Force a rescan of all game pointers."""
        self.pointers.invalidate_cache()
        self.scanner.clear_cache()
