from collections import deque
from typing import Optional


class LidarObstacleDetector:
    """
    Detects obstacles using lidar altitude variation over time.

    When the drone passes under an object, the lidar altitude changes rapidly.
    This detector uses a buffer to track changes and detect when ArduPilot's
    rangefinder-based altitude control should take over.
    """

    def __init__(
        self,
        buffer_size: int = 10,
        height_threshold: float = 0.35,
        timeout: float = 8.0,
    ):
        """
        Initialize obstacle detector.

        Parameters
        ----------
        buffer_size : int
            Number of samples to keep for variation calculation.
        height_threshold : float
            Minimum height change (meters) to trigger obstacle detection.
        timeout : float
            Maximum time (seconds) to maintain obstacle state.
        """
        self.buffer_size = buffer_size
        self.height_threshold = height_threshold
        self.timeout = timeout

        self._buffer: deque[float] = deque(maxlen=buffer_size)
        self._baseline: Optional[float] = None
        self._obstacle_detected = False
        self._obstacle_start_time: Optional[float] = None

    def update(self, lidar_altitude: float, current_time: float) -> bool:
        """
        Update detector with new lidar reading.

        Parameters
        ----------
        lidar_altitude : float
            Current lidar altitude reading (meters).
        current_time : float
            Current timestamp (seconds).

        Returns
        -------
        bool
            True if obstacle is detected, False otherwise.
        """
        self._buffer.append(lidar_altitude)

        if len(self._buffer) < self.buffer_size:
            return False

        # baseline from buffer mean
        if self._baseline is None:
            self._baseline = sum(self._buffer) / len(self._buffer)

        deviation = lidar_altitude - self._baseline

        # obstacle detection
        if not self._obstacle_detected and abs(deviation) > self.height_threshold:
            self._obstacle_detected = True
            self._obstacle_start_time = current_time
            return True

        # obstacle state should be cleared
        if self._obstacle_detected:
            elapsed = current_time - self._obstacle_start_time

            if elapsed > self.timeout:
                self._clear_obstacle_state(lidar_altitude)
                return False

            # obstacle cleared - altitude returned close to baseline
            if abs(deviation) < 0.1:
                self._clear_obstacle_state(lidar_altitude)
                return False

            return True

        return False

    def _clear_obstacle_state(self, current_altitude: float):
        """Clear obstacle detection state and update baseline."""
        self._obstacle_detected = False
        self._obstacle_start_time = None
        self._baseline = current_altitude
        self._buffer.clear()
        self._buffer.append(current_altitude)

    def reset(self):
        """Reset detector to initial state."""
        self._buffer.clear()
        self._baseline = None
        self._obstacle_detected = False
        self._obstacle_start_time = None

    @property
    def is_obstacle_detected(self) -> bool:
        """Check if obstacle is currently detected."""
        return self._obstacle_detected

    def get_elapsed_time(self, current_time: float) -> float:
        """
        Get elapsed time since obstacle detection.

        Parameters
        ----------
        current_time : float
            Current timestamp (seconds).

        Returns
        -------
        float
            Elapsed time in seconds, or 0.0 if no obstacle detected.
        """
        if self._obstacle_detected and self._obstacle_start_time is not None:
            return current_time - self._obstacle_start_time
        return 0.0
