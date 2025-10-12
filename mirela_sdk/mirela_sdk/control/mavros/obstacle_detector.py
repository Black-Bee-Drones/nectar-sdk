from collections import deque
from typing import Optional
import numpy as np


class LidarObstacleDetector:
    """
    Detects obstacles using lidar altitude variation over time.

    When the drone passes over an object (like a table or platform), the lidar
    altitude reading changes rapidly. This detector identifies such changes and
    temporarily disables PID altitude control, allowing the Pixhawk's internal
    rangefinder-based altitude control to handle the situation.

    The detector uses a timeout-based approach: once an obstacle is detected,
    altitude control remains disabled for a specified duration to prevent
    oscillations while the drone passes over the obstacle.
    """

    def __init__(
        self,
        buffer_size: int = 10,
        height_threshold: float = 0.25,
        timeout: float = 8.0,
    ):
        """
        Initialize obstacle detector.

        Parameters
        ----------
        buffer_size : int
            Number of lidar samples to keep for baseline calculation.
            Used to determine the average altitude before obstacle detection.
        height_threshold : float
            Minimum height change (meters) to trigger obstacle detection.
            Lower values detect smaller obstacles but may cause false positives.
        timeout : float
            Duration (seconds) to maintain obstacle state after detection.
            This prevents oscillations while the drone passes over the obstacle.
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
            True if obstacle is detected (altitude control should be disabled),
            False otherwise.
        """
        self._buffer.append(lidar_altitude)

        if len(self._buffer) < self.buffer_size:
            return False

        self._baseline = np.mean(self._buffer)
        deviation = lidar_altitude - self._baseline

        # Detect new obstacle based on deviation threshold
        if not self._obstacle_detected and abs(deviation) > self.height_threshold:
            self._obstacle_detected = True
            self._obstacle_start_time = current_time
            return True

        if self._obstacle_detected:
            elapsed = current_time - self._obstacle_start_time

            if elapsed > self.timeout:
                # Timeout expired - re-enable altitude control
                self._clear_obstacle_state()
                return False

            # Continue disabling altitude control during timeout
            return True

        return False

    def _clear_obstacle_state(self):
        """Clear obstacle detection state and reset timer."""
        self._obstacle_detected = False
        self._obstacle_start_time = None
        self._buffer.clear()  # Clear buffer for fresh baseline after obstacle

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
