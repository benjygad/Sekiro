"""
Sekiro Overlay Trainer - Main Entry Point
==========================================
Orchestrates all trainer components:
- Game memory reading
- Animation tracking
- Parry assistant
- Overlay rendering
- Hotkey management
- Training statistics

Usage:
    python main.py [options]

Options:
    --config FILE   Path to config file (default: config.toml)
    --no-overlay    Run without visual overlay (headless mode)
    --demo          Run in demo mode with simulated data
    --debug         Enable debug logging
"""

import sys
import os
import time
import signal
import logging
import argparse
import threading
from typing import Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# ── Logging Setup ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sekiro_trainer")


# ── Configuration Loading ─────────────────────────────────

def load_config(config_path: str = "config.toml") -> dict:
    """Load configuration from TOML file."""
    try:
        import toml
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return toml.load(f)
        else:
            logger.warning(f"Config file not found: {config_path}")
    except ImportError:
        logger.warning("toml package not available, using defaults")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")

    # Return default configuration
    return {
        "game": {
            "process_name": "sekiro.exe",
            "poll_interval_ms": 8,
            "scan_interval_ms": 2000,
        },
        "overlay": {
            "opacity": 0.85,
            "scale": 1.0,
            "show_on_start": True,
            "click_through": True,
            "position": "top-right",
            "padding": 20,
        },
        "parry_assistant": {
            "enabled": True,
            "perfect_window_ms": 50,
            "early_window_ms": 150,
            "late_window_ms": 100,
            "show_countdown": True,
            "show_result_flash": True,
            "sound_on_perfect": True,
            "show_attack_name": True,
        },
        "hud": {
            "show_player_hp": True,
            "show_player_posture": True,
            "show_enemy_hp": True,
            "show_enemy_posture": True,
            "show_combat_stats": True,
            "show_coordinates": False,
            "show_animation_id": False,
        },
        "training": {
            "auto_death_counter": True,
            "track_parry_success_rate": True,
            "save_history": True,
            "history_file": "training_history.json",
        },
        "hotkeys": {
            "toggle_overlay": "F1",
            "toggle_parry": "F2",
            "toggle_hud": "F3",
            "toggle_stats": "F4",
            "reset_stats": "F5",
            "toggle_settings": "F6",
            "quit": "F12",
        },
    }


# ── Hotkey Manager ────────────────────────────────────────

class HotkeyManager:
    """Manages global hotkey bindings."""

    def __init__(self):
        self._bindings = {}
        self._keyboard = None
        self._active = False

    def setup(self, config: dict, callbacks: dict):
        """Set up hotkey bindings from config."""
        try:
            import keyboard
            self._keyboard = keyboard
        except ImportError:
            logger.warning("keyboard module not available - hotkeys disabled")
            return

        hotkey_config = config.get("hotkeys", {})

        for action, key in hotkey_config.items():
            if action in callbacks:
                try:
                    keyboard.add_hotkey(key, callbacks[action])
                    self._bindings[key] = action
                    logger.info(f"Hotkey: {key} -> {action}")
                except Exception as e:
                    logger.warning(f"Could not bind {key}: {e}")

        self._active = True

    def cleanup(self):
        """Remove all hotkey bindings."""
        if self._keyboard and self._active:
            try:
                self._keyboard.unhook_all()
            except Exception:
                pass
        self._active = False


# ── Demo Mode ─────────────────────────────────────────────

