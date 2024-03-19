#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import cv2
from math import degrees

from tadini_sdk.image_processing.aruco.aruco_detect import Aruco
from tadinisdk_interfaces.msg import ArucoTransforms

from tadini_sdk.image_processing.camera.image_handler import ImageHandler


class ArucoNode(ImageHandler):
    POSE_TOPIC = "/aruco/pose_estimate"

    def __init__(self, image_source, marker_dict, tag_size):

        super().__init__(image_source)

        self.marker_dict = int(marker_dict)
        self.tag_size = float(tag_size)

        self.aruco_pose_estimate = ArucoTransforms()

        self.pose_estime_pub = self.create_publisher(
            ArucoTransforms, self.
    def _check_position(self):
        current_lat: float 
    def process_image(self):
        # Process the image and perform aruco pose estimate

        if self.img is not None:
            id, Tvect, Rvect = self.aruco.pose_estimate(
                self.img, self.marker_dict, self.tag_size, True
            )

            if id is not None:
                # Publish line setpoints

                self.aruco_pose_estimate.id = id

                self.aruco_pose_estimate.translation.x = Tvect[0]
                self.aruco_pose_estimate.translation.y = Tvect[1]
                self.aruco_pose_estimate.translation.z = Tvect[2]

                self.aruco_pose_estimate.yaw.data = degrees(Rvect[1])

                self.pose_estime_pub.publish(self.aruco_pose_estimate)

    def __del__(self):

        if hasattr(self, "cap") and self.cap.isOpened():
            self.cap.release()
            rclpy.shutdown()


def main():

    rclpy.init()

    # Get detection parameters (marker_dict, tag_size and image_source) from the command line
    marker_dict = Node.get_parameter("marker_dict").get_parameter_value().string_value
    tag_size = Node.get_parameter("tag_size").get_parameter_value().string_value
    image_source = Node.get_parameter("image_source").get_parameter_value().string_value

    # Instantiate the line detection node
    Node = ArucoNode(
        image_source=image_source, marker_dict=marker_dict, tag_size=tag_size
    )

    Node.run()

    rclpy.spin(Node)

    Node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
