#!/usr/bin/env python3
import argparse
from typing import Optional

import rclpy
from nectar_interfaces.msg import ArucoTransforms
from rclpy.node import Node

from nectar.vision.algorithms.markers import Aruco
from nectar.vision.camera import ImageHandler, add_camera_arguments, parse_camera_args
from nectar.vision.camera.config import CameraConfig
from nectar.vision.stream import CompressedFramePublisher, add_stream_arguments


class ArucoNode(Node):
    """
    ROS2 node for ArUco marker pose estimation.

    Detects ArUco markers and publishes their pose (translation, yaw).

    Publishes
    ---------
    /aruco/pose_estimate : ArucoTransforms
        Detected marker ID, translation vector, and yaw angle.
    """

    POSE_TOPIC = "/aruco/pose_estimate"
    WINDOW = "Aruco"

    def __init__(
        self,
        source: str = "webcam",
        camera_config: Optional[CameraConfig] = None,
        *,
        show: bool = True,
        publish: bool = False,
        publish_topic: str = "/aruco/image/compressed",
        jpeg_quality: int = 80,
        marker_dict: int = 5,
        tag_size: float = 0.2,
    ) -> None:
        super().__init__("aruco_node")

        self.source = source
        self.marker_dict = marker_dict
        self.tag_size = tag_size

        self.aruco_pose_estimate = ArucoTransforms()
        self.pose_estime_pub = self.create_publisher(ArucoTransforms, ArucoNode.POSE_TOPIC, 10)
        self.aruco = Aruco(marker_dict=self.marker_dict, tag_size=self.tag_size)

        self._image_pub: Optional[CompressedFramePublisher] = None
        if publish:
            self._image_pub = CompressedFramePublisher(
                publish_topic, jpeg_quality=jpeg_quality, node=self
            )

        self.img_handler = ImageHandler(
            image_source=self.source,
            image_processing_callback=self.process_image,
            show_result=self.WINDOW if show else None,
            config=camera_config,
        )
        self.img_handler.run()

    def process_image(self, img):
        """Process frame, publish marker pose, optionally publish the annotated image."""
        marker_id, tvect, yaw = self.aruco.pose_estimate(img, True)

        if marker_id is not None:
            self.aruco_pose_estimate.id = int(marker_id)
            self.aruco_pose_estimate.translation.x = tvect[0]
            self.aruco_pose_estimate.translation.y = tvect[1]
            self.aruco_pose_estimate.translation.z = tvect[2]
            self.aruco_pose_estimate.yaw.data = yaw
            self.pose_estime_pub.publish(self.aruco_pose_estimate)

        if self._image_pub is not None:
            self._image_pub.publish(img)
        return img

    def cleanup(self) -> None:
        """Clean up resources and shutdown."""
        self.img_handler.cleanup()
        if self._image_pub is not None:
            self._image_pub.cleanup()
        self.destroy_publisher(self.pose_estime_pub)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ArUco marker pose estimation")
    add_camera_arguments(parser)
    add_stream_arguments(parser, show_default=True, publish_topic="/aruco/image/compressed")
    parser.add_argument("--marker-dict", type=int, default=5)
    parser.add_argument("--tag-size", type=float, default=0.2)
    return parser


def main(args=None) -> None:
    """Entry point for ArUco node."""
    import nectar

    ns, ros_argv, source, camera_config = parse_camera_args(_parser(), args)
    rclpy.init(args=ros_argv)
    nectar.init()
    node = ArucoNode(
        source,
        camera_config,
        show=ns.show,
        publish=ns.publish,
        publish_topic=ns.publish_topic,
        jpeg_quality=ns.jpeg_quality,
        marker_dict=ns.marker_dict,
        tag_size=ns.tag_size,
    )
    nectar.add_node(node)
    try:
        nectar.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
