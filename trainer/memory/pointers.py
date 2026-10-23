"""
Game Pointers & Offset Tables
==============================
Defines pointer chains for navigating Sekiro's memory structures.

The game uses a hierarchy of singleton managers:
  WorldChrMan -> ChrIns[] (character instances)
  GameDataMan -> Player data
  GameManImp  -> Global game state
"""

import logging
from typing import Optional, List, Dict
from .process_reader import ProcessReader
from .pattern_scanner import PatternScanner

logger = logging.getLogger(__name__)


class OffsetTable:
    """
    Centralized offset definitions for Sekiro memory structures.

    These offsets correspond to Sekiro v1.06 (Steam).
    Update these if the game receives a patch.
    """

    # ── WorldChrMan offsets ──────────────────────────────
    WORLD_CHR_MAN_CHR_INS_LIST = 0x68        # -> ChrIns array
    WORLD_CHR_MAN_PLAYER_INDEX = 0x68        # Player is usually first
    WORLD_CHR_MAN_CHR_COUNT = 0x78           # Number of character instances

    # ── ChrIns (Character Instance) offsets ──────────────
    CHR_INS_NEXT = 0x08                       # -> next ChrIns in list
    CHR_INS_MAP_ITEM_MAN = 0x18              # -> map item manager
    CHR_INS_CHR_TYPE = 0x40                  # Character type (int32)
    CHR_INS_TEAM_TYPE = 0x70                 # Team type (int32)

    # Position / Transform
    CHR_INS_MODEL_SKELETON = 0x28            # -> ModelSkeleton
    CHR_INS_POS_X = 0x6C                     # float
    CHR_INS_POS_Y = 0x70                     # float
    CHR_INS_POS_Z = 0x74                     # float
    CHR_INS_ROT_Y = 0x68                     # float (yaw)

    # Character stats
    CHR_INS_HP = 0x1F8                       # float - current HP
    CHR_INS_HP_MAX = 0x1FC                   # float - max HP
    CHR_INS_STAMINA = 0x200                  # float - current stamina
    CHR_INS_STAMINA_MAX = 0x204             # float - max stamina
    CHR_INS_POSTURE = 0x210                  # float - current posture
    CHR_INS_POSTURE_MAX = 0x214             # float - max posture

    # Status effects
    CHR_INS_BURN = 0x230                     # float
    CHR_INS_POISON = 0x234                   # float

    # Death & state
    CHR_INS_IS_DEAD = 0x230                  # byte
    CHR_INS_IS_GUARD = 0x3A0                 # byte - guarding/parrying
    CHR_INS_GUARD_TYPE = 0x3C0               # int32 - guard type

    # Animation
    CHR_INS_ANIM_CONTROLLER = 0x280          # -> AnimController
    CHR_INS_ANIM_ID = 0x320                  # int32
    CHR_INS_ANIM_TIME = 0x330                # float
    CHR_INS_ANIM_LENGTH = 0x334              # float
    CHR_INS_ANIM_SPEED = 0x338               # float

    # Combat
    CHR_INS_ATTACK_PHASE = 0x3B0             # int32 - attack phase
    CHR_INS_IS_ATTACKING = 0x3B4             # byte
    CHR_INS_SUPER_ARMOR = 0x3D0              # float
    CHR_INS_DAMAGE_LEVEL = 0x3D4             # int32

    # ── AnimController offsets ───────────────────────────
    ANIM_CTRL_CURRENT_ANIM = 0x48            # -> Current animation
    ANIM_CTRL_ANIM_ID = 0x10                 # int32
    ANIM_CTRL_ANIM_TIME = 0x18               # float
    ANIM_CTRL_ANIM_LENGTH = 0x1C             # float
    ANIM_CTRL_BLEND_TIME = 0x20              # float
    ANIM_CTRL_SPEED = 0x24                   # float
    ANIM_CTRL_IS_PLAYING = 0x28              # byte
    ANIM_CTRL_LAYER_COUNT = 0x30             # int32

    # ── GameDataMan offsets ──────────────────────────────
    GAME_DATA_PLAYER_STATS = 0x58            # -> Player stats
    PLAYER_STATS_HP = 0x138                  # int32 - base HP
    PLAYER_STATS_STAMINA = 0x148             # int32
    PLAYER_STATS_POSTURE = 0x158             # int32
    PLAYER_STATS_ATTACK_POWER = 0x188        # int32
    PLAYER_STATS_SPIRIT_EMBLEM = 0x2C0       # int32

    # ── GameManImp offsets ───────────────────────────────
    GAME_MAN_IS_PAUSED = 0xB0                # byte
    GAME_MAN_IS_LOADING = 0xB8               # byte
    GAME_MAN_GAME_STATE = 0xA0               # int32

    # ── Entity name offsets ──────────────────────────────
    CHR_INS_NAME_PTR = 0x00                  # -> Name string
    CHR_INS_NAME_OFFSET = 0x00               # Name string offset
    ENTITY_NAME_BUFFER = 0x100               # Max name length


