from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class AbstractCam(ABC):
    """
    Base interface for any RGB-capable camera.
    """

    def __init__(self, name: str = "camera") -> None:
        self._name = name
        self._is_running: bool = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_running(self) -> bool:
        return self._is_running

    @abstractmethod
    def start(self) -> None:
        """Start camera acquisition and make frames available."""
        ...

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]:
        """Return the latest BGR frame or None if not available."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release resources and stop acquisition."""
        ...


class DepthCam(AbstractCam, ABC):
    """
    Base interface for cameras capable of producing depth maps and distance queries.
    """

    @abstractmethod
    def get_depth_frame(self) -> Optional[np.ndarray]:
        """Return the latest depth frame (in meters or millimeters, implementation-defined)."""
        ...

    @abstractmethod
    def get_distance(self, u: int, v: int) -> Optional[float]:
        """Return the distance at pixel (u, v) in meters if available, else None."""
        ... 