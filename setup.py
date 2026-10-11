"""
Sekiro Trainer - Setup Script
==============================
Installs dependencies and verifies the environment.

Run: python setup.py
"""

import sys
import subprocess
import os
from pathlib import Path


def check_python_version():
    """Verify Python version."""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("  ⚠ Python 3.10+ recommended")
        return False
    print("  ✓ Version OK")
    return True


def check_platform():
    """Verify platform."""
    import platform
    system = platform.system()
    print(f"Platform: {system} {platform.release()}")
    if system != "Windows":
        print("  ⚠ Windows required for game memory access")
        print("  (Overlay can still be tested on other platforms)")
        return False
    print("  ✓ Platform OK")
    return True


def install_dependencies():
    """Install Python dependencies."""
    requirements = Path(__file__).parent / "requirements.txt"
    if not requirements.exists():
        print("  ✗ requirements.txt not found")
        return False

    print(f"Installing from {requirements}...")

    # Try with --break-system-packages first (for PEP 668 environments)
    pip_cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
    result = subprocess.run(pip_cmd, capture_output=True, text=True)

    if result.returncode != 0 and "externally-managed" in result.stderr:
        print("  Retrying with --break-system-packages...")
        pip_cmd.append("--break-system-packages")
        result = subprocess.run(pip_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ✗ Installation failed:")
        print(result.stderr)
        return False

    print("  ✓ Dependencies installed")
    return True


def verify_imports():
    """Verify key imports work."""
    modules = {
        "pymem": "Memory reading",
        "PyQt5": "Overlay rendering",
        "numpy": "Math operations",
        "psutil": "Process management",
    }

    all_ok = True
    for module, purpose in modules.items():
        try:
            __import__(module)
            print(f"  ✓ {module} ({purpose})")
        except ImportError:
            print(f"  ✗ {module} ({purpose}) - NOT INSTALLED")
            all_ok = False

    # Optional modules
    optional = {
        "keyboard": "Hotkey support",
        "toml": "Config file parsing",
        "colorama": "Colored console output",
    }

    for module, purpose in optional.items():
        try:
            __import__(module)
            print(f"  ✓ {module} ({purpose})")
        except ImportError:
            print(f"  ○ {module} ({purpose}) - optional, not installed")

    return all_ok


def verify_project_structure():
    """Check that all project files exist."""
    root = Path(__file__).parent
    required_files = [
        "main.py",
        "config.toml",
        "requirements.txt",
        "trainer/__init__.py",
        "trainer/memory/process_reader.py",
        "trainer/memory/pattern_scanner.py",
        "trainer/memory/pointers.py",
        "trainer/memory/structures.py",
        "trainer/game/game_state.py",
        "trainer/game/entity.py",
        "trainer/game/animation.py",
        "trainer/game/combat.py",
        "trainer/overlay/window.py",
        "trainer/overlay/widgets.py",
        "trainer/overlay/parry_display.py",
        "trainer/overlay/hud.py",
        "trainer/assistant/parry_trainer.py",
        "trainer/assistant/pattern_learner.py",
        "trainer/assistant/stats.py",
    ]

    all_ok = True
    for file_path in required_files:
        full_path = root / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} - MISSING")
            all_ok = False

    return all_ok


def run_demo_test():
    """Quick test of the demo mode."""
    print("\nRunning quick demo test (5 seconds)...")
    try:
        # Import and test core modules
        sys.path.insert(0, str(Path(__file__).parent))
        from main import DemoMode
        demo = DemoMode()
        state = demo.get_world_state()

        if state and state.player and state.nearest_enemy:
            print(f"  ✓ Player: {state.player.name}")
            print(f"    HP: {state.player.combat.hp:.0f}/{state.player.combat.hp_max:.0f}")
            print(f"  ✓ Enemy: {state.nearest_enemy.name}")
            print(f"    HP: {state.nearest_enemy.combat.hp:.0f}/{state.nearest_enemy.combat.hp_max:.0f}")
            print(f"    Anim: {state.nearest_enemy.animation.category}")
            print(f"  ✓ Demo data generation working")
            return True
        else:
            print("  ✗ Demo data generation failed")
            return False
    except Exception as e:
        print(f"  ✗ Demo test error: {e}")
        return False


def main():
    print()
    print("╔═══════════════════════════════════════╗")
    print("║   ⚔ Sekiro Trainer Setup ⚔           ║")
    print("╚═══════════════════════════════════════╝")
    print()

    # Step 1: Check environment
    print("── Environment Check ──")
    check_python_version()
    check_platform()
    print()

    # Step 2: Install dependencies
    print("── Dependencies ──")
    install_dependencies()
    print()

    # Step 3: Verify imports
    print("── Module Verification ──")
    verify_imports()
    print()

    # Step 4: Verify project structure
    print("── Project Structure ──")
    verify_project_structure()
    print()

    # Step 5: Quick demo test
    print("── Demo Test ──")
    run_demo_test()
    print()

    # Summary
    print("═══════════════════════════════════════")
    print()
    print("Setup complete!")
    print()
    print("Quick Start:")
    print("  Demo mode:  python main.py --demo")
    print("  With game:  python main.py")
    print("  Debug:      python main.py --debug")
    print()
    print("Hotkeys: F1=Toggle Overlay  F2=Parry Assist")
    print("         F3=HUD  F4=Stats  F12=Quit")
    print()
    print("═══════════════════════════════════════")


if __name__ == "__main__":
    main()
