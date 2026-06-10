"""Geometry helpers for navigation.

These work on two families of inputs:

1. **Plain core types** (:mod:`nectar.control.ardupilot.types`) -
   ``LocalPose``/``GeoPoint`` for the current position and
   ``LocalTarget``/``GlobalTarget`` for the goal. The transport-agnostic
   vehicle core uses only these, so the math never depends on ROS.
2. **ROS messages** (``PoseStamped``/``NavSatFix``/``PositionTarget``/
   ``GeoPoseStamped``) - kept for back-compat and the MAVROS transport.

ROS message classes are imported lazily so that importing this module (and
therefore the core) does not pull ``mavros_msgs``/``geometry_msgs``.
"""

from typing import Optional

import numpy as np
from geographiclib.geodesic import Geodesic
from tf_transformations import euler_from_quaternion, quaternion_from_euler

from nectar.control.ardupilot.types import (
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
)


def _ros_msgs():
    """Lazily import the ROS message classes used by the back-compat paths."""
    from geographic_msgs.msg import GeoPoseStamped
    from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
    from mavros_msgs.msg import PositionTarget
    from sensor_msgs.msg import NavSatFix

    return PoseStamped, PoseWithCovarianceStamped, PositionTarget, GeoPoseStamped, NavSatFix


class PositionUtils:
    @staticmethod
    def _extract_pose(msg):
        """Extract geometry_msgs/Pose from stamped pose messages."""
        PoseStamped, PoseWithCovarianceStamped, _, _, _ = _ros_msgs()
        if isinstance(msg, PoseWithCovarianceStamped):
            return msg.pose.pose
        if isinstance(msg, PoseStamped):
            return msg.pose
        raise ValueError(f"Cannot extract pose from {type(msg).__name__}")

    @staticmethod
    def _body_distance_local(
        target_x: float,
        target_y: float,
        target_z: float,
        cur_x: float,
        cur_y: float,
        cur_z: float,
        yaw: float,
    ) -> tuple[float, float, float]:
        """Rotate a world-frame ENU delta into the body frame given ``yaw``."""
        dx_world = target_x - cur_x
        dy_world = target_y - cur_y
        dz = target_z - cur_z
        dx_body = np.cos(yaw) * dx_world + np.sin(yaw) * dy_world
        dy_body = -np.sin(yaw) * dx_world + np.cos(yaw) * dy_world
        return dx_body, dy_body, dz

    @staticmethod
    def _body_distance_global(
        t_lat: float,
        t_lon: float,
        t_alt: float,
        c_lat: float,
        c_lon: float,
        c_alt: float,
        heading: float,
    ) -> tuple[float, float, float]:
        """Geodesic body-frame delta from current GPS to target GPS."""
        result = Geodesic.WGS84.Inverse(c_lat, c_lon, t_lat, t_lon)
        dist = result["s12"]
        bearing_to_target = result["azi1"]
        relative_angle_rad = np.radians(bearing_to_target - heading)
        dx_body = dist * np.cos(relative_angle_rad)
        dy_body = -dist * np.sin(relative_angle_rad)
        dz_body = t_alt - c_alt
        return dx_body, dy_body, dz_body

    @staticmethod
    def get_body_distance(
        target,
        current,
        heading: float | None = None,
    ) -> tuple[float, float, float]:
        """
        Calculate the distance from current position to target in body frame.

        Body frame: x=forward, y=left, z=up.

        Parameters
        ----------
        target : LocalTarget | GlobalTarget | PositionTarget | GeoPoseStamped
            Target position.
        current : LocalPose | GeoPoint | PoseStamped | PoseWithCovarianceStamped | NavSatFix
            Current position.
        heading : float, optional
            Compass heading in degrees. Required for GPS coordinates.

        Returns
        -------
        tuple[float, float, float]
            (dx_body, dy_body, dz_body) in meters.
        """
        # --- Plain core types (no ROS) ---
        if isinstance(target, LocalTarget) and isinstance(current, LocalPose):
            return PositionUtils._body_distance_local(
                target.position.x,
                target.position.y,
                target.position.z,
                current.position.x,
                current.position.y,
                current.position.z,
                current.yaw,
            )

        if (
            isinstance(target, GlobalTarget)
            and isinstance(current, GeoPoint)
            and heading is not None
        ):
            return PositionUtils._body_distance_global(
                target.latitude,
                target.longitude,
                target.altitude,
                current.latitude,
                current.longitude,
                current.altitude,
                heading,
            )

        # --- ROS message types (back-compat / MAVROS) ---
        PoseStamped, PoseWithCovarianceStamped, PositionTarget, GeoPoseStamped, NavSatFix = (
            _ros_msgs()
        )

        if isinstance(target, PositionTarget) and isinstance(
            current, (PoseStamped, PoseWithCovarianceStamped)
        ):
            pose = PositionUtils._extract_pose(current)
            yaw = PositionUtils.get_yaw_from_pose(current)
            return PositionUtils._body_distance_local(
                target.position.x,
                target.position.y,
                target.position.z,
                pose.position.x,
                pose.position.y,
                pose.position.z,
                yaw,
            )

        if (
            isinstance(target, GeoPoseStamped)
            and isinstance(current, NavSatFix)
            and heading is not None
        ):
            return PositionUtils._body_distance_global(
                target.pose.position.latitude,
                target.pose.position.longitude,
                target.pose.position.altitude,
                current.latitude,
                current.longitude,
                current.altitude,
                heading,
            )

        raise ValueError("Invalid combination of target and current position types.")

    @staticmethod
    def get_yaw_from_pose(pose) -> float:
        """
        Extract yaw angle from a pose/target.

        Parameters
        ----------
        pose : LocalPose | LocalTarget | GlobalTarget | PoseStamped \
            | PoseWithCovarianceStamped | GeoPoseStamped | PositionTarget
            Pose containing orientation/yaw.

        Returns
        -------
        float
            Yaw in radians (-π to π for quaternion sources).
        """
        # --- Plain core types (no ROS) ---
        if isinstance(pose, (LocalPose, LocalTarget)):
            return pose.yaw
        if isinstance(pose, GlobalTarget):
            return pose.yaw if pose.yaw is not None else 0.0

        # --- ROS message types ---
        _, _, PositionTarget, GeoPoseStamped, _ = _ros_msgs()
        if isinstance(pose, PositionTarget):
            return pose.yaw

        if isinstance(pose, GeoPoseStamped):
            orientation_q = pose.pose.orientation
        else:
            p = PositionUtils._extract_pose(pose)
            orientation_q = p.orientation

        orientation_list = [
            orientation_q.x,
            orientation_q.y,
            orientation_q.z,
            orientation_q.w,
        ]
        (_, _, yaw) = euler_from_quaternion(orientation_list)
        return yaw

    @staticmethod
    def compute_yaw_error(target_yaw: float, current_yaw: float, threshold: float = 0.0) -> float:
        """
        Compute shortest-path yaw error.

        Parameters
        ----------
        target_yaw : float
            Target yaw in radians.
        current_yaw : float
            Current yaw in radians.
        threshold : float, default=0.0
            Deadband in radians. Errors smaller than this return 0.0.

        Returns
        -------
        float
            Yaw error in radians, wrapped to [-pi, pi].
        """
        dyaw = target_yaw - current_yaw
        dyaw = (dyaw + np.pi) % (2 * np.pi) - np.pi
        if threshold > 0.0 and abs(dyaw) < threshold:
            return 0.0
        return dyaw

    @staticmethod
    def convert_position_to_target(
        pose,
        heading: Optional[float] = None,
        lidar: Optional[float] = None,
    ):
        """
        Convert ROS position messages to their corresponding target types.

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
        PoseStamped, PoseWithCovarianceStamped, PositionTarget, GeoPoseStamped, NavSatFix = (
            _ros_msgs()
        )

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
            # Convert NED heading (0=North, CW) to ENU yaw (0=East, CCW)
            quaternion = quaternion_from_euler(0, 0, np.radians(90.0 - heading))
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
