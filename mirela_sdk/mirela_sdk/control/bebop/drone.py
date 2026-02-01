from typing import Optional
from time import sleep

from rclpy.node import Node
from rclpy.duration import Duration
from std_msgs.msg import Empty, UInt8, Bool
from geometry_msgs.msg import Twist, Vector3

from mirela_sdk.control.base import BaseDrone
from mirela_sdk.control.types import (
    MoveReference,
    NavigationStrategy,
    RTLStrategy,
)
from mirela_sdk.control.config import BebopConfig, DroneConfig
from mirela_sdk.control.factory import DroneFactory
from mirela_sdk.control.exceptions import CapabilityNotSupportedError
from mirela_sdk.utils.process import ProcessUtils


class BebopDrone(BaseDrone):
    """
    Parrot Bebop 2 drone implementation.

    Parameters
    ----------
    config : BebopConfig
        Bebop-specific configuration.
    node : Node
        ROS2 node for communication.
    """

    def __init__(self, config: BebopConfig, node: Node) -> None:
        super().__init__(config, node)
        self._setup_publishers()
        self._node.get_logger().info("BebopDrone initialized")

    @classmethod
    def from_config(cls, config: DroneConfig, node: Node) -> "BebopDrone":
        """
        Factory method for DroneFactory registration.

        Parameters
        ----------
        config : DroneConfig
            Configuration (converted to BebopConfig if needed).
        node : Node
            ROS2 node.

        Returns
        -------
        BebopDrone
            Configured drone instance.
        """
        if not isinstance(config, BebopConfig):
            config = BebopConfig()
        return cls(config, node)

    def _setup_publishers(self) -> None:
        config: BebopConfig = self._config

        self._takeoff_pub = self._create_publisher(
            Empty, f"/{config.namespace}/takeoff", 1
        )
        self._land_pub = self._create_publisher(Empty, f"/{config.namespace}/land", 1)
        self._vel_pub = self._create_publisher(Twist, f"/{config.namespace}/cmd_vel", 1)
        self._flip_pub = self._create_publisher(UInt8, f"/{config.namespace}/flip", 1)
        self._gimbal_pub = self._create_publisher(
            Vector3, f"/{config.namespace}/move_camera", 1
        )
        self._emergency_pub = self._create_publisher(
            Empty, f"/{config.namespace}/reset", 1
        )
        self._flattrim_pub = self._create_publisher(
            Empty, f"/{config.namespace}/flattrim", 1
        )
        self._photo_pub = self._create_publisher(Bool, f"/{config.namespace}/photo", 1)
        self._navigate_home_pub = self._create_publisher(
            Empty, f"/{config.namespace}/autoflight/navigate_home", 1
        )

    def _get_driver_name(self) -> str:
        return "bebop_driver"

    def _get_driver_command(self) -> str:
        config: BebopConfig = self._config
        return f"ros2 launch ros2_bebop_driver bebop_node_launch.xml ip:={config.ip}"

    def _start_driver(self) -> bool:
        cmd = self._get_driver_command()
        return ProcessUtils.start_process(cmd, self._get_driver_name())

    def connect(self) -> bool:
        self._connected = self._driver_running
        return self._connected

    def disconnect(self) -> None:
        self.cleanup()

    def arm(self) -> bool:
        return True

    def disarm(self) -> bool:
        """Force disarm motors via emergency stop."""
        self._emergency_pub.publish(Empty())
        return True

    def takeoff(self, altitude: float) -> bool:
        self._takeoff_pub.publish(Empty())
        self._node.get_logger().info("Takeoff")
        self.delay(3.0)
        return True

    def land(self, timeout: float = 30.0) -> bool:
        self._land_pub.publish(Empty())
        self._node.get_logger().info("Land")
        return True

    def move_velocity(
        self,
        vx: float = 0.0,
        vy: float = 0.0,
        vz: float = 0.0,
        vyaw: float = 0.0,
        duration: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
    ) -> None:
        """
        Command velocity-based movement.

        Note: Bebop only supports BODY frame. WORLD and TAKEOFF references are ignored.
        """
        msg = Twist()
        msg.linear.x = max(-1.0, min(1.0, vx))
        msg.linear.y = max(-1.0, min(1.0, vy))
        msg.linear.z = max(-1.0, min(1.0, vz))
        msg.angular.z = max(-1.0, min(1.0, vyaw))

        if duration is None:
            self._vel_pub.publish(msg)
        else:
            rate = 1.0 / 30
            start = self._node.get_clock().now()
            dur = Duration(seconds=duration)

            while self._node.get_clock().now() - start < dur:
                self._vel_pub.publish(msg)
                sleep(rate)

    def move_to(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        yaw: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
        timeout: Optional[float] = 60.0,
        precision: float = 0.2,
        strategy: NavigationStrategy = NavigationStrategy.PID,
    ) -> bool:
        raise CapabilityNotSupportedError("Position control", "Bebop")

    def emergency_stop(self) -> None:
        self._emergency_pub.publish(Empty())
        self._node.get_logger().info("Emergency stop")

    def rtl(
        self,
        altitude: Optional[float] = None,
        precision: float = 0.2,
        strategy: RTLStrategy = RTLStrategy.PID,
        land: bool = True,
    ) -> bool:
        self._navigate_home_pub.publish(Empty())
        self._node.get_logger().info("Navigate home (RTL)")
        if land:
            self.delay(10.0)
        return True

    def flip(self, direction: int) -> None:
        """
        Execute acrobatic flip maneuver.

        Parameters
        ----------
        direction : int
            Flip direction: 0=Front, 1=Back, 2=Right, 3=Left.
        """
        directions = ["Front", "Back", "Right", "Left"]
        if 0 <= direction <= 3:
            self._flip_pub.publish(UInt8(data=direction))
            self._node.get_logger().info(f"Flip {directions[direction]}")

    def camera_control(self, tilt: float, pan: float) -> None:
        """
        Control camera gimbal.

        Parameters
        ----------
        tilt : float
            Tilt angle in degrees (positive=down, negative=up).
        pan : float
            Pan angle in degrees (positive=left, negative=right).
        """
        msg = Vector3()
        msg.x = tilt
        msg.y = pan
        self._gimbal_pub.publish(msg)
        self._node.get_logger().info(f"Camera tilt={tilt}, pan={pan}")

    def snapshot(self) -> None:
        """Capture photo with onboard camera."""
        self._photo_pub.publish(Bool(data=True))
        self._node.get_logger().info("Snapshot")

    def flat_trim(self) -> None:
        """
        Calibrate IMU.

        Drone must be on flat, level surface before calling.
        """
        self._flattrim_pub.publish(Empty())
        self._node.get_logger().info("Flat trim")


DroneFactory.register("bebop", BebopDrone.from_config)
