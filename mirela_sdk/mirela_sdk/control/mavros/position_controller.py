from pathlib import Path
import numpy as np

import rclpy
from rclpy.duration import Duration

from mavros_msgs.msg import PositionTarget
from geometry_msgs.msg import PoseWithCovarianceStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix

from mirela_sdk.control.mavros.mavros_api import MavDrone
from mirela_sdk.utils.gps_calculate import GPSCalculate
from mirela_sdk.utils.position_utils import PositionUtils
from mirela_sdk.control.pid import PIDController, PIDConfig, PositionPIDConfig
from mirela_sdk.control.mavros.obstacle_detector import LidarObstacleDetector

LIDAR_ALTITUDE_LIMIT = 15.0  # meters


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
                z=PIDConfig(kp=0.5, output_min=-0.2, output_max=0.2),
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
            raise RuntimeError("GPS navigation cannot be used in indoor mode")

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
        lidar_target_alt: float | None = None,
        precision_radius: float = 0.2,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to position using PID velocity control.

        Parameters
        ----------
        target_position : PositionTarget | GeoPoseStamped
            Target position setpoint:
            - PositionTarget: for indoor/vision coordinates (NED frame)
            - GeoPoseStamped: for outdoor/GPS coordinates

        lidar_target_alt : float, optional
            Target altitude above ground using lidar (meters). Limited to 15m.
            When provided, enables obstacle detection.
        precision_radius : float
            Acceptable distance in meters to consider the target reached.
            Controller stops when 3D distance to target is within this radius.

        timeout_sec : float, optional
            Maximum time in seconds to reach the target position.
            If None, no timeout is applied.

        Notes
        -----
        - Uses velocity control commands to reach the target position
        - Obstacle detection activates when lidar_target_alt is provided
        - PID gains are automatically selected based on indoor/outdoor mode
        - Resets PID controllers and stops movement when target is reached
        """

        pid_controllers = self._create_pid_controllers()
        use_lidar = self._should_use_lidar(lidar_target_alt)
        self._obstacle_detector.reset()

        start_time = self.drone.node.get_clock().now()
        timeout_duration = Duration(seconds=timeout_sec) if timeout_sec else None

        while True:
            current_pose = self.get_current_position(timeout=0.01)
            current_time = self.drone.node.get_clock().now().nanoseconds / 1e9

            # Calculate position errors in body frame
            heading = None if self.drone.indoor else self.drone.get_heading.data
            dx, dy, dz = PositionUtils.get_body_distance(
                target_position, current_pose, heading
            )

            # Handle lidar-based altitude control and obstacle detection
            obstacle_detected = False
            if use_lidar:
                lidar_alt = self.drone.get_rng_alt.range
                dz = lidar_target_alt - lidar_alt
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

            vx = pid_controllers["x"].update(-dx)  # Negative for body frame
            vy = pid_controllers["y"].update(-dy)
            vz = pid_controllers["z"].update(dz)

            # Stop vertical control if obstacle detected (let ArduPilot handle it)
            if obstacle_detected:
                vz = 0.0

            dead_zone = precision_radius / 2
            if abs(dx) < dead_zone:
                vx = 0.0
            if abs(dy) < dead_zone:
                vy = 0.0
            if abs(dz) < dead_zone:
                vz = 0.0

            # Log state
            distance = np.sqrt(dx**2 + dy**2 + dz**2)
            self.drone.node.get_logger().info(
                f"Distance: {distance:.2f}m | Error: dx={dx:.2f}, dy={dy:.2f}, dz={dz:.2f} | "
                f"Vel: vx={vx:.2f}, vy={vy:.2f}, vz={vz:.2f}",
                throttle_duration_sec=0.5,
            )

            self.drone.offboard_velocity(
                linear_x=vx,
                linear_y=vy,
                linear_z=vz,
                angular_z=0.0,
                ground_reference=False,
            )

            # Check arrival
            if distance <= precision_radius:
                self._stop_and_reset(pid_controllers)
                self.drone.node.get_logger().info(
                    f"\033[32;1mTarget reached! Final distance: {distance:.2f}m\033[0m"
                )
                return

            # Check timeout
            if (
                timeout_duration
                and (self.drone.node.get_clock().now() - start_time) > timeout_duration
            ):
                self._stop_and_reset(pid_controllers)
                self.drone.node.get_logger().warn("\033[33;1mTimeout reached\033[0m")
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
