# ⚔️ Sekiro Overlay Trainer

**A perfect parry training assistant for Sekiro: Shadows Die Twice**

A real-time transparent overlay that reads game memory and character animations to help you master Sekiro's deflect system. Tracks enemy attack patterns, shows perfect parry timing windows, and provides combat statistics to measure your progress.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Game](https://img.shields.io/badge/game-Sekiro-red)

## ✨ Features

### 🎯 Perfect Parry Assistant
- **Countdown Ring** — Visual ring shrinks to zero at the perfect deflect moment
- **Timing Classification** — PERFECT / EARLY / LATE / MISS feedback with color coding
- **Accuracy Tracking** — Real-time parry accuracy percentage and streak counter
- **Auto-Difficulty** — Progressive difficulty scaling adjusts timing windows as you improve

### 📊 Enhanced HUD
- **Player Bars** — HP, posture, and stamina with animated damage indicators
- **Enemy Bars** — Enemy HP/posture with distance readout
- **Combat Phase** — Shows current combat state (Pressure / Defensive / Engaged)
- **Attack Pattern** — Identifies incoming attack types with counter suggestions

### 🧠 Pattern Recognition
- **Animation Reading** — Reads enemy animation IDs and classifies attack types
- **Combo Tracking** — Logs enemy attack sequences for pattern analysis
- **Next Attack Prediction** — Markov chain prediction of likely next attack
- **Perilous Detection** — Identifies perilous attacks (thrust/sweep/grab) with counter suggestions

### 📈 Training Statistics
- **Session Tracking** — Deaths, parry count, accuracy, best streak
- **Boss Fight Records** — Per-boss attempt/win tracking
- **All-Time History** — Persistent progress across sessions
- **Progress Reports** — Detailed text reports of training improvement

### 🎮 Overlay Features
- **Transparent & Click-Through** — Doesn't interfere with gameplay
- **Always-On-Top** — Renders over the game window
- **Customizable** — Opacity, scale, position, and toggleable elements
- **Hotkey Control** — F1-F6 for toggling features, F12 to quit

---

## 🚀 Quick Start

### Prerequisites
- **Windows 10/11** (required for memory access)
- **Python 3.10+** (64-bit)
- **Sekiro: Shadows Die Twice** (Steam version recommended)
- **Administrator privileges** (needed to read game memory)

### Installation

```bash
# Clone the repository
git clone <repo-url> Sekiro
cd Sekiro

# Install dependencies
pip install -r requirements.txt

# Run in demo mode (no game needed - tests the overlay)
python main.py --demo

# Run with the game
python main.py
```

### Windows Quick Launch

```bat
# Double-click to run:
start_trainer.bat

# Or run as administrator from command prompt:
python main.py
```

---

## 🎮 Controls

| Hotkey | Action |
|--------|--------|
| **F1** | Toggle overlay visibility |
| **F2** | Toggle parry assistant |
| **F3** | Toggle enhanced HUD |
| **F4** | Toggle training stats |
| **F5** | Reset session stats |
| **F6** | Toggle settings panel |
| **F12** | Quit trainer |

All hotkeys are configurable in `config.toml`.

---

## 🏗️ Architecture

```
Sekiro/
├── main.py                     # Entry point & app controller
├── config.toml                 # Configuration file
├── requirements.txt            # Python dependencies
│
├── trainer/
│   ├── memory/                 # Game memory reading
│   │   ├── process_reader.py   # Low-level memory access (pymem)
│   │   ├── pattern_scanner.py  # AOB signature scanning
│   │   ├── pointers.py         # Pointer chains & offsets
│   │   └── structures.py       # Game data structures
│   │
│   ├── game/                   # Game state management
│   │   ├── game_state.py       # Central state coordinator
│   │   ├── entity.py           # Entity tracking with history
│   │   ├── animation.py        # Animation state & timing analysis
│   │   └── combat.py           # Combat phase detection
│   │
│   ├── overlay/                # Visual overlay (PyQt5)
│   │   ├── window.py           # Transparent overlay window
│   │   ├── widgets.py          # Custom drawn UI widgets
│   │   ├── parry_display.py    # Parry timing visualization
│   │   └── hud.py              # Enhanced HUD elements
│   │
│   └── assistant/              # Training assistants
│       ├── parry_trainer.py    # Perfect parry trainer
│       ├── pattern_learner.py  # Attack pattern learning
│       └── stats.py            # Statistics tracking
│
└── assets/
    └── fonts/                  # Custom fonts
```

### Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│  Sekiro.exe  │────▶│ProcessReader │────▶│ PatternScanner │
│  (Game Proc) │     │  (pymem)     │     │ (AOB Scanning) │
└─────────────┘     └──────┬───────┘     └───────┬────────┘
                           │                      │
                    ┌──────▼──────────────────────▼──────┐
                    │          GamePointers               │
                    │  (Pointer chains → entity data)     │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        GameStateManager              │
                    │  (WorldState with player + enemies)  │
                    └──┬──────────┬───────────┬───────────┘
                       │          │           │
              ┌────────▼───┐ ┌───▼────┐ ┌───▼──────┐
              │AnimationTracker│ │Combat  │ │Entity   │
              │(Timing Analysis)│ │Analyzer│ │Manager  │
              └────────┬───┘ └───┬────┘ └───┬──────┘
                       │          │           │
              ┌────────▼──────────▼───────────▼──────────┐
              │             ParryTrainer                   │
              │  (Timing classification + scoring)         │
              └────────────────┬───────────────────────────┘
                               │
              ┌────────────────▼───────────────────────────┐
              │          OverlayWindow (PyQt5)              │
              │  ┌──────────┐  ┌────────────────────────┐  │
              │  │ ParryRing │  │     EnhancedHUD        │  │
              │  │ (Countdown│  │ (HP/Posture/Stats/    │  │
              │  │  Ring)    │  │  Combat Phase)         │  │
              │  └──────────┘  └────────────────────────┘  │
              └────────────────────────────────────────────┘
```

---

## ⚙️ Configuration

Edit `config.toml` to customize:

```toml
[overlay]
opacity = 0.85          # Overlay transparency
scale = 1.0             # UI scale factor
click_through = true    # Clicks pass through to game

[parry_assistant]
perfect_window_ms = 50  # Perfect parry window (±50ms)
early_window_ms = 150   # Early timing window
late_window_ms = 100    # Late timing window
show_countdown = true   # Show countdown ring
show_result_flash = true # Flash PERFECT/EARLY/LATE

[hud]
show_player_hp = true
show_enemy_hp = true
show_combat_stats = true
show_coordinates = false  # Debug: show world coordinates
```

---

## 🔧 Development

### Demo Mode
Test the overlay without the game running:
```bash
python main.py --demo
```

### Debug Mode
Enable verbose logging:
```bash
python main.py --debug
```

### Adding Custom Patterns
```python
from trainer.memory.pattern_scanner import PatternScanner

scanner.add_custom_pattern(
    name="MyPattern",
    pattern="48 8B 05 ?? ?? ?? ?? 48 85 C0",
    instruction_size=7,
    offset=3,
    type="rip_relative",
    description="My custom pattern"
)
```

### Updating Offsets
When Sekiro receives a game update, memory offsets may change. Update them in:
- `trainer/memory/pointers.py` — Structure offsets
- `trainer/memory/pattern_scanner.py` — AOB signatures

---

## ⚠️ Important Notes

1. **Anti-Cheat**: Sekiro uses EasyAntiCheat (EAC). This trainer reads memory only — it does not modify game files or inject code. However, use at your own risk in online modes.

2. **Game Version**: Current patterns are for Sekiro v1.06 (Steam). Patterns may need updating after game patches.

3. **Performance**: The overlay runs at ~120 FPS with <1% CPU overhead. Memory polling uses <2% CPU.

4. **Administrator**: Memory reading requires administrator privileges on Windows.

5. **Resolution**: The overlay auto-detects your screen resolution. Adjust `scale` in config for high-DPI displays.

---

## 📋 Attack Types Reference

| Attack Type | Icon | Counter | Parry Window |
|-------------|------|---------|-------------|
| Light Slash | ⚔️ | Deflect | ~250ms |
| Heavy Slam | 🔨 | Deflect | ~420ms |
| Thrust | ➡️ | Mikiri Counter | ~350ms |
| Sweep | ↙️ | Jump over | ~380ms |
| Grab | 🤜 | Dodge/Run | Cannot parry |
| Jump Attack | ⬆️ | Deflect | ~300ms |
| Perilous | ⚠️ | Type-specific | Cannot parry |

---

## 📄 License

This project is for educational purposes only. Sekiro: Shadows Die Twice is a trademark of FromSoftware Inc.
