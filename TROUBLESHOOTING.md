# 🔧 Troubleshooting Guide

## Pattern Scanning Failures

If you see warnings like:
```
Pattern not found (all N variants failed): WorldChrMan
```

This means the byte signatures don't match your Sekiro version. Here's how to fix it:

---

### Step 1: Verify Basic Access

Run the pattern finder tool:
```bash
python find_patterns.py
```

Choose option 1 to verify the trainer can attach to the game.

**If this fails:**
- ✓ Make sure Sekiro is running and fully loaded (past the main menu)
- ✓ Run the script as **Administrator** (right-click → Run as administrator)
- ✓ Check if EAC is blocking access (see "Disabling EAC" below)

---

### Step 2: Find Your HP Address

If the trainer attaches but patterns fail:

```bash
python find_patterns.py --scan-hp
```

1. Look at your HP in the game (e.g., 350)
2. Enter the value when prompted
3. The tool will find potential addresses
4. Take damage in-game to change your HP
5. Re-run the scan with the new HP value
6. Repeat until only 1-2 addresses remain

**Note the address** (e.g., `0x14A3B2C8`)

---

### Step 3: Trace the Pointer Chain

Open **Cheat Engine** and:

1. Add the HP address you found
2. Right-click → "Find out what accesses this address"
3. Attack an enemy or take damage
4. Note the instruction that reads your HP
5. Look at the register used (e.g., `[rsi+1F8]`)
6. The base register (rsi) points to your ChrIns structure
7. Search for what writes to rsi to find the pointer chain

**Typical pointer chain for Sekiro:**
```
sekiro.exe+OFFSET -> pointer -> pointer+0x68 -> ChrIns
```

---

### Step 4: Add Manual Addresses

Once you find the base address, add it to `config.toml`:

```toml
[game.manual_addresses]
WorldChrMan = "0x1448A7B30"  # Replace with your address
```

The trainer will use this address instead of scanning.

---

### Step 5: Generate New Patterns (Advanced)

If you want to contribute working patterns:

```bash
python find_patterns.py --interactive
```

Navigate to a known address and use the `s` command to generate a signature:
```
> s 1448A7B30
```

This outputs a byte pattern you can add to `pattern_scanner.py`.

---

## Disabling EasyAntiCheat (EAC)

**⚠️ Only do this for single-player/offline mode!**

### Method 1: Rename EAC Folder
1. Navigate to your Sekiro installation:
   ```
   Steam\steamapps\common\Sekiro\
   ```
2. Rename the `EasyAntiCheat` folder to `EasyAntiCheat.disabled`
3. Launch the game normally

### Method 2: Launch Without EAC
1. Right-click Sekiro in Steam → Properties
2. Add launch option: `-nointro`
3. Some versions allow launching without EAC this way

### Method 3: Use EAC Bypass
Some community tools can bypass EAC for single-player. Search for "Sekiro EAC bypass" on GitHub.

---

## Common Issues

### "Cannot attach to sekiro.exe"

**Cause:** Game not running or insufficient permissions

**Fix:**
- Start Sekiro and wait for it to fully load
- Run Python/script as Administrator
- Check Task Manager to verify `sekiro.exe` is running

---

### "Memory read failed"

**Cause:** EAC blocking access or invalid address

**Fix:**
- Disable EAC (see above)
- Verify the address is correct
- Try running as Administrator

---

### Overlay doesn't appear

**Cause:** PyQt5 not installed or display issues

**Fix:**
```bash
pip install PyQt5
```

If on Windows with multiple monitors, try:
```toml
[overlay]
position = "top-left"
```

---

### High CPU usage

**Cause:** Polling too frequently

**Fix:**
```toml
[game]
poll_interval_ms = 16  # Increase from 8 to 16 (60 FPS instead of 120)
```

---

### Trainer crashes immediately

**Cause:** Missing dependencies

**Fix:**
```bash
pip install -r requirements.txt
python setup.py  # Run setup verification
```

---

## Finding Patterns for Your Version

If you're comfortable with reverse engineering:

### Using x64dbg

1. Attach x64dbg to `sekiro.exe`
2. Search for strings like "WorldChrMan" or "ChrIns"
3. Find cross-references to locate the singleton pointers
4. Note the instruction bytes at that location
5. Create a pattern with wildcards for address bytes

### Using IDA Pro / Ghidra

1. Load `sekiro.exe` in the disassembler
2. Search for strings: "WorldChrMan", "GameDataMan", etc.
3. Find the functions that reference these strings
4. Look for the singleton access pattern:
   ```asm
   mov rax, cs:WorldChrMan
   ```
5. Note the bytes at that instruction

### Pattern Format

```
48 8B 05 ?? ?? ?? ?? 48 8B 48 68
```

- Each pair is one byte in hex
- `??` is a wildcard (matches any byte)
- Use wildcards for addresses/offsets that change
- Keep at least 8-12 concrete bytes for uniqueness

---

## Sharing Your Patterns

If you find working patterns for your version:

1. Note your Sekiro version (Steam/Epic, version number)
2. List the patterns that work
3. Open an issue or PR on GitHub with the patterns

Example:
```
Version: Sekiro v1.06 (Steam, Build ID 12345)
WorldChrMan: 48 8B 05 ?? ?? ?? ?? 48 8B 48 68 48 85 C9
GameDataMan: 48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58
```

---

## Alternative: Use Cheat Engine Tables

If pattern scanning is too difficult:

1. Download a Sekiro Cheat Engine table from FearLess Cheat Engine
2. Open it in Cheat Engine while Sekiro is running
3. Note the addresses it finds for WorldChrMan, etc.
4. Add those addresses to your `config.toml`

The CE tables are regularly updated by the community and often work with current game versions.

---

## Still Having Issues?

1. Run `python find_patterns.py` and share the output
2. Note your Sekiro version (right-click in Steam → Properties → Updates)
3. Check if you're running as Administrator
4. Try disabling EAC temporarily
5. Open an issue on GitHub with details

---

## Quick Reference

| Problem | Quick Fix |
|---------|-----------|
| Can't attach | Run as Admin, start game first |
| Patterns fail | Use `find_patterns.py --scan-hp` |
| No overlay | `pip install PyQt5` |
| High CPU | Increase `poll_interval_ms` to 16 |
| EAC blocking | Rename `EasyAntiCheat` folder |
| Wrong addresses | Add manual addresses to `config.toml` |

---

## Contact

For help with pattern finding:
- **Cheat Engine Forums**: cheatengine.org
- **FearLess Cheat Engine**: fearlessrevolution.com
- **GitHub Issues**: Open an issue with your game version

Good luck, Shinobi! ⚔️