class GamePointers:
    """
    High-level pointer navigation for game data structures.

    Resolves pointer chains and provides typed access to
    game entities (player, enemies, NPCs).
    """

    def __init__(self, reader: ProcessReader, scanner: PatternScanner):
        self.reader = reader
        self.scanner = scanner
        self.offsets = OffsetTable()
        self._player_address: Optional[int] = None
        self._enemy_addresses: List[int] = []
        self._world_chr_man: Optional[int] = None

    def find_world_chr_man(self) -> Optional[int]:
        """Find the WorldChrMan singleton address."""
        if self._world_chr_man:
            return self._world_chr_man

        base = self.scanner.find_pattern("WorldChrMan")
        if base is None:
            base = self.scanner.find_pattern("WorldChrMan_alt")

        if base is None:
            return None

        # Dereference the pointer to get the actual manager
        ptr = self.reader.read_uint64(base)
        if ptr and ptr != 0:
            self._world_chr_man = ptr
            logger.info(f"WorldChrMan found at 0x{ptr:X}")
            return ptr

        return None

    def find_player(self) -> Optional[int]:
        """
        Find the player character instance.

        The player is typically the first character in the
        WorldChrMan list, or can be found via GameDataMan.
        """
        world_man = self.find_world_chr_man()
        if world_man is None:
            return None

        # Read the character list
        chr_list_ptr = self.reader.read_uint64(
            world_man + self.offsets.WORLD_CHR_MAN_CHR_INS_LIST
        )
        if not chr_list_ptr:
            return None

        # First entry in the list is typically the player
        # In FromSoftware games, player has team_type = 1
        player = self._find_entity_by_team(chr_list_ptr, team_type=1)
        if player:
            self._player_address = player
            return player

        # Fallback: try GameDataMan path
        game_data = self.scanner.find_pattern("GameDataMan")
        if game_data:
            ptr = self.reader.read_uint64(game_data)
            if ptr:
                self._player_address = ptr
                return ptr

        return None

    def find_enemies(self) -> List[int]:
        """
        Find all enemy character instances.

        Returns list of addresses for enemies (team_type != 1).
        """
        world_man = self.find_world_chr_man()
        if world_man is None:
            return []

        chr_list_ptr = self.reader.read_uint64(
            world_man + self.offsets.WORLD_CHR_MAN_CHR_INS_LIST
        )
        if not chr_list_ptr:
            return []

        enemies = []
        current = self.reader.read_uint64(chr_list_ptr)

        # Walk the linked list of character instances
        max_entities = 256  # Safety limit
        for _ in range(max_entities):
            if not current or current == 0:
                break

            # Read team type to classify entity
            team_type = self.reader.read_int32(
                current + self.offsets.CHR_INS_TEAM_TYPE
            )

            if team_type is not None and team_type != 1:
                # Check if alive
                hp = self.reader.read_float(current + self.offsets.CHR_INS_HP)
                if hp and hp > 0:
                    enemies.append(current)

            # Move to next entity
            current = self.reader.read_uint64(
                current + self.offsets.CHR_INS_NEXT
            )

        self._enemy_addresses = enemies
        return enemies

    def find_nearest_enemy(self, player_pos: tuple) -> Optional[int]:
        """
        Find the nearest alive enemy to the player.

        Args:
            player_pos: Player's (x, y, z) position

        Returns:
            Address of nearest enemy, or None
        """
        enemies = self.find_enemies()
        if not enemies:
            return None

        nearest = None
        min_dist = float("inf")

        for enemy_addr in enemies:
            ex = self.reader.read_float(enemy_addr + self.offsets.CHR_INS_POS_X)
            ey = self.reader.read_float(enemy_addr + self.offsets.CHR_INS_POS_Y)
            ez = self.reader.read_float(enemy_addr + self.offsets.CHR_INS_POS_Z)

            if ex is None or ey is None or ez is None:
                continue

            dx = ex - player_pos[0]
            dy = ey - player_pos[1]
            dz = ez - player_pos[2]
            dist = (dx*dx + dy*dy + dz*dz) ** 0.5

            if dist < min_dist:
                min_dist = dist
                nearest = enemy_addr

        return nearest

    def _find_entity_by_team(self, list_ptr: int, team_type: int) -> Optional[int]:
        """Find an entity with a specific team type."""
        current = self.reader.read_uint64(list_ptr)
        max_search = 256

        for _ in range(max_search):
            if not current or current == 0:
                break

            entity_team = self.reader.read_int32(
                current + self.offsets.CHR_INS_TEAM_TYPE
            )
            if entity_team == team_type:
                return current

            current = self.reader.read_uint64(
                current + self.offsets.CHR_INS_NEXT
            )

        return None

    def read_character_data(self, address: int) -> Optional[dict]:
        """
        Read all relevant data from a character instance.

        Returns dict with HP, posture, position, animation, etc.
        """
        if not address:
            return None

        data = {}

        # Stats
        data["hp"] = self.reader.read_float(address + self.offsets.CHR_INS_HP)
        data["hp_max"] = self.reader.read_float(address + self.offsets.CHR_INS_HP_MAX)
        data["posture"] = self.reader.read_float(address + self.offsets.CHR_INS_POSTURE)
        data["posture_max"] = self.reader.read_float(address + self.offsets.CHR_INS_POSTURE_MAX)
        data["stamina"] = self.reader.read_float(address + self.offsets.CHR_INS_STAMINA)
        data["stamina_max"] = self.reader.read_float(address + self.offsets.CHR_INS_STAMINA_MAX)

        # Position
        data["pos_x"] = self.reader.read_float(address + self.offsets.CHR_INS_POS_X)
        data["pos_y"] = self.reader.read_float(address + self.offsets.CHR_INS_POS_Y)
        data["pos_z"] = self.reader.read_float(address + self.offsets.CHR_INS_POS_Z)
        data["rot_y"] = self.reader.read_float(address + self.offsets.CHR_INS_ROT_Y)

        # Animation
        data["anim_id"] = self.reader.read_int32(address + self.offsets.CHR_INS_ANIM_ID)
        data["anim_time"] = self.reader.read_float(address + self.offsets.CHR_INS_ANIM_TIME)
        data["anim_length"] = self.reader.read_float(address + self.offsets.CHR_INS_ANIM_LENGTH)
        data["anim_speed"] = self.reader.read_float(address + self.offsets.CHR_INS_ANIM_SPEED)

        # Combat state
        data["attack_phase"] = self.reader.read_int32(address + self.offsets.CHR_INS_ATTACK_PHASE)
        data["is_attacking"] = self.reader.read_bytes(address + self.offsets.CHR_INS_IS_ATTACKING, 1)
        data["is_guarding"] = self.reader.read_bytes(address + self.offsets.CHR_INS_IS_GUARD, 1)
        data["super_armor"] = self.reader.read_float(address + self.offsets.CHR_INS_SUPER_ARMOR)

        # Team
        data["team_type"] = self.reader.read_int32(address + self.offsets.CHR_INS_TEAM_TYPE)

        # Post-process boolean fields
        if data["is_attacking"] is not None:
            data["is_attacking"] = data["is_attacking"][0] != 0
        if data["is_guarding"] is not None:
            data["is_guarding"] = data["is_guarding"][0] != 0

        return data

    def invalidate_cache(self):
        """Clear all cached addresses (call when game reloads)."""
        self._player_address = None
        self._enemy_addresses = []
        self._world_chr_man = None
