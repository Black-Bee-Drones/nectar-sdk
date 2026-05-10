#!/usr/bin/env python3
"""ROS2 node that bridges a serial rangefinder to MAVLink DISTANCE_SENSOR.

Designed to run in parallel with MAVROS so that missions stay unchanged:
the FCU is configured with ``RNGFND1_TYPE = 10`` (MAVLink) and consumes
the ``DISTANCE_SENSOR`` stream this node emits. ArduPilot then re-emits
``RANGEFINDER`` (id 173) telemetry that MAVROS publishes on
``/mavros/rangefinder/rangefinder``, which any
``nectar.control.MavrosDrone``-based mission is already subscribed to.

Run::

    ros2 run nectar rangefinder_node.py --ros-args \\
        -p serial_port:=/dev/ttyUSB0 \\
        -p mavlink_url:=udp:127.0.0.1:14551 \\
        -p filter:=obstacle_mask
"""

import rclpy
from rclpy.node import Node

from nectar.control.mavlink import MavlinkConnection
from nectar.sensors import ObstacleMaskFilter, RangefinderPublisher, TFLuna


class RangefinderNode(Node):
    """
    ROS2 entry point that wires TF-Luna + filter + MAVLink publisher.

    All knobs are exposed as ROS parameters so per-mission tuning lives in
    the launch file. The node owns a background thread (the publisher),
    not a ROS timer, so it is independent of the ROS executor's load.
    """

    FILTER_NONE = "none"
    FILTER_OBSTACLE_MASK = "obstacle_mask"

    def __init__(self) -> None:
        super().__init__("rangefinder_node")

        self.declare_parameter("serial_port", "/dev/ttyUSB0")
        self.declare_parameter("baudrate", 115200)
        self.declare_parameter("mavlink_url", "udp:127.0.0.1:14551")
        self.declare_parameter("mavlink_baud", 921600)
        self.declare_parameter("source_system", 1)
        self.declare_parameter("source_component", 191)
        self.declare_parameter("heartbeat_timeout_s", 30.0)

        self.declare_parameter("sensor_id", 0)
        self.declare_parameter("orientation", 25)
        self.declare_parameter("min_distance_m", 0.05)
        self.declare_parameter("max_distance_m", 8.0)
        self.declare_parameter("covariance_cm", 0)
        self.declare_parameter("rate_hz", 50.0)

        self.declare_parameter("filter", self.FILTER_NONE)
        self.declare_parameter("obstacle_height_m", 0.0)
        self.declare_parameter("max_change_m", 0.30)
        self.declare_parameter("avg_window", 10)
        self.declare_parameter("estimate_lock_s", 0.2)
        self.declare_parameter("timeout_s", 5.0)

        self._sensor: TFLuna | None = None
        self._connection: MavlinkConnection | None = None
        self._publisher: RangefinderPublisher | None = None

        self._build_pipeline()
        self._publisher.start()
        self.get_logger().info("Rangefinder publisher started")

    def _build_pipeline(self) -> None:
        port = self.get_parameter("serial_port").value
        baudrate = int(self.get_parameter("baudrate").value)
        mavlink_url = self.get_parameter("mavlink_url").value
        mavlink_baud = int(self.get_parameter("mavlink_baud").value)
        heartbeat_timeout = float(self.get_parameter("heartbeat_timeout_s").value)
        source_system = int(self.get_parameter("source_system").value)
        source_component = int(self.get_parameter("source_component").value)

        self.get_logger().info(f"Opening TF-Luna on {port} @ {baudrate} bps")
        self._sensor = TFLuna(port=port, baudrate=baudrate)

        self.get_logger().info(f"Connecting MAVLink to {mavlink_url}")
        self._connection = MavlinkConnection(
            source_system=source_system,
            source_component=source_component,
            heartbeat_timeout=heartbeat_timeout,
        )
        self._connection.connect(mavlink_url, baud=mavlink_baud)
        self.get_logger().info(
            f"FCU heartbeat received "
            f"(sys={self._connection.master.target_system}, "
            f"comp={self._connection.master.target_component})"
        )

        self._publisher = RangefinderPublisher(
            sensor=self._sensor,
            connection=self._connection,
            sensor_id=int(self.get_parameter("sensor_id").value),
            orientation=int(self.get_parameter("orientation").value),
            min_distance_m=float(self.get_parameter("min_distance_m").value),
            max_distance_m=float(self.get_parameter("max_distance_m").value),
            covariance_cm=int(self.get_parameter("covariance_cm").value),
            rate_hz=float(self.get_parameter("rate_hz").value),
            filter=self._build_filter(),
        )

    def _build_filter(self):
        kind = self.get_parameter("filter").value
        if kind == self.FILTER_NONE:
            self.get_logger().info("Filter disabled (raw passthrough)")
            return None

        if kind == self.FILTER_OBSTACLE_MASK:
            obstacle_height_raw = float(self.get_parameter("obstacle_height_m").value)
            obstacle_height = obstacle_height_raw if obstacle_height_raw > 0 else None
            max_change = float(self.get_parameter("max_change_m").value)
            avg_window = int(self.get_parameter("avg_window").value)
            estimate_lock = float(self.get_parameter("estimate_lock_s").value)
            timeout_raw = float(self.get_parameter("timeout_s").value)
            timeout = timeout_raw if timeout_raw > 0 else None
            height_label = (
                f"fixed={obstacle_height:.2f}m"
                if obstacle_height is not None
                else f"auto-estimated (lock={estimate_lock:.2f}s)"
            )
            self.get_logger().info(
                f"Filter: obstacle_mask "
                f"(height={height_label}, max_change={max_change:.2f}m, "
                f"window={avg_window}, timeout={timeout})"
            )
            return ObstacleMaskFilter(
                obstacle_height_m=obstacle_height,
                max_change_m=max_change,
                avg_window=avg_window,
                estimate_lock_s=estimate_lock,
                timeout_s=timeout,
            )

        raise ValueError(
            f"Unknown filter '{kind}'. Valid: {self.FILTER_NONE}, {self.FILTER_OBSTACLE_MASK}"
        )

    def destroy_node(self) -> bool:
        if self._publisher is not None:
            self._publisher.stop()
        if self._sensor is not None:
            self._sensor.close()
        if self._connection is not None:
            self._connection.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RangefinderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
