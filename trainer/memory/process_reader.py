"""
Process Memory Reader
=====================
Low-level memory reading from the Sekiro process.

Uses pymem for process attachment and raw memory access.
Handles pointer dereferencing, type conversion, and error recovery.
"""

import ctypes
import struct
import logging
import time
from typing import Optional, Union, List, Tuple

logger = logging.getLogger(__name__)

try:
    import pymem
    import pymem.process
    import pymem.pattern
    HAS_PYMEM = True
except ImportError:
    HAS_PYMEM = False
    logger.warning("pymem not installed - using stub implementation for development")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class MemoryReadError(Exception):
    """Raised when a memory read operation fails."""
    pass


class ProcessReader:
    """
    Reads memory from the Sekiro process.

    Provides typed memory reads (int32, float, string, bytes)
    and pointer chain dereferencing. Handles reconnection
    when the game restarts.
    """

    PROCESS_NAME = "sekiro.exe"
    PROCESS_ACCESS = 0x1F0FFF  # PROCESS_ALL_ACCESS

    def __init__(self, process_name: str = None):
        self.process_name = process_name or self.PROCESS_NAME
        self._pm: Optional["pymem.Pymem"] = None
        self._process_handle = None
        self._base_address: int = 0
        self._is_attached: bool = False
        self._last_scan_time: float = 0
        self._modules_cache: dict = {}

    @property
    def is_attached(self) -> bool:
        """Whether currently attached to the game process."""
        return self._is_attached and self._pm is not None

    @property
    def base_address(self) -> int:
        """Base address of the main game module."""
        return self._base_address

    def connect(self) -> bool:
        """
        Attempt to connect to the Sekiro process.

        Returns True if successfully attached, False otherwise.
        """
        if not HAS_PYMEM:
            logger.error("pymem not available - cannot attach to process")
            return self._create_stub_connection()

        try:
            self._pm = pymem.Pymem(self.process_name)
            self._base_address = pymem.process.module_from_name(
                self._pm.process_handle, self.process_name
            ).lpBaseOfDll
            self._is_attached = True
            self._modules_cache.clear()
            logger.info(
                f"Attached to {self.process_name} (PID: {self._pm.process_id}, "
                f"Base: 0x{self._base_address:X})"
            )
            return True
        except pymem.exception.ProcessNotFound:
            self._is_attached = False
            logger.debug(f"Process {self.process_name} not found")
            return False
        except pymem.exception.PymemError as e:
            self._is_attached = False
            logger.error(f"Failed to attach to {self.process_name}: {e}")
            return False

    def _create_stub_connection(self) -> bool:
        """Create a stub connection for development without the game running."""
        self._is_attached = True
        self._base_address = 0x140000000
        logger.info("Using stub connection (development mode)")
        return True

    def disconnect(self):
        """Disconnect from the game process."""
        if self._pm:
            try:
                self._pm.close()
            except Exception:
                pass
        self._pm = None
        self._is_attached = False
        self._base_address = 0
        self._modules_cache.clear()
        logger.info("Disconnected from game process")

    def reconnect(self) -> bool:
        """Attempt to reconnect after losing connection."""
        self.disconnect()
        time.sleep(0.5)
        return self.connect()

    def is_process_alive(self) -> bool:
        """Check if the game process is still running."""
        if not self._pm:
            return False
        if HAS_PSUTIL:
            try:
                proc = psutil.Process(self._pm.process_id)
                return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return False
        return True

    def get_module_base(self, module_name: str) -> Optional[int]:
        """Get the base address of a loaded module."""
        if module_name in self._modules_cache:
            return self._modules_cache[module_name]

        if not self._pm:
            return None

        try:
            module = pymem.process.module_from_name(
                self._pm.process_handle, module_name
            )
            base = module.lpBaseOfDll
            self._modules_cache[module_name] = base
            return base
        except Exception:
            return None

    def read_bytes(self, address: int, length: int) -> Optional[bytes]:
        """Read raw bytes from memory."""
        if not self.is_attached:
            return None

        try:
            if self._pm:
                return self._pm.read_bytes(address, length)
            return None
        except Exception as e:
            logger.debug(f"Read error at 0x{address:X} ({length} bytes): {e}")
            self._is_attached = False
            return None

    def read_int32(self, address: int) -> Optional[int]:
        """Read a 32-bit signed integer."""
        data = self.read_bytes(address, 4)
        if data is None:
            return None
        return struct.unpack("<i", data)[0]

    def read_uint32(self, address: int) -> Optional[int]:
        """Read a 32-bit unsigned integer."""
        data = self.read_bytes(address, 4)
        if data is None:
            return None
        return struct.unpack("<I", data)[0]

    def read_int64(self, address: int) -> Optional[int]:
        """Read a 64-bit signed integer."""
        data = self.read_bytes(address, 8)
        if data is None:
            return None
        return struct.unpack("<q", data)[0]

    def read_uint64(self, address: int) -> Optional[int]:
        """Read a 64-bit unsigned integer."""
        data = self.read_bytes(address, 8)
        if data is None:
            return None
        return struct.unpack("<Q", data)[0]

    def read_float(self, address: int) -> Optional[float]:
        """Read a 32-bit float."""
        data = self.read_bytes(address, 4)
        if data is None:
            return None
        return struct.unpack("<f", data)[0]

    def read_double(self, address: int) -> Optional[float]:
        """Read a 64-bit double."""
        data = self.read_bytes(address, 8)
        if data is None:
            return None
        return struct.unpack("<d", data)[0]

    def read_string(self, address: int, max_length: int = 256) -> Optional[str]:
        """Read a null-terminated ASCII string."""
        data = self.read_bytes(address, max_length)
        if data is None:
            return None
        null_idx = data.find(b"\x00")
        if null_idx >= 0:
            data = data[:null_idx]
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return None

    def read_vector3(self, address: int) -> Optional[Tuple[float, float, float]]:
        """Read a 3D vector (x, y, z) as three floats."""
        data = self.read_bytes(address, 12)
        if data is None:
            return None
        x, y, z = struct.unpack("<fff", data)
        return (x, y, z)

    def read_matrix4x4(self, address: int) -> Optional[List[List[float]]]:
        """Read a 4x4 transformation matrix."""
        data = self.read_bytes(address, 64)
        if data is None:
            return None
        values = struct.unpack("<16f", data)
        return [list(values[i:i+4]) for i in range(0, 16, 4)]

    def read_pointer_chain(self, base: int, offsets: List[int]) -> Optional[int]:
        """
        Dereference a pointer chain.

        Follows: base -> [base + offsets[0]] -> [+ offsets[1]] -> ...

        Args:
            base: Starting address
            offsets: List of offsets to follow

        Returns:
            Final address, or None if any dereference fails
        """
        if not offsets:
            return base

        current = base

        for i, offset in enumerate(offsets):
            if i == 0:
                # First offset: read pointer at base + offset
                ptr_data = self.read_bytes(current + offset, 8)
            else:
                # Subsequent: read pointer at current + offset
                ptr_data = self.read_bytes(current + offset, 8)

            if ptr_data is None:
                logger.debug(
                    f"Pointer chain broke at offset {i} "
                    f"(0x{offset:X} from 0x{current:X})"
                )
                return None

            current = struct.unpack("<Q", ptr_data)[0]

            if current == 0 or current > 0x7FFFFFFFFFFF:
                logger.debug(f"Invalid pointer value: 0x{current:X}")
                return None

        return current

    def write_bytes(self, address: int, data: bytes) -> bool:
        """Write raw bytes to memory."""
        if not self.is_attached or not self._pm:
            return False
        try:
            self._pm.write_bytes(address, data, len(data))
            return True
        except Exception as e:
            logger.debug(f"Write error at 0x{address:X}: {e}")
            return False

    def write_int32(self, address: int, value: int) -> bool:
        """Write a 32-bit signed integer."""
        return self.write_bytes(address, struct.pack("<i", value))

    def write_float(self, address: int, value: float) -> bool:
        """Write a 32-bit float."""
        return self.write_bytes(address, struct.pack("<f", value))

    def _parse_aob_pattern(self, pattern: str) -> bytes:
        """
        Parse an AOB pattern string into bytes.

        Converts "48 8B 05 ?? ?? ??" to b'\\x48\\x8B\\x05???'.
        Wildcards (??) become single '?' bytes for pymem.

        Args:
            pattern: Space-separated hex bytes with ?? wildcards

        Returns:
            Pattern as bytes suitable for pymem scanning
        """
        result = []
        for byte_str in pattern.split():
            if byte_str in ("??", "?"):
                result.append(ord("?"))
            else:
                result.append(int(byte_str, 16))
        return bytes(result)

    def scan_pattern(self, pattern: str, module_name: str = None) -> Optional[int]:
        """
        Scan for a byte pattern in memory.

        Args:
            pattern: Space-separated hex bytes with ?? for wildcards
            module_name: Module to scan (None = main game module)

        Returns:
            Address of first match, or None
        """
        if not HAS_PYMEM or not self._pm:
            return None

        try:
            # Parse pattern string to proper bytes
            aob_pattern = self._parse_aob_pattern(pattern)

            if module_name:
                module = pymem.process.module_from_name(
                    self._pm.process_handle, module_name
                )
                result = pymem.pattern.pattern_scan_module(
                    aob_pattern, module, return_multiple=False
                )
            else:
                result = pymem.pattern.pattern_scan_all(
                    self._pm.process_handle, aob_pattern
                )
            return result
        except Exception as e:
            logger.debug(f"Pattern scan failed for '{pattern}': {e}")
            return None
