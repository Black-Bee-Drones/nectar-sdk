"""Benewake TF-series single-point LiDAR UART driver.

Reads the standard 9-byte UART frame (``0x59 0x59``, Dist, Strength, Temp,
checksum). Each :meth:`BenewakeTF.read`
drains whatever bytes are available, parses every full frame, and returns the
most recent valid distance.
"""

from dataclasses import dataclass, replace
from typing import Optional

import serial

HEADER = b"\x59\x59"
FRAME_SIZE = 9
SATURATED_STRENGTH = 0xFFFF


@dataclass(frozen=True)
class BenewakeModel:
    """Per-model validity and advertised range. Values from Benewake manuals."""

    name: str
    min_strength: int
    invalid_dist_cm: frozenset[int]
    min_range_m: float
    max_range_m: float
    ambient_overexposure: Optional[int] = None


MODELS: dict[str, BenewakeModel] = {
    "tfluna": BenewakeModel(
        name="tfluna",
        min_strength=100,
        invalid_dist_cm=frozenset(),
        min_range_m=0.05,
        max_range_m=8.0,
        ambient_overexposure=32768,
    ),  # ref: https://en.benewake.com/TFLuna/
    "tfmini-s": BenewakeModel(
        name="tfmini-s",
        min_strength=100,
        invalid_dist_cm=frozenset({65535, 65534, 65532}),
        min_range_m=0.10,
        max_range_m=12.0,
    ),  # ref: https://en.benewake.com/TFminiS/
    "tf02-pro": BenewakeModel(
        name="tf02-pro",
        min_strength=60,
        invalid_dist_cm=frozenset({4500, 65534}),
        min_range_m=0.10,
        max_range_m=40.0,
    ),  # ref: https://en.benewake.com/TF02Pro/
}


def decode_frame(frame: bytes, model: BenewakeModel) -> Optional[float]:
    """Return distance in meters from a 9-byte frame, or ``None`` if invalid."""
    if len(frame) != FRAME_SIZE:
        return None
    if (sum(frame[:8]) & 0xFF) != frame[8]:
        return None

    strength = frame[4] | (frame[5] << 8)
    if strength < model.min_strength or strength == SATURATED_STRENGTH:
        return None
    if model.ambient_overexposure is not None and strength > model.ambient_overexposure:
        return None

    dist_cm = frame[2] | (frame[3] << 8)
    if dist_cm in model.invalid_dist_cm:
        return None
    return dist_cm / 100.0


class BenewakeTF:
    """
    Benewake TF-series serial driver (factory 9-byte/cm UART).

    Parameters
    ----------
    port : str
        Serial device path (e.g. ``"/dev/ttyUSB0"``).
    model : str, optional
        ``"tfluna"`` (default), ``"tfmini-s"``, or ``"tf02-pro"``.
    baudrate : int, optional
        Default 115200 (factory setting).
    timeout : float, optional
        Serial read timeout in seconds. Default 0.02.
    min_strength : int, optional
        Override the model's minimum accepted signal strength.
    """

    def __init__(
        self,
        port: str,
        model: str = "tfluna",
        baudrate: int = 115200,
        timeout: float = 0.02,
        min_strength: Optional[int] = None,
    ) -> None:
        if model not in MODELS:
            raise ValueError(f"unknown Benewake model {model!r}; valid: {', '.join(MODELS)}")
        profile = MODELS[model]
        if min_strength is not None:
            profile = replace(profile, min_strength=min_strength)

        self._model = profile
        self._ser = serial.Serial(port, baudrate, timeout=timeout)
        self._buffer = bytearray()

    @property
    def model(self) -> str:
        return self._model.name

    @property
    def min_range_m(self) -> float:
        return self._model.min_range_m

    @property
    def max_range_m(self) -> float:
        return self._model.max_range_m

    def read(self) -> Optional[float]:
        """
        Drain the serial buffer and return the latest valid distance in meters.

        Returns ``None`` when no full valid frame is currently buffered.
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
        idx = self._buffer.find(HEADER)
        if idx < 0:
            self._buffer.clear()
            return None

        if len(self._buffer) - idx < FRAME_SIZE:
            if idx > 0:
                del self._buffer[:idx]
            return None

        frame = bytes(self._buffer[idx : idx + FRAME_SIZE])
        del self._buffer[: idx + FRAME_SIZE]
        return decode_frame(frame, self._model)
