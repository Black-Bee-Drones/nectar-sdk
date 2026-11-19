"""MAVLink system-time publication and TIMESYNC exchange."""

import math
import time
from collections import deque
from typing import Optional

from rclpy.clock import Clock, ClockType
from rclpy.node import Node

from nectar.control.mavlink.connection import MavlinkConnection


class MavlinkTimeSync:
    """Publish ROS system time and exchange MAVLink TIMESYNC messages.

    This component owns the receive loop for its connection and is intended for
    the standalone vision-pose node, which has no other MAVLink reader.
    """

    def __init__(
        self,
        node: Node,
        connection: MavlinkConnection,
        system_time_rate_hz: float = 1.0,
        timesync_rate_hz: float = 10.0,
    ) -> None:
        self._node = node
        self._connection = connection
        self._system_time_period = self._rate_period(
            "system_time_rate", system_time_rate_hz
        )
        self._timesync_period = self._rate_period("timesync_rate", timesync_rate_hz)
        self._pending_requests: deque[int] = deque(maxlen=64)
        self._last_system_time = 0.0
        self._last_timesync = 0.0
        self._timer = None
        self._rx_error_reported = False

    @staticmethod
    def _rate_period(name: str, rate_hz: float) -> Optional[float]:
        if not math.isfinite(rate_hz) or rate_hz < 0:
            raise ValueError(f"{name} must be a finite, non-negative rate")
        return 1.0 / rate_hz if rate_hz > 0 else None

    def start(self) -> None:
        if self._timer is not None:
            return
        if self._connection.master is None:
            raise RuntimeError("MAVLink time sync requires a connected FCU")

        periods = [
            period
            for period in (self._system_time_period, self._timesync_period)
            if period is not None
        ]
        if not periods:
            self._node.get_logger().info("MAVLink time sync disabled")
            return

        self._timer = self._node.create_timer(
            min(periods),
            self._tick,
            clock=Clock(clock_type=ClockType.STEADY_TIME),
        )
        self._node.get_logger().info(
            "MAVLink time sync: "
            f"SYSTEM_TIME={self._rate_label(self._system_time_period)} Hz, "
            f"TIMESYNC={self._rate_label(self._timesync_period)} Hz"
        )

    def stop(self) -> None:
        if self._timer is not None:
            self._node.destroy_timer(self._timer)
            self._timer = None

    @staticmethod
    def _rate_label(period: Optional[float]) -> str:
        return f"{1.0 / period:g}" if period is not None else "disabled"

    def _tick(self) -> None:
        self._drain_messages()
        now = time.monotonic()

        if (
            self._system_time_period is not None
            and now - self._last_system_time >= self._system_time_period
        ):
            self._send_system_time()
            self._last_system_time = now

        if (
            self._timesync_period is not None
            and now - self._last_timesync >= self._timesync_period
        ):
            self._send_timesync_request()
            self._last_timesync = now

    def _send_system_time(self) -> None:
        time_unix_usec = self._node.get_clock().now().nanoseconds // 1000
        if time_unix_usec < 0:
            self._node.get_logger().error("Cannot send negative ROS time as SYSTEM_TIME")
            return
        with self._connection.send_lock:
            self._connection.master.mav.system_time_send(time_unix_usec, 0)

    def _send_timesync_request(self) -> None:
        ts1 = self._node.get_clock().now().nanoseconds
        self._pending_requests.append(ts1)
        with self._connection.send_lock:
            self._connection.master.mav.timesync_send(0, ts1)

    def _drain_messages(self) -> None:
        master = self._connection.master
        if master is None:
            return
        try:
            for _ in range(200):
                msg = master.recv_match(blocking=False)
                if msg is None:
                    self._rx_error_reported = False
                    return
                self._rx_error_reported = False
                if msg.get_type() == "TIMESYNC":
                    self._handle_timesync(msg)
        except OSError as exc:
            if not self._rx_error_reported:
                self._node.get_logger().error(f"MAVLink time-sync RX failed: {exc}")
                self._rx_error_reported = True

    def _handle_timesync(self, msg) -> None:
        if msg.tc1 == 0:
            ts1 = int(msg.ts1)
            tc1 = self._node.get_clock().now().nanoseconds
            with self._connection.send_lock:
                self._connection.master.mav.timesync_send(tc1, ts1)
        elif msg.ts1 in self._pending_requests:
            self._pending_requests.remove(msg.ts1)
