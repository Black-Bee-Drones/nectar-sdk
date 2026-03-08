from typing import Optional

import numpy as np
from geographic_msgs.msg import GeoPoseStamped
from geographiclib.geodesic import Geodesic
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import PositionTarget
from sensor_msgs.msg import NavSatFix
from tf_transformations import quaternion_from_euler

from nectar.control.mavros.gps_utils import GPSUtils
from nectar.control.types import MoveReference
from nectar.utils.gps_calculate import GPSCalculate
from nectar.utils.position_utils import PositionUtils

# Bitmask: position + yaw active
_POSITION_MASK = (
    PositionTarget.IGNORE_AFX
    | PositionTarget.IGNORE_AFY
    | PositionTarget.IGNORE_AFZ
    | PositionTarget.IGNORE_YAW_RATE
    | PositionTarget.IGNORE_VX
    | PositionTarget.IGNORE_VY
    | PositionTarget.IGNORE_VZ
)


class TargetComputer:
    """
    Stateless target computation for MAVROS navigation.
    """

    @staticmethod
    def compute_local_target(
        current_pos,
        current_yaw: float,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
        takeoff_pos: Optional[PositionTarget] = None,
    ) -> PositionTarget:
        """
        Compute target in local NED frame.

        Used for PID (indoor), PID_LOCAL (all), and SETPOINT (all) strategies.

        Parameters
        ----------
        current_pos : geometry_msgs.msg.Point
            Current position (x, y, z).
        current_yaw : float
            Current yaw in radians.
        x, y, z : float, optional
            Body-frame offsets in meters.
        yaw : float, optional
            Yaw offset in degrees.
        reference : MoveReference
            BODY or TAKEOFF.
        takeoff_pos : PositionTarget, optional
            Takeoff position. Required for TAKEOFF reference.

        Returns
        -------
        PositionTarget
        """
        if reference == MoveReference.TAKEOFF:
            pos = takeoff_pos.position
            ref_yaw = takeoff_pos.yaw
        else:
            pos = current_pos
            ref_yaw = current_yaw

        dx = (x or 0) * np.cos(ref_yaw) - (y or 0) * np.sin(ref_yaw)
        dy = (x or 0) * np.sin(ref_yaw) + (y or 0) * np.cos(ref_yaw)
        dz = z or 0

        msg = PositionTarget()
        msg.header.frame_id = "map"
        msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        msg.type_mask = _POSITION_MASK
        msg.position.x = float(pos.x + dx)
        msg.position.y = float(pos.y + dy)
        msg.position.z = float(pos.z + dz)
        msg.yaw = float(ref_yaw + np.radians(yaw) if yaw is not None else ref_yaw)
        return msg

    @staticmethod
    def compute_gps_target(
        current_gps: NavSatFix,
        current_heading: float,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
        takeoff_pos: Optional[GeoPoseStamped] = None,
    ) -> GeoPoseStamped:
        """
        Compute target in GPS frame for PID with raw GPS.

        Parameters
        ----------
        current_gps : NavSatFix
            Current GPS fix.
        current_heading : float
            Compass heading in degrees.
        x, y, z : float, optional
            Body-frame offsets in meters.
        yaw : float, optional
            Yaw offset in degrees.
        reference : MoveReference
            BODY or TAKEOFF.
        takeoff_pos : GeoPoseStamped, optional
            Takeoff GPS position. Required for TAKEOFF reference.

        Returns
        -------
        GeoPoseStamped
        """
        if reference == MoveReference.TAKEOFF:
            hdg = np.degrees(PositionUtils.get_yaw_from_pose(takeoff_pos))
            lat, lon, alt = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                z or 0,
                takeoff_pos.pose.position.latitude,
                takeoff_pos.pose.position.longitude,
                takeoff_pos.pose.position.altitude,
                hdg,
            )
        else:
            hdg = current_heading
            lat, lon, alt = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                z or 0,
                current_gps.latitude,
                current_gps.longitude,
                current_gps.altitude,
                hdg,
            )

        target_yaw = hdg + (yaw if yaw is not None else 0)
        quat = quaternion_from_euler(0, 0, np.radians(target_yaw))

        msg = GeoPoseStamped()
        msg.pose.position.latitude = float(lat)
        msg.pose.position.longitude = float(lon)
        msg.pose.position.altitude = float(alt)
        msg.pose.orientation.x = float(quat[0])
        msg.pose.orientation.y = float(quat[1])
        msg.pose.orientation.z = float(quat[2])
        msg.pose.orientation.w = float(quat[3])
        return msg

    @staticmethod
    def compute_gps_setpoint(
        current_gps: NavSatFix,
        current_heading: float,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
        takeoff_pos: Optional[GeoPoseStamped],
        current_rel_alt: float,
        initial_altitude: float,
    ) -> GeoPoseStamped:
        """
        Compute GPS setpoint with AMSL altitude correction.

        Uses GPSUtils.create_gps_setpoint for EGM96 geoid correction.

        Parameters
        ----------
        current_gps : NavSatFix
            Current GPS fix.
        current_heading : float
            Compass heading in degrees.
        x, y, z : float, optional
            Body-frame offsets in meters.
        yaw : float, optional
            Yaw offset in degrees.
        reference : MoveReference
            BODY or TAKEOFF.
        takeoff_pos : GeoPoseStamped, optional
            Takeoff GPS position. Required for TAKEOFF reference.
        current_rel_alt : float
            Current relative altitude in meters.
        initial_altitude : float
            GPS altitude at startup.

        Returns
        -------
        GeoPoseStamped
            GPS setpoint with AMSL-corrected altitude.
        """
        if reference == MoveReference.TAKEOFF:
            hdg = np.degrees(PositionUtils.get_yaw_from_pose(takeoff_pos))
            lat, lon, _ = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                0,
                takeoff_pos.pose.position.latitude,
                takeoff_pos.pose.position.longitude,
                takeoff_pos.pose.position.altitude,
                hdg,
            )
        else:
            hdg = current_heading
            lat, lon, _ = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                0,
                current_gps.latitude,
                current_gps.longitude,
                current_gps.altitude,
                hdg,
            )

        target_rel_alt = TargetComputer.compute_target_rel_alt(current_rel_alt, z, reference)
        target_hdg = hdg + (yaw if yaw is not None else 0)

        return GPSUtils.create_gps_setpoint(lat, lon, target_rel_alt, target_hdg, initial_altitude)

    @staticmethod
    def compute_target_rel_alt(
        current_rel_alt: float, z: Optional[float], reference: MoveReference
    ) -> float:
        """
        Compute target relative altitude for GPS navigation.

        Parameters
        ----------
        current_rel_alt : float
            Current relative altitude in meters.
        z : float, optional
            Altitude offset. None treated as 0.
        reference : MoveReference
            BODY: offset from current. TAKEOFF: absolute relative altitude.

        Returns
        -------
        float
        """
        if reference == MoveReference.TAKEOFF:
            return z or 0
        return current_rel_alt + (z or 0)

    @staticmethod
    def gps_to_local_target(
        target_lat: float,
        target_lon: float,
        target_rel_alt: float,
        current_gps: NavSatFix,
        current_local: PoseStamped,
        current_rel_alt: float,
        heading: float,
    ) -> PositionTarget:
        """
        Convert GPS coordinates to local target using current position mapping.

        Computes geodesic offset from current GPS to target GPS and applies it
        to the current local position. Used for move_to_gps with PID_LOCAL.

        Parameters
        ----------
        target_lat, target_lon : float
            Target GPS coordinates in degrees.
        target_rel_alt : float
            Target relative altitude in meters.
        current_gps : NavSatFix
            Current GPS fix.
        current_local : PoseStamped
            Current EKF local position.
        current_rel_alt : float
            Current relative altitude in meters.
        heading : float
            Current heading in degrees (for yaw).

        Returns
        -------
        PositionTarget
        """
        result = Geodesic.WGS84.Inverse(
            current_gps.latitude,
            current_gps.longitude,
            target_lat,
            target_lon,
        )
        dist = result["s12"]
        azimuth_rad = np.radians(result["azi1"])

        # Azimuth: 0=North, 90=East. Local frame follows MAVROS convention.
        dx = dist * np.sin(azimuth_rad)
        dy = dist * np.cos(azimuth_rad)
        dz = target_rel_alt - current_rel_alt

        msg = PositionTarget()
        msg.header.frame_id = "map"
        msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        msg.type_mask = _POSITION_MASK
        msg.position.x = float(current_local.pose.position.x + dx)
        msg.position.y = float(current_local.pose.position.y + dy)
        msg.position.z = float(current_local.pose.position.z + dz)
        msg.yaw = float(np.radians(90 - heading))
        return msg
