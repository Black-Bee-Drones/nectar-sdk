"""Benewake TF-Luna single-point LiDAR driver.

Reads the standard 9-byte UART frame format documented at
https://en.benewake.com/TFLuna/. The driver is non-blocking: each
:meth:`read` drains whatever bytes are available, parses every full
frame found, and returns the most recent valid distance. Bad-checksum
and low-signal frames are dropped per the Benewake spec.
"""

from typing import Optional

import serial


class TFLuna:
    """
    Benewake TF-Luna serial driver.

    Parameters
    ----------
    port : str
        Serial device path (e.g. ``"/dev/ttyUSB0"``).
    baudrate : int, optional
        Default 115200 (TF-Luna factory setting).
    timeout : float, optional
        Serial read timeout in seconds. Small non-zero value avoids
        busy-polling while still keeping :meth:`read` snappy. Default 0.02.
    min_strength : int, optional
        Minimum signal strength to accept a frame. Frames below this or
        equal to ``0xFFFF`` are discarded per Benewake's data sheet.
        Default 100.
    """

    HEADER = b"\x59\x59"
    FRAME_SIZE = 9
    BAD_STRENGTH = 0xFFFF

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 0.02,
        min_strength: int = 100,
    ) -> None:
        self._ser = serial.Serial(port, baudrate, timeout=timeout)
        self._buffer = bytearray()
        self._min_strength = min_strength

    def read(self) -> Optional[float]:
        """
        Drain the serial buffer and return the latest valid distance in meters.

        Returns ``None`` when no full valid frame is currently buffered
        """
        pending = self._ser.in_waiting
        if pending:
            self._buffer.extend(self._ser.read(pending))

        latest: Optional[float] = None
        while True:
            value = self._parse_one_frame()
            if value is None:
                break
            latest = value
        return latest

    def close(self) -> None:
        """Close the underlying serial port."""
        if self._ser.is_open:
            self._ser.close()

    def _parse_one_frame(self) -> Optional[float]:
        """Find and consume the next valid frame in the buffer."""
        idx = self._buffer.find(self.HEADER)
        if idx < 0:
            self._buffer.clear()
            return None

        if len(self._buffer) - idx < self.FRAME_SIZE:
            if idx > 0:
                del self._buffer[:idx]
            return None

        frame = bytes(self._buffer[idx : idx + self.FRAME_SIZE])
        del self._buffer[: idx + self.FRAME_SIZE]

        if (sum(frame[:8]) & 0xFF) != frame[8]:
            return None

        strength = frame[4] | (frame[5] << 8)
        if strength < self._min_strength or strength == self.BAD_STRENGTH:
            return None

        dist_cm = frame[2] | (frame[3] << 8)
        return dist_cm / 100.0
