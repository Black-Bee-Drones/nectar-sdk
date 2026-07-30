# @loc:boilerplate:begin
#!/usr/bin/env python3
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Empty

NS = "bebop"


class BebopPilot(Node):
    def __init__(self) -> None:
        super().__init__("a12_bebop_hover")
        self._takeoff = self.create_publisher(Empty, f"/{NS}/takeoff", 1)
        self._land = self.create_publisher(Empty, f"/{NS}/land", 1)
        self._vel = self.create_publisher(Twist, f"/{NS}/cmd_vel", 1)

    def _spin(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def takeoff(self) -> None:
        self._takeoff.publish(Empty())
        self._spin(3.0)

    def move_velocity(self, vx: float = 0.0, duration: float = 2.0) -> None:
        msg = Twist()
        msg.linear.x = max(-1.0, min(1.0, vx))
        rate = 1.0 / 30.0
        end = time.monotonic() + duration
        while time.monotonic() < end:
            self._vel.publish(msg)
            self._spin(rate)
        self._vel.publish(Twist())

    def land(self) -> None:
        self._land.publish(Empty())

    # @loc:boilerplate:end
    # @loc:core:begin
    def run(self) -> None:
        self.takeoff()
        self.move_velocity(vx=0.3, duration=2.0)
        self.land()


# @loc:core:end
# @loc:boilerplate:begin


def main() -> None:
    rclpy.init()
    node = BebopPilot()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
