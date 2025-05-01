#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import os


class WebcamPublisher(Node):
    """
    Publishes images from the webcam to the /image_raw topic.
    """

    def __init__(self):
        super().__init__("webcam_publisher")
        self.publisher_ = self.create_publisher(Image, "image_raw", 10)
        timer_period = 0.001  # seconds (publish at 10 Hz)
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.bridge = CvBridge()

        # Try different camera indices if 0 doesn't work
        camera_indices_to_try = [0, 1, 2, -1]
        self.cap = None
        for index in camera_indices_to_try:
            # Check if the device exists (Linux specific)
            if os.path.exists(f"/dev/video{index}"):
                self.cap = cv2.VideoCapture(index)
                if self.cap.isOpened():
                    self.get_logger().info(
                        f"Successfully opened webcam with index {index}"
                    )
                    break
                else:
                    self.get_logger().warn(
                        f"Could not open webcam with index {index}, trying next one."
                    )
                    self.cap.release()  # Release if opened but not usable
                    self.cap = None
            else:
                self.get_logger().warn(
                    f"Webcam device /dev/video{index} does not exist."
                )

        if self.cap is None or not self.cap.isOpened():
            self.get_logger().error(
                "Could not open any webcam. Please check connection and permissions."
            )
            # Optional: raise an exception or shut down the node
            # raise RuntimeError("Could not open webcam")
            rclpy.shutdown()  # Or destroy the node: self.destroy_node()

        self.get_logger().info("Webcam Publisher node started.")

    def timer_callback(self):
        if self.cap is None or not self.cap.isOpened():
            self.get_logger().warn("Webcam not available, skipping frame.")
            return

        ret, frame = self.cap.read()
        if ret:
            # Convert OpenCV BGR image to ROS Image message
            ros_image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
            # Add timestamp
            ros_image.header.stamp = self.get_clock().now().to_msg()
            ros_image.header.frame_id = "camera_frame"  # Optional: set a frame ID
            self.publisher_.publish(ros_image)
            # self.get_logger().info('Publishing webcam frame') # Uncomment for debugging
        else:
            self.get_logger().warn("Failed to capture frame from webcam.")

    def destroy_node(self):
        """Cleanup resources."""
        self.get_logger().info("Shutting down Webcam Publisher node.")
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.get_logger().info("Webcam released.")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    webcam_publisher = WebcamPublisher()
    try:
        rclpy.spin(webcam_publisher)
    except KeyboardInterrupt:
        pass  # Explicitly handle Ctrl+C
    except Exception as e:
        webcam_publisher.get_logger().error(f"Unhandled exception: {e}")
    finally:
        # Destroy the node explicitly
        # (optional - otherwise it will be done automatically
        # when the garbage collector destroys the node object)
        webcam_publisher.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
