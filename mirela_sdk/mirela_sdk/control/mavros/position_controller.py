from typing import TYPE_CHECKING
if TYPE_CHECKING:  # for type checking only
    from mirela_sdk.control.mavros.mavros_api import MavDrone

import rclpy
from rclpy.duration import Duration

import numpy as np

from mirela_sdk.utils.gps_calculate import GPSCalculate
from mirela_sdk.utils.position_utils import PositionUtils

from mavros_msgs.msg import PositionTarget
from geometry_msgs.msg import PoseWithCovarianceStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix

# LIDAR ALTITUDE LIMIT
LIDAR_ALTITUDE_LIMIT = 15.0  # meters

# INDOOR PID PARAMETERS
HORIZONTAL_INDOOR_KP = 0.5
HORIZONTAL_INDOOR_KI = 0.0
HORIZONTAL_INDOOR_KD = 0.0

VERTICAL_INDOOR_KP = 0.5
VERTICAL_INDOOR_KI = 0.0
VERTICAL_INDOOR_KD = 0.0

HORIZONTAL_INDOOR_MAX_SPEED = 0.3  # m/s
HORIZONTAL_INDOOR_MIN_SPEED = 0.1  # m/s

VERTICAL_INDOOR_MAX_SPEED = 0.2  # m/s
VERTICAL_INDOOR_MIN_SPEED = 0.1  # m/s

# OUTDOOR PID PARAMETERS
HORIZONTAL_OUTDOOR_KP = 0.8
HORIZONTAL_OUTDOOR_KI = 0.0
HORIZONTAL_OUTDOOR_KD = 0.0

VERTICAL_OUTDOOR_KP = 0.5
VERTICAL_OUTDOOR_KI = 0.0
VERTICAL_OUTDOOR_KD = 0.0

HORIZONTAL_OUTDOOR_MAX_SPEED = 1.0  # m/s
HORIZONTAL_OUTDOOR_MIN_SPEED = 0.1  # m/s

VERTICAL_OUTDOOR_MAX_SPEED = 0.8  # m/s
VERTICAL_OUTDOOR_MIN_SPEED = 0.1  # m/s

# LIDAR OVER OBSTACLE PARAMETER
OBSTACLE_TIMEOUT = 8.0 # s
OBSTACLE_HEIGHT = 0.35 # m


class PID:
    def __init__(self, kp: float, ki: float, kd: float, dt: float, max_output: float = 1.0, min_output: float = 0.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt

        self.integral = 0.0
        self.prev_error = 0.0

        self.max_output = max_output
        self.min_output = min_output

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, error: float) -> float:
        self.integral += error * self.dt
        derivative = (error - self.prev_error) / self.dt if self.dt > 0 else 0.0

        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)

        self.prev_error = error

        output = max(min(output, self.max_output), self.min_output)

        return output

