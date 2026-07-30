# @loc:boilerplate:begin
#!/usr/bin/env python3
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


class OneShotCam(Node):
    def __init__(self, topic: str = "/camera/color/image_raw") -> None:
        super().__init__("oneshot_cam")
        self.bridge = CvBridge()
        self.frame = None
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(Image, topic, self._on_image, qos)

    def _on_image(self, msg: Image) -> None:
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")


def main() -> None:
    rclpy.init()
    node = OneShotCam()
    try:
        # @loc:boilerplate:end
        # @loc:core:begin
        while node.frame is None:
            rclpy.spin_once(node, timeout_sec=0.1)
        print(node.frame.shape)
    # @loc:core:end
    # @loc:boilerplate:begin
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
