#!/usr/bin/env python3
"""Republish a time-windowed (rolling) copy of VSLAM path topics.

cuVSLAM publishes the full trajectory from start on ``/visual_slam/tracking/
slam_path`` and ``/visual_slam/tracking/vo_path``;
This relay keeps only the most recent
``window_seconds`` of poses and republishes them on ``<topic><output_suffix>``
so RViz shows a rolling, auto-cleaning path

Run::

    ros2 run nectar path_window_node.py --ros-args -p window_seconds:=15.0
"""

import rclpy
from nav_msgs.msg import Path
from rclpy.node import Node


def _stamp_ns(stamp) -> int:
    return stamp.sec * 1_000_000_000 + stamp.nanosec


class PathWindowNode(Node):
    """Subscribe to path topics and republish only their recent tail."""

    def __init__(self) -> None:
        super().__init__("path_window_node")

        self.declare_parameter(
            "input_topics",
            [
                "/visual_slam/tracking/slam_path",
                "/visual_slam/tracking/vo_path",
            ],
        )
        self.declare_parameter("window_seconds", 15.0)
        self.declare_parameter("output_suffix", "_windowed")

        self._window = float(self.get_parameter("window_seconds").value)
        suffix = self.get_parameter("output_suffix").value
        topics = self.get_parameter("input_topics").value

        for topic in topics:
            out_topic = f"{topic}{suffix}"
            pub = self.create_publisher(Path, out_topic, 10)
            self.create_subscription(Path, topic, self._make_callback(pub), 10)
            self.get_logger().info(f"Windowing {topic} -> {out_topic} (last {self._window:.1f}s)")

    def _make_callback(self, pub):
        def _callback(msg: Path) -> None:
            pub.publish(self._trim(msg))

        return _callback

    def _trim(self, msg: Path) -> Path:
        poses = msg.poses
        if self._window <= 0.0 or not poses:
            return msg

        ref_ns = _stamp_ns(poses[-1].header.stamp)
        if ref_ns == 0:  # poses carry no usable stamp: pass through
            return msg

        cutoff = ref_ns - int(self._window * 1e9)
        out = Path()
        out.header = msg.header
        out.poses = [p for p in poses if _stamp_ns(p.header.stamp) >= cutoff]
        return out


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PathWindowNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