class PositionController:
    def __init__(self, drone: "MavDrone"):  # Quotes here are required for runtime, but IDEs and mypy will resolve the type!
        self.drone = drone
    
    def get_current_position(self, timeout: float|None = None) -> PoseWithCovarianceStamped | NavSatFix:
        """
        Get the current position of the drone, either in local coordinates (PoseWithCovarianceStamped) or GPS coordinates (NavSatFix),

        depending on whether the drone is in indoor or outdoor mode.

        :param timeout: Optional timeout in seconds to wait for the position data. 
        
        If None, it will return immediately with the latest data.
        
        :return: PoseWithCovarianceStamped or NavSatFix
        :rtype: PoseWithCovarianceStamped | NavSatFix
        """

        if timeout is not None:
            start_t = self.drone.node.get_clock().now()
            sleep_dur = Duration(seconds=timeout)
            while self.drone.node.get_clock().now() - start_t < sleep_dur:
                rclpy.spin_once(self.drone.node, timeout_sec=0.01)

        if self.drone.indoor == True:
            return self.drone.get_visual_pos
        else:
            return self.drone.get_gps
        
    def navigate_local_msg(
        self,
        target_position: PositionTarget = None,
        precision_radius: float = 0.2,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to a local position setpoint using closed-loop control.
        
        Publishes position setpoint messages until the target is reached within
        the specified precision radius or timeout is exceeded.

        Parameters
        ----------
        target_position : PositionTarget
            Target local position setpoint.

        precision_radius : float
            Acceptable distance in meters to consider target reached.

        timeout_sec : float, optional
            Maximum time in seconds to reach the target.
            If None, no timeout is applied.

        Warnings
        --------
        This method is not recommended for outdoor mode due to reduced
        precision when using GPS coordinates.
        """
        
        if self.drone.indoor == False:
            self.drone.node.get_logger().warn("offboard_position with local coordinates should not be used in outdoor mode, since it has less precision when using the GPS.")

        if timeout_sec is not None:
            start_time = self.drone.node.get_clock().now()
            timeout_duration = Duration(seconds=timeout_sec)

        while True:
            target_position.header.stamp = self.drone.node.get_clock().now().to_msg()
            self.drone.local_pub.publish(target_position)

            current_pos: PoseWithCovarianceStamped = self.get_current_position(timeout=0.01)

            #Calculates distance to target
            dist_to_target = np.sqrt(
                (current_pos.pose.position.x - target_position.position.x)**2 +
                (current_pos.pose.position.y - target_position.position.y)**2 +
                (current_pos.pose.position.z - target_position.position.z)**2
            )

            self.drone.node.get_logger().info(f"   Distance to target: {dist_to_target:.2f}m", throttle_duration_sec=1.0)

            #Checks if arrival is is complete
            if dist_to_target <= precision_radius:
                self.drone.node.get_logger().info(f"\033[32;1m   Target reached! Distance: {dist_to_target:.2f}m\033[0m")
                return

            #Checks for timeout
            if timeout_sec is not None and (self.drone.node.get_clock().now() - start_time) > timeout_duration:
                self.drone.node.get_logger().warn(f"\033[33;1m   Timeout reached before arriving at target position. Distance: {dist_to_target:.2f}m\033[0m")
                return

    def navigate_gps_msg(
        self,
        gps_setpoint: GeoPoseStamped = None,
        precision_radius: float = 0.5,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to a GPS coordinate setpoint using closed-loop control.
        
        Publishes GPS position setpoint messages until the target is reached
        within the specified precision radius or timeout is exceeded.

        Parameters
        ----------
        gps_setpoint : GeoPoseStamped
            GPS coordinate setpoint containing latitude, longitude, altitude,
            and orientation information.

        precision_radius : float
            Acceptable distance in meters to consider target reached.
            Takes into account both horizontal and vertical distance.

        timeout_sec : float, optional
            Maximum time in seconds to reach the target.
            If None, no timeout is applied.

        Raises
        ------
        RuntimeError
            If called in indoor mode where GPS coordinates are not available.
        """
        if self.drone.indoor == True:
            raise RuntimeError("offboard_position with GPS coordinates cannot be used in indoor mode.")

        target_position = gps_setpoint.pose.position
        target_orientation = gps_setpoint.pose.orientation
        quat = [target_orientation.x, target_orientation.y, target_orientation.z, target_orientation.w]
        target_heading = PositionUtils.get_yaw_from_pose(gps_setpoint)
        self.drone.node.get_logger().info(
            "-- Moving to GPS coordinate:\n" +
            f"{target_position.latitude}, {target_position.longitude}, {target_position.altitude}, {target_heading}"
        )

        # fix height issue?
        # https://wiki.ros.org/mavros#mavros.2FPlugins.Avoiding_Pitfalls_Related_to_Ellipsoid_Height_and_Height_Above_Mean_Sea_Level
        # https://wiki.ros.org/mavros/Plugins#:~:text=~global_position/global%20(,for%20more.
        # gps_setpoint.pose.position.altitude (+-?)= self.egm96.height(
        #     gps_setpoint.pose.position.latitude,
        #     gps_setpoint.pose.position.longitude
        #     )

        self.drone.gps_pub.publish(gps_setpoint)
        if timeout_sec is not None:
            start_time = self.drone.node.get_clock().now()
            timeout = Duration(seconds=timeout_sec)

        while True:
            gps_setpoint.header.stamp = self.drone.node.get_clock().now().to_msg()
            self.drone.gps_pub.publish(gps_setpoint)
            
            current_pos: NavSatFix = self.get_current_position(timeout=0.01)

            distance = GPSCalculate.haversine(
                current_pos.latitude, current_pos.longitude,
                target_position.latitude, target_position.longitude
            )

            distance = np.sqrt(distance**2 + (current_pos.altitude - target_position.altitude)**2)

            self.drone.node.get_logger().info(f"-- Distance to target: {distance:.2f} m", throttle_duration_sec=1.0)

            if distance < precision_radius:
                self.drone.node.get_logger().info("-- Reached target position")
                return
            
            if timeout_sec is not None and (self.drone.node.get_clock().now() - start_time) > timeout:
                self.drone.node.get_logger().warn("-- Timeout reached before arriving at target position")
                return

    def navigate_PID(
        self,
        target_position: PositionTarget | GeoPoseStamped = None,
        lidar_target_alt: float | None = None,
        precision_radius: float = 0.2,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to a position setpoint using PID controllers for precise closed-loop control.

        Uses separate PID controllers for X, Y, and Z axes to compute velocity commands
        that will guide the drone to the target position. Includes obstacle detection
        using lidar data with EMA filtering when lidar altitude control is enabled.

        Parameters
        ----------
        target_position : PositionTarget | GeoPoseStamped
            Target position setpoint:
            - PositionTarget: for indoor/local coordinates (NED frame)
            - GeoPoseStamped: for outdoor/GPS coordinates

        lidar_target_alt : float, optional
            Desired altitude above ground level in meters, measured by lidar.
            If provided, overrides the Z component of target_position.
            Limited to 15m maximum for safety. Enables obstacle detection.

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

        # Initialize timing and obstacle detection variables
        start_time = self.drone.node.get_clock().now()
        timeout = Duration(seconds=timeout_sec) if timeout_sec is not None else None

        obstacle_state = {
            'detected': False,
            'start_time': None,
            'height_offset': 0.0,
            'duration': Duration(seconds=OBSTACLE_TIMEOUT)
        }

        # Configure lidar altitude control and obstacle detection
        lidar_config = self._setup_lidar_control(lidar_target_alt)
        lidar_ema = None  # Method-level EMA variable
        
        # Initialize PID controllers based on flight mode
        pid_controllers = self._initialize_pid_controllers()

        while True:
            current_pose = self.get_current_position(timeout=0.01)

            # Calculate distance to target in body frame
            heading = None if self.drone.indoor else self.drone.get_heading.data
            dx_body, dy_body, dz_body = PositionUtils.get_body_distance(target_position, current_pose, heading)

            # Process lidar data for altitude control and obstacle detection
            if lidar_config['enabled']:
                dz_body, obstacle_state, lidar_ema = self._process_lidar_data(
                    lidar_config, obstacle_state, dz_body, lidar_ema
                )

            # Compute PID control outputs
            vx, vy, vz = self._compute_pid_velocities(pid_controllers, dx_body, dy_body, dz_body)

            # Override vertical velocity if obstacle detected
            if obstacle_state['detected']:
                vz = 0.0 # halt vertical movement to let ArduPilot's obstacle avoidance take over

            # Apply precision radius dead zones
            vx, vy, vz = self._apply_precision_zones(vx, vy, vz, dx_body, dy_body, dz_body, precision_radius)

            # Log current state
            self._log_controller_state(dx_body, dy_body, dz_body, vx, vy, vz)

            # Send velocity commands to drone
            self.drone.offboard_velocity(
                linear_x=vx, linear_y=vy, linear_z=vz, angular_z=0.0, ground_reference=False
            )

            # Check for arrival or timeout
            if self._check_arrival_conditions(dx_body, dy_body, dz_body, precision_radius, pid_controllers):
                return
            
            if self._check_timeout(start_time, timeout):
                return

    def _setup_lidar_control(self, lidar_target_alt: float | None) -> dict:
        """Setup lidar configuration for altitude control and obstacle detection."""
        config = {
            'enabled': False,
            'target_alt': None,
            'ema_alpha': 0.1  # EMA smoothing factor
        }
        
        if lidar_target_alt is not None:
            if not self.drone.lidar_on:
                self.drone.node.get_logger().warn(
                    "Lidar altitude setpoint provided, but lidar is not enabled. Ignoring lidar altitude."
                )
                return config
            
            if lidar_target_alt > LIDAR_ALTITUDE_LIMIT:
                self.drone.node.get_logger().warn(
                    f"Requested altitude {lidar_target_alt}m exceeds {LIDAR_ALTITUDE_LIMIT}m limit "
                    "for lidar-based control, using altitude parameter instead."
                )
                return config
            
            config['enabled'] = True
            config['target_alt'] = lidar_target_alt
            self.drone.node.get_logger().info("Using lidar for altitude control with obstacle detection.")
        
        return config

    def _initialize_pid_controllers(self) -> dict:
        """Initialize PID controllers based on indoor/outdoor flight mode."""
        if self.drone.indoor:
            return {
                'x': PID(HORIZONTAL_INDOOR_KP, HORIZONTAL_INDOOR_KI, HORIZONTAL_INDOOR_KD, 
                        dt=0.01, max_output=HORIZONTAL_INDOOR_MAX_SPEED, min_output=HORIZONTAL_INDOOR_MIN_SPEED),
                'y': PID(HORIZONTAL_INDOOR_KP, HORIZONTAL_INDOOR_KI, HORIZONTAL_INDOOR_KD,
                        dt=0.01, max_output=HORIZONTAL_INDOOR_MAX_SPEED, min_output=HORIZONTAL_INDOOR_MIN_SPEED),
                'z': PID(VERTICAL_INDOOR_KP, VERTICAL_INDOOR_KI, VERTICAL_INDOOR_KD,
                        dt=0.01, max_output=VERTICAL_INDOOR_MAX_SPEED, min_output=VERTICAL_INDOOR_MIN_SPEED)
            }
        else:
            return {
                'x': PID(HORIZONTAL_OUTDOOR_KP, HORIZONTAL_OUTDOOR_KI, HORIZONTAL_OUTDOOR_KD,
                        dt=0.01, max_output=HORIZONTAL_OUTDOOR_MAX_SPEED, min_output=HORIZONTAL_OUTDOOR_MIN_SPEED),
                'y': PID(HORIZONTAL_OUTDOOR_KP, HORIZONTAL_OUTDOOR_KI, HORIZONTAL_OUTDOOR_KD,
                        dt=0.01, max_output=HORIZONTAL_OUTDOOR_MAX_SPEED, min_output=HORIZONTAL_OUTDOOR_MIN_SPEED),
                'z': PID(VERTICAL_OUTDOOR_KP, VERTICAL_OUTDOOR_KI, VERTICAL_OUTDOOR_KD,
                        dt=0.01, max_output=VERTICAL_OUTDOOR_MAX_SPEED, min_output=VERTICAL_OUTDOOR_MIN_SPEED)
            }

    def _process_lidar_data(self, lidar_config: dict, obstacle_state: dict, dz_body: float, lidar_ema: float | None) -> tuple[float, dict, float]:
        """Process lidar data for altitude control and obstacle detection."""
        if not lidar_config['enabled']:
            return dz_body, obstacle_state, lidar_ema
        
        current_lidar = self.drone.get_rng_alt.range
        
        # Initialize EMA on first reading
        if lidar_ema is None:
            lidar_ema = current_lidar
        
        # Calculate deviation from EMA
        lidar_deviation = current_lidar - lidar_ema

        # Update EMA for obstacle detection
        lidar_ema = (lidar_config['ema_alpha'] * current_lidar + 
                    (1 - lidar_config['ema_alpha']) * lidar_ema)
        
        # Use lidar for altitude control
        dz_body = lidar_config['target_alt'] - current_lidar
        
        # Detect obstacles using EMA filtering
        if abs(lidar_deviation) > OBSTACLE_HEIGHT and not obstacle_state['detected']:
            self.drone.node.get_logger().info(
                f"Obstacle detected! Lidar deviation: {lidar_deviation:.2f}m (threshold: {OBSTACLE_HEIGHT}m)"
            )
            obstacle_state.update({
                'detected': True,
                'start_time': self.drone.node.get_clock().now(),
                'height_offset': lidar_deviation
            })

        if obstacle_state['detected']:
            elapsed_time = self.drone.node.get_clock().now() - obstacle_state['start_time']

            # Log obstacle avoidance status
            self.drone.node.get_logger().info(
                f"Obstacle avoidance active for {elapsed_time.nanoseconds / 1e9:.1f}s "
                f"(timeout: {OBSTACLE_TIMEOUT}s)",
                throttle_duration_sec=1.0
            )

            # Check if obstacle avoidance timeout has elapsed
            if elapsed_time > obstacle_state['duration']:
                self.drone.node.get_logger().info("Obstacle avoidance timeout reached, resuming normal operation.")
                obstacle_state.update({
                    'detected': False,
                    'start_time': None,
                    'height_offset': 0.0
                })
        
            # Check if obstacle is cleared
            if (lidar_deviation < -obstacle_state["height_offset"] + 0.05) and (lidar_deviation > -obstacle_state["height_offset"] - 0.05):
                self.drone.node.get_logger().info(f"Obstacle cleared. Lidar deviation: {lidar_deviation:.2f}m. Height offset was {obstacle_state['height_offset']:.2f}m.")
                obstacle_state.update({
                    'detected': False,
                    'start_time': None,
                    'height_offset': 0.0
                })
                lidar_ema = current_lidar  # Reset EMA to current reading to avoid false positives
                
        return dz_body, obstacle_state, lidar_ema

    def _compute_pid_velocities(self, pid_controllers: dict, dx_body: float, dy_body: float, dz_body: float) -> tuple[float, float, float]:
        """Compute velocity commands using PID controllers."""
        # Use signed error directly with PID controllers that have symmetric limits
        vx = pid_controllers['x'].compute(dx_body)
        vy = pid_controllers['y'].compute(dy_body)
        vz = pid_controllers['z'].compute(dz_body)

        if dx_body < 0: vx = -vx
        if dy_body < 0: vy = -vy
        if dz_body < 0: vz = -vz

        return vx, vy, vz

    def _apply_precision_zones(self, vx: float, vy: float, vz: float, 
                              dx_body: float, dy_body: float, dz_body: float, 
                              precision_radius: float) -> tuple[float, float, float]:
        """Apply dead zones near target to prevent oscillation."""
        dead_zone = precision_radius / 2
        
        if abs(dx_body) < dead_zone: vx = 0.0
        if abs(dy_body) < dead_zone: vy = 0.0
        if abs(dz_body) < dead_zone: vz = 0.0
            
        return vx, vy, vz

    def _log_controller_state(self, dx_body: float, dy_body: float, dz_body: float, 
                             vx: float, vy: float, vz: float):
        """Log current controller state for debugging."""
        self.drone.node.get_logger().info(
            f"Error: dx={dx_body:.2f}, dy={dy_body:.2f}, dz={dz_body:.2f}m",
            throttle_duration_sec=0.1
        )
        self.drone.node.get_logger().info(
            f"Velocity: vx={vx:.2f}, vy={vy:.2f}, vz={vz:.2f}m/s",
            throttle_duration_sec=0.1
        )

    def _check_arrival_conditions(self, dx_body: float, dy_body: float, dz_body: float,
                                 precision_radius: float, pid_controllers: dict) -> bool:
        """Check if drone has arrived at target position."""
        dist_to_target = np.sqrt(dx_body ** 2 + dy_body ** 2 + dz_body ** 2)
        
        self.drone.node.get_logger().info(
            f"Distance to target: {dist_to_target:.2f}m (precision: {precision_radius}m)",
            throttle_duration_sec=1.0
        )
        
        if dist_to_target <= precision_radius:
            # Reset PID controllers and stop movement
            for controller in pid_controllers.values():
                controller.reset()
            
            self.drone.offboard_velocity(0.0, 0.0, 0.0, 0.0, ground_reference=False)
            self.drone.node.get_logger().info(
                f"\033[32;1mTarget reached! Final distance: {dist_to_target:.2f}m\033[0m"
            )
            return True
        
        return False

    def _check_timeout(self, start_time, timeout: Duration | None) -> bool:
        """Check if navigation timeout has been exceeded."""
        if timeout is not None and (self.drone.node.get_clock().now() - start_time) > timeout:
            self.drone.node.get_logger().warn(
                f"\033[33;1mTimeout reached before arriving at target position\033[0m"
            )
            return True
        return False
