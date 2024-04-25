import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage

from cv_bridge import CvBridge
import cv2

from typing import Optional


class ImageHandler:
    RASPICAM_LAUNCH = "camerav2_410x308_30fps.launch"

    BEBOP_TOPIC = "/bebop/camera/image_raw"

    def __init__(
        self,
        node: Node,
        image_source: str,
        image_processing_callback: callable,
        show_result: str = None,
        cap: Optional[int] = 0,
    ):
        """
        Class to handle image processing from a ROS topic or webcam.

        :param node (rclpy.node.Node): the ROS node to handle the image processing
        :param image_source (str): the source of the image (ROS topic or webcam)
        :param image_processing_callback (callable): the callback function to process the image
        :param cap (int): the webcam index.
            Use this parameter only if the image source is "webcam"
        """

        self.node = node
        self.image_processing_callback = image_processing_callback

        # Initialize the camera source (ROS topic or webcam)
        self.image_source = image_source
        self.img = None
        self.show_result = show_result
        self.cap_num = cap
        self.bridge = CvBridge()

        self.node.get_logger().info(f"Image source: {self.image_source}")

    def _configure_ros_topic(self):
        """
        Configure the ROS topic to subscribe to the image source
            Could be a compressed image or a raw image
        """
        if self.image_source.endswith("compressed"):
            self.convert_bridge = self.bridge.compressed_imgmsg_to_cv2
            self.image_sub = self.node.create_subscription(
                CompressedImage, self.image_source, self.ros_topic_callback, 10
            )
        else:
            self.convert_bridge = self.bridge.imgmsg_to_cv2
            self.image_sub = self.node.create_subscription(
                Image, self.image_source, self.ros_topic_callback, 10
            )

    def process(self):
        self.image_processing_callback(self.img)

        if self.show_result is not None:
            cv2.imshow(self.show_result, self.img)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            self.cleanup()

    def ros_topic_callback(self, data):
        """
        Callback function for ROS topic

        :param data: the ROS message
        """
        try:
            self.img = self.convert_bridge(data, "bgr8")

            self.process()

        except Exception as e:
            self.node.get_logger().error(
                f"Failed to convert ROS image message: {str(e)}"
            )

    def webcam_callback(self):
        """
        Callback function for webcam
        """
        try:
            ret, self.img = self.cap.read()

            if not ret:
                self.node.get_logger().error("Webcam is not functioning correctly.")
                return

            self.process()

        except Exception as e:
            self.node.get_logger().error(f"Failed to read from webcam: {str(e)}")

    def run(self):
        """
        Run the image handler
        """
        self.node.get_logger().info("Running image handler")

        if self.image_source == "webcam":
            # For webcam, the image is read by VideoCapture
            # and detection is maintained by the Timer together with the callback function
            self.cap = cv2.VideoCapture(self.cap_num)

            self.webcam_timer = self.node.create_timer(0.0001, self.webcam_callback)

        else:
            self._configure_ros_topic()

    def cleanup(self):
        """
        Clean up the image handler
        """

        self.node.get_logger().info("Image Handler Shutting down")
        if self.image_source == "webcam":
            self.cap.release()
            self.node.destroy_timer(self.webcam_timer)
        else:
            self.node.destroy_subscription(self.image_sub)

        if self.show_result is not None:
            cv2.destroyWindow(self.show_result)

        self.node.destroy_node()

    def __del__(self):
        self.cleanup()
