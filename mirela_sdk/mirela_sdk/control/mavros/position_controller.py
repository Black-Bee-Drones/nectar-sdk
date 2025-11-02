from typing import TYPE_CHECKING, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from mirela_sdk.control.mavros.mavros_api import MavDrone

from pathlib import Path
import numpy as np

import rclpy
from rclpy.duration import Duration

from mavros_msgs.msg import PositionTarget
from geometry_msgs.msg import PoseWithCovarianceStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix

from mirela_sdk.utils.gps_calculate import GPSCalculate
from mirela_sdk.utils.position_utils import PositionUtils
from mirela_sdk.control.pid import PIDController, PIDConfig, PositionPIDConfig
from mirela_sdk.control.mavros.obstacle_detector import LidarObstacleDetector, RealsenseObstacleDetector
from mirela_sdk.control.mavros.exceptions import InvalidModeError

LIDAR_ALTITUDE_LIMIT = 15.0  # meters

@dataclass
class NavigationConfig:
    """Internal configuration for navigation control."""
    control_x: bool = True
    control_y: bool = True
    control_z: bool = True
    control_yaw: bool = True
    use_lidar: bool = False
    obstacle_avoidance: bool = False
    lidar_target_alt: Optional[float] = None
    
    @classmethod
    def from_offboard_params(
        cls,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        lidar_available: bool = False,
        current_lidar_alt: Optional[float] = None,
        ground_reference: bool = False,
        obstacle_avoidance: bool = False
    ) -> 'NavigationConfig':
        """
        Create NavigationConfig from offboard_position parameters.
        
        Parameters
        ----------
        x, y, z, yaw : Optional[float]
            Movement parameters. None means disable control for that axis.
        lidar_available : bool
            Whether lidar sensor is available.
        current_lidar_alt : Optional[float]
            Current lidar altitude reading.
        ground_reference : bool
            Whether movement is ground-referenced.
        obstacle_avoidance: bool
            Whether to avoid obstacles using Realsense.
        
        Returns
        -------
        NavigationConfig
            Configuration object for navigate_PID.
        """
        config = cls(
            control_x=(x is not None),
            control_y=(y is not None),
            control_z=(z is not None),
            control_yaw=(yaw is not None),
            obstacle_avoidance=obstacle_avoidance
        )
        
        # Determine lidar usage for altitude control
        if config.control_z and lidar_available and current_lidar_alt is not None:
            config.use_lidar = True
            if ground_reference:
                # For ground reference, z is absolute altitude from takeoff
                config.lidar_target_alt = z
            else:
                # For relative movement, add z offset to current altitude
                config.lidar_target_alt = current_lidar_alt + z
        
        return config

