"""Rangefinder filter that masks readings while crossing a known-height obstacle.

When a downward-facing rangefinder is the EKF altitude source, flying over
a fixed obstacle (e.g. a sphere on a hose) causes a step drop in the
reading that ArduPilot interprets as the vehicle descending. The position
controller then climbs to compensate, lifting the drone above its target
altitude. This filter detects the step drop, masks the affected samples,
and reports a stable altitude until the obstacle is cleared.

Algorithm
---------
While not over an obstacle, the filter maintains a rolling average of
recent raw readings. A drop greater than ``max_change_m`` below that
average flags entry; the raw value at entry is saved as ``entry_raw``.
While over an obstacle the filter returns ``raw + obstacle_height_m``,
which keeps the masked output close to the pre-entry baseline. Exit is
declared when the raw reading climbs back above ``entry_raw + max_change_m``,
or after ``timeout_s`` has elapsed (safety reset).
"""

import time
from collections import deque
from typing import Optional


class ObstacleMaskFilter:
    """
    Mask rangefinder samples while the beam is over a known-height obstacle.

    Parameters
    ----------
    obstacle_height_m : float
        Vertical thickness of the expected obstacle, in meters. The masked
        output adds this to each raw reading while in the masked state.
    max_change_m : float, optional
        Magnitude of sample-to-baseline drop that triggers entry, and the
        magnitude of recovery above ``entry_raw`` that triggers exit.
        Default 0.30.
    avg_window : int, optional
        Number of recent samples averaged for the entry baseline. Default 10.
    timeout_s : float, optional
        Maximum time to remain in the masked state before forcing a reset.
        ``None`` disables the safety. Default 5.0.

    Notes
    -----
    The entry baseline is only updated outside the masked state, so a long
    masked period does not corrupt the average. While masked, raw samples
    are not pushed into the rolling window.
    """

    def __init__(
        self,
        obstacle_height_m: float,
        *,
        max_change_m: float = 0.30,
        avg_window: int = 10,
        timeout_s: Optional[float] = 5.0,
    ) -> None:
        if obstacle_height_m <= 0:
            raise ValueError("obstacle_height_m must be positive")
        if max_change_m <= 0:
            raise ValueError("max_change_m must be positive")
        if avg_window < 1:
            raise ValueError("avg_window must be >= 1")

        self._obstacle_height_m = obstacle_height_m
        self._max_change_m = max_change_m
        self._timeout_s = timeout_s
        self._window: deque[float] = deque(maxlen=avg_window)
        self._over_obstacle = False
        self._entry_raw: Optional[float] = None
        self._entry_time: Optional[float] = None

    @property
    def is_masking(self) -> bool:
        """Whether the filter is currently masking readings."""
        return self._over_obstacle

    def process(self, raw_distance: float) -> Optional[float]:
        """
        Apply the mask to a raw reading.

        Parameters
        ----------
        raw_distance : float
            Raw rangefinder reading in meters. ``None`` is not accepted;
            callers should skip invalid samples upstream.

        Returns
        -------
        float
            The filtered distance in meters.
        """
        if self._over_obstacle:
            if self._timed_out() or raw_distance > self._entry_raw + self._max_change_m:
                self._exit_masked_state()
                return raw_distance
            return raw_distance + self._obstacle_height_m

        self._window.append(raw_distance)
        baseline = sum(self._window) / len(self._window)
        if raw_distance < baseline - self._max_change_m:
            self._enter_masked_state(raw_distance)
            return raw_distance + self._obstacle_height_m
        return raw_distance

    def reset(self) -> None:
        """Clear all internal state."""
        self._window.clear()
        self._exit_masked_state()

    def _enter_masked_state(self, raw_distance: float) -> None:
        self._over_obstacle = True
        self._entry_raw = raw_distance
        self._entry_time = time.monotonic()

    def _exit_masked_state(self) -> None:
        self._over_obstacle = False
        self._entry_raw = None
        self._entry_time = None

    def _timed_out(self) -> bool:
        if self._timeout_s is None or self._entry_time is None:
            return False
        return (time.monotonic() - self._entry_time) >= self._timeout_s
