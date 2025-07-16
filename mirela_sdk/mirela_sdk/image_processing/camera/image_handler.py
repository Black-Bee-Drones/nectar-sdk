import os
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage

from cv_bridge import CvBridge
import cv2

from typing import Optional
from mirela_sdk.image_processing.camera.oakd_cam import OakdCam

import re
import subprocess

from time import sleep


class ImageHandler:
    RASPICAM_LAUNCH = "camerav2_410x308_30fps.launch"
    RASPICAM_TOPIC = "/image_raw"
    RASPICAM_COMPRESS_TOPIC = "/image_raw/compressed"
    BEBOP_TOPIC = "/bebop/camera/image_raw"

    C920_CTRL_MAP = {
        "HD Pro Webcam C920": "focus_automatic_continuous=0",
        "Logi Webcam C920e": "focus_auto=0",
    }

    def __init__(
        self,
        node: Node,
        image_source: str,
        image_processing_callback: Optional[callable] = None,
        show_result: str = None,
        cap: Optional[int] = 0,
        oakd_num: Optional[int] = 1,
        c920_config: Optional[int] = 1,
    ):
        """
        Class to handle image processing from a ROS topic or webcam.

        :param node (rclpy.node.Node): the ROS node to handle the image processing
        :param image_source (str): the source of the image (ROS topic, webcam, c920 or oakd)
        :param image_processing_callback (callable): the callback function to process the image
        :param cap (int): the webcam index.
            Use this parameter only if the image source is "webcam"
        :param oakd_num (int): index number for oakd cam - 1 for rgb, 2 for left monochrome cam, 3 for
         right monochrome cam
            Use this parameter only if the image source is "oakd"
        :param c920_config (int): index number for c920 configuration. 0 -> 640x480, 1 (default) -> 1280x720, 2-> 1920x1080. All are captured in 30 FPS.
        """

        self.node = node
        self.image_processing_callback = image_processing_callback

        # Initialize the camera source (ROS topic or webcam)
        self.image_source = image_source
        self.img = None
        self.show_result = show_result
        self.cap_num = cap
        self.oakd_num = oakd_num
        self.c920_config = c920_config
        self.cleaned = False
        self.bridge = CvBridge()

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
        """
        Process the image using the callback function

        Show the result if the show_result is not None
        """
        if self.image_processing_callback is not None:
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

    def oakd_callback(self):
        """
        Callback function for oakd
        """
        try:
            # getFrame function converts the frame from camera pattern to cv2.Mat
            self.img = self.oakd.getLatestFrameBlocking(self.queue)
            self.process()

        except RuntimeError as e:
            self.node.get_logger().error(f"RuntimeError at OAK-D callback: {e}")
            self.node.get_logger().info("Restarting camera communication...")
            
            # Stop the current timer if it exists
            if self.oakd_timer is not None:
                self.oakd_timer.cancel()
                self.oakd_timer = None
            
            # Clean up the OAK-D camera resources
            if self.oakd:
                self.oakd.clean()
                self.oakd = None
                self.queue = None
            
            # Attempt to reinitialize the OAK-D camera
            sleep(0.1)
            self._initialize_oakd()

    def _initialize_oakd(self) -> bool:
        """
        OakdCam class initializes the pipeline, configures the camera according to the address,
        returns the queue with frames in the camera pattern
        """
        try:
            self.oakd = OakdCam()
            self.oakd.setup_camera(self.oakd_num)
            self.oakd.init_cam(True)
            self.queue = self.oakd.getQueue_CamType()
            self.oakd_timer = self.node.create_timer(0.0001, self.oakd_callback)

        except Exception as e:
            self.node.get_logger().error(f"Failed to initialize OAK-D camera: {str(e)}")
            return False


    def run(self):
        """
        Run the image handler
        """
        self.node.get_logger().info("Running image handler [" + self.image_source + "]")

        if self.image_source == "webcam":
            # For webcam, the image is read by VideoCapture
            # and detection is maintained by the Timer together with the callback function
            self.cap = cv2.VideoCapture(self.cap_num)
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.cap.set(cv2.CAP_PROP_FOCUS, 0)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            self.webcam_timer = self.node.create_timer(0.0001, self.webcam_callback)

        elif self.image_source == "c920":
            result = subprocess.run(
                ["v4l2-ctl", "--list-devices"], capture_output=True, text=True
            )
            lines = result.stdout.splitlines()
            device = None
            ctrl_param = None

            for i, line in enumerate(lines):
                for model_name, param in self.C920_CTRL_MAP.items():
                    if model_name in line:
                        ctrl_param = param
                        j = i + 1
                        while j < len(lines) and lines[j].startswith("\t"):
                            match = re.search(r"(/dev/video\d+)", lines[j])
                            if match:
                                device = match.group(1)
                                break
                            j += 1
                        break
                if device and ctrl_param:
                    subprocess.run(
                        ["v4l2-ctl", "-d", device, "--set-ctrl=" + ctrl_param]
                    )
                    break

            if device is None:
                self.node.get_logger().error(
                    "C920 camera not detected. Please ensure the device is connected and that 'v4l2-ctl' is installed."
                )
                self.node.get_logger().warn(
                    f"Falling back to default camera: cv2.VideoCapture({self.cap_num})."
                )
                self.cap = cv2.VideoCapture(self.cap_num)

            else:
                if self.c920_config == 0:
                    width, height = 640, 480
                elif self.c920_config == 2:
                    width, height = 1920, 1080
                else:
                    width, height = 1280, 720

                self.node.get_logger().info(
                    f"C920 camera detected at {device}. Applying configuration profile {width}x{height}@30."
                )

                self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
                success = True
                success &= self.cap.set(
                    cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")
                )
                success &= self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                success &= self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                success &= self.cap.set(cv2.CAP_PROP_FPS, 30)

                if not success:
                    self.node.get_logger().warn(
                        "Failed to apply all camera settings. Continuing, but performance may be degraded."
                    )

            self.webcam_timer = self.node.create_timer(0.0001, self.webcam_callback)

        elif self.image_source == "oakd":
            # For oakd, OakdCam class initializes the pipeline, configures the camera according
            # to the address, returns the queue with frames in the camera pattern

            self.oakd = OakdCam()
            self.oakd.setup_camera(self.oakd_num)
            self.oakd.init_cam(True)
            self.queue = self.oakd.getQueue_CamType()
            self.oakd_timer = self.node.create_timer(0.0001, self.oakd_callback)

        elif os.path.isfile(self.image_source):
            # For image file, the image is read by cv2.imread
            try:
                self.img = cv2.imread(self.image_source)
                self.image_timer = self.node.create_timer(0.0001, self.process)
            except Exception as e:
                self.node.get_logger().error(f"Failed to read image file: {str(e)}")

        else:
            # For ROS topic, the image is read by the callback function
            self._configure_ros_topic()

    def cleanup(self):
        """
        Clean up the image handler
        """

        if not self.cleaned:
            self.node.get_logger().info("Image Handler Shutting Down")
            self.cleaned = True
            if self.image_source == "webcam":
                self.cap.release()
                self.node.destroy_timer(self.webcam_timer)

            elif self.image_source == "oakd":

                try:
                    self.oakd.clean()

                except AttributeError as ex:
                    self.node.get_logger().error(f"{ex}")

                else:
                    self.node.destroy_timer(self.oakd_timer)

            elif os.path.isfile(self.image_source):
                self.node.destroy_timer(self.image_timer)
            else:
                self.node.destroy_subscription(self.image_sub)

            if self.show_result is not None:
                try:
                    cv2.destroyWindow(self.show_result)
                except Exception as e:
                    self.node.get_logger().warning(str(e))
                    cv2.destroyAllWindows()
        else:
            print("Image Handler already cleaned up")

    def __del__(self):
        if not self.cleaned:
            self.cleanup()
