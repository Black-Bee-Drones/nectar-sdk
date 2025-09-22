from typing import TYPE_CHECKING
if TYPE_CHECKING:  # for type checking only
    from mirela_sdk.control.mavros.mavros_api import MavDrone

import rclpy
from rclpy.duration import Duration

import numpy as np

from mirela_sdk.utils.gps_calculate import GPSCalculate

from tf_transformations import euler_from_quaternion

from mavros_msgs.msg import PositionTarget
from geometry_msgs.msg import PoseStamped
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

    def calculate_body_distance(self, target: PositionTarget | GeoPoseStamped, current: PoseStamped | NavSatFix) -> float:
        if self.drone.indoor == True:
            if isinstance(target, PositionTarget) and isinstance(current, PoseStamped):
                return self.get_body_distance_indoor(target=target, current=current)
            else:
                raise ValueError("For indoor drones, target and current parameters must be PositionTarget() and PoseStamped(), respectivelly.")
            
        elif isinstance(target, GeoPoseStamped) and isinstance(current, NavSatFix):
            return self.get_body_distance_outdoor(target=target, current=current)

        else:
            raise ValueError("For outdoor drones, target and current parameters must be GeoPoseStamped() and NavSatFix(), respectivelly.")

    @staticmethod
    def get_body_distance_indoor(target: PositionTarget, current: PoseStamped) -> float:
        """
        Calculate the distance from the current position to the target position in the body frame.

        :param target: Target position as PositionTarget
        :param current: Current position as PoseStamped
        :return: Distance to target in meters
        :rtype: float
        """
        cx, cy, cz = current.pose.position.x, current.pose.position.y, current.pose.position.z
        tx, ty, tz = target.position.x, target.position.y, target.position.z

        # Calculate distance to target
        dist_to_target = np.sqrt(
            (cx - tx)**2 +
            (cy - ty)**2 +
            (cz - tz)**2
        )

        # Calculate difference in world frame
        dx_world = tx - cx
        dy_world = ty - cy
        dz = tz - cz

        # Get current yaw
        orientation = current.pose.orientation
        quat = [orientation.x, orientation.y, orientation.z, orientation.w]
        _, _, yaw = euler_from_quaternion(quat)  # Returns roll, pitch, yaw

        # Transform difference to body frame
        dx_body =  np.cos(yaw) * dx_world + np.sin(yaw) * dy_world
        dy_body = -np.sin(yaw) * dx_world + np.cos(yaw) * dy_world
        dz_body = dz  # No change in z axis

        return dist_to_target, dx_body, dy_body, dz_body
    
    @staticmethod
    def get_body_distance_outdoor(target: GeoPoseStamped, current: NavSatFix) -> float:
        """
        Calculate the distance from the current GPS position to the target GPS position in the body frame.

        :param target: Target position as GeoPoseStamped
        :param current: Current position as NavSatFix
        :return: Distance to target in meters
        :rtype: float
        """
        cx, cy, cz = current.latitude, current.longitude, current.altitude
        tx, ty, tz = target.pose.position.latitude, target.pose.position.longitude, target.pose.position.altitude

        # Calculate distance to target using Haversine formula for lat/lon and Pythagorean for altitude
        horizontal_distance = GPSCalculate.haversine(cx, cy, tx, ty)
        dist_to_target = np.sqrt(horizontal_distance**2 + (cz - tz)**2)

        # Calculate difference in world frame
        dx_world = GPSCalculate.haversine(cx, cy, tx, cy)  # North-South distance
        dy_world = GPSCalculate.haversine(cx, cy, cx, ty)  # East-West distance
        dz = tz - cz

        if tx < cx:
            dx_world = -dx_world
        if ty < cy:
            dy_world = -dy_world

        # Get current yaw from target orientation (assuming drone is facing target direction)
        orientation = target.pose.orientation
        quat = [orientation.x, orientation.y, orientation.z, orientation.w]
        _, _, yaw = euler_from_quaternion(quat)  # Returns roll, pitch, yaw

        # Transform difference to body frame
        dx_body =  np.cos(yaw) * dx_world + np.sin(yaw) * dy_world
        dy_body = np.sin(yaw) * dx_world - np.cos(yaw) * dy_world
        dz_body = dz  # No change in z axis

        return dist_to_target, dx_body, dy_body, dz_body

    def get_current_position(self, timeout: float|None = None) -> PoseStamped | NavSatFix:
        """
        Get the current position of the drone, either in local coordinates (PoseStamped) or GPS coordinates (NavSatFix),

        depending on whether the drone is in indoor or outdoor mode.

        :param timeout: Optional timeout in seconds to wait for the position data. 
        
        If None, it will return immediately with the latest data.
        
        :return: PoseStamped or NavSatFix
        :rtype: PoseStamped | NavSatFix
        """

        if timeout is not None:
            start_t = self.drone.node.get_clock().now()
            sleep_dur = Duration(seconds=timeout)
            while self.drone.node.get_clock().now() - start_t < sleep_dur:
                rclpy.spin_once(self.drone.node, timeout_sec=0.01)

        if self.drone.indoor == True:
            return self.drone.get_local_pos
        else:
            return self.drone.get_gps
        
    def navigate_local_msg(
        self,
        target_position: PositionTarget = None,
        precision_radius: float = 0.2,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to a local position setpoint, using closed loop control to ensure arrival.
        
        Parameters
        ----------

        target_position : PositionTarget
            Target local position setpoint.

        precision_radius : float (meters)
            Radius of the precision

        timeout_sec : float|None (seconds)
            Timeout for reach check
            If None, no timeout

        """
        
        if self.drone.indoor == False:
            self.drone.node.get_logger().warn("offboard_position with local coordinates should not be used in outdoor mode, since it has less precision when using the GPS.")

        if timeout_sec is not None:
            start_time = self.drone.node.get_clock().now()
            timeout_duration = Duration(seconds=timeout_sec)

        while True:
            target_position.header.stamp = self.drone.node.get_clock().now().to_msg()
            self.drone.local_pub.publish(target_position)

            current_pos: PoseStamped = self.get_current_position(timeout=0.01)

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
        gps_setpoint: GeoPoseStamped = GeoPoseStamped(),
        precision_radius: float = 0.5,
        timeout_sec: float | None = 60.0,
    ):
        """
        Navigate to a GPS coordinate setpoint, using closed loop control to ensure arrival.
        
        Parameters
        ----------

        gps_setpoint : GeoPoseStamped()
            GPS coordinate setpoint to navigate to.

        precision_radius : float (meters)
            Radius of the precision

        timeout_sec : float|None (seconds)
            Timeout for reach check
            If None, no timeout

        """
        if self.drone.indoor == True:
            raise RuntimeError("offboard_position with GPS coordinates cannot be used in indoor mode.")

        target_position = gps_setpoint.pose.position
        target_orientation = gps_setpoint.pose.orientation
        quat = [target_orientation.x, target_orientation.y, target_orientation.z, target_orientation.w]
        target_heading = np.degrees(euler_from_quaternion(quat)[2])
        self.drone.node.get_logger().info(
            "-- Moving to GPS coordinate:\n" +
            f"{target_position.latitude}, {target_position.longitude}, {target_position.altitude}, {target_heading}"
        )

        # fix height issue?
        # gps_setpoint.pose.position.altitude -= self.egm96.height(
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
        Navigate to a local position setpoint using a PID controller for closed loop control.

        Parameters
        ----------
        target_position : PositionTarget | GeoPoseStamped
            Target local position setpoint.

        lidar_target_alt : float | None (meters)
            If not None, use this altitude as reference instead of the target_position.z.

            Lidar altitude control is limited to 15m above ground level.

        precision_radius : float (meters)
            Radius of the precision

        timeout_sec : float|None (seconds)
            Timeout for reach check
            If None, no timeout

        """

        start_time = self.drone.node.get_clock().now()
        timeout = Duration(seconds=timeout_sec) if timeout_sec is not None else None

        if lidar_target_alt is not None and self.drone.lidar_on == True:
            self.drone.node.get_logger().info("Using lidar for altitude control.")
            if lidar_target_alt > LIDAR_ALTITUDE_LIMIT:
                self.drone.node.get_logger().warn("Requested altitude exceeds 15m limit for lidar-based control, using altitude parameter instead.")
                lidar_target_alt = None
        elif lidar_target_alt is not None and self.drone.lidar_on == False:
            self.drone.node.get_logger().warn("Lidar altitude setpoint provided, but lidar is not enabled. Ignoring lidar altitude.")
            lidar_target_alt = None

        if self.drone.indoor == True:
            pid_x = PID(HORIZONTAL_INDOOR_KP, HORIZONTAL_INDOOR_KI, HORIZONTAL_INDOOR_KD, dt=0.01, max_output=HORIZONTAL_INDOOR_MAX_SPEED, min_output=HORIZONTAL_INDOOR_MIN_SPEED)
            pid_y = PID(HORIZONTAL_INDOOR_KP, HORIZONTAL_INDOOR_KI, HORIZONTAL_INDOOR_KD, dt=0.01, max_output=HORIZONTAL_INDOOR_MAX_SPEED, min_output=HORIZONTAL_INDOOR_MIN_SPEED)
            pid_z = PID(VERTICAL_INDOOR_KP, VERTICAL_INDOOR_KI, VERTICAL_INDOOR_KD, dt=0.01, max_output=VERTICAL_INDOOR_MAX_SPEED, min_output=VERTICAL_INDOOR_MIN_SPEED)

        else:
            pid_x = PID(HORIZONTAL_OUTDOOR_KP, HORIZONTAL_OUTDOOR_KI, HORIZONTAL_OUTDOOR_KD, dt=0.01, max_output=HORIZONTAL_OUTDOOR_MAX_SPEED, min_output=HORIZONTAL_OUTDOOR_MIN_SPEED)
            pid_y = PID(HORIZONTAL_OUTDOOR_KP, HORIZONTAL_OUTDOOR_KI, HORIZONTAL_OUTDOOR_KD, dt=0.01, max_output=HORIZONTAL_OUTDOOR_MAX_SPEED, min_output=HORIZONTAL_OUTDOOR_MIN_SPEED)
            pid_z = PID(VERTICAL_OUTDOOR_KP, VERTICAL_OUTDOOR_KI, VERTICAL_OUTDOOR_KD, dt=0.01, max_output=VERTICAL_OUTDOOR_MAX_SPEED, min_output=VERTICAL_OUTDOOR_MIN_SPEED)

        while True:
            current_pose: PoseStamped|NavSatFix = self.get_current_position(timeout=0.01)

            #Calculates distance to target in body frame
            if self.drone.indoor == True:
                dist_to_target, dx_body, dy_body, dz_body = self.get_body_distance_indoor(target_position, current_pose)
            else:
                dist_to_target, dx_body, dy_body, dz_body = self.get_body_distance_outdoor(target_position, current_pose)

            if lidar_target_alt is not None:
                self.drone.node.get_logger().info(f"lidar target: {lidar_target_alt} e {self.drone.get_rng_alt.range}")
                dz_body = lidar_target_alt - self.drone.get_rng_alt.range

            vx = pid_x.compute(abs(dx_body)) if dx_body > 0 else -pid_x.compute(abs(dx_body))
            vy = pid_y.compute(abs(dy_body)) if dy_body > 0 else -pid_y.compute(abs(dy_body))
            vz = pid_z.compute(abs(dz_body)) if dz_body > 0 else -pid_z.compute(abs(dz_body))

            if abs(dx_body) < precision_radius / 2:
                vx = 0.0
            if abs(dy_body) < precision_radius / 2:
                vy = 0.0
            if abs(dz_body) < precision_radius / 2:
                vz = 0.0

            self.drone.node.get_logger().info(f"   E: dx: {dx_body:.2f}, dy: {dy_body:.2f}, dz: {dz_body:.2f}")
            self.drone.node.get_logger().info(f"   V: vx: {vx:.2f}, vy: {vy:.2f}, vz: {vz:.2f}")

            # Compute PID outputs
            self.drone.offboard_velocity(
                linear_x=vx,
                linear_y=vy,
                linear_z=vz,
                angular_z=0.0,
                ground_reference=False
            )

            self.drone.node.get_logger().info(f"   Distance to target: {dist_to_target:.2f}m", throttle_duration_sec=1.0)

            #Checks if arrival is is complete
            if dist_to_target <= precision_radius:
                pid_x.reset()
                pid_y.reset()
                pid_z.reset()
                self.drone.offboard_velocity(0.0, 0.0, 0.0, 0.0, ground_reference=False)
                self.drone.node.get_logger().info(f"\033[32;1m   Target reached! Distance: {dist_to_target:.2f}m\033[0m")
                return

            #Checks for timeout
            if timeout_sec is not None and (self.drone.node.get_clock().now() - start_time) > timeout:
                self.drone.node.get_logger().warn(f"\033[33;1m   Timeout reached before arriving at target position. Distance: {dist_to_target:.2f}m\033[0m")
                return
