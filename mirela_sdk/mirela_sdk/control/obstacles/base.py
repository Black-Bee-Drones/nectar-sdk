from abc import ABC, abstractmethod
from threading import Lock

from mirela_sdk.control.protocols import ObstacleInfo


class BaseObstacleDetector(ABC):
    """
    Thread-safe base class for obstacle detectors.
    Subclasses must implement _detect() for platform-specific detection logic.
    """

    def __init__(self):
        self._enabled = False
        self._lock = Lock()
        self._last_info = ObstacleInfo(detected=False)

    @property
    def is_enabled(self) -> bool:
        """
        Get enabled state.

        Returns
        -------
        bool
            Enabled state.
        """
        with self._lock:
            return self._enabled

    def enable(self) -> None:
        """
        Enable detector
        """
        with self._lock:
            self._enabled = True
            self._on_enable()

    def disable(self) -> None:
        """
        Disable detector and call lifecycle hook.

        Calls _on_disable() for resource cleanup.
        """
        with self._lock:
            self._enabled = False
            self._on_disable()

    def update(self) -> ObstacleInfo:
        """
        Update detection state.

        Thread-safe. Returns cached result if disabled.

        Returns
        -------
        ObstacleInfo
            Detection result.
        """
        with self._lock:
            if not self._enabled:
                return ObstacleInfo(detected=False)
            self._last_info = self._detect()
            return self._last_info

    def get_last_info(self) -> ObstacleInfo:
        """
        Get last detection result.

        Returns
        -------
        ObstacleInfo
            Last detection result.
        """
        with self._lock:
            return self._last_info

    def reset(self) -> None:
        """Reset detection state"""
        with self._lock:
            self._last_info = ObstacleInfo(detected=False)
            self._on_reset()

    @abstractmethod
    def _detect(self) -> ObstacleInfo:
        """
        Implement platform-specific detection logic.

        Returns
        -------
        ObstacleInfo
            Detection result.
        """
        pass

    def _on_enable(self) -> None:
        """Optional hook called during enable(). Override for resource initialization."""
        pass

    def _on_disable(self) -> None:
        """Optional hook called during disable(). Override for resource cleanup."""
        pass

    def _on_reset(self) -> None:
        """Optional hook called during reset(). Override for state reset."""
        pass
