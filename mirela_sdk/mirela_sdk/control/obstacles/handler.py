from threading import Lock
from typing import TYPE_CHECKING, Optional

from rclpy.node import Node

from mirela_sdk.control.obstacles.strategies import (
    AvoidanceStrategy,
    DisableAxisStrategy,
)
from mirela_sdk.control.obstacles.types import ObstacleHandlerConfig
from mirela_sdk.control.protocols import ObstacleDetector, ObstacleInfo

if TYPE_CHECKING:
    from mirela_sdk.control.base import BaseDrone


class ObstacleHandler:
    """
    Combines obstacle detector with avoidance strategy.

    Parameters
    ----------
    detector : ObstacleDetector
        Detector implementation.
    strategy : AvoidanceStrategy
        Avoidance strategy implementation.
    node : Node
        ROS2 node for timer creation.
    config : ObstacleHandlerConfig, optional
        Handler configuration. If None, uses defaults.
    """

    def __init__(
        self,
        detector: ObstacleDetector,
        strategy: AvoidanceStrategy,
        node: Node,
        config: Optional[ObstacleHandlerConfig] = None,
    ):
        self._detector = detector
        self._strategy = strategy
        self._node = node
        self._config = config or ObstacleHandlerConfig()
        self._last_info: ObstacleInfo = ObstacleInfo(detected=False)
        self._lock = Lock()
        self._timer = None

        if self._config.update_rate > 0:
            self._timer = node.create_timer(
                self._config.update_rate,
                self._update_callback,
            )

    def _update_callback(self) -> None:
        with self._lock:
            if self._config.enabled and self._detector.is_enabled:
                self._last_info = self._detector.update()

    @property
    def detector(self) -> ObstacleDetector:
        return self._detector

    @property
    def strategy(self) -> AvoidanceStrategy:
        return self._strategy

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled and self._detector.is_enabled

    @property
    def last_info(self) -> ObstacleInfo:
        with self._lock:
            return self._last_info

    def enable(self) -> None:
        self._config.enabled = True
        self._detector.enable()

    def disable(self) -> None:
        self._config.enabled = False
        self._detector.disable()

    def update(self) -> ObstacleInfo:
        with self._lock:
            if self.is_enabled:
                self._last_info = self._detector.update()
            return self._last_info

    def should_continue(self, drone: "BaseDrone") -> bool:
        """
        Query if navigation should continue based on obstacle state.

        Executes strategy's decision logic. Thread-safe access to detection state.

        Parameters
        ----------
        drone : BaseDrone
            Drone instance for strategy execution.

        Returns
        -------
        bool
            True if navigation should continue, False to pause.
        """
        with self._lock:
            info = self._last_info

        if not self.is_enabled:
            return True

        return self._strategy.execute(drone, info)

    def get_axis_modifiers(self) -> tuple[bool, bool, bool]:
        """
        Get axis disable flags from strategy.

        Returns
        -------
        tuple of (bool, bool, bool)
            (disable_x, disable_y, disable_z) flags.
        """
        if not self.is_enabled or not self._last_info.detected:
            return (False, False, False)

        if isinstance(self._strategy, DisableAxisStrategy):
            return (
                self._strategy.disable_x,
                self._strategy.disable_y,
                self._strategy.disable_z,
            )

        return (False, False, False)

    def reset(self) -> None:
        """Reset detector and strategy state."""
        with self._lock:
            self._detector.reset()
            self._strategy.reset()
            self._last_info = ObstacleInfo(detected=False)

    def cleanup(self) -> None:
        """Disable detector and cancel timer."""
        self.disable()
        if self._timer:
            self._timer.cancel()


class ObstacleManager:
    """
    Manages multiple obstacle handlers for a drone.
    """

    def __init__(self):
        self._handlers: dict[str, ObstacleHandler] = {}

    def add(self, name: str, handler: ObstacleHandler) -> None:
        """
        Add obstacle handler.

        Parameters
        ----------
        name : str
            Unique identifier.
        handler : ObstacleHandler
            Handler instance.
        """
        self._handlers[name] = handler

    def remove(self, name: str) -> Optional[ObstacleHandler]:
        """
        Remove and cleanup obstacle handler.

        Parameters
        ----------
        name : str
            Handler identifier.

        Returns
        -------
        ObstacleHandler, optional
            Removed handler, or None if not found.
        """
        handler = self._handlers.pop(name, None)
        if handler:
            handler.cleanup()
        return handler

    def get(self, name: str) -> Optional[ObstacleHandler]:
        """Get handler by name."""
        return self._handlers.get(name)

    def enable(self, name: str) -> None:
        """Enable handler by name."""
        if handler := self._handlers.get(name):
            handler.enable()

    def disable(self, name: str) -> None:
        """Disable handler by name."""
        if handler := self._handlers.get(name):
            handler.disable()

    def enable_all(self) -> None:
        """Enable all registered handlers."""
        for handler in self._handlers.values():
            handler.enable()

    def disable_all(self) -> None:
        """Disable all registered handlers."""
        for handler in self._handlers.values():
            handler.disable()

    def should_continue_navigation(self, drone: "BaseDrone") -> bool:
        """
        Check if navigation should continue.

        Queries all enabled handlers. If any returns False, navigation pauses.

        Parameters
        ----------
        drone : BaseDrone
            Drone instance for strategy execution.

        Returns
        -------
        bool
            True if all handlers allow navigation, False to pause.
        """
        for handler in self._handlers.values():
            if handler.is_enabled and not handler.should_continue(drone):
                return False
        return True

    def get_axis_control(self) -> tuple[bool, bool, bool]:
        """
        Get combined axis disable flags from all handlers.

        Returns
        -------
        tuple of (bool, bool, bool)
            (disable_x, disable_y, disable_z). True if any handler requests disable.
        """
        disable_x = False
        disable_y = False
        disable_z = False

        for handler in self._handlers.values():
            if handler.is_enabled:
                dx, dy, dz = handler.get_axis_modifiers()
                disable_x = disable_x or dx
                disable_y = disable_y or dy
                disable_z = disable_z or dz

        return (disable_x, disable_y, disable_z)

    def reset_all(self) -> None:
        """Reset all handlers."""
        for handler in self._handlers.values():
            handler.reset()

    def cleanup(self) -> None:
        """Cleanup all handlers and clear registry."""
        for handler in self._handlers.values():
            handler.cleanup()
        self._handlers.clear()

    @property
    def handlers(self) -> dict[str, ObstacleHandler]:
        """Dictionary of all registered handlers."""
        return self._handlers
