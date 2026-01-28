from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class AbstractCam(ABC):
    """
    Abstract base class for camera implementations.

    All camera drivers must implement start(), get_frame(), and close() methods.

    Parameters
    ----------
    name : str, optional
        Camera identifier for logging. Default is 'camera'.

    Attributes
    ----------
    name : str
        Camera identifier.
    is_running : bool
        True if camera is started and ready for capture.
    """

    def __init__(self, name: str = "camera") -> None:
        self._name = name
        self._is_running: bool = False

    @property
    def name(self) -> str:
        """Camera identifier."""
        return self._name

    @property
    def is_running(self) -> bool:
        """True if camera is started and ready for capture."""
        return self._is_running

    @abstractmethod
    def start(self) -> None:
        """
        Initialize and start the camera.

        Must be called before get_frame(). Sets is_running to True on success.

        Raises
        ------
        RuntimeError
            If camera initialization fails.
        """
        raise NotImplementedError("Subclasses must implement a start method")

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Capture and return a single frame.

        Returns
        -------
        np.ndarray or None
            BGR image as numpy array, or None if capture failed.
        """
        raise NotImplementedError("Subclasses must implement a get_frame method")

    @abstractmethod
    def close(self) -> None:
        """
        Release camera resources.

        Sets is_running to False. Safe to call multiple times.
        """
        raise NotImplementedError("Subclasses must implement a close method")


class DepthCam(AbstractCam, ABC):
    """
    Abstract base class for depth-capable cameras.

    Extends AbstractCam with depth frame capture and distance measurement.
    """

    @abstractmethod
    def get_depth_frame(self) -> Optional[np.ndarray]:
        """
        Capture and return depth frame.

        Returns
        -------
        np.ndarray or None
            Depth image in meters (float32), or None if capture failed.
        """
        raise NotImplementedError("Subclasses must implement a get_depth_frame method")

    @abstractmethod
    def get_distance(self, u: int, v: int) -> Optional[float]:
        """
        Get distance at pixel coordinates.

        Parameters
        ----------
        u : int
            Horizontal pixel coordinate (column).
        v : int
            Vertical pixel coordinate (row).

        Returns
        -------
        float or None
            Distance in meters, or None if invalid/unavailable.
        """
        raise NotImplementedError("Subclasses must implement a get_distance method")
