#!/usr/bin/env python
import sys
import os
import rclpy
from rclpy.node import Node
import cv2
import cvzone

from mirela_sdk.image_processing.camera.image_handler import ImageHandler

from mirela_sdk.image_processing.color.color_detector import ColorDetector


class ColorCalibrationNode(Node):
    def __init__(self, image_source: str = None):
        super().__init__("color_calibration_node")

        if image_source is None:
            self.declare_parameter("image_source", "/bebop/camera/image_raw")
            image_source = self.get_parameter("image_source").value

        self.image_source = image_source
        self.image_handler = ImageHandler(
            self, self.image_source, image_processing_callback=self.process
        )
        self.color_detector = ColorDetector("track")
        self.galinha = True

        self.get_logger().info("Color calibration node initialized")
        self.get_logger().info("Press 'q' to exit or 's' to save calibration values")

        self.image_handler.run()

    def process(self, img):
        try:
            if img is not None:

                if self.galinha:
                    self.color_detector.initTrackbars()
                    self.galinha = False

                self.color_detector.filterColor(img)

                hStack = cvzone.stackImages(
                    [img, self.color_detector.mask, self.color_detector.result], 3, 0.7
                )

                cv2.imshow("Color Calibration", hStack)

                key = cv2.waitKey(1)

                if key == ord("q"):
                    self.image_handler.cleanup()
                    cv2.destroyAllWindows()

                if cv2.waitKey(1) == ord("s"):
                    self.get_logger().info("Saving color calibration values to file...")
                    self.color_detector.saveColorHSV()
                    self.get_logger().info("Calibration values saved. Exiting...")

        except Exception as e:
            self.get_logger().error(f"Error during image processing: {str(e)}")


def main(args=None):
    rclpy.init(args=args)

    # Get image source (webcam or ROS topic

    node = ColorCalibrationNode()

    try:
        # Start the color calibration process
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
