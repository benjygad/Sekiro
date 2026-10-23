"""
Sekiro Pattern Finder
=====================
Helper tool to find correct memory addresses when pattern scanning fails.

This tool helps you:
1. Verify the game process is accessible
2. Scan for common byte sequences
3. Find your player HP address manually
4. Generate pattern signatures from known addresses
5. Test memory reading without the full trainer

Usage:
    python find_patterns.py
    python find_patterns.py --scan-hp
    python find_patterns.py --dump-region 0x140000000 0x1000
    python find_patterns.py --test-address 0x1448A7B30
"""

import sys
import time
import struct
import logging
import argparse
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from trainer.memory.process_reader import ProcessReader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pattern_finder")


def check_process_access():
    """Verify we can attach to the Sekiro process."""
    print("\n═══ Step 1: Process Access Check ═══\n")

    reader = ProcessReader("sekiro.exe")

    print("Attempting to attach to sekiro.exe...")
    if reader.connect():
        print(f"✓ Connected successfully!")
        print(f"  Process ID: {reader._pm.process_id}")
        print(f"  Base Address: 0x{reader.base_address:X}")
        print(f"  Process Handle: {reader._pm.process_handle}")

        # Test basic memory read
        test_data = reader.read_bytes(reader.base_address, 2)
        if test_data:
            print(f"  Memory Read Test: ✓ (MZ header: {test_data.hex()})")
        else:
            print(f"  Memory Read Test: ✗ (cannot read memory)")
            print("  → Try running as Administrator")
            return None

        return reader
    else:
        print("✗ Failed to attach to sekiro.exe")
        print("\nPossible issues:")
        print("  1. Sekiro is not running")
        print("  2. Need to run as Administrator")
        print("  3. Anti-cheat is blocking access")
        print("\nSolutions:")
        print("  • Start Sekiro and wait for it to fully load")
        print("  • Right-click this script → Run as Administrator")
        print("  • Try disabling EasyAntiCheat:")
        print("    - Rename EasyAntiCheat folder in game directory")
        print("    - Or launch with: sekiro.exe -nointro")
        return None


def scan_for_hp(reader: ProcessReader):
    """
    Scan memory for player HP value.

    Asks user for their current HP and searches for it in memory.
    """
    print("\n═══ Step 2: HP Address Scanner ═══\n")

    try:
        hp_value = float(input("Enter your current HP (from game HUD): "))
    except ValueError:
        print("Invalid HP value")
        return

    print(f"\nScanning for float value: {hp_value}")
    print("This may take 30-60 seconds...\n")

    # Convert HP to bytes (little-endian float)
    hp_bytes = struct.pack("<f", hp_value)
    print(f"Searching for bytes: {hp_bytes.hex()}")

    # Scan the game's memory space
    import pymem
    import pymem.pattern

    try:
        # Use pymem's built-in pattern scanner for the HP value
        matches = []

        # Scan in chunks to avoid timeout
        base = reader.base_address
        chunk_size = 0x1000000  # 16MB chunks

        for offset in range(0, 0x10000000, chunk_size):  # Scan 256MB
            addr = base + offset
            try:
                # Read chunk and search for HP bytes
                chunk = reader.read_bytes(addr, chunk_size)
                if chunk:
                    # Find all occurrences
                    pos = 0
                    while True:
                        pos = chunk.find(hp_bytes, pos)
                        if pos == -1:
                            break
                        match_addr = addr + pos
                        matches.append(match_addr)
                        pos += 1

                        if len(matches) > 100:
                            break

            except Exception:
                pass

            if len(matches) > 100:
                break

            # Progress indicator
            if offset % (chunk_size * 4) == 0:
                print(f"  Scanned: {offset // 0x100000}MB...", end="\r")

        print(f"\n\nFound {len(matches)} potential HP addresses:")

        if matches:
            # Show first 20 matches
            for i, addr in enumerate(matches[:20], 1):
                # Try to read context around the address
                context = reader.read_bytes(addr - 16, 48)
                if context:
                    print(f"  {i:2d}. 0x{addr:X}")

            if len(matches) > 20:
                print(f"  ... and {len(matches) - 20} more")

            print(f"\n→ Use Cheat Engine to narrow down:")
            print(f"  1. Take damage in game")
            print(f"  2. Re-scan for new HP value")
            print(f"  3. Repeat until 1-2 addresses remain")
            print(f"  4. Trace pointer chain back to base")
        else:
            print("No matches found")
            print("  → HP might be stored as int instead of float")
            print("  → Or EAC is blocking memory reads")

    except Exception as e:
        print(f"Scan failed: {e}")


def test_address(reader: ProcessReader, address: int):
    """Test reading from a specific address."""
    print(f"\n═══ Testing Address: 0x{address:X} ═══\n")

    # Read different data types
    print("Reading as different types:")

    # Bytes
    data = reader.read_bytes(address, 64)
    if data:
        print(f"  Raw bytes (64): {data[:32].hex()}...")
    else:
        print(f"  ✗ Cannot read from this address")
        return

    # Float
    fval = reader.read_float(address)
    if fval is not None:
        print(f"  Float: {fval}")

    # Int32
    ival = reader.read_int32(address)
    if ival is not None:
        print(f"  Int32: {ival}")

    # Int64
    lval = reader.read_int64(address)
    if lval is not None:
        print(f"  Int64: 0x{lval:X}")

    # String
    sval = reader.read_string(address, 64)
    if sval:
        print(f"  String: {sval[:50]}")

    # Vector3
    vec = reader.read_vector3(address)
    if vec:
        print(f"  Vector3: ({vec[0]:.2f}, {vec[1]:.2f}, {vec[2]:.2f})")


