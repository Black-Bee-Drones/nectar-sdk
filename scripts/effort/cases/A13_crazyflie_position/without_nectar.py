# @loc:boilerplate:begin
#!/usr/bin/env python3
import time

import rclpy
from crazyflie_interfaces.srv import GoTo, Land, Takeoff
from geometry_msgs.msg import Point
from rclpy.duration import Duration
from rclpy.node import Node

CF = "cf231"


class CrazyfliePilot(Node):
    def __init__(self) -> None:
        super().__init__("a13_crazyflie_position")
        prefix = f"/{CF}"
        self._takeoff = self.create_client(Takeoff, f"{prefix}/takeoff")
        self._land = self.create_client(Land, f"{prefix}/land")
        self._goto = self.create_client(GoTo, f"{prefix}/go_to")
        for client in (self._takeoff, self._land, self._goto):
            client.wait_for_service(timeout_sec=5.0)

    def _call(self, client, request) -> None:
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=30.0)
        if not future.done() or future.result() is None:
            raise RuntimeError("service call failed")

    def takeoff(self, altitude: float = 0.5) -> None:
        req = Takeoff.Request()
        req.group_mask = 0
        req.height = float(altitude)
        req.duration = Duration(seconds=2.0).to_msg()
        self._call(self._takeoff, req)
        time.sleep(2.5)

    def move_to(self, x: float = 0.3, z: float = 0.5) -> None:
        req = GoTo.Request()
        req.group_mask = 0
        req.relative = True
        req.goal = Point(x=float(x), y=0.0, z=float(z))
        req.yaw = 0.0
        req.duration = Duration(seconds=2.0).to_msg()
        self._call(self._goto, req)
        time.sleep(2.5)

    def land(self) -> None:
        req = Land.Request()
        req.group_mask = 0
        req.height = 0.04
        req.duration = Duration(seconds=2.0).to_msg()
        self._call(self._land, req)

    # @loc:boilerplate:end
    # @loc:core:begin
    def run(self) -> None:
        self.takeoff(altitude=0.5)
        self.move_to(x=0.3, z=0.5)
        self.land()


# @loc:core:end
# @loc:boilerplate:begin


def main() -> None:
    rclpy.init()
    node = CrazyfliePilot()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
