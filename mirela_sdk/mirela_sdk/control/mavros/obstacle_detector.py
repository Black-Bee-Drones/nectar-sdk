from typing import TYPE_CHECKING, Tuple
if TYPE_CHECKING:
    from mirela_sdk.control.mavros.mavros_api import MavDrone

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
    def __init__(self, drone: "MavDrone"):

        self.drone = drone
        self.cam = RealsenseCam(
            config=RealSenseConfig(
                use_ros_topics=True,
                color_topic="/camera/color/image_raw",
                depth_topic="/camera/depth/image_rect_raw",
                color_compressed=True,
                enable_depth=True,
            ),
            node=self.drone.node
        )
        self.cam.start()

        self.image_handler: ImageHandler = ImageHandler(
            node=self.drone.node,
            image_source="realsense_ros",
            camera=self.cam,
            poll_interval=0.15,
            image_processing_callback=None
        )
        self.image_handler.run()

        self.obstacle_event = Event()

        self.drone.node.create_timer(0.15, self.process_depth)
        
        self.drone.node.get_logger().info("RealsenseDepthTest initialized")

    def control_func(self, x: float) -> float:
        x -= 31
        flag = 1 if x < 0 else -1
        return flag #flag * min(1.1, max(0.5, abs(x)))

    def detect_obstacle(self) -> Tuple[bool, float]:
        depth = self.cam.get_depth_frame(wait_for_new=True, timeout=1.0)
        
        if depth is None:
            self.drone.delay(0.5)
            depth = self.cam.get_depth_frame(wait_for_new=True, timeout=1.0)
            if depth is None:
                raise RuntimeError("aqui deu merda")
        
        depth_mm = depth * 1000.0
        depth_small = cv2.resize(depth_mm, None, fx=0.1, fy=0.1, interpolation=cv2.INTER_NEAREST)

        mask = (depth_small > 0) & (depth_small < 1500)
        depth_small[~mask] = 0

        ys, xs = np.where(depth_small > 0)
        
        if len(xs) < 50:
            return (False, None)
        
        depths = depth_small[ys, xs]
        
        pts = np.column_stack((xs, ys, depths * 0.5))

        clustering = DBSCAN(eps=20, min_samples=20).fit(pts)
        labels = clustering.labels_
        unique_labels = set(labels)
        unique_labels.discard(-1)

        if len(unique_labels) == 0:
            return (False, None)

        img_center = depth_small.shape[1] / 2

        centroids_x = []
        centroids_y = []

        for lb in unique_labels:
            idx = labels == lb
            xs_l = xs[idx]
            ys_l = ys[idx]
            depths_l = depths[idx]
            depth_mean = np.mean(depths_l)

            if depth_mean > 1300:
                continue

            cx = np.mean(xs_l)
            cy = np.mean(ys_l)
            centroids_x.append(cx)
            centroids_y.append(cy)

            self.obstacle_event.set()

            self.drone.node.get_logger().info(
                f"[Cluster {lb}] Depth={int(depth_mean)}mm | "
                f"X={cx:.1f} Y={cy:.1f} | Pixels={len(xs_l)}"
            )
        
        if len(centroids_x) == 0:
            return (False, None)

        # <<< NOVO >>>
        all_left = all(cx < img_center for cx in centroids_x)

        if all_left:
            # todos obstáculos na esquerda → desviar para a direita
            return (True, max(centroids_x))
        else:
            # tem obstáculo na direita ou misturados → desviar para a esquerda
            return (True, min(centroids_x))

    def process_depth(self):
        detect, decision = self.detect_obstacle()

        if not detect:
            self.obstacle_event.clear()
            return
        
        self.obstacle_event.set()

        out = self.control_func(decision)

        self.drone.node.get_logger().info(
            f"[Avoid] direction={out}"
        )

        self.drone.offboard_position(
            x=0.0, y=out, z=0.0, yaw=0.0,
            ground_reference=False,
            precision_radius=0.2,
            timeout_sec=10.0,
            strategy="default",
            obstacle_avoidance=False
        )

        for _ in range(2):
            detect, decision = self.detect_obstacle()

            if not detect:
                break
            
            out = self.control_func(decision)

            self.drone.node.get_logger().info(
                f"[Avoid] direction={out}"
            )

            self.drone.offboard_position(
                x=0.0, y=out, z=0.0, yaw=0.0,
                ground_reference=False,
                precision_radius=0.2,
                timeout_sec=10.0,
                strategy="default",
                obstacle_avoidance=False
            )

        self.drone.offboard_position(
            x=2.5, y=0.0, z=0.0, yaw=0.0,
            ground_reference=False,
            precision_radius=0.2,
            timeout_sec=10.0,
            strategy="default",
            obstacle_avoidance=False
        )
