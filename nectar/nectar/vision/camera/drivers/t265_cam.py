from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from math import pi, tan
from threading import Lock
from typing import TYPE_CHECKING, Optional, Tuple

import cv2
import numpy as np

from nectar import runtime as nectar_runtime
from nectar.vision.camera.abstract import DepthCam
from nectar.vision.camera.config import T265Config

if TYPE_CHECKING:
    from rclpy.node import Node

try:
    import pyrealsense2 as rs

    REALSENSE_AVAILABLE = True
except ImportError:
    rs = None
    REALSENSE_AVAILABLE = False


@dataclass
class T265Pose:
    """6DOF pose from T265 tracking camera."""

    translation: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rotation: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0, 1.0]))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    tracker_confidence: int = 0
    timestamp: float = 0.0


class T265Cam(DepthCam):
    """
    Intel RealSense T265 tracking camera driver with stereo depth computation.

    Parameters
    ----------
    config : T265Config
        Camera configuration.
    node : Node, optional
        ROS2 node, required for ROS topic mode.

    Raises
    ------
    ImportError
        If pyrealsense2 is not installed (direct mode).

    Notes
    -----
    Stereo depth is computed on the host from the two fisheye cameras using
    Kannala-Brandt fisheye undistortion and StereoSGBM. The output resolution
    and FOV are configurable. Effective depth range is roughly 0.3-3m given
    the 64mm stereo baseline.

    References
    ----------
    .. [1] librealsense t265_stereo.py example
       https://github.com/IntelRealSense/librealsense/blob/v2.53.1/wrappers/python/examples/t265_stereo.py
    """

    def __init__(self, config: T265Config, node: Optional["Node"] = None) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._node = node
        self._owns_node = False

        self._mutex = Lock()
        self._left: Optional[np.ndarray] = None
        self._right: Optional[np.ndarray] = None
        self._frame_ts: Optional[float] = None
        self._pose = T265Pose()

        self._pipeline = None
        self._stereo: Optional[cv2.StereoSGBM] = None
        self._undistort_left: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self._undistort_right: Optional[Tuple[np.ndarray, np.ndarray]] = None
        self._Q: Optional[np.ndarray] = None
        self._stereo_size: Optional[Tuple[int, int]] = None
        self._max_disp: int = 0
        self._baseline: float = 0.0

        self._cached_depth: Optional[np.ndarray] = None
        self._depth_frame_ts: Optional[float] = None

        self._ros_subs = []
        self._stereo_ready = False
        self._bridge = None
        self._ros_cam_info = {"left": None, "right": None}

    def start(self) -> None:
        """Initialize camera and compute stereo rectification maps."""
        if self._config.use_ros_topics:
            self._start_ros()
        else:
            self._start_direct()
        self._is_running = True

    def _start_direct(self) -> None:
        if not REALSENSE_AVAILABLE:
            raise ImportError(
                "pyrealsense2 is required for T265Cam direct mode. "
                "Install with: pip install pyrealsense2"
            )

        pipe = rs.pipeline()
        cfg = rs.config()

        pipe.start(cfg, self._rs_callback)
        self._pipeline = pipe

        profiles = pipe.get_active_profile()
        streams = {
            "left": profiles.get_stream(rs.stream.fisheye, 1).as_video_stream_profile(),
            "right": profiles.get_stream(rs.stream.fisheye, 2).as_video_stream_profile(),
        }

        intrinsics = {
            "left": streams["left"].get_intrinsics(),
            "right": streams["right"].get_intrinsics(),
        }

        K_left = self._camera_matrix(intrinsics["left"])
        D_left = np.array(intrinsics["left"].coeffs[:4])
        K_right = self._camera_matrix(intrinsics["right"])
        D_right = np.array(intrinsics["right"].coeffs[:4])

        extrinsics = streams["left"].get_extrinsics_to(streams["right"])
        R = np.reshape(extrinsics.rotation, [3, 3]).T
        T = np.array(extrinsics.translation)

        self._setup_stereo(K_left, D_left, K_right, D_right, R, T)

    def _start_ros(self) -> None:
        if self._node is None:
            from rclpy.node import Node as _Node

            self._node = _Node(
                f"nectar_t265_cam_{uuid.uuid4().hex[:8]}",
                start_parameter_services=False,
            )
            nectar_runtime.add_node(self._node)
            self._owns_node = True

        from cv_bridge import CvBridge
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        from sensor_msgs.msg import CameraInfo, Image

        self._bridge = CvBridge()
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)

        self._ros_subs.append(
            self._node.create_subscription(
                Image,
                self._config.fisheye1_topic,
                self._ros_fisheye1_cb,
                qos,
            )
        )
        self._ros_subs.append(
            self._node.create_subscription(
                Image,
                self._config.fisheye2_topic,
                self._ros_fisheye2_cb,
                qos,
            )
        )

        info_topic_1 = self._config.fisheye1_topic.rsplit("/", 1)[0] + "/camera_info"
        info_topic_2 = self._config.fisheye2_topic.rsplit("/", 1)[0] + "/camera_info"

        self._ros_subs.append(
            self._node.create_subscription(
                CameraInfo,
                info_topic_1,
                self._ros_cam_info1_cb,
                qos,
            )
        )
        self._ros_subs.append(
            self._node.create_subscription(
                CameraInfo,
                info_topic_2,
                self._ros_cam_info2_cb,
                qos,
            )
        )

        if self._config.enable_pose:
            from geometry_msgs.msg import PoseStamped
            from nav_msgs.msg import Odometry

            try:
                self._ros_subs.append(
                    self._node.create_subscription(
                        Odometry,
                        self._config.pose_topic,
                        self._ros_odom_cb,
                        qos,
                    )
                )
            except Exception:
                self._ros_subs.append(
                    self._node.create_subscription(
                        PoseStamped,
                        self._config.pose_topic,
                        self._ros_pose_cb,
                        qos,
                    )
                )

    def _rs_callback(self, frame) -> None:
        """pyrealsense2 frame callback (runs on sensor thread)."""
        if frame.is_frameset():
            frameset = frame.as_frameset()
            f1 = frameset.get_fisheye_frame(1).as_video_frame()
            f2 = frameset.get_fisheye_frame(2).as_video_frame()
            with self._mutex:
                self._left = np.asanyarray(f1.get_data())
                self._right = np.asanyarray(f2.get_data())
                self._frame_ts = frameset.get_timestamp()
                self._cached_depth = None

        if frame.is_pose_frame() and self._config.enable_pose:
            pose = frame.as_pose_frame().get_pose_data()
            with self._mutex:
                self._pose = T265Pose(
                    translation=np.array(
                        [pose.translation.x, pose.translation.y, pose.translation.z]
                    ),
                    rotation=np.array(
                        [
                            pose.rotation.x,
                            pose.rotation.y,
                            pose.rotation.z,
                            pose.rotation.w,
                        ]
                    ),
                    velocity=np.array([pose.velocity.x, pose.velocity.y, pose.velocity.z]),
                    angular_velocity=np.array(
                        [
                            pose.angular_velocity.x,
                            pose.angular_velocity.y,
                            pose.angular_velocity.z,
                        ]
                    ),
                    tracker_confidence=pose.tracker_confidence,
                    timestamp=frame.get_timestamp(),
                )

    def _ros_fisheye1_cb(self, msg) -> None:
        img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")
        with self._mutex:
            self._left = img
            self._frame_ts = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            self._cached_depth = None

    def _ros_fisheye2_cb(self, msg) -> None:
        img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")
        with self._mutex:
            self._right = img
            self._cached_depth = None

    def _ros_cam_info1_cb(self, msg) -> None:
        if self._ros_cam_info["left"] is not None:
            return
        self._ros_cam_info["left"] = msg
        self._try_init_stereo_from_ros()

    def _ros_cam_info2_cb(self, msg) -> None:
        if self._ros_cam_info["right"] is not None:
            return
        self._ros_cam_info["right"] = msg
        self._try_init_stereo_from_ros()

    def _ros_odom_cb(self, msg) -> None:
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        v = msg.twist.twist.linear
        av = msg.twist.twist.angular
        with self._mutex:
            self._pose = T265Pose(
                translation=np.array([p.x, p.y, p.z]),
                rotation=np.array([q.x, q.y, q.z, q.w]),
                velocity=np.array([v.x, v.y, v.z]),
                angular_velocity=np.array([av.x, av.y, av.z]),
                tracker_confidence=3,
                timestamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
            )

    def _ros_pose_cb(self, msg) -> None:
        p = msg.pose.position
        q = msg.pose.orientation
        with self._mutex:
            self._pose = T265Pose(
                translation=np.array([p.x, p.y, p.z]),
                rotation=np.array([q.x, q.y, q.z, q.w]),
                timestamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
            )

    def _try_init_stereo_from_ros(self) -> None:
        """Initialize stereo maps once both CameraInfo messages arrive."""
        if self._stereo_ready:
            return
        left_info = self._ros_cam_info.get("left")
        right_info = self._ros_cam_info.get("right")
        if left_info is None or right_info is None:
            return

        K_left = np.array(left_info.k).reshape(3, 3)
        D_left = np.array(left_info.d[:4])
        K_right = np.array(right_info.k).reshape(3, 3)
        D_right = np.array(right_info.d[:4])

        R = np.array(right_info.r).reshape(3, 3) if np.any(right_info.r) else np.eye(3)

        P_right_ros = np.array(right_info.p).reshape(3, 4)
        fx = P_right_ros[0, 0]
        tx = P_right_ros[0, 3]
        baseline = -tx / fx if fx != 0 else 0.064
        T = np.array([baseline, 0.0, 0.0])

        self._setup_stereo(K_left, D_left, K_right, D_right, R, T)

        if self._node:
            self._node.get_logger().info("T265 stereo calibration initialized from CameraInfo")

    def _setup_stereo(
        self,
        K_left: np.ndarray,
        D_left: np.ndarray,
        K_right: np.ndarray,
        D_right: np.ndarray,
        R: np.ndarray,
        T: np.ndarray,
    ) -> None:
        """Compute undistortion/rectification maps and create StereoSGBM matcher."""
        cfg = self._config
        stereo_fov_rad = cfg.stereo_fov_deg * (pi / 180)
        stereo_focal_px = cfg.stereo_height_px / 2 / tan(stereo_fov_rad / 2)

        min_disp = 0
        num_disp = cfg.num_disparities - min_disp
        num_disp = max(16, (num_disp // 16) * 16)
        self._max_disp = min_disp + num_disp

        stereo_width_px = cfg.stereo_height_px + self._max_disp
        self._stereo_size = (stereo_width_px, cfg.stereo_height_px)
        stereo_cx = (cfg.stereo_height_px - 1) / 2 + self._max_disp
        stereo_cy = (cfg.stereo_height_px - 1) / 2

        R_left = np.eye(3)
        R_right = R

        P_left = np.array(
            [
                [stereo_focal_px, 0, stereo_cx, 0],
                [0, stereo_focal_px, stereo_cy, 0],
                [0, 0, 1, 0],
            ]
        )
        P_right = P_left.copy()
        P_right[0][3] = T[0] * stereo_focal_px

        self._Q = np.array(
            [
                [1, 0, 0, -(stereo_cx - self._max_disp)],
                [0, 1, 0, -stereo_cy],
                [0, 0, 0, stereo_focal_px],
                [0, 0, -1 / T[0] if T[0] != 0 else 0, 0],
            ]
        )

        m1type = cv2.CV_32FC1
        lm1, lm2 = cv2.fisheye.initUndistortRectifyMap(
            K_left, D_left, R_left, P_left, self._stereo_size, m1type
        )
        rm1, rm2 = cv2.fisheye.initUndistortRectifyMap(
            K_right, D_right, R_right, P_right, self._stereo_size, m1type
        )
        self._undistort_left = (lm1, lm2)
        self._undistort_right = (rm1, rm2)

        ws = cfg.smoothness_window
        self._stereo = cv2.StereoSGBM_create(
            minDisparity=min_disp,
            numDisparities=num_disp,
            blockSize=cfg.block_size,
            P1=8 * 3 * ws**2,
            P2=32 * 3 * ws**2,
            disp12MaxDiff=1,
            uniquenessRatio=cfg.uniqueness_ratio,
            speckleWindowSize=cfg.speckle_window_size,
            speckleRange=cfg.speckle_range,
        )

        self._baseline = abs(T[0]) if T[0] != 0 else 0.064
        self._stereo_ready = True

    @staticmethod
    def _camera_matrix(intrinsics) -> np.ndarray:
        return np.array(
            [
                [intrinsics.fx, 0, intrinsics.ppx],
                [0, intrinsics.fy, intrinsics.ppy],
                [0, 0, 1],
            ]
        )

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Capture left fisheye frame as 3-channel BGR image.

        Returns
        -------
        np.ndarray or None
            Left fisheye image converted to BGR, or None if not available.
        """
        with self._mutex:
            if self._left is None:
                return None
            return cv2.cvtColor(self._left.copy(), cv2.COLOR_GRAY2BGR)

    def get_stereo_frames(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Get raw fisheye stereo pair.

        Returns
        -------
        tuple of (np.ndarray, np.ndarray) or None
            (left, right) grayscale fisheye images, or None if not available.
        """
        with self._mutex:
            if self._left is None or self._right is None:
                return None
            return self._left.copy(), self._right.copy()

    def get_depth_frame(self) -> Optional[np.ndarray]:
        """
        Compute stereo depth from fisheye pair.

        Uses pre-computed undistortion/rectification maps and StereoSGBM.
        Result is cached until new frames arrive.

        Returns
        -------
        np.ndarray or None
            Depth image in meters (float32) at stereo output resolution,
            or None if frames not available or stereo not initialized.
        """
        if not self._config.enable_depth or not self._stereo_ready:
            return None

        with self._mutex:
            if self._left is None or self._right is None:
                return None
            if self._cached_depth is not None and self._depth_frame_ts == self._frame_ts:
                return self._cached_depth.copy()
            left = self._left.copy()
            right = self._right.copy()
            ts = self._frame_ts

        rect_left = cv2.remap(
            src=left,
            map1=self._undistort_left[0],
            map2=self._undistort_left[1],
            interpolation=cv2.INTER_LINEAR,
        )
        rect_right = cv2.remap(
            src=right,
            map1=self._undistort_right[0],
            map2=self._undistort_right[1],
            interpolation=cv2.INTER_LINEAR,
        )

        disparity = self._stereo.compute(rect_left, rect_right).astype(np.float32) / 16.0
        disparity = disparity[:, self._max_disp :]

        depth = np.zeros_like(disparity)
        valid = disparity > 0
        focal = self._Q[2, 3]
        if focal != 0 and self._baseline != 0:
            depth[valid] = (focal * self._baseline) / disparity[valid]

        max_d = self._config.max_depth_m
        if max_d > 0:
            depth[depth > max_d] = 0

        with self._mutex:
            self._cached_depth = depth
            self._depth_frame_ts = ts

        return depth.copy()

    def get_distance(self, u: int, v: int) -> Optional[float]:
        """
        Get distance at pixel coordinates in the stereo depth output.

        Parameters
        ----------
        u : int
            Horizontal pixel coordinate (column).
        v : int
            Vertical pixel coordinate (row).

        Returns
        -------
        float or None
            Distance in meters, or None if invalid.
        """
        depth = self.get_depth_frame()
        if depth is None:
            return None
        h, w = depth.shape[:2]
        if not (0 <= v < h and 0 <= u < w):
            return None
        d = float(depth[v, u])
        return d if d > 0 else None

    def get_pose(self) -> T265Pose:
        """
        Get latest 6DOF pose from T265 tracker.

        Returns
        -------
        T265Pose
            Current pose with translation, rotation, velocity,
            angular velocity, tracker confidence, and timestamp.
        """
        with self._mutex:
            return T265Pose(
                translation=self._pose.translation.copy(),
                rotation=self._pose.rotation.copy(),
                velocity=self._pose.velocity.copy(),
                angular_velocity=self._pose.angular_velocity.copy(),
                tracker_confidence=self._pose.tracker_confidence,
                timestamp=self._pose.timestamp,
            )

    def get_rectified_frames(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Get undistorted and rectified stereo pair (cropped to valid region).

        Useful for visualization of the stereo matching input.

        Returns
        -------
        tuple of (np.ndarray, np.ndarray) or None
            (left_rectified, right_rectified), or None if not available.
        """
        if not self._stereo_ready:
            return None
        with self._mutex:
            if self._left is None or self._right is None:
                return None
            left = self._left.copy()
            right = self._right.copy()

        rect_left = cv2.remap(
            left, self._undistort_left[0], self._undistort_left[1], cv2.INTER_LINEAR
        )
        rect_right = cv2.remap(
            right, self._undistort_right[0], self._undistort_right[1], cv2.INTER_LINEAR
        )
        return rect_left[:, self._max_disp :], rect_right[:, self._max_disp :]

    def close(self) -> None:
        """Release camera resources."""
        if self._pipeline:
            try:
                self._pipeline.stop()
            except Exception:
                pass
            self._pipeline = None

        if self._node and self._ros_subs:
            for sub in self._ros_subs:
                self._node.destroy_subscription(sub)
            self._ros_subs.clear()

        if self._owns_node and self._node is not None:
            nectar_runtime.remove_node(self._node)
            try:
                self._node.destroy_node()
            except Exception:
                pass
            self._owns_node = False
            self._node = None

        self._is_running = False