def dump_memory_region(reader: ProcessReader, address: int, size: int):
    """Dump a memory region to a file."""
    print(f"\n═══ Dumping Memory Region ═══")
    print(f"Address: 0x{address:X}")
    print(f"Size: {size} bytes\n")

    data = reader.read_bytes(address, size)
    if not data:
        print("✗ Failed to read memory region")
        return

    # Save to file
    filename = f"memory_dump_0x{address:X}_{size}.bin"
    with open(filename, "wb") as f:
        f.write(data)

    print(f"✓ Saved to: {filename}")
    print(f"\nFirst 256 bytes:")
    for i in range(0, min(256, len(data)), 16):
        hex_str = " ".join(f"{b:02X}" for b in data[i:i+16])
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data[i:i+16])
        print(f"  {address+i:08X}: {hex_str:<48} {ascii_str}")


def generate_signature(reader: ProcessReader, address: int):
    """Generate a byte signature from an address."""
    print(f"\n═══ Generating Signature ═══")
    print(f"Address: 0x{address:X}\n")

    # Read bytes around the address
    data = reader.read_bytes(address - 32, 64)
    if not data:
        print("✗ Cannot read memory")
        return

    # Generate pattern from the bytes
    pattern_bytes = data[32:48]  # 16 bytes starting at address
    pattern = " ".join(f"{b:02X}" for b in pattern_bytes)

    print(f"Raw bytes: {pattern_bytes.hex()}")
    print(f"Pattern:   {pattern}")
    print(f"\nYou can add this to config.toml:")
    print(f'  [game.manual_addresses]')
    print(f'  WorldChrMan = "0x{address:X}"')


def common_pattern_scan(reader: ProcessReader):
    """Try scanning for common FromSoftware engine patterns."""
    print("\n═══ Common Pattern Scan ═══\n")

    common_patterns = [
        ("ChrIns HP", "00 00 C8 42 00 00 00 00"),  # 100.0 float followed by padding
        ("Posture", "00 00 00 43 00 00 C8 42"),    # 128.0 and 100.0 floats
        ("Player Marker", "FF FF FF FF 01 00 00 00"),  # Common player marker
        ("Team Type 1", "01 00 00 00 00 00 00 00"),  # Team type = 1 (player)
        ("Animation ID", "E8 03 00 00"),  # 1000 as int32 (common anim ID)
    ]

    for name, pattern in common_patterns:
        print(f"Scanning for {name}: {pattern}")
        addr = reader.scan_pattern(pattern)
        if addr:
            print(f"  ✓ Found at: 0x{addr:X}")
        else:
            print(f"  ✗ Not found")


def interactive_mode(reader: ProcessReader):
    """Interactive address testing mode."""
    print("\n═══ Interactive Mode ═══")
    print("Commands:")
    print("  r <addr>       - Read from address")
    print("  d <addr> <size> - Dump memory region")
    print("  s <addr>       - Generate signature")
    print("  scan           - Scan common patterns")
    print("  q              - Quit")
    print()

    while True:
        try:
            cmd = input("> ").strip().split()
            if not cmd:
                continue

            if cmd[0] == "q":
                break
            elif cmd[0] == "r" and len(cmd) >= 2:
                addr = int(cmd[1], 16)
                test_address(reader, addr)
            elif cmd[0] == "d" and len(cmd) >= 3:
                addr = int(cmd[1], 16)
                size = int(cmd[2], 16)
                dump_memory_region(reader, addr, size)
            elif cmd[0] == "s" and len(cmd) >= 2:
                addr = int(cmd[1], 16)
                generate_signature(reader, addr)
            elif cmd[0] == "scan":
                common_pattern_scan(reader)
            else:
                print("Unknown command")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Sekiro Pattern Finder - Memory Analysis Tool"
    )
    parser.add_argument(
        "--scan-hp", action="store_true",
        help="Scan for player HP address"
    )
    parser.add_argument(
        "--test-address", type=str,
        help="Test reading from a specific address (hex)"
    )
    parser.add_argument(
        "--dump-region", nargs=2, metavar=("ADDR", "SIZE"),
        help="Dump memory region to file"
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="Enter interactive mode"
    )

    args = parser.parse_args()

    print("\n╔═══════════════════════════════════════╗")
    print("║   Sekiro Pattern Finder               ║")
    print("║   Memory Analysis & Pattern Discovery ║")
    print("╚═══════════════════════════════════════╝")

    # Step 1: Check process access
    reader = check_process_access()
    if not reader:
        print("\n✗ Cannot proceed without process access")
        return 1

    # Run requested operation
    if args.scan_hp:
        scan_for_hp(reader)
    elif args.test_address:
        addr = int(args.test_address, 16)
        test_address(reader, addr)
    elif args.dump_region:
        addr = int(args.dump_region[0], 16)
        size = int(args.dump_region[1], 16)
        dump_memory_region(reader, addr, size)
    elif args.interactive:
        interactive_mode(reader)
    else:
        # Default: show menu
        print("\n═══ What would you like to do? ═══\n")
        print("1. Scan for HP address (helps find player pointer)")
        print("2. Test a specific address")
        print("3. Scan common patterns")
        print("4. Interactive mode")
        print("5. Exit")

        try:
            choice = input("\nChoice [1-5]: ").strip()

            if choice == "1":
                scan_for_hp(reader)
            elif choice == "2":
                addr_str = input("Enter address (hex): ").strip()
                addr = int(addr_str, 16)
                test_address(reader, addr)
            elif choice == "3":
                common_pattern_scan(reader)
            elif choice == "4":
                interactive_mode(reader)
            else:
                print("Exiting...")

        except KeyboardInterrupt:
            pass

    reader.disconnect()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
