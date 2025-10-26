from typing import Optional
import numpy as np
from rclpy.node import Node
from sensor_msgs.msg import Image as RosImage
from sensor_msgs.msg import CompressedImage as RosCompressedImage
from cv_bridge import CvBridge

from .abstract_cam import DepthCam
from .camera_config import RealSenseConfig

try:
    import pyrealsense2 as rs
except Exception as e:
    rs = None


class RealsenseCam(DepthCam):
    def __init__(self, config: RealSenseConfig, node: Optional[Node] = None) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._node = node

        self._use_ros_topics = config.use_ros_topics
        self._enable_depth = config.enable_depth

        if self._use_ros_topics:
            # ROS topic mode
            if self._node is None:
                raise ValueError("ROS topic mode requires a ROS node to be provided")
            self._bridge = CvBridge()
            self._rgb: Optional[np.ndarray] = None
            self._depth: Optional[np.ndarray] = None if self._enable_depth else None
            self._color_sub = None
            self._depth_sub = None
            self._pipeline = None
            self._align = None
            self._depth_scale = None
        else:
            # Direct pyrealsense2 mode
            self._pipeline = None
            self._align = None
            self._depth_scale: Optional[float] = None
            self._rgb: Optional[np.ndarray] = None
            self._depth: Optional[np.ndarray] = None if self._enable_depth else None
            self._bridge = None
            self._color_sub = None
            self._depth_sub = None

    def _color_callback(self, msg):
        """Callback for color image topic"""
        try:
            if self._config.color_compressed:
                self._rgb = self._bridge.compressed_imgmsg_to_cv2(
                    msg, desired_encoding="bgr8"
                )
            else:
                self._rgb = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            if self._node:
                self._node.get_logger().error(
                    f"RealsenseCam: failed to convert color image: {e}"
                )

    def _depth_callback(self, msg):
        """Callback for depth image topic"""
        try:
            if self._config.depth_compressed:
                depth_raw = self._bridge.compressed_imgmsg_to_cv2(
                    msg, desired_encoding="passthrough"
                )
            else:
                depth_raw = self._bridge.imgmsg_to_cv2(
                    msg, desired_encoding="passthrough"
                )

            # Convert to meters (RealSense publishes depth in millimeters as uint16)
            if depth_raw.dtype == np.uint16:
                self._depth = depth_raw.astype(np.float32) / 1000.0  # mm to meters
            else:
                self._depth = depth_raw.astype(np.float32)
        except Exception as e:
            if self._node:
                self._node.get_logger().error(
                    f"RealsenseCam: failed to convert depth image: {e}"
                )

    def start(self) -> None:
        if self._use_ros_topics:
            if self._config.color_compressed:
                self._color_sub = self._node.create_subscription(
                    RosCompressedImage,
                    self._config.color_topic + "/compressed",
                    self._color_callback,
                    10,
                )
            else:
                self._color_sub = self._node.create_subscription(
                    RosImage, self._config.color_topic, self._color_callback, 10
                )

            if self._enable_depth:
                if self._config.depth_compressed:
                    self._depth_sub = self._node.create_subscription(
                        RosCompressedImage,
                        self._config.depth_topic + "/compressedDepth",
                        self._depth_callback,
                        10,
                    )
                else:
                    self._depth_sub = self._node.create_subscription(
                        RosImage, self._config.depth_topic, self._depth_callback, 10
                    )

            self._is_running = True
            if self._node:
                topics_str = f"{self._config.color_topic}"
                if self._enable_depth:
                    topics_str += f" and {self._config.depth_topic}"
                self._node.get_logger().info(
                    f"RealsenseCam: Subscribed to {topics_str}"
                )
        else:
            # Use pyrealsense2 directly
            if rs is None:
                raise RuntimeError(
                    "pyrealsense2 is not installed. Please install librealsense and pyrealsense2."
                )

            config = rs.config()
            config.enable_stream(
                rs.stream.color,
                self._config.color_res[0],
                self._config.color_res[1],
                rs.format.bgr8,
                self._config.fps,
            )

            if self._enable_depth:
                config.enable_stream(
                    rs.stream.depth,
                    self._config.depth_res[0],
                    self._config.depth_res[1],
                    rs.format.z16,
                    self._config.fps,
                )

            self._pipeline = rs.pipeline()
            profile = self._pipeline.start(config)

            if self._enable_depth:
                depth_sensor = profile.get_device().first_depth_sensor()
                self._depth_scale = float(
                    depth_sensor.get_depth_scale()
                )  # meters per unit

                if self._config.align_to_color:
                    self._align = rs.align(rs.stream.color)
                else:
                    self._align = None
            else:
                self._depth_scale = None
                self._align = None

            self._is_running = True

    def _wait_for_frames(self):
        """Only for pyrealsense2 mode"""
        if not self._pipeline:
            return None
        frames = self._pipeline.wait_for_frames()
        if self._align is not None:
            frames = self._align.process(frames)
        return frames

    def get_frame(self) -> Optional[np.ndarray]:
        if self._use_ros_topics:
            return self._rgb
        else:
            frames = self._wait_for_frames()
            if frames is None:
                return None
            color_frame = frames.get_color_frame()
            if not color_frame:
                return None
            self._rgb = np.asanyarray(color_frame.get_data())
            return self._rgb

    def get_depth_frame(self) -> Optional[np.ndarray]:
        if not self._enable_depth:
            return None
        if self._use_ros_topics:
            return self._depth
        else:
            frames = self._wait_for_frames()
            if frames is None:
                return None
            depth_frame = frames.get_depth_frame()
            if not depth_frame:
                return None
            depth_image = np.asanyarray(depth_frame.get_data())  # in raw depth units
            if self._depth_scale is None:
                return None
            self._depth = depth_image.astype(np.float32) * self._depth_scale  # meters
            return self._depth

    def get_distance(self, u: int, v: int) -> Optional[float]:
        if not self._enable_depth:
            return None
        if self._use_ros_topics:
            # Use the cached depth frame from ROS topic
            if self._depth is None:
                return None
            h, w = self._depth.shape[:2]
            if not (0 <= v < h and 0 <= u < w):
                return None
            dist = float(self._depth[int(v), int(u)])
            return dist if dist > 0 else None
        else:
            # Ensure we have a recent aligned depth frame
            frames = self._wait_for_frames()
            if frames is None:
                return None
            depth_frame = frames.get_depth_frame()
            if not depth_frame:
                return None
            try:
                distance_m = float(depth_frame.get_distance(int(u), int(v)))
            except Exception:
                return None
            return distance_m

    def close(self) -> None:
        if self._use_ros_topics:
            if self._color_sub is not None and self._node is not None:
                self._node.destroy_subscription(self._color_sub)
                self._color_sub = None
            if self._depth_sub is not None and self._node is not None:
                self._node.destroy_subscription(self._depth_sub)
                self._depth_sub = None
        else:
            if self._pipeline:
                try:
                    self._pipeline.stop()
                except Exception:
                    pass
                self._pipeline = None
        self._is_running = False
