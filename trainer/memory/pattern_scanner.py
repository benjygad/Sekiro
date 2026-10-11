"""
AOB Pattern Scanner
===================
Signature scanning for finding game function and data addresses.

Contains known byte patterns for Sekiro: Shadows Die Twice.
Patterns are version-specific and may need updating after game patches.
"""

import re
import logging
import time
from typing import Optional, Dict, List, Tuple

from .process_reader import ProcessReader

logger = logging.getLogger(__name__)


# ============================================================
# Known byte patterns for Sekiro v1.06 (latest Steam)
# ============================================================
# Each pattern includes:
#   - AOB signature with ?? wildcards
#   - Instruction offset (where to read relative to match)
#   - Type of resolution (RIP-relative, direct, pointer chain)
# ============================================================

SEKIRO_PATTERNS: Dict[str, dict] = {
    # WorldChrMan - Character instance manager
    # Multiple pattern variants for different game versions
    "WorldChrMan": {
        "patterns": [
            # Variant 1: Common pattern for Sekiro v1.06
            "48 8B 05 ?? ?? ?? ?? 48 8B 48 68 48 85 C9 74 0D",
            # Variant 2: Alternate from community tables
            "48 8B 0D ?? ?? ?? ?? 48 85 C9 0F 84 ?? ?? ?? ?? 48 39 99",
            # Variant 3: Another common variant
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 88 ?? ?? ?? ?? 48 85 C9",
            # Variant 4: Pattern near ChrIns initialization
            "48 83 EC 28 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 85 C0 74",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Character instance manager singleton",
    },

    # GameManImp - Game manager (pause, loading, etc.)
    "GameManImp": {
        "patterns": [
            "48 8B 05 ?? ?? ?? ?? C6 80 ?? ?? ?? ?? ?? 48 83 C4 20",
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 80 B8 ?? ?? ?? ?? ?? 74",
            "48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 84 C0 74 ?? 48 8B 05",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Game manager singleton",
    },

    # CSMenuManImp - Menu state
    "CSMenuManImp": {
        "patterns": [
            "48 8B 05 ?? ?? ?? ?? 48 89 44 24 ?? 48 8B F1 48 85 C0 74 ?? 48 8B 88",
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 88 ?? ?? ?? ?? E8",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Menu manager singleton",
    },

    # WorldChrMan (alternate pattern for newer patches)
    "WorldChrMan_alt": {
        "patterns": [
            "48 8B 0D ?? ?? ?? ?? 48 85 C9 0F 84 ?? ?? ?? ?? 48 39 99",
            "48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B D8 48 85 C0",
            "48 83 EC 28 48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 85 C0",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Character manager (alternate)",
    },

    # GameDataMan - Player save data
    "GameDataMan": {
        "patterns": [
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58 C3",
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 80 ?? ?? ?? ?? C3",
            "48 8B 0D ?? ?? ?? ?? 48 85 C9 74 ?? 48 8B 89 ?? ?? ?? ?? E8",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Player save data manager",
    },

    # FieldArea - World/area management
    "FieldArea": {
        "patterns": [
            "48 8B 05 ?? ?? ?? ?? 48 8B 48 08 48 85 C9 74 1F 48 39 59 68",
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 40 08 C3",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Field/area manager",
    },

    # ChrAsm - Character equipment assembly
    "ChrAsm": {
        "patterns": [
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 88 ?? ?? ?? ?? 48 85 C9 74 ?? E8",
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 40 08 C3 48 8B 05",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Character assembly/equipment",
    },

    # DamageManagement
    "DamageMan": {
        "patterns": [
            "48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 8B D8 48 85 C0 75 ?? 48 8D 0D",
            "48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B C8",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Damage calculation manager",
    },

    # AnimSpeed multiplier hook point
    "AnimSpeed": {
        "patterns": [
            "F3 0F 10 84 C8 ?? ?? ?? ?? F3 0F 59 C7",
            "F3 0F 10 ?? ?? ?? ?? ?? F3 0F 59 ?? F3 0F 5C",
        ],
        "instruction_size": 8,
        "offset": 4,
        "type": "rip_relative",
        "description": "Animation speed calculation",
    },

    # Input manager
    "PadMan": {
        "patterns": [
            "48 8B 05 ?? ?? ?? ?? 48 8B 48 08 48 85 C9 74 ?? 83 B9",
            "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? 48 8B 48 08 48 85 C9",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Input/pad manager",
    },

    # ChrIns lookup helper - for finding player character
    "ChrInsLookup": {
        "patterns": [
            "48 8B 8F ?? ?? ?? ?? 48 85 C9 74 ?? E8 ?? ?? ?? ?? 84 C0",
            "48 8B 89 ?? ?? ?? ?? 48 85 C9 74 ?? E8 ?? ?? ?? ?? 48 85 C0",
        ],
        "instruction_size": 7,
        "offset": 3,
        "type": "rip_relative",
        "description": "Character instance lookup",
    },
}


# ============================================================
# Entity structure offsets (relative to ChrIns base)
# ============================================================

ENTITY_OFFSETS = {
    # Character instance base offsets
    "hp": 0x1F8,              # Current HP (float)
    "hp_max": 0x1FC,          # Maximum HP (float)
    "posture": 0x210,         # Current posture (float)
    "posture_max": 0x214,     # Maximum posture (float)
    "stamina": 0x200,         # Current stamina (float)
    "stamina_max": 0x204,     # Maximum stamina (float)

    # Status effects
    "burn": 0x230,            # Burn status (float)
    "poison": 0x234,          # Poison status (float)

    # Position and rotation
    "position_x": 0x6C,       # World X coordinate (float)
    "position_y": 0x70,       # World Y coordinate (float)
    "position_z": 0x74,       # World Z coordinate (float)
    "rotation_y": 0x68,       # Y-axis rotation (float)

    # Character state
    "team_type": 0x70,        # Team affiliation (int32)
    "force_play_anim": 0x368, # Force animation ID
    "is_dead": 0x230,         # Death flag (byte)
    "is_parrying": 0x3A0,     # Parry state flag

    # Animation data
    "anim_id": 0x320,         # Current animation ID (int32)
    "anim_time": 0x330,       # Animation playback time (float)
    "anim_length": 0x334,     # Animation total length (float)
    "anim_speed": 0x338,      # Animation speed multiplier (float)

    # Combat
    "attack_phase": 0x3B0,    # Current attack phase (int32)
    "is_attacking": 0x3B4,    # Attacking flag (byte)
    "guard_type": 0x3C0,      # Guard/parry type (int32)
    "super_armor": 0x3D0,     # Super armor frames (float)
}


# ============================================================
# Animation ID ranges for attack classification
# ============================================================

ANIM_CATEGORIES = {
    "idle": range(0, 100),
    "walk": range(100, 200),
    "run": range(200, 300),
    "dodge": range(300, 400),
    "attack_light": range(1000, 1100),
    "attack_heavy": range(1100, 1200),
    "attack_thrust": range(1200, 1300),
    "attack_sweep": range(1300, 1400),
    "attack_grab": range(1400, 1500),
    "attack_jump": range(1500, 1600),
    "attack_perilous": range(1600, 1800),
    "parry_success": range(2000, 2100),
    "parry_fail": range(2100, 2200),
    "death": range(3000, 3100),
    "stagger": range(3100, 3200),
}


class PatternScanner:
    """
    Scans game memory for known byte patterns.

    Caches discovered addresses for fast repeated lookups.
    Handles RIP-relative addressing common in 64-bit code.
    """

    def __init__(self, reader: ProcessReader):
        self.reader = reader
        self._address_cache: Dict[str, int] = {}
        self._scan_timestamps: Dict[str, float] = {}
        self._patterns = dict(SEKIRO_PATTERNS)
        self._entity_offsets = dict(ENTITY_OFFSETS)

    @property
    def entity_offsets(self) -> Dict[str, int]:
        return self._entity_offsets

    @property
    def anim_categories(self) -> Dict[str, range]:
        return ANIM_CATEGORIES

    def clear_cache(self):
        """Clear all cached addresses."""
        self._address_cache.clear()
        self._scan_timestamps.clear()

    def find_pattern(self, name: str, force_rescan: bool = False) -> Optional[int]:
        """
        Find a named pattern and return its resolved address.

        Uses caching to avoid repeated scans. Tries multiple pattern
        variants if the first one fails. Handles RIP-relative
        addressing resolution automatically.

        Args:
            name: Pattern name from SEKIRO_PATTERNS
            force_rescan: Bypass cache and rescan

        Returns:
            Resolved address, or None if not found
        """
        if name in self._address_cache and not force_rescan:
            return self._address_cache[name]

        pattern_info = self._patterns.get(name)
        if not pattern_info:
            logger.warning(f"Unknown pattern: {name}")
            return None

        # Support both single "pattern" and multiple "patterns" keys
        pattern_list = pattern_info.get("patterns", [])
        if not pattern_list and "pattern" in pattern_info:
            pattern_list = [pattern_info["pattern"]]

        if not pattern_list:
            logger.warning(f"No patterns defined for: {name}")
            return None

        logger.info(
            f"Scanning for pattern: {name} - {pattern_info['description']} "
            f"({len(pattern_list)} variant(s))"
        )

        # Try each pattern variant
        for i, pattern_str in enumerate(pattern_list):
            raw_address = self.reader.scan_pattern(pattern_str)
            if raw_address is not None:
                logger.info(
                    f"  Variant {i+1}/{len(pattern_list)} matched at 0x{raw_address:X}"
                )

                # Resolve the address based on type
                resolved = self._resolve_address(
                    raw_address,
                    pattern_info["instruction_size"],
                    pattern_info["offset"],
                    pattern_info["type"],
                )

                if resolved:
                    self._address_cache[name] = resolved
                    self._scan_timestamps[name] = time.time()
                    logger.info(
                        f"Found {name} at 0x{resolved:X} "
                        f"(raw: 0x{raw_address:X}, variant {i+1})"
                    )
                    return resolved
                else:
                    logger.debug(
                        f"  Variant {i+1} matched but address resolution failed"
                    )
            else:
                logger.debug(f"  Variant {i+1}/{len(pattern_list)}: no match")

        logger.warning(f"Pattern not found (all {len(pattern_list)} variants failed): {name}")
        return None

    def _resolve_address(
        self,
        raw_address: int,
        instruction_size: int,
        offset: int,
        address_type: str,
    ) -> Optional[int]:
        """
        Resolve a raw pattern match to the actual data address.

        For RIP-relative addressing (most common in 64-bit):
          actual_address = match_address + instruction_size + read_i32(match_address + offset)
        """
        if address_type == "rip_relative":
            # Read the 32-bit relative offset embedded in the instruction
            rel_offset_data = self.reader.read_bytes(raw_address + offset, 4)
            if rel_offset_data is None:
                return None

            import struct
            rel_offset = struct.unpack("<i", rel_offset_data)[0]

            # RIP-relative: address = next_instruction + relative_offset
            resolved = raw_address + instruction_size + rel_offset
            return resolved

        elif address_type == "direct":
            # Direct address - the match IS the address
            return raw_address

        elif address_type == "pointer_chain":
            # Follow a pointer chain from the match
            return raw_address

        else:
            logger.warning(f"Unknown address type: {address_type}")
            return raw_address

    def find_all_patterns(self) -> Dict[str, Optional[int]]:
        """
        Scan for all known patterns.

        Returns dict mapping pattern names to their resolved addresses.
        """
        results = {}
        for name in self._patterns:
            results[name] = self.find_pattern(name)
        return results

    def get_cached_address(self, name: str) -> Optional[int]:
        """Get a previously cached address without scanning."""
        return self._address_cache.get(name)

    def validate_addresses(self) -> Dict[str, bool]:
        """
        Validate that cached addresses still point to valid data.

        Returns dict mapping pattern names to validity status.
        """
        results = {}
        for name, address in self._address_cache.items():
            # Try reading a byte at the address to validate
            data = self.reader.read_bytes(address, 1)
            results[name] = data is not None
        return results

    def classify_animation(self, anim_id: int) -> str:
        """
        Classify an animation ID into a category.

        Args:
            anim_id: Raw animation ID from game memory

        Returns:
            Category name string
        """
        for category, id_range in ANIM_CATEGORIES.items():
            if anim_id in id_range:
                return category
        return "unknown"

    def is_attack_animation(self, anim_id: int) -> bool:
        """Check if animation ID represents an attack."""
        category = self.classify_animation(anim_id)
        return category.startswith("attack_")

    def is_perilous_attack(self, anim_id: int) -> bool:
        """Check if animation is a perilous (unblockable) attack."""
        return anim_id in range(1600, 1800)

    def get_attack_type(self, anim_id: int) -> str:
        """Get the specific attack type for display."""
        category = self.classify_animation(anim_id)
        type_names = {
            "attack_light": "Light Attack",
            "attack_heavy": "Heavy Attack",
            "attack_thrust": "Thrust Attack",
            "attack_sweep": "Sweep Attack",
            "attack_grab": "Grab Attack",
            "attack_jump": "Jump Attack",
            "attack_perilous": "Perilous Attack",
        }
        return type_names.get(category, "Unknown")

    def add_custom_pattern(self, name: str, pattern: str, **kwargs):
        """
        Add a custom pattern for scanning.

        Args:
            name: Unique name for the pattern
            pattern: AOB pattern string with ?? wildcards
            **kwargs: Additional pattern info (instruction_size, offset, type)
        """
        existing = self._patterns.get(name, {})
        patterns = existing.get("patterns", [])
        patterns.append(pattern)

        self._patterns[name] = {
            "patterns": patterns,
            "instruction_size": kwargs.get("instruction_size", existing.get("instruction_size", 7)),
            "offset": kwargs.get("offset", existing.get("offset", 3)),
            "type": kwargs.get("type", existing.get("type", "rip_relative")),
            "description": kwargs.get("description", existing.get("description", f"Custom: {name}")),
        }

    def set_manual_address(self, name: str, address: int):
        """
        Manually set an address, bypassing pattern scanning.

        Useful when patterns don't match and you know the correct
        address from Cheat Engine or other tools.

        Args:
            name: Pattern name (e.g., "WorldChrMan")
            address: Known address value
        """
        self._address_cache[name] = address
        self._scan_timestamps[name] = time.time()
        logger.info(f"Manual address set: {name} = 0x{address:X}")

    def get_scan_report(self) -> dict:
        """Get a report of all pattern scan results."""
        report = {
            "scanned": {},
            "not_found": [],
            "cached": {},
        }

        for name in self._patterns:
            if name in self._address_cache:
                report["cached"][name] = {
                    "address": hex(self._address_cache[name]),
                    "timestamp": self._scan_timestamps.get(name, 0),
                }
            else:
                report["not_found"].append(name)

        return report
