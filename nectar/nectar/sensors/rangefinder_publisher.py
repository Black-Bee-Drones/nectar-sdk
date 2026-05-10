"""Rangefinder-to-MAVLink publisher.

Composes a :class:`DistanceSensor`, an optional :class:`DistanceFilter`,
and a :class:`MavlinkConnection`. Runs a background thread that reads
the sensor, applies the filter, and sends MAVLink ``DISTANCE_SENSOR``
(message id 132) to the FCU at a configurable rate.

When the FCU has ``RNGFND1_TYPE = 10`` (MAVLink) it consumes these
messages as its primary rangefinder source and re-emits ``RANGEFINDER``
(id 173) telemetry that MAVROS publishes on
``/mavros/rangefinder/rangefinder``. See
https://mavlink.io/en/messages/common.html#DISTANCE_SENSOR.
"""

import threading
import time
from typing import Optional

from pymavlink import mavutil

from nectar.control.mavlink.connection import MavlinkConnection
from nectar.sensors.base import DistanceFilter, DistanceSensor


class RangefinderPublisher:
    """
    Bridge a :class:`DistanceSensor` to MAVLink ``DISTANCE_SENSOR``.

    Parameters
    ----------
    sensor : DistanceSensor
        Source of raw distance readings in meters.
    connection : MavlinkConnection
        Open MAVLink endpoint to the FCU.
    sensor_id : int, optional
        MAVLink sensor id (0-7). ArduPilot maps this to ``RNGFND<id+1>_*``.
        Default 0.
    sensor_type : int, optional
        MAVLink ``MAV_DISTANCE_SENSOR`` enum. Default ``LASER``.
    orientation : int, optional
        MAVLink ``MAV_SENSOR_ORIENTATION`` enum. Default ``PITCH_270``
        (downward).
    min_distance_m : float, optional
        Minimum range the sensor can report, in meters. Default 0.05.
    max_distance_m : float, optional
        Maximum range the sensor can report, in meters. Default 8.0.
    covariance_cm : int, optional
        Measurement covariance hint in centimeters (0-254). 0 means
        "unknown / use ArduPilot defaults". Default 0.
    rate_hz : float, optional
        Publishing rate. Default 50.
    filter : DistanceFilter, optional
        Pre-publish filter. ``None`` means publish raw readings.

    Notes
    -----
    A background thread is created on :meth:`start`. The thread sleeps on
    a :class:`threading.Event`, so :meth:`stop` is responsive.
    """

    def __init__(
        self,
        sensor: DistanceSensor,
        connection: MavlinkConnection,
        *,
        sensor_id: int = 0,
        sensor_type: int = mavutil.mavlink.MAV_DISTANCE_SENSOR_LASER,
        orientation: int = mavutil.mavlink.MAV_SENSOR_ROTATION_PITCH_270,
        min_distance_m: float = 0.05,
        max_distance_m: float = 8.0,
        covariance_cm: int = 0,
        rate_hz: float = 50.0,
        filter: Optional[DistanceFilter] = None,
    ) -> None:
        if rate_hz <= 0:
            raise ValueError("rate_hz must be positive")
        if not (0 <= sensor_id <= 7):
            raise ValueError("sensor_id must be in [0, 7]")
        if min_distance_m < 0 or max_distance_m <= min_distance_m:
            raise ValueError("require 0 <= min_distance_m < max_distance_m")

        self._sensor = sensor
        self._connection = connection
        self._filter = filter

        self._sensor_id = sensor_id
        self._sensor_type = sensor_type
        self._orientation = orientation
        self._min_cm = int(round(min_distance_m * 100))
        self._max_cm = int(round(max_distance_m * 100))
        self._covariance = max(0, min(254, int(covariance_cm)))
        self._period = 1.0 / rate_hz

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        """Whether the background loop is active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the background read/filter/publish loop."""
        if self.is_running:
            return
        if not self._connection.is_connected:
            raise RuntimeError("MavlinkConnection is not connected")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="rangefinder-publisher", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signal the loop to exit and join the thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            cycle_start = time.monotonic()

            raw = self._sensor.read()
            if raw is not None:
                value = raw if self._filter is None else self._filter.process(raw)
                if value is not None:
                    self._send(value)

            elapsed = time.monotonic() - cycle_start
            self._stop_event.wait(timeout=max(0.0, self._period - elapsed))

    def _send(self, distance_m: float) -> None:
        distance_cm = max(0, min(0xFFFF, int(round(distance_m * 100))))
        time_boot_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF
        self._connection.master.mav.distance_sensor_send(
            time_boot_ms,
            self._min_cm,
            self._max_cm,
            distance_cm,
            self._sensor_type,
            self._sensor_id,
            self._orientation,
            self._covariance,
        )
