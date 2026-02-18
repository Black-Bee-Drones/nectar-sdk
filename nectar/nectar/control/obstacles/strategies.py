from abc import ABC, abstractmethod
from threading import Event
from typing import TYPE_CHECKING, Optional

from nectar.control.protocols import ObstacleDirection, ObstacleInfo

if TYPE_CHECKING:
    from nectar.control.base import BaseDrone


class AvoidanceStrategy(ABC):
    """
    Abstract base for obstacle avoidance strategies.

    Strategies define how drone responds to obstacle detection.
    """

    @abstractmethod
    def execute(self, drone: "BaseDrone", info: ObstacleInfo) -> bool:
        """
        Execute avoidance behavior.

        Parameters
        ----------
        drone : BaseDrone
            Drone instance for control commands.
        info : ObstacleInfo
            Current obstacle detection info.

        Returns
        -------
        bool
            True if navigation should continue, False to pause.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal strategy state."""
        pass


class PauseStrategy(AvoidanceStrategy):
    """
    Pause navigation when obstacle detected.

    Sends zero velocity command when obstacle present, resumes when clear.
    """

    def __init__(self):
        self._paused = False

    def execute(self, drone: "BaseDrone", info: ObstacleInfo) -> bool:
        if info.detected:
            if not self._paused:
                drone.node.get_logger().info("Obstacle detected - pausing")
                self._paused = True
            drone.move_velocity(0, 0, 0, 0)
            return False
        else:
            if self._paused:
                drone.node.get_logger().info("Path clear - resuming")
                self._paused = False
            return True

    def reset(self) -> None:
        self._paused = False


class DisableAxisStrategy(AvoidanceStrategy):
    """
    Disable specific axis control during obstacle detection.

    Used for terrain following where altitude PID should defer to ArduPilot's
    rangefinder-based altitude control.

    Parameters
    ----------
    disable_x : bool, default=False
        Disable forward/backward control.
    disable_y : bool, default=False
        Disable lateral control.
    disable_z : bool, default=False
        Disable altitude control.
    """

    def __init__(self, disable_x: bool = False, disable_y: bool = False, disable_z: bool = False):
        self.disable_x = disable_x
        self.disable_y = disable_y
        self.disable_z = disable_z

    def execute(self, drone: "BaseDrone", info: ObstacleInfo) -> bool:
        return not info.detected

    def reset(self) -> None:
        pass


class SequenceStrategy(AvoidanceStrategy):
    """
    Execute callable sequence when obstacle detected.

    Sequence function receives drone and obstacle info, executes drone.move_to() directly.

    Parameters
    ----------
    sequence_func : callable
        Function with signature (drone: BaseDrone, info: ObstacleInfo, **kwargs) -> None.
    """

    def __init__(self, sequence_func):
        self._sequence_func = sequence_func
        self._executed = False
        self._executing = Event()

    def execute(self, drone: "BaseDrone", info: ObstacleInfo) -> bool:
        if not info.detected:
            self._executed = False
            return True

        if self._executed or self._executing.is_set():
            return False

        self._executing.set()
        self._executed = True

        try:
            self._sequence_func(drone, info)
        finally:
            self._executing.clear()

        return False

    def reset(self) -> None:
        self._executed = False
        self._executing.clear()


def lateral_pass_return_sequence(
    drone: "BaseDrone",
    info: ObstacleInfo,
    lateral_distance: float = 1.0,
    forward_distance: float = 2.5,
    precision: float = 0.2,
):
    lateral = _compute_lateral(info.direction, lateral_distance)

    drone.node.get_logger().info(f"Executing lateral-pass-return: {lateral:.2f}m lateral")

    drone.move_to(x=0.0, y=lateral, z=0.0, precision=precision, timeout=10.0)
    drone.move_to(x=forward_distance, y=0.0, z=0.0, precision=precision, timeout=10.0)
    drone.move_to(x=0.0, y=-lateral, z=0.0, precision=precision, timeout=10.0)

    drone.node.get_logger().info("Evasion sequence completed")


def lateral_pass_sequence(
    drone: "BaseDrone",
    info: ObstacleInfo,
    lateral_distance: float = 1.0,
    forward_distance: float = 2.5,
    precision: float = 0.2,
):
    lateral = _compute_lateral(info.direction, lateral_distance)

    drone.move_to(x=0.0, y=lateral, z=0.0, precision=precision, timeout=10.0)
    drone.move_to(x=forward_distance, y=0.0, z=0.0, precision=precision, timeout=10.0)


def simple_lateral_sequence(
    drone: "BaseDrone",
    info: ObstacleInfo,
    lateral_distance: float = 1.0,
    precision: float = 0.2,
):
    lateral = _compute_lateral(info.direction, lateral_distance)
    drone.move_to(x=0.0, y=lateral, z=0.0, precision=precision, timeout=10.0)


def climb_over_sequence(
    drone: "BaseDrone",
    info: ObstacleInfo,
    climb_height: float = 1.0,
    forward_distance: float = 2.5,
    precision: float = 0.2,
):
    drone.move_to(x=0.0, y=0.0, z=climb_height, precision=precision, timeout=10.0)
    drone.move_to(x=forward_distance, y=0.0, z=0.0, precision=precision, timeout=10.0)
    drone.move_to(x=0.0, y=0.0, z=-climb_height, precision=precision, timeout=10.0)


def _compute_lateral(direction: Optional[ObstacleDirection], distance: float) -> float:
    if direction == ObstacleDirection.LEFT:
        return -distance
    elif direction == ObstacleDirection.RIGHT:
        return distance
    else:
        return distance
