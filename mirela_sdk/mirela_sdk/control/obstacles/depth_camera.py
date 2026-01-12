from typing import TYPE_CHECKING, Tuple, Optional
from threading import Event
import numpy as np
import cv2
from sklearn.cluster import DBSCAN

from mirela_sdk.control.obstacles.base import BaseObstacleDetector
from mirela_sdk.control.protocols import ObstacleInfo, ObstacleDirection
from mirela_sdk.vision.camera.handler import ImageHandler
from mirela_sdk.vision.camera.drivers.realsense_cam import RealsenseCam
from mirela_sdk.vision.camera.config import RealSenseConfig

if TYPE_CHECKING:
    from rclpy.node import Node


class DepthObstacleDetector(BaseObstacleDetector):
    """
    RealSense D435i depth camera obstacle detector using DBSCAN clustering.

    Processes depth frames to identify obstacle clusters, determines direction (LEFT, RIGHT, FRONT)
    based on cluster position relative to image center, and returns closest obstacle distance.

    Parameters
    ----------
    node : Node
        ROS2 node for camera subscription.
    min_distance_mm : float, default=100
        Minimum valid depth in millimeters (closer depths ignored).
    max_distance_mm : float, default=1500
        Maximum detection range in millimeters.
    cluster_eps : float, default=20
        DBSCAN epsilon parameter (max distance between points in same cluster).
    cluster_min_samples : int, default=20
        DBSCAN min_samples parameter (minimum points to form cluster).
    min_cluster_pixels : int, default=50
        Minimum total valid pixels to attempt clustering.
    depth_threshold_mm : float, default=1300
        Maximum cluster mean depth to consider as obstacle.
    color_topic : str, default="/camera/color/image_raw"
        RealSense color image topic.
    depth_topic : str, default="/camera/depth/image_rect_raw"
        RealSense aligned depth topic.
    """

    def __init__(
        self,
        node: "Node",
        min_distance_mm: float = 100,
        max_distance_mm: float = 1500,
        cluster_eps: float = 20,
        cluster_min_samples: int = 20,
        min_cluster_pixels: int = 50,
        depth_threshold_mm: float = 1300,
        color_topic: str = "/camera/color/image_raw",
        depth_topic: str = "/camera/depth/image_rect_raw",
    ):
        super().__init__()
        self._node = node
        self._color_topic = color_topic
        self._depth_topic = depth_topic
        self._min_distance_mm = min_distance_mm
        self._max_distance_mm = max_distance_mm
        self._cluster_eps = cluster_eps
        self._cluster_min_samples = cluster_min_samples
        self._min_cluster_pixels = min_cluster_pixels
        self._depth_threshold_mm = depth_threshold_mm

        self._camera: Optional[RealsenseCam] = None
        self._image_handler: Optional[ImageHandler] = None
        self._detection_event = Event()

    def _on_enable(self) -> None:
        if self._camera is None:
            self._camera = RealsenseCam(
                config=RealSenseConfig(
                    use_ros_topics=True,
                    color_topic=self._color_topic,
                    depth_topic=self._depth_topic,
                    color_compressed=True,
                    enable_depth=True,
                ),
                node=self._node,
            )
            self._camera.start()

            self._image_handler = ImageHandler(
                node=self._node,
                image_source="realsense_ros",
                camera=self._camera,
                poll_interval=0.15,
                image_processing_callback=None,
            )
            self._image_handler.run()

        self._node.get_logger().info("DepthObstacleDetector enabled")

    def _on_disable(self) -> None:
        if self._image_handler:
            self._image_handler.close()
            self._image_handler.cleanup()
            self._image_handler = None

        if self._camera:
            self._camera = None

        self._detection_event.clear()
        self._node.get_logger().info("DepthObstacleDetector disabled")

    def _on_reset(self) -> None:
        self._detection_event.clear()

    def _detect(self) -> ObstacleInfo:
        """
        Perform obstacle detection from RealSense depth data.

        Returns
        -------
        ObstacleInfo
            Detection result with direction and distance.
        """
        if not self._camera:
            return ObstacleInfo(detected=False)

        depth = self._camera.get_depth_frame(wait_for_new=True, timeout=0.5)
        if depth is None:
            return ObstacleInfo(detected=False)

        detected, direction, distance = self._process_depth_frame(depth)

        if detected:
            self._detection_event.set()
        else:
            self._detection_event.clear()

        return ObstacleInfo(
            detected=detected,
            direction=direction,
            distance=distance,
        )

    def _process_depth_frame(
        self, depth: np.ndarray
    ) -> Tuple[bool, Optional[ObstacleDirection], Optional[float]]:
        """
        Process depth frame using DBSCAN clustering.

        Algorithm:
        1. Convert depth to millimeters and downsample to 10% for performance
        2. Filter valid depth range (min_distance_mm to max_distance_mm)
        3. Apply DBSCAN clustering to group obstacle points
        4. Filter clusters by mean depth threshold
        5. Determine direction based on cluster position relative to image center
        6. Return mean distance of valid clusters

        Parameters
        ----------
        depth : np.ndarray
            Depth frame in meters.

        Returns
        -------
        tuple of (bool, Optional[ObstacleDirection], Optional[float])
            (detected, direction, distance_meters)
        """
        depth_mm = depth * 1000.0
        depth_small = cv2.resize(
            depth_mm, None, fx=0.1, fy=0.1, interpolation=cv2.INTER_NEAREST
        )

        mask = (depth_small > self._min_distance_mm) & (
            depth_small < self._max_distance_mm
        )
        depth_small[~mask] = 0

        ys, xs = np.where(depth_small > 0)

        if len(xs) < self._min_cluster_pixels:
            return False, None, None

        depths = depth_small[ys, xs]
        pts = np.column_stack((xs, ys, depths * 0.5))

        clustering = DBSCAN(
            eps=self._cluster_eps, min_samples=self._cluster_min_samples
        ).fit(pts)
        labels = clustering.labels_
        unique_labels = set(labels)
        unique_labels.discard(-1)

        if len(unique_labels) == 0:
            return False, None, None

        img_center = depth_small.shape[1] / 2
        cluster_info = []

        for lb in unique_labels:
            idx = labels == lb
            xs_l = xs[idx]
            depths_l = depths[idx]

            depth_mean = np.mean(depths_l)
            if depth_mean > self._depth_threshold_mm:
                continue

            min_x = float(np.min(xs_l))
            max_x = float(np.max(xs_l))
            cluster_info.append((min_x, max_x, depth_mean, len(xs_l)))

            self._node.get_logger().info(
                f"Cluster {lb}: depth={int(depth_mean)}mm, "
                f"x=[{min_x:.1f}, {max_x:.1f}], pixels={len(xs_l)}",
                throttle_duration_sec=1.0,
            )

        if not cluster_info:
            return False, None, None

        cluster_min_x = [c[0] for c in cluster_info]
        cluster_max_x = [c[1] for c in cluster_info]
        avg_depth = np.mean([c[2] for c in cluster_info])

        all_left = all(mx < img_center for mx in cluster_max_x)
        all_right = all(mn > img_center for mn in cluster_min_x)

        if all_left:
            direction = ObstacleDirection.RIGHT
        elif all_right:
            direction = ObstacleDirection.LEFT
        else:
            direction = ObstacleDirection.FRONT

        return True, direction, avg_depth / 1000.0

    @property
    def detection_event(self) -> Event:
        """Threading event set when obstacle detected, cleared when path clear."""
        return self._detection_event
