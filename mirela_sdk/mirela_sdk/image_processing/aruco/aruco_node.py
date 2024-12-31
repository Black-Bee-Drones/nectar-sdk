#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

import sys

from mirela_sdk.image_processing.aruco.aruco_detect import Aruco
from mirela_interfaces.msg import ArucoTransforms
from mirela_sdk.image_processing.camera.image_handler import ImageHandler


class ArucoNode(Node):
    POSE_TOPIC = "/aruco/pose_estimate"

    def __init__(self):

        super().__init__("aruco_node")

        self.declare_parameter("image_source", "webcam")
        self.declare_parameter("marker_dict", 5)
        self.declare_parameter("tag_size", 0.2)

        self.image_source = self.get_parameter("image_source").value
        self.marker_dict = self.get_parameter("marker_dict").value
        self.tag_size = self.get_parameter("tag_size").value

        self.aruco_pose_estimate = ArucoTransforms()

        self.pose_estime_pub = self.create_publisher(
            ArucoTransforms, ArucoNode.POSE_TOPIC, 10
        )

        self.aruco = Aruco(marker_dict=self.marker_dict, tag_size=self.tag_size)

        self.img_handler = ImageHandler(
            self, self.image_source, self.process_image, show_result="Aruco"
        )
        self.img_handler.run()

    def process_image(self, img):
        """
        Process the image and perform aruco pose estimate
        """

        id, Tvect, yaw = self.aruco.pose_estimate(img, True)

        if id is not None:
            # Publish line setpoints

            self.aruco_pose_estimate.id = int(id)

            self.aruco_pose_estimate.translation.x = Tvect[0]
            self.aruco_pose_estimate.translation.y = Tvect[1]
            self.aruco_pose_estimate.translation.z = Tvect[2]

            self.aruco_pose_estimate.yaw.data = yaw

            self.pose_estime_pub.publish(self.aruco_pose_estimate)

    def cleanup(self):
        self.img_handler.cleanup()
        print("Shutting down aruco node")
        self.destroy_publisher(self.pose_estime_pub)


def main(args=None) -> None:
    rclpy.init(args=args)

    # Instantiate the line detection node
    node = ArucoNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.cleanup()
        node.destroy_node()
        sys.exit(0)


if __name__ == "__main__":
    main()
