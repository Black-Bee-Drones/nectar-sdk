#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from math import degrees
import cv2

from mirela_sdk.image_processing.aruco.aruco_detect import Aruco
from tadinisdk_interfaces.msg import ArucoTransforms

from mirela_sdk.image_processing.camera.image_handler import ImageHandler


class ArucoNode(Node):
    POSE_TOPIC = "/aruco/pose_estimate"

    def __init__(
        self,
        image_source: str = "webcam",
        marker_dict: str = "5",
        tag_size: str = "0.2",
    ):
        super().__init__("aruco_node")

        self.marker_dict = int(marker_dict)
        self.tag_size = float(tag_size)

        self.aruco_pose_estimate = ArucoTransforms()

        self.pose_estime_pub = self.create_publisher(
            ArucoTransforms, ArucoNode.POSE_TOPIC, 10
        )

        self.aruco = Aruco(marker_dict=self.marker_dict, tag_size=self.tag_size)

        self.img_handler = ImageHandler(
            self, image_source, self.process_image, show_result="Aruco"
        )
        self.img_handler.run()

    def process_image(self, img):
        """
        Process the image and perform aruco pose estimate
        """

        id, Tvect, Rvect = self.aruco.pose_estimate(img, True)

        if id is not None:
            # Publish line setpoints

            self.aruco_pose_estimate.id = id

            self.aruco_pose_estimate.translation.x = Tvect[0]
            self.aruco_pose_estimate.translation.y = Tvect[1]
            self.aruco_pose_estimate.translation.z = Tvect[2]

            self.aruco_pose_estimate.yaw.data = degrees(Rvect[1])

            self.pose_estime_pub.publish(self.aruco_pose_estimate)


def main(args=None) -> None:
    rclpy.init(args=args)

    # Instantiate the line detection node
    node = ArucoNode()

    # Get detection parameters (marker_dict, tag_size and image_source) from the command line
    # marker_dict = node.get_parameter("marker_dict").get_parameter_value().string_value
    # tag_size = node.get_parameter("tag_size").get_parameter_value().string_value
    # image_source = node.get_parameter("image_source").get_parameter_value().string_value

    rclpy.spin(node)

    rclpy.shutdown()


if __name__ == "__main__":
    main()
