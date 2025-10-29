import numpy as np
from tf_transformations import euler_from_quaternion, quaternion_from_euler
from mavros_msgs.msg import PositionTarget
from geometry_msgs.msg import PoseWithCovarianceStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix
from mirela_sdk.utils.gps_calculate import GPSCalculate

class PositionUtils:
    @staticmethod
    def get_body_distance(target: PositionTarget|GeoPoseStamped, current: PoseWithCovarianceStamped|NavSatFix, heading: float|None=None) -> tuple[float, float, float]:
        """
        Calculate the distance from current position to target position in body frame coordinates.

        The body frame is relative to the drone's orientation:
        - x-axis: forward/backward (positive = forward)
        - y-axis: left/right (positive = left)
        - z-axis: up/down (positive = up)

        Parameters
        ----------
        target : PositionTarget | GeoPoseStamped
            Target position to calculate distance to.
            - PositionTarget: for indoor/local coordinates
            - GeoPoseStamped: for outdoor/GPS coordinates
        
        current : PoseWithCovarianceStamped | NavSatFix
            Current position of the drone.
            - PoseWithCovarianceStamped: for indoor/local coordinates
            - NavSatFix: for outdoor/GPS coordinates
        
        heading : float, optional
            Current heading in degrees (0 = North, positive clockwise).
            Required when using GPS coordinates (GeoPoseStamped + NavSatFix).
            Ignored for indoor coordinates as heading is extracted from pose.

        Returns
        -------
        tuple[float, float, float]
            Distance in body frame coordinates (dx_body, dy_body, dz_body) in meters.

        Raises
        ------
        ValueError
            If invalid combination of target and current position types is provided.
        """
        if isinstance(target, PositionTarget) and isinstance(current, PoseWithCovarianceStamped):
            cx, cy, cz = current.pose.pose.position.x, current.pose.pose.position.y, current.pose.pose.position.z
            tx, ty, tz = target.position.x, target.position.y, target.position.z

            # Calculate difference in world frame
            dx_world = tx - cx
            dy_world = ty - cy
            dz = tz - cz

            # Get current yaw
            yaw = PositionUtils.get_yaw_from_pose(current)

            # Transform difference to body frame
            dx_body =  np.cos(yaw) * dx_world + np.sin(yaw) * dy_world
            dy_body = -np.sin(yaw) * dx_world + np.cos(yaw) * dy_world
            dz_body =  dz  # No change in z axis

            return dx_body, dy_body, dz_body
        
        elif isinstance(target, GeoPoseStamped) and isinstance(current, NavSatFix) and heading is not None:
            c_lat, c_lon, c_alt = current.latitude, current.longitude, current.altitude
            t_lat, t_lon, t_alt = target.pose.position.latitude, target.pose.position.longitude, target.pose.position.altitude
            
            # Calculate bearing from current position to target position (in degrees, 0 = North, positive clockwise)
            bearing_to_target = GPSCalculate.bearing(c_lat, c_lon, t_lat, t_lon)
            
            # Calculate distance using Haversine formula
            dist = GPSCalculate.haversine(c_lat, c_lon, t_lat, t_lon)
            
            # Convert from world frame (North-East) to body frame
            # The angle we need is: "where is the target relative to where I'm pointing?"
            relative_angle = bearing_to_target - heading
            
            # Convert to radians for trigonometry
            relative_angle_rad = np.radians(relative_angle)
            
            # In body frame: x = forward, y = right
            dx_body = dist * np.cos(relative_angle_rad)  # Forward distance
            dy_body = -dist * np.sin(relative_angle_rad)  # Left distance  
            dz_body = t_alt - c_alt                     # Altitude difference
            
            return dx_body, dy_body, dz_body

        else:
            raise ValueError("Invalid combination of target and current position types.")

    @staticmethod
    def get_yaw_from_pose(pose: PoseWithCovarianceStamped|GeoPoseStamped|PositionTarget) -> float:
        """
        Extract yaw angle (rotation around z-axis) from a pose message.

        Parameters
        ----------
        pose : PoseWithCovarianceStamped | GeoPoseStamped | PositionTarget
            Pose message containing orientation quaternion.

        Returns
        -------
        float
            Yaw angle in radians (-π to π).
        """
        if isinstance(pose, PoseWithCovarianceStamped):
            orientation_q = pose.pose.pose.orientation
        elif isinstance(pose, GeoPoseStamped):
            orientation_q = pose.pose.orientation
        elif isinstance(pose, PositionTarget):
            return pose.yaw
        else:
            raise ValueError("pose parameter must be of type PoseWithCovarianceStamped | GeoPoseStamped | PositionTarget")
        orientation_list = [orientation_q.x, orientation_q.y, orientation_q.z, orientation_q.w]
        (_, _, yaw) = euler_from_quaternion(orientation_list)
        return yaw

    @staticmethod
    def convert_position_to_target(pose: PoseWithCovarianceStamped|NavSatFix, heading: float = None, lidar: float = None) -> PositionTarget|GeoPoseStamped:
        """
        Convert position messages to their corresponding target message types.

        Converts between different ROS message types while preserving position information:
        - PoseWithCovarianceStamped → PositionTarget (for indoor/local coordinates)
        - NavSatFix → GeoPoseStamped (for outdoor/GPS coordinates)

        Parameters
        ----------
        pose : PoseWithCovarianceStamped | NavSatFix
            Input position message to convert.

        heading : float, optional
            Current heading in degrees (0 = North, positive clockwise).
            Required when converting NavSatFix to GeoPoseStamped to set orientation.
            Ignored when converting PoseWithCovarianceStamped to PositionTarget.
        lidar : float, optional
            Optional altitude value from lidar sensor to override z position in PositionTarget.
            If provided, it replaces the z value from PoseWithCovarianceStamped.

        Returns
        -------
        PositionTarget | GeoPoseStamped
            Converted target message:
            - PositionTarget: if input was PoseWithCovarianceStamped
            - GeoPoseStamped: if input was NavSatFix

        Raises
        ------
        ValueError
            If pose parameter is not of supported type.
        """
        if isinstance(pose, PoseWithCovarianceStamped):
            msg = PositionTarget()
            msg.position.x = pose.pose.pose.position.x
            msg.position.y = pose.pose.pose.position.y
            msg.position.z = pose.pose.pose.position.z if lidar is None else lidar
            # Convert orientation from quaternion to yaw and set it
            yaw = PositionUtils.get_yaw_from_pose(pose)
            msg.yaw = yaw
            return msg
            
        elif isinstance(pose, NavSatFix) and heading is not None:
            msg = GeoPoseStamped()
            msg.pose.position.latitude = pose.latitude
            msg.pose.position.longitude = pose.longitude
            msg.pose.position.altitude = pose.altitude
            # Convert heading (degrees) to quaternion
            quaternion = quaternion_from_euler(0, 0, np.radians(heading))
            msg.pose.orientation.x = quaternion[0]
            msg.pose.orientation.y = quaternion[1]
            msg.pose.orientation.z = quaternion[2]
            msg.pose.orientation.w = quaternion[3]
            return msg
        
        else:
            raise ValueError("pose parameter must be of type PoseWithCovarianceStamped or NavSatFix")