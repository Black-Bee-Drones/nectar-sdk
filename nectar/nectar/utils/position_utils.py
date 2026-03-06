import numpy as np
from geographic_msgs.msg import GeoPoseStamped
from geographiclib.geodesic import Geodesic
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from mavros_msgs.msg import PositionTarget
from sensor_msgs.msg import NavSatFix
from tf_transformations import euler_from_quaternion, quaternion_from_euler


class PositionUtils:
    @staticmethod
    def _extract_pose(msg):
        """Extract geometry_msgs/Pose from stamped pose messages."""
        if isinstance(msg, PoseWithCovarianceStamped):
            return msg.pose.pose
        if isinstance(msg, PoseStamped):
            return msg.pose
        raise ValueError(f"Cannot extract pose from {type(msg).__name__}")

    @staticmethod
    def get_body_distance(
        target: PositionTarget | GeoPoseStamped,
        current: PoseStamped | PoseWithCovarianceStamped | NavSatFix,
        heading: float | None = None,
    ) -> tuple[float, float, float]:
        """
        Calculate the distance from current position to target in body frame.

        Body frame: x=forward, y=left, z=up.

        Parameters
        ----------
        target : PositionTarget | GeoPoseStamped
            Target position.
        current : PoseStamped | PoseWithCovarianceStamped | NavSatFix
            Current position.
        heading : float, optional
            Compass heading in degrees. Required for GPS coordinates.

        Returns
        -------
        tuple[float, float, float]
            (dx_body, dy_body, dz_body) in meters.
        """
        if isinstance(target, PositionTarget) and isinstance(
            current, (PoseStamped, PoseWithCovarianceStamped)
        ):
            pose = PositionUtils._extract_pose(current)
            cx, cy, cz = pose.position.x, pose.position.y, pose.position.z
            tx, ty, tz = target.position.x, target.position.y, target.position.z

            dx_world = tx - cx
            dy_world = ty - cy
            dz = tz - cz

            yaw = PositionUtils.get_yaw_from_pose(current)
            dx_body = np.cos(yaw) * dx_world + np.sin(yaw) * dy_world
            dy_body = -np.sin(yaw) * dx_world + np.cos(yaw) * dy_world

            return dx_body, dy_body, dz

        if (
            isinstance(target, GeoPoseStamped)
            and isinstance(current, NavSatFix)
            and heading is not None
        ):
            c_lat, c_lon, c_alt = current.latitude, current.longitude, current.altitude
            t_lat = target.pose.position.latitude
            t_lon = target.pose.position.longitude
            t_alt = target.pose.position.altitude

            # Geodesic: distance and forward azimuth
            result = Geodesic.WGS84.Inverse(c_lat, c_lon, t_lat, t_lon)
            dist = result["s12"]
            bearing_to_target = result["azi1"]

            relative_angle_rad = np.radians(bearing_to_target - heading)
            dx_body = dist * np.cos(relative_angle_rad)
            dy_body = -dist * np.sin(relative_angle_rad)
            dz_body = t_alt - c_alt

            return dx_body, dy_body, dz_body

        raise ValueError("Invalid combination of target and current position types.")

    @staticmethod
    def get_yaw_from_pose(
        pose: PoseStamped | PoseWithCovarianceStamped | GeoPoseStamped | PositionTarget,
    ) -> float:
        """
        Extract yaw angle from a pose message.

        Parameters
        ----------
        pose : PoseStamped | PoseWithCovarianceStamped | GeoPoseStamped | PositionTarget
            Pose message containing orientation.

        Returns
        -------
        float
            Yaw in radians (-π to π).
        """
        if isinstance(pose, PositionTarget):
            return pose.yaw

        if isinstance(pose, GeoPoseStamped):
            orientation_q = pose.pose.orientation
        elif isinstance(pose, (PoseStamped, PoseWithCovarianceStamped)):
            p = PositionUtils._extract_pose(pose)
            orientation_q = p.orientation
        else:
            raise ValueError(f"Unsupported pose type: {type(pose).__name__}")

        orientation_list = [
            orientation_q.x,
            orientation_q.y,
            orientation_q.z,
            orientation_q.w,
        ]
        (_, _, yaw) = euler_from_quaternion(orientation_list)
        return yaw

    @staticmethod
    def convert_position_to_target(
        pose: PoseStamped | PoseWithCovarianceStamped | NavSatFix,
        heading: float = None,
        lidar: float = None,
    ) -> PositionTarget | GeoPoseStamped:
        """
        Convert position messages to their corresponding target types.

        - PoseStamped / PoseWithCovarianceStamped → PositionTarget
        - NavSatFix → GeoPoseStamped (requires heading)

        Parameters
        ----------
        pose : PoseStamped | PoseWithCovarianceStamped | NavSatFix
            Input position.
        heading : float, optional
            Heading in degrees. Required for NavSatFix conversion.
        lidar : float, optional
            Lidar altitude to override z position.

        Returns
        -------
        PositionTarget | GeoPoseStamped
        """
        if isinstance(pose, (PoseStamped, PoseWithCovarianceStamped)):
            p = PositionUtils._extract_pose(pose)
            msg = PositionTarget()
            msg.position.x = p.position.x
            msg.position.y = p.position.y
            msg.position.z = p.position.z if lidar is None else lidar
            msg.yaw = PositionUtils.get_yaw_from_pose(pose)
            return msg

        if isinstance(pose, NavSatFix) and heading is not None:
            msg = GeoPoseStamped()
            msg.pose.position.latitude = pose.latitude
            msg.pose.position.longitude = pose.longitude
            msg.pose.position.altitude = pose.altitude
            quaternion = quaternion_from_euler(0, 0, np.radians(heading))
            msg.pose.orientation.x = quaternion[0]
            msg.pose.orientation.y = quaternion[1]
            msg.pose.orientation.z = quaternion[2]
            msg.pose.orientation.w = quaternion[3]
            return msg

        raise ValueError(
            "pose must be PoseStamped, PoseWithCovarianceStamped, or NavSatFix (with heading)"
        )

    @staticmethod
    def transform_takeoff_to_body_velocities(
        vx: float, vy: float, vz: float, current_yaw: float, takeoff_yaw: float
    ) -> tuple[float, float, float]:
        """
        Transform velocities from takeoff frame to body frame.

        Parameters
        ----------
        vx, vy, vz : float
            Velocities in takeoff frame (m/s).
        current_yaw : float
            Current yaw in radians.
        takeoff_yaw : float
            Takeoff yaw in radians.

        Returns
        -------
        tuple[float, float, float]
            Body frame velocities (vx_body, vy_body, vz_body).
        """
        relative_yaw = takeoff_yaw - current_yaw
        cos_yaw = np.cos(relative_yaw)
        sin_yaw = np.sin(relative_yaw)

        # Apply 2D rotation matrix transformation
        vx_body = cos_yaw * vx + sin_yaw * vy
        vy_body = -sin_yaw * vx + cos_yaw * vy

        return vx_body, vy_body, vz
