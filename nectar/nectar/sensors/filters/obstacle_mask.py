"""Rangefinder filter that masks readings while crossing an obstacle.

Algorithm
---------
While not masking, the filter maintains a rolling average of recent raw
readings. A drop greater than ``max_change_m`` below that average flags
entry; the pre-entry baseline and the entry sample are snapshotted.

The obstacle height is by default **auto-estimated** as
``pre_baseline - entry_raw``. For the first ``estimate_lock_s`` after
entry, ``entry_raw`` is refined downward whenever a deeper sample arrives
(captures the deepest beam reading as the obstacle is fully crossed).
After the lock window the height is frozen, so subsequent drone descent
over the obstacle does not inflate the estimate.

Pass ``obstacle_height_m`` explicitly to override the estimate with a
fixed value (useful for SITL or known fixtures).

Exit is declared when the raw reading climbs back above
``entry_raw + max_change_m``, or after ``timeout_s`` elapses.
"""

import time
from collections import deque
from typing import Optional


class ObstacleMaskFilter:
    """
    Mask rangefinder samples while the beam is over an obstacle.

    Parameters
    ----------
    obstacle_height_m : float, optional
        Vertical thickness of the obstacle in meters. ``None`` (default)
        enables auto-estimation from the entry drop magnitude. A positive
        value locks the height to that constant.
    max_change_m : float, optional
        Magnitude of sample-to-baseline drop that triggers entry, and the
        magnitude of recovery above ``entry_raw`` that triggers exit.
        Default 0.30 m (at 50 Hz this excludes any physically achievable
        descent rate).
    avg_window : int, optional
        Number of recent samples averaged for the entry baseline. Default 10.
    estimate_lock_s : float, optional
        Refinement window after entry during which ``entry_raw`` may be
        updated downward. After this elapses the height is frozen until
        exit. Ignored when ``obstacle_height_m`` is set. Default 0.2 s.
    timeout_s : float, optional
        Maximum time to remain in the masked state before forcing a reset.
        ``None`` disables the safety. Default 5.0 s.

    Notes
    -----
    The entry baseline is only updated outside the masked state, so a long
    masked period does not corrupt the average. While masked, raw samples
    are not pushed into the rolling window.
    """

    def __init__(
        self,
        obstacle_height_m: Optional[float] = None,
        *,
        max_change_m: float = 0.30,
        avg_window: int = 10,
        estimate_lock_s: float = 0.2,
        timeout_s: Optional[float] = 5.0,
    ) -> None:
        if obstacle_height_m is not None and obstacle_height_m <= 0:
            raise ValueError("obstacle_height_m, when set, must be positive")
        if max_change_m <= 0:
            raise ValueError("max_change_m must be positive")
        if avg_window < 1:
            raise ValueError("avg_window must be >= 1")
        if estimate_lock_s < 0:
            raise ValueError("estimate_lock_s must be >= 0")

        self._fixed_height: Optional[float] = obstacle_height_m
        self._max_change_m = max_change_m
        self._estimate_lock_s = estimate_lock_s
        self._timeout_s = timeout_s
        self._window: deque[float] = deque(maxlen=avg_window)

        self._over_obstacle = False
        self._entry_raw: Optional[float] = None
        self._entry_time: Optional[float] = None
        self._pre_baseline: Optional[float] = None
        self._locked = False

    @property
    def is_masking(self) -> bool:
        """Whether the filter is currently masking readings."""
        return self._over_obstacle

    @property
    def estimated_height_m(self) -> Optional[float]:
        """Current obstacle-height estimate, or ``None`` outside the masked state."""
        return self._height() if self._over_obstacle else None

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

            if not self._locked:
                if raw_distance < self._entry_raw:
                    self._entry_raw = raw_distance
                if (time.monotonic() - self._entry_time) >= self._estimate_lock_s:
                    self._locked = True

            return raw_distance + self._height()

        if not self._window:
            self._window.append(raw_distance)
            return raw_distance

        baseline = sum(self._window) / len(self._window)
        if raw_distance < baseline - self._max_change_m:
            self._enter_masked_state(raw_distance, baseline)
            return raw_distance + self._height()

        self._window.append(raw_distance)
        return raw_distance

    def reset(self) -> None:
        """Clear all internal state."""
        self._window.clear()
        self._exit_masked_state()

    def _height(self) -> float:
        if self._fixed_height is not None:
            return self._fixed_height
        return self._pre_baseline - self._entry_raw

    def _enter_masked_state(self, raw_distance: float, pre_baseline: float) -> None:
        self._over_obstacle = True
        self._entry_raw = raw_distance
        self._entry_time = time.monotonic()
        self._pre_baseline = pre_baseline
        self._locked = self._estimate_lock_s == 0

    def _exit_masked_state(self) -> None:
        self._over_obstacle = False
        self._entry_raw = None
        self._entry_time = None
        self._pre_baseline = None
        self._locked = False

    def _timed_out(self) -> bool:
        if self._timeout_s is None or self._entry_time is None:
            return False
        return (time.monotonic() - self._entry_time) >= self._timeout_s