class DemoMode:
    """
    Generates simulated game data for testing the overlay
    without the actual game running.
    """

    def __init__(self):
        import math
        self._math = math
        self._start = time.time()
        self._attack_cycle_time = 0
        self._current_attack = None
        self._attack_phase = 0

        self.attack_patterns = [
            ("attack_light", 0.8),
            ("attack_heavy", 1.2),
            ("attack_thrust", 1.0),
            ("attack_sweep", 1.1),
            ("attack_perilous", 1.5),
        ]
        self._pattern_idx = 0

    def get_world_state(self):
        """Generate simulated WorldState."""
        from trainer.memory.structures import (
            WorldState, CharacterData, CombatState, AnimState,
            Position, AttackPhase, TeamType, GameState
        )

        now = time.time()
        elapsed = now - self._start

        # Simulate attack cycles
        cycle_period = 3.0  # seconds between attacks
        attack_progress = (elapsed % cycle_period) / cycle_period

        if attack_progress < 0.3:
            phase = AttackPhase.NONE
            anim_cat = "idle"
            anim_id = 0
            attack_time = 0
        elif attack_progress < 0.5:
            phase = AttackPhase.WINDUP
            attack_name, _ = self.attack_patterns[
                self._pattern_idx % len(self.attack_patterns)
            ]
            anim_cat = attack_name
            anim_id = 1000 + self._pattern_idx % 7
            attack_time = (attack_progress - 0.3) / 0.2
        elif attack_progress < 0.65:
            phase = AttackPhase.ACTIVE
            attack_name, _ = self.attack_patterns[
                self._pattern_idx % len(self.attack_patterns)
            ]
            anim_cat = attack_name
            anim_id = 1000 + self._pattern_idx % 7
            attack_time = 0.5 + (attack_progress - 0.5) / 0.15 * 0.3
        else:
            phase = AttackPhase.RECOVERY
            anim_cat = "idle"
            anim_id = 0
            attack_time = 0
            if attack_progress > 0.95:
                self._pattern_idx += 1

        is_attack = phase in (AttackPhase.WINDUP, AttackPhase.ACTIVE)
        is_perilous = anim_cat == "attack_perilous"

        # Enemy
        enemy = CharacterData(
            address=0xDEAD0001,
            name="Genichiro",
            team_type=TeamType.BOSS,
            position=Position(x=5.0, y=0, z=3.0),
            rotation_y=self._math.sin(elapsed * 0.5) * 0.5,
            combat=CombatState(
                hp=800 + self._math.sin(elapsed * 0.1) * 200,
                hp_max=1200,
                posture=300 + self._math.sin(elapsed * 0.3) * 200,
                posture_max=600,
                stamina=100,
                stamina_max=100,
                is_attacking=is_attack,
                attack_phase=phase,
            ),
            animation=AnimState(
                anim_id=anim_id,
                anim_time=attack_time * 1.0,
                anim_length=1.0,
                anim_speed=1.0,
                category=anim_cat,
                is_attack=is_attack,
                is_perilous=is_perilous,
                attack_phase=phase,
            ),
        )

        # Player
        player = CharacterData(
            address=0xDEAD0000,
            name="Sekiro",
            team_type=TeamType.PLAYER,
            position=Position(x=2.0, y=0, z=3.0),
            rotation_y=self._math.sin(elapsed * 0.5) * 0.5 + self._math.pi,
            combat=CombatState(
                hp=350 + self._math.sin(elapsed * 0.05) * 50,
                hp_max=450,
                posture=80 + self._math.sin(elapsed * 0.2) * 60,
                posture_max=200,
                stamina=80 + self._math.sin(elapsed * 0.15) * 20,
                stamina_max=100,
                is_guarding=is_attack and phase == AttackPhase.ACTIVE,
            ),
            animation=AnimState(
                anim_id=0,
                anim_time=0,
                anim_length=0,
                anim_speed=1.0,
                category="idle",
            ),
        )

        state = WorldState(
            game_state=GameState.IN_GAME,
            player=player,
            enemies=[enemy],
            nearest_enemy=enemy,
            death_count=int(elapsed // 30),
            fps=120.0,
            frame_count=int(elapsed * 120),
        )

        return state


# ── Main Application ──────────────────────────────────────

class SekiroTrainer:
    """
    Main application controller.

    Ties together all subsystems and manages the application lifecycle.
    """

    def __init__(self, config: dict, demo_mode: bool = False, no_overlay: bool = False):
        self.config = config
        self.demo_mode = demo_mode
        self.no_overlay = no_overlay
        self._running = False

        # Initialize subsystems
        self._init_game_state()
        self._init_assistants()
        self._init_overlay()
        self._init_hotkeys()

    def _init_game_state(self):
        """Initialize game state management."""
        if self.demo_mode:
            self._demo = DemoMode()
            self.game_state = None
        else:
            from trainer.game.game_state import GameStateManager
            self.game_state = GameStateManager(
                process_name=self.config["game"]["process_name"],
                poll_interval_ms=self.config["game"]["poll_interval_ms"],
            )

            # Apply manual address overrides from config
            manual_addrs = self.config.get("game", {}).get("manual_addresses", {})
            if manual_addrs:
                for name, addr_str in manual_addrs.items():
                    try:
                        addr = int(addr_str, 16)
                        if addr > 0:
                            self.game_state.scanner.set_manual_address(name, addr)
                            logger.info(f"Manual override: {name} = 0x{addr:X}")
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid manual address for {name}: {addr_str}")

            self._demo = None

    def _init_assistants(self):
        """Initialize training assistants."""
        from trainer.game.animation import AnimationTracker
        from trainer.game.entity import EntityManager
        from trainer.game.combat import CombatAnalyzer
        from trainer.assistant.parry_trainer import ParryTrainer
        from trainer.assistant.pattern_learner import PatternLearner
        from trainer.assistant.stats import TrainingStats

        self.anim_tracker = AnimationTracker()
        self.entity_manager = EntityManager()
        self.combat_analyzer = CombatAnalyzer()
        self.parry_trainer = ParryTrainer(self.anim_tracker)
        self.pattern_learner = PatternLearner()
        self.training_stats = TrainingStats(
            history_file=self.config["training"].get(
                "history_file", "training_history.json"
            )
        )

        # Configure parry trainer
        parry_config = self.config.get("parry_assistant", {})
        self.parry_trainer.enabled = parry_config.get("enabled", True)

    def _init_overlay(self):
        """Initialize the overlay window system."""
        if self.no_overlay:
            self.overlay_app = None
            self.overlay_window = None
            self.hud = None
            self.parry_display = None
            return

        try:
            from trainer.overlay.window import OverlayApp
            from trainer.overlay.hud import EnhancedHUD
            from trainer.overlay.parry_display import ParryDisplay

            overlay_config = self.config.get("overlay", {})

            self.overlay_app = OverlayApp()
            self.overlay_app.start(
                opacity=overlay_config.get("opacity", 0.85),
                scale=overlay_config.get("scale", 1.0),
            )

            # Wait for window to be ready
            time.sleep(0.5)

            self.overlay_window = self.overlay_app.window
            if self.overlay_window:
                scale = overlay_config.get("scale", 1.0)

                # Create HUD
                self.hud = EnhancedHUD(
                    screen_width=self.overlay_window.width(),
                    screen_height=self.overlay_window.height(),
                    scale=scale,
                )

                # Configure HUD from config
                hud_config = self.config.get("hud", {})
                self.hud.show_player_bars = hud_config.get("show_player_hp", True)
                self.hud.show_enemy_bars = hud_config.get("show_enemy_hp", True)
                self.hud.show_combat_stats = hud_config.get("show_combat_stats", True)
                self.hud.show_coordinates = hud_config.get("show_coordinates", False)
                self.hud.show_animation_debug = hud_config.get("show_animation_id", False)

                # Create parry display
                self.parry_display = ParryDisplay(
                    x=self.overlay_window.width() - 220,
                    y=350,
                    scale=scale,
                )

                # Register draw callback
                self.overlay_window.add_draw_callback(self._draw_overlay)

                logger.info("Overlay initialized")
            else:
                logger.warning("Overlay window not available")
                self.hud = None
                self.parry_display = None

        except Exception as e:
            logger.error(f"Failed to initialize overlay: {e}", exc_info=True)
            self.overlay_app = None
            self.overlay_window = None
            self.hud = None
            self.parry_display = None

    def _init_hotkeys(self):
        """Initialize hotkey bindings."""
        self.hotkey_manager = HotkeyManager()

    def _draw_overlay(self, painter, window):
        """Main overlay draw callback - called each frame."""
        world_state = self._get_world_state()
        if not world_state:
            return

        # Update all subsystems
        self.entity_manager.update(world_state)
        self.anim_tracker.update(world_state)
        self.combat_analyzer.update(world_state)
        if self.parry_trainer:
            self.parry_trainer.update(world_state)

        connected = (
            self.game_state.is_attached if self.game_state else self.demo_mode
        )

        # Draw HUD
        if self.hud:
            combat_stats = self.combat_analyzer.get_combat_stats()
            session_stats = self.training_stats.get_session_stats()
            self.hud.draw(
                painter, window, world_state,
                combat_stats=combat_stats,
                session_stats=session_stats,
                connected=connected,
            )

        # Draw parry display
        if self.parry_display:
            parry_timing = self.parry_trainer.get_timing_data(world_state)
            accuracy_stats = self.parry_trainer.get_accuracy_stats()
            suggestion = self.combat_analyzer.get_suggestion(world_state)

            self.parry_display.draw(
                painter, window,
                parry_timing=parry_timing,
                accuracy_stats=accuracy_stats,
                suggestion=suggestion,
            )

    def _get_world_state(self):
        """Get current world state from game or demo mode."""
        if self.demo_mode:
            return self._demo.get_world_state()
        elif self.game_state:
            return self.game_state.get_state()
        return None

    def start(self):
        """Start the trainer."""
        self._running = True
        self.training_stats.start_session()

        if self.game_state and not self.demo_mode:
            self.game_state.on("player_death", self._on_player_death)
            self.game_state.on("enemy_attack", self._on_enemy_attack)
            self.game_state.start()

        # Set up hotkeys
        callbacks = {
            "toggle_overlay": self._toggle_overlay,
            "toggle_parry": self._toggle_parry,
            "toggle_hud": self._toggle_hud,
            "toggle_stats": self._toggle_stats,
            "reset_stats": self._reset_stats,
            "quit": self.stop,
        }
        self.hotkey_manager.setup(self.config, callbacks)

        mode = "DEMO" if self.demo_mode else "LIVE"
        logger.info(f"═══ Sekiro Trainer Started ({mode} mode) ═══")
        logger.info("Hotkeys:")
        for action, key in self.config.get("hotkeys", {}).items():
            logger.info(f"  {key}: {action}")
        logger.info("═" * 40)

    def stop(self):
        """Stop the trainer."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping Sekiro Trainer...")

        self.hotkey_manager.cleanup()
        self.training_stats.end_session()
        self.pattern_learner.save_patterns()

        if self.game_state:
            self.game_state.stop()
        if self.overlay_app:
            self.overlay_app.stop()

        # Print final report
        print("\n" + self.training_stats.get_progress_report())
        logger.info("Sekiro Trainer stopped")

    def run(self):
        """Main run loop - blocks until stopped."""
        self.start()

        try:
            if self.overlay_app and self.overlay_app.window:
                # Qt event loop handles rendering
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    # Run Qt event loop in current thread
                    while self._running:
                        app.processEvents()
                        time.sleep(0.01)
            else:
                # No overlay - just run the update loop
                while self._running:
                    state = self._get_world_state()
                    if state:
                        self.entity_manager.update(state)
                        self.anim_tracker.update(state)
                        self.combat_analyzer.update(state)
                    time.sleep(0.008)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ── Hotkey Callbacks ──────────────────────────────────

    def _toggle_overlay(self):
        if self.overlay_window:
            self.overlay_window.toggle_visibility()
            state = "ON" if self.overlay_window.visible else "OFF"
            logger.info(f"Overlay: {state}")

    def _toggle_parry(self):
        self.parry_trainer.enabled = not self.parry_trainer.enabled
        if self.parry_display:
            self.parry_display.enabled = self.parry_trainer.enabled
        state = "ON" if self.parry_trainer.enabled else "OFF"
        logger.info(f"Parry Assistant: {state}")

    def _toggle_hud(self):
        if self.hud:
            self.hud.enabled = not self.hud.enabled
            state = "ON" if self.hud.enabled else "OFF"
            logger.info(f"Enhanced HUD: {state}")

    def _toggle_stats(self):
        if self.hud:
            self.hud.show_training_stats = not self.hud.show_training_stats
            state = "ON" if self.hud.show_training_stats else "OFF"
            logger.info(f"Training Stats: {state}")

    def _reset_stats(self):
        self.parry_trainer.reset_session()
        self.training_stats.start_session()
        logger.info("Session stats reset")

    # ── Game Event Handlers ──────────────────────────────

    def _on_player_death(self, state):
        """Handle player death event."""
        self.training_stats.record_death()
        logger.info(f"Death #{state.death_count}")

    def _on_enemy_attack(self, state):
        """Handle enemy attack start event."""
        if state.nearest_enemy:
            enemy_id = hex(state.nearest_enemy.address)
            category = state.nearest_enemy.animation.category
            self.pattern_learner.observe_attack(enemy_id, category)


# ── Entry Point ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sekiro Overlay Trainer - Perfect Parry Assistant"
    )
    parser.add_argument(
        "--config", default="config.toml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--no-overlay", action="store_true",
        help="Run without visual overlay"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run in demo mode with simulated data"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    config = load_config(args.config)

    # Handle graceful shutdown
    trainer = None

    def signal_handler(sig, frame):
        if trainer:
            trainer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run trainer
    trainer = SekiroTrainer(
        config=config,
        demo_mode=args.demo,
        no_overlay=args.no_overlay,
    )

    trainer.run()


if __name__ == "__main__":
    main()
