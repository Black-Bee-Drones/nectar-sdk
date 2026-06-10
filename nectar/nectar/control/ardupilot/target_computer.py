"""Stateless target computation for ArduPilot navigation."""

from typing import Optional

import numpy as np
from geographiclib.geodesic import Geodesic

from nectar.control.ardupilot.gps_utils import GPSUtils
from nectar.control.ardupilot.types import (
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    TargetFrame,
    Vec3,
)
from nectar.control.types import MoveReference
from nectar.utils.gps_calculate import GPSCalculate


class TargetComputer:
    """Stateless target computation for ArduPilot navigation."""

    @staticmethod
    def compute_local_target(
        current_pos: Vec3,
        current_yaw: float,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
        takeoff_pos: Optional[LocalTarget] = None,
    ) -> LocalTarget:
        """
        Compute a target in the local ENU frame.

        Used for PID (indoor), PID_EKF (all), and POSITION (all) strategies.

        Parameters
        ----------
        current_pos : Vec3
            Current position (ENU meters).
        current_yaw : float
            Current yaw in radians (ENU).
        x, y, z : float, optional
            Body-frame offsets in meters.
        yaw : float, optional
            Yaw offset in degrees.
        reference : MoveReference
            BODY or TAKEOFF.
        takeoff_pos : LocalTarget, optional
            Takeoff position. Required for TAKEOFF reference.

        Returns
        -------
        LocalTarget
        """
        if reference == MoveReference.TAKEOFF:
            pos = takeoff_pos.position
            ref_yaw = takeoff_pos.yaw
            # For None axes, preserve current position in takeoff body frame
            cos_r, sin_r = np.cos(ref_yaw), np.sin(ref_yaw)
            dxw = current_pos.x - pos.x
            dyw = current_pos.y - pos.y
            x_off = x if x is not None else (cos_r * dxw + sin_r * dyw)
            y_off = y if y is not None else (-sin_r * dxw + cos_r * dyw)
        else:
            pos = current_pos
            ref_yaw = current_yaw
            x_off = x or 0
            y_off = y or 0

        dx = x_off * np.cos(ref_yaw) - y_off * np.sin(ref_yaw)
        dy = x_off * np.sin(ref_yaw) + y_off * np.cos(ref_yaw)

        return LocalTarget(
            position=Vec3(
                x=float(pos.x + dx),
                y=float(pos.y + dy),
                z=float(pos.z + z if z is not None else current_pos.z),
            ),
            yaw=float(ref_yaw + np.radians(yaw) if yaw is not None else ref_yaw),
            frame=TargetFrame.LOCAL,
        )

    @staticmethod
    def compute_gps_target(
        current_gps: GeoPoint,
        current_heading: float,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
        takeoff_pos: Optional[GlobalTarget] = None,
    ) -> GlobalTarget:
        """
        Compute a target in the GPS frame for PID with raw GPS.

        Parameters
        ----------
        current_gps : GeoPoint
            Current GPS fix.
        current_heading : float
            Compass heading in degrees.
        x, y, z : float, optional
            Body-frame offsets in meters.
        yaw : float, optional
            Yaw offset in degrees.
        reference : MoveReference
            BODY or TAKEOFF.
        takeoff_pos : GlobalTarget, optional
            Takeoff GPS position. Required for TAKEOFF reference.

        Returns
        -------
        GlobalTarget
        """
        if reference == MoveReference.TAKEOFF:
            # Takeoff yaw stores ENU radians; convert back to NED heading
            hdg = 90.0 - np.degrees(takeoff_pos.yaw if takeoff_pos.yaw is not None else 0.0)
            ref_lat = takeoff_pos.latitude
            ref_lon = takeoff_pos.longitude
            ref_alt = takeoff_pos.altitude

            # For None axes, preserve current position in takeoff body frame
            if x is None or y is None:
                result = Geodesic.WGS84.Inverse(
                    ref_lat,
                    ref_lon,
                    current_gps.latitude,
                    current_gps.longitude,
                )
                dist = result["s12"]
                rel = np.radians(result["azi1"] - hdg)
                x_off = x if x is not None else dist * np.cos(rel)
                y_off = y if y is not None else -dist * np.sin(rel)
            else:
                x_off, y_off = x, y

            lat, lon, alt = GPSCalculate.calculate_gps_offset(
                x_off,
                -y_off,
                z or 0,
                ref_lat,
                ref_lon,
                ref_alt,
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

        target_heading = hdg - (yaw if yaw is not None else 0)

        return GlobalTarget(
            latitude=float(lat),
            longitude=float(lon),
            altitude=float(alt),
            yaw=float(np.radians(90.0 - target_heading)),
        )

    @staticmethod
    def compute_gps_setpoint(
        current_gps: GeoPoint,
        current_heading: float,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
        takeoff_pos: Optional[GlobalTarget],
        current_rel_alt: float,
        initial_altitude: float,
    ) -> GlobalTarget:
        """
        Compute a GPS setpoint with AMSL altitude correction.

        Uses :meth:`GPSUtils.create_global_target` for EGM96 geoid correction.

        Returns
        -------
        GlobalTarget
            With AMSL-corrected altitude.
        """
        if reference == MoveReference.TAKEOFF:
            hdg = 90.0 - np.degrees(takeoff_pos.yaw if takeoff_pos.yaw is not None else 0.0)
            ref_lat = takeoff_pos.latitude
            ref_lon = takeoff_pos.longitude
            ref_alt = takeoff_pos.altitude

            if x is None or y is None:
                result = Geodesic.WGS84.Inverse(
                    ref_lat,
                    ref_lon,
                    current_gps.latitude,
                    current_gps.longitude,
                )
                dist = result["s12"]
                rel = np.radians(result["azi1"] - hdg)
                x_off = x if x is not None else dist * np.cos(rel)
                y_off = y if y is not None else -dist * np.sin(rel)
            else:
                x_off, y_off = x, y

            lat, lon, _ = GPSCalculate.calculate_gps_offset(
                x_off,
                -y_off,
                0,
                ref_lat,
                ref_lon,
                ref_alt,
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
        target_hdg = hdg - (yaw if yaw is not None else 0)

        return GPSUtils.create_global_target(lat, lon, target_rel_alt, target_hdg, initial_altitude)

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
            Altitude offset. None = hold current altitude.
        reference : MoveReference
            BODY: offset from current. TAKEOFF: absolute relative altitude.

        Returns
        -------
        float
        """
        if z is None:
            return current_rel_alt
        if reference == MoveReference.TAKEOFF:
            return z
        return current_rel_alt + z

    @staticmethod
    def gps_to_local_target(
        target_lat: float,
        target_lon: float,
        target_rel_alt: float,
        current_gps: GeoPoint,
        current_local: LocalPose,
        current_rel_alt: float,
        heading: float,
    ) -> LocalTarget:
        """
        Convert GPS coordinates to a local target using current position mapping.

        Computes the geodesic offset from current GPS to target GPS and applies
        it to the current EKF local position. Used for move_to_gps with PID_EKF.

        Returns
        -------
        LocalTarget
        """
        result = Geodesic.WGS84.Inverse(
            current_gps.latitude,
            current_gps.longitude,
            target_lat,
            target_lon,
        )
        dist = result["s12"]
        azimuth_rad = np.radians(result["azi1"])

        # Azimuth: 0=North, 90=East. Local frame follows MAVROS ENU convention.
        dx = dist * np.sin(azimuth_rad)
        dy = dist * np.cos(azimuth_rad)
        dz = target_rel_alt - current_rel_alt

        return LocalTarget(
            position=Vec3(
                x=float(current_local.position.x + dx),
                y=float(current_local.position.y + dy),
                z=float(current_local.position.z + dz),
            ),
            yaw=float(np.radians(90 - heading)),
            frame=TargetFrame.LOCAL,
        )