class PositionController:
    """
    Position controller using PID for precise navigation.

    Supports both indoor (local coordinates) and outdoor (GPS coordinates) modes.
    Includes lidar-based obstacle detection for altitude control.
    """

    def __init__(self, drone: "MavDrone"):
        """
        Initialize position controller.

        Parameters
        ----------
        drone : MavDrone
            Reference to the MAVLink drone instance.
        """
        self.drone = drone
        self._pid_config = None
        self._load_pid_config()
        self._obstacle_detector = LidarObstacleDetector(
            buffer_size=10, height_threshold=0.25, timeout=8.0
        )

    def _load_pid_config(self):
        """Load default PID configuration based on indoor/outdoor mode."""
        # Use default config based on mode
        config_dir = Path(__file__).parent.parent.parent / "config" / "mavros"
        if self.drone.indoor:
            default_config = config_dir / "position_indoor.yaml"
        else:
            default_config = config_dir / "position_outdoor.yaml"

        if default_config.exists():
            self._pid_config = PositionPIDConfig.from_yaml(default_config)
        else:
            # Fallback to hardcoded defaults
            self.drone.node.get_logger().warn(
                f"Config file not found: {default_config}, using hardcoded defaults"
            )
            self._pid_config = self._get_default_config()

    def _get_default_config(self) -> PositionPIDConfig:
        """Get default PID configuration based on flight mode."""
        if self.drone.indoor:
            return PositionPIDConfig(
                x=PIDConfig(kp=0.5, output_min=-0.42, output_max=0.42),
                y=PIDConfig(kp=0.5, output_min=-0.42, output_max=0.42),
                z=PIDConfig(kp=0.22, output_min=-0.15, output_max=0.1),
            )
        else:
            return PositionPIDConfig(
                x=PIDConfig(kp=0.8, output_min=-1.0, output_max=1.0),
                y=PIDConfig(kp=0.8, output_min=-1.0, output_max=1.0),
                z=PIDConfig(kp=0.5, output_min=-0.8, output_max=0.8),
            )

    def _create_pid_controllers(self) -> dict[str, PIDController]:
        """Create PID controllers for X, Y, Z axes."""
        return {
            "x": PIDController(
                kp=self._pid_config.x.kp,
                ki=self._pid_config.x.ki,
                kd=self._pid_config.x.kd,
                output_limits=self._pid_config.x.get_output_limits(),
                integral_limits=self._pid_config.x.get_integral_limits(),
            ),
            "y": PIDController(
                kp=self._pid_config.y.kp,
                ki=self._pid_config.y.ki,
                kd=self._pid_config.y.kd,
                output_limits=self._pid_config.y.get_output_limits(),
                integral_limits=self._pid_config.y.get_integral_limits(),
            ),
            "z": PIDController(
                kp=self._pid_config.z.kp,
                ki=self._pid_config.z.ki,
                kd=self._pid_config.z.kd,
                output_limits=self._pid_config.z.get_output_limits(),
                integral_limits=self._pid_config.z.get_integral_limits(),
            ),
            "yaw": PIDController(
                kp=0.5,
                ki=0.1,
                kd=0.0,
                output_limits=(-0.2, 0.2),
                integral_limits=(-0.05, 0.05),
            ),
        }

    def get_current_position(
        self, timeout: float | None = None
    ) -> PoseWithCovarianceStamped | NavSatFix:
        """
        Get current drone position.

        Parameters
        ----------
        timeout : float, optional
            Time to wait for position update (seconds).

        Returns
        -------
        PoseWithCovarianceStamped or NavSatFix
            Current position based on flight mode.
        """
        if timeout is not None:
            start_t = self.drone.node.get_clock().now()
            sleep_dur = Duration(seconds=timeout)
            while self.drone.node.get_clock().now() - start_t < sleep_dur:
                rclpy.spin_once(self.drone.node, timeout_sec=0.01)

        if self.drone.indoor:
            return self.drone.get_vision_pos
        else:
            return self.drone.get_gps

    def navigate_local_msg(
        self,
        target_position: PositionTarget,
        precision_radius: float = 0.2,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to local position using setpoint messages.

        Parameters
        ----------
        target_position : PositionTarget
            Target local position setpoint.
        precision_radius : float
            Acceptable distance to consider target reached (meters).
        timeout_sec : float, optional
            Maximum time to reach target (seconds).
        """
        if not self.drone.indoor:
            self.drone.node.get_logger().warn(
                "Local coordinate navigation not recommended in outdoor mode"
            )

        start_time = self.drone.node.get_clock().now()
        timeout_duration = Duration(seconds=timeout_sec) if timeout_sec else None

        while True:
            target_position.header.stamp = self.drone.node.get_clock().now().to_msg()
            self.drone.local_pub.publish(target_position)

            current_pos = self.get_current_position(timeout=0.01)

            distance = np.sqrt(
                (current_pos.pose.pose.position.x - target_position.position.x) ** 2
                + (current_pos.pose.pose.position.y - target_position.position.y) ** 2
                + (current_pos.pose.pose.position.z - target_position.position.z) ** 2
            )

            self.drone.node.get_logger().info(
                f"Distance to target: {distance:.2f}m", throttle_duration_sec=1.0
            )

            if distance <= precision_radius:
                self.drone.node.get_logger().info(
                    f"\033[32;1mTarget reached! Distance: {distance:.2f}m\033[0m"
                )
                return

            if (
                timeout_duration
                and (self.drone.node.get_clock().now() - start_time) > timeout_duration
            ):
                self.drone.node.get_logger().warn(
                    f"\033[33;1mTimeout reached. Distance: {distance:.2f}m\033[0m"
                )
                return

    def navigate_gps_msg(
        self,
        gps_setpoint: GeoPoseStamped,
        precision_radius: float = 0.5,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to GPS coordinate using setpoint messages.

        Parameters
        ----------
        gps_setpoint : GeoPoseStamped
            GPS coordinate setpoint with latitude, longitude, altitude, and orientation.
        precision_radius : float
            Acceptable distance to consider target reached (meters).
        timeout_sec : float, optional
            Maximum time to reach target (seconds).
        """
        if self.drone.indoor:
            raise InvalidModeError("GPS navigation", "indoor", "outdoor")

        target_position = gps_setpoint.pose.position
        target_heading = PositionUtils.get_yaw_from_pose(gps_setpoint)

        self.drone.node.get_logger().info(
            "-- Moving to GPS coordinate:\n"
            + f"{target_position.latitude}, {target_position.longitude}, {target_position.altitude}, {target_heading}"
        )

        start_time = self.drone.node.get_clock().now()
        timeout_duration = Duration(seconds=timeout_sec) if timeout_sec else None

        while True:
            gps_setpoint.header.stamp = self.drone.node.get_clock().now().to_msg()
            self.drone.gps_pub.publish(gps_setpoint)

            current_pos: NavSatFix = self.get_current_position(timeout=0.01)

            horizontal_dist = GPSCalculate.haversine(
                current_pos.latitude,
                current_pos.longitude,
                target_position.latitude,
                target_position.longitude,
            )

            distance = np.sqrt(
                horizontal_dist**2
                + (current_pos.altitude - target_position.altitude) ** 2
            )

            self.drone.node.get_logger().info(
                f"-- Distance to target: {distance:.2f} m", throttle_duration_sec=1.0
            )

            if distance < precision_radius:
                self.drone.node.get_logger().info("-- Reached target position")
                return

            if (
                timeout_duration
                and (self.drone.node.get_clock().now() - start_time) > timeout_duration
            ):
                self.drone.node.get_logger().warn(
                    "-- Timeout reached before arriving at target position"
                )
                return

    def navigate_PID(
        self,
        target_position: PositionTarget | GeoPoseStamped = None,
        precision_radius: float = 0.2,
        timeout_sec: float | None = 60.0,
        nav_config: Optional[NavigationConfig] = None,
    ):
        """
        Navigate to position using PID velocity control.

        Parameters
        ----------
        target_position : PositionTarget | GeoPoseStamped
            Target position setpoint:
            - PositionTarget: for indoor/vision coordinates (NED frame)
            - GeoPoseStamped: for outdoor/GPS coordinates

        precision_radius : float
            Acceptable distance in meters to consider the target reached.
            Controller stops when 3D distance to target is within this radius.

        timeout_sec : float, optional
            Maximum time in seconds to reach the target position.
            If None, no timeout is applied.

        nav_config : NavigationConfig, optional
            Navigation configuration specifying control behavior:
            - control_x, control_y, control_z, control_yaw: Enable/disable axis control
            - use_lidar: Whether to use lidar for altitude control
            - lidar_target_alt: Target altitude for lidar (if use_lidar=True)
            
            If None, defaults to controlling all axes without lidar.

        Notes
        -----
        - Uses velocity control commands to reach the target position
        - Obstacle detection activates when nav_config.use_lidar is True
        - PID gains are automatically selected based on indoor/outdoor mode
        - Resets PID controllers and stops movement when target is reached
        """
        if nav_config is None:
            nav_config = NavigationConfig()  # Default: control all axes

        pid_controllers = self._create_pid_controllers()
        use_lidar = self._should_use_lidar(nav_config.lidar_target_alt if nav_config.use_lidar else None)
        self._obstacle_detector.reset()

        if nav_config.obstacle_avoidance:
            rs_obstacle_detector = RealsenseObstacleDetector(drone=self.drone)

        start_time = self.drone.node.get_clock().now()
        timeout_duration = Duration(seconds=timeout_sec) if timeout_sec else None

        while True:
            current_pose = self.get_current_position(timeout=0.01)
            current_time = self.drone.node.get_clock().now().nanoseconds / 1e9

            if nav_config.obstacle_avoidance and rs_obstacle_detector.obstacle_event.is_set():
                self.drone.node.get_logger().info(
                    "Obstacle detected by Realsense - hovering in place",
                    throttle_duration_sec=1.0,
                )
                self.drone.offboard_velocity(0.0, 0.0, 0.0, 0.0, ground_reference=False)
                continue

            # Calculate position errors in body frame
            heading = None if self.drone.indoor else self.drone.get_heading.data
            dx, dy, dz = PositionUtils.get_body_distance(
                target_position, current_pose, heading
            )

            if nav_config.control_yaw:
                if self.drone.indoor:
                    current_yaw = PositionUtils.get_yaw_from_pose(current_pose)
                else:
                    current_yaw = heading

                dyaw = PositionUtils.get_yaw_from_pose(target_position) - current_yaw
                # Normalize yaw error to [-pi, pi]
                dyaw = (dyaw + np.pi) % (2 * np.pi) - np.pi
                if abs(dyaw) < np.radians(3):
                    # Yaw is close enough - consider it reached
                    dyaw = 0.0
                vyaw = pid_controllers["yaw"].update(-dyaw)
            else:
                dyaw = 0.0
                vyaw = 0.0

            # Handle lidar-based altitude control and obstacle detection
            obstacle_detected = False
            if use_lidar:
                lidar_alt = self.drone.get_rng_alt.range
                dz = nav_config.lidar_target_alt - lidar_alt
                obstacle_detected = self._obstacle_detector.update(
                    lidar_alt, current_time
                )

                if obstacle_detected:
                    elapsed = self._obstacle_detector.get_elapsed_time(current_time)
                    self.drone.node.get_logger().info(
                        f"Obstacle detected - deferring to ArduPilot altitude control "
                        f"(elapsed: {elapsed:.1f}s)",
                        throttle_duration_sec=1.0,
                    )

            # Calculate velocities based on control flags
            vx = pid_controllers["x"].update(-dx) if nav_config.control_x else 0.0
            vy = pid_controllers["y"].update(-dy) if nav_config.control_y else 0.0

            # Handle altitude control
            if not nav_config.control_z:
                # Altitude control disabled - let Pixhawk handle altitude
                dz = 0.0
                vz = 0.0
            elif obstacle_detected:
                # Obstacle detected - defer to ArduPilot altitude control
                # [Note]: Not tested yet, can be generating false positives
                vz = pid_controllers["z"].update(-dz)
            else:
                # Normal PID altitude control
                vz = pid_controllers["z"].update(-dz)

            # Apply dead zone to prevent oscillations
            dead_zone = precision_radius / 2
            if abs(dx) < dead_zone:
                vx = 0.0
            if abs(dy) < dead_zone:
                vy = 0.0
            if abs(dz) < dead_zone:
                vz = 0.0

            # Calculate distance considering only controlled axes
            distance_components = []
            if nav_config.control_x:
                distance_components.append(dx**2)
            if nav_config.control_y:
                distance_components.append(dy**2)
            if nav_config.control_z:
                distance_components.append(dz**2)
            
            distance = np.sqrt(sum(distance_components)) if distance_components else 0.0

            # Build status string
            control_status = []
            if nav_config.control_x:
                control_status.append(f"dx={dx:.2f}")
            if nav_config.control_y:
                control_status.append(f"dy={dy:.2f}")
            if nav_config.control_z:
                control_status.append(f"dz={dz:.2f}")
            if nav_config.control_yaw:
                control_status.append(f"dyaw={np.degrees(dyaw):.2f}")

            error_str = ", ".join(control_status)

            self.drone.node.get_logger().info(
                f"Distance: {distance:.2f}m | Error: {error_str} | "
                f"Vel: vx={vx:.2f}, vy={vy:.2f}, vz={vz:.2f}, vyaw={vyaw:.2f}",
                throttle_duration_sec=0.5,
            )

            self.drone.offboard_velocity(
                linear_x=vx,
                linear_y=vy,
                linear_z=vz,
                angular_z=vyaw,
                ground_reference=False,
            )

            # Check timeout
            if (
                timeout_duration
                and (self.drone.node.get_clock().now() - start_time) > timeout_duration
            ):
                self._stop_and_reset(pid_controllers)
                self.drone.node.get_logger().warn("\033[33;1mTimeout reached\033[0m")
                if nav_config.obstacle_avoidance:
                    rs_obstacle_detector.close()
                return

            # Check arrival (only for controlled axes)
            if distance <= precision_radius:
                if nav_config.control_yaw:
                    if abs(dyaw) > np.radians(3):
                        continue  # Still need to adjust yaw
                self._stop_and_reset(pid_controllers)
                if nav_config.obstacle_avoidance:
                    rs_obstacle_detector.close()
                self.drone.node.get_logger().info(
                    f"\033[32;1mTarget reached! Final distance: {distance:.2f}m\033[0m"
                )
                return

    def _should_use_lidar(self, lidar_target_alt: float | None) -> bool:
        """Check if lidar should be used for altitude control."""
        if lidar_target_alt is None:
            return False

        if not self.drone.lidar_on:
            self.drone.node.get_logger().warn(
                "Lidar altitude requested but lidar not available"
            )
            return False

        if lidar_target_alt > LIDAR_ALTITUDE_LIMIT:
            self.drone.node.get_logger().warn(
                f"Lidar altitude {lidar_target_alt}m exceeds {LIDAR_ALTITUDE_LIMIT}m limit"
            )
            return False

        self.drone.node.get_logger().info(
            "Using lidar for altitude control with obstacle detection"
        )
        return True

    def set_pid_config(self, config: PositionPIDConfig):
        """
        Update PID configuration.

        Parameters
        ----------
        config : PositionPIDConfig
            New PID configuration for X, Y, Z axes.
        """
        self._pid_config = config
        self.drone.node.get_logger().info(
            "Position controller PID configuration updated"
        )

    def _stop_and_reset(self, pid_controllers: dict[str, PIDController]):
        """Stop drone and reset PID controllers."""
        for controller in pid_controllers.values():
            controller.reset()
        self.drone.offboard_velocity(0.0, 0.0, 0.0, 0.0, ground_reference=False)
