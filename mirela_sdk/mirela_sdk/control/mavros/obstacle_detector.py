from collections import deque
from typing import Optional
import numpy as np
import cv2
from sklearn.cluster import DBSCAN
from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.image_processing.camera.realsense_cam import RealSenseConfig, RealsenseCam
from rclpy.node import Node
from threading import Event
from rclpy.duration import Duration


class LidarObstacleDetector:
    """
    Detects obstacles using lidar altitude variation over time.

    When the drone passes over an object (like a table or platform), the lidar
    altitude reading changes rapidly. This detector identifies such changes and
    temporarily disables PID altitude control, allowing the Pixhawk's internal
    rangefinder-based altitude control to handle the situation.

    The detector uses a timeout-based approach: once an obstacle is detected,
    altitude control remains disabled for a specified duration to prevent
    oscillations while the drone passes over the obstacle.
    """

    def __init__(
        self,
        buffer_size: int = 10,
        height_threshold: float = 0.25,
        timeout: float = 8.0,
    ):
        """
        Initialize obstacle detector.

        Parameters
        ----------
        buffer_size : int
            Number of lidar samples to keep for baseline calculation.
            Used to determine the average altitude before obstacle detection.
        height_threshold : float
            Minimum height change (meters) to trigger obstacle detection.
            Lower values detect smaller obstacles but may cause false positives.
        timeout : float
            Duration (seconds) to maintain obstacle state after detection.
            This prevents oscillations while the drone passes over the obstacle.
        """
        self.buffer_size = buffer_size
        self.height_threshold = height_threshold
        self.timeout = timeout

        self._buffer: deque[float] = deque(maxlen=buffer_size)
        self._baseline: Optional[float] = None
        self._obstacle_detected = False
        self._obstacle_start_time: Optional[float] = None

    def update(self, lidar_altitude: float, current_time: float) -> bool:
        """
        Update detector with new lidar reading.

        Parameters
        ----------
        lidar_altitude : float
            Current lidar altitude reading (meters).
        current_time : float
            Current timestamp (seconds).

        Returns
        -------
        bool
            True if obstacle is detected (altitude control should be disabled),
            False otherwise.
        """
        self._buffer.append(lidar_altitude)

        if len(self._buffer) < self.buffer_size:
            return False

        self._baseline = np.mean(self._buffer)
        deviation = lidar_altitude - self._baseline

        # Detect new obstacle based on deviation threshold
        if not self._obstacle_detected and abs(deviation) > self.height_threshold:
            self._obstacle_detected = True
            self._obstacle_start_time = current_time
            return True

        if self._obstacle_detected:
            elapsed = current_time - self._obstacle_start_time

            if elapsed > self.timeout:
                # Timeout expired - re-enable altitude control
                self._clear_obstacle_state()
                return False

            # Continue disabling altitude control during timeout
            return True

        return False

    def _clear_obstacle_state(self):
        """Clear obstacle detection state and reset timer."""
        self._obstacle_detected = False
        self._obstacle_start_time = None
        self._buffer.clear()  # Clear buffer for fresh baseline after obstacle

    def reset(self):
        """Reset detector to initial state."""
        self._buffer.clear()
        self._baseline = None
        self._obstacle_detected = False
        self._obstacle_start_time = None

    @property
    def is_obstacle_detected(self) -> bool:
        """Check if obstacle is currently detected."""
        return self._obstacle_detected

    def get_elapsed_time(self, current_time: float) -> float:
        """
        Get elapsed time since obstacle detection.

        Parameters
        ----------
        current_time : float
            Current timestamp (seconds).

        Returns
        -------
        float
            Elapsed time in seconds, or 0.0 if no obstacle detected.
        """
        if self._obstacle_detected and self._obstacle_start_time is not None:
            return current_time - self._obstacle_start_time
        return 0.0


class RealsenseObstacleDetector:
    def __init__(self, node: Node):

        self.node = node
        self.cam = RealsenseCam(
            config=RealSenseConfig(
                use_ros_topics=True,
                color_topic="/camera/color/image_raw",
                depth_topic="/camera/depth/image_rect_raw",
                color_compressed=True,
                enable_depth=True,
            ),
            node=self.node
        )
        self.cam.start()
        self.image_handler: ImageHandler = ImageHandler(
            node=self.node,
            image_source="realsense_ros",
            camera=self.cam,
            poll_interval=0.1,
            image_processing_callback=None
        )
        self.image_handler.run()

        self.obstacle_event = Event()
        self.fps_time = self.node.get_clock().now()

        self.node.create_timer(0.01, self.processing_cb)

    def processing_cb(self) -> None:
        # Get depth frame - returns numpy array directly when using ROS topics
        depth = self.cam.get_depth_frame(wait_for_new=True, timeout=0.1)
        
        if depth is None:
            return
        
        # Convert from meters to millimeters for processing
        depth_mm = (depth * 1000.0).astype(np.float32)

        # Resize antes de filtrar
        depth_small = cv2.resize(depth_mm, None, fx=0.125, fy=0.125, interpolation=cv2.INTER_NEAREST)

        # Filtra pixels entre 0 e 1500mm
        mask = (depth_small > 0) & (depth_small < 1500)
        depth_small[~mask] = 0

        # Pega pixels válidos
        ys, xs = np.where(depth_small > 0)
        depths = depth_small[ys, xs]

        if len(xs) < 50:
            return

        # Prepara pontos para DBSCAN: (x₂d, y₂d, depth_mm)
        pts = np.vstack((xs, ys, depths * 0.5)).T  # depth reduzido no peso

        # DBSCAN
        clustering = DBSCAN(eps=20, min_samples=20).fit(pts)
        labels = clustering.labels_
        unique_labels = set(labels)
        unique_labels.discard(-1)  # remove ruído

        for lb in unique_labels:
            idx = labels == lb
            xs_l = xs[idx]
            ys_l = ys[idx]
            depths_l = depths[idx]

            depth_mean = np.mean(depths_l)
            if depth_mean > 1000:  # obstáculo muito longe
                continue

            self.node.get_logger().info(f"[Cluster {lb}] Depth={int(depth_mean)}mm | X={xs_l} Y={ys_l}")
            self.obstacle_event.set()

        now = self.node.get_clock().now()
        elapsed_ns = (now - self.fps_time).nanoseconds
        self.node.get_logger().info(f"Obstacle delay: {elapsed_ns / 1e6:.2f}ms")
        self.fps_time = now



    



