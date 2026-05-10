"""Sensor protocols."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class DistanceSensor(Protocol):
    """One-shot distance sensor.

    Implementations should be non-blocking: ``read`` returns the latest
    valid measurement available right now, or ``None`` if no fresh valid
    reading is ready (e.g. partial frame, bad checksum, low signal).
    """

    def read(self) -> Optional[float]:
        """Return the latest distance in meters, or ``None`` if unavailable."""
        ...

    def close(self) -> None:
        """Release any underlying resources (serial port, file handle, etc.)."""
        ...


@runtime_checkable
class DistanceFilter(Protocol):
    """Stateful filter mapping a raw distance reading to a processed value.

    A filter may suppress a reading entirely by returning ``None``.
    """

    def process(self, raw_distance: float) -> Optional[float]:
        """Process one raw reading and return the filtered distance."""
        ...

    def reset(self) -> None:
        """Clear internal state."""
        ...
