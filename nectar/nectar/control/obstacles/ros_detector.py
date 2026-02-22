import logging
import sys
from threading import Lock
from typing import TYPE_CHECKING, Optional

from std_msgs.msg import Bool, Float32, String

from nectar.control.obstacles.base import BaseObstacleDetector
from nectar.control.protocols import ObstacleDirection, ObstacleInfo
from nectar.utils.process import ProcessUtils

if TYPE_CHECKING:
    from rclpy.node import Node

_logger = logging.getLogger("nectar.control.obstacles.ros_detector")

if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)

_DIRECTION_MAP = {
    "FRONT": ObstacleDirection.FRONT,
    "BACK": ObstacleDirection.BACK,
    "LEFT": ObstacleDirection.LEFT,
    "RIGHT": ObstacleDirection.RIGHT,
    "UP": ObstacleDirection.UP,
    "DOWN": ObstacleDirection.DOWN,
}


class ROSObstacleDetector(BaseObstacleDetector):
    """
    Obstacle detector that receives detection data from a ROS2 node via topics.

    The external ROS2 node is launched using :class:`ProcessUtils` and communicates
    obstacle information through three topics:

    - ``<namespace>/obstacle_detected`` (std_msgs/Bool): Whether an obstacle is detected.
    - ``<namespace>/obstacle_distance`` (std_msgs/Float32): Distance to the obstacle in meters.
    - ``<namespace>/obstacle_direction`` (std_msgs/String): Direction of the obstacle
      (FRONT, BACK, LEFT, RIGHT, UP, DOWN).

    Parameters
    ----------
    node : Node
        ROS2 node used to create subscriptions.
    package : str
        ROS2 package containing the detector node.
    executable : str
        Name of the executable (node) to launch.
    namespace : str, default="obstacle_detection"
        Topic namespace prefix for the obstacle topics.
    node_startup_timeout : float, default=15.0
        Maximum time in seconds to wait for the external node to appear.
    gui : bool, default=False
        If True, launch the node process in a GUI terminal.
    """

    def __init__(
        self,
        node: "Node",
        package: str,
        executable: str,
        namespace: str = "obstacle_detection",
        node_startup_timeout: float = 15.0,
        gui: bool = False,
    ):
        super().__init__()
        self._node = node
        self._package = package
        self._executable = executable
        self._namespace = namespace.strip("/")
        self._node_startup_timeout = node_startup_timeout
        self._gui = gui

        self._session_name = f"obstacle_{self._executable}"
        self._topic_lock = Lock()

        # Latest values received from topics
        self._detected = False
        self._distance: Optional[float] = None
        self._direction: Optional[ObstacleDirection] = None

        # Subscriptions (created on enable)
        self._sub_detected = None
        self._sub_distance = None
        self._sub_direction = None

    # ------------------------------------------------------------------ #
    #  Topic callbacks
    # ------------------------------------------------------------------ #

    def _on_detected_msg(self, msg: Bool) -> None:
        with self._topic_lock:
            self._detected = msg.data

    def _on_distance_msg(self, msg: Float32) -> None:
        with self._topic_lock:
            self._distance = msg.data

    def _on_direction_msg(self, msg: String) -> None:
        with self._topic_lock:
            direction = _DIRECTION_MAP.get(msg.data.upper())
            if direction is not None:
                self._direction = direction

    # ------------------------------------------------------------------ #
    #  Lifecycle hooks
    # ------------------------------------------------------------------ #

    def _on_enable(self) -> None:
        # Launch the external node via ProcessUtils
        command = f"ros2 run {self._package} {self._executable}"
        started = ProcessUtils.start_process(
            command=command,
            name=self._session_name,
            gui=self._gui,
        )

        if not started:
            _logger.error(
                "Failed to start obstacle detector node: %s/%s",
                self._package,
                self._executable,
            )
            return

        # Wait for the node to appear in the ROS2 graph
        if not ProcessUtils.wait_for_node(
            self._executable,
            timeout=self._node_startup_timeout,
        ):
            _logger.warning(
                "Obstacle detector node '%s' did not appear within %.1fs",
                self._executable,
                self._node_startup_timeout,
            )

        # Create topic subscriptions
        self._sub_detected = self._node.create_subscription(
            Bool,
            f"/{self._namespace}/obstacle_detected",
            self._on_detected_msg,
            10,
        )
        self._sub_distance = self._node.create_subscription(
            Float32,
            f"/{self._namespace}/obstacle_distance",
            self._on_distance_msg,
            10,
        )
        self._sub_direction = self._node.create_subscription(
            String,
            f"/{self._namespace}/obstacle_direction",
            self._on_direction_msg,
            10,
        )

        _logger.info(
            "ROSObstacleDetector enabled — listening on /%s/*",
            self._namespace,
        )

    def _on_disable(self) -> None:
        # Destroy subscriptions
        for sub in (self._sub_detected, self._sub_distance, self._sub_direction):
            if sub is not None:
                self._node.destroy_subscription(sub)
        self._sub_detected = None
        self._sub_distance = None
        self._sub_direction = None

        # Kill the external node process
        ProcessUtils.kill_process(self._session_name)
        _logger.info("ROSObstacleDetector disabled")

    def _on_reset(self) -> None:
        with self._topic_lock:
            self._detected = False
            self._distance = None
            self._direction = None

    # ------------------------------------------------------------------ #
    #  Detection
    # ------------------------------------------------------------------ #

    def _detect(self) -> ObstacleInfo:
        with self._topic_lock:
            return ObstacleInfo(
                detected=self._detected,
                direction=self._direction if self._detected else None,
                distance=self._distance if self._detected else None,
            )
