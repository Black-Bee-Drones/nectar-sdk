"""GPS helpers for the vehicle core"""

from math import cos, radians
from typing import Optional, Tuple

from geopy.distance import geodesic
from pygeodesy.geoids import GeoidPGM

from nectar.control.vehicle.types import GlobalTarget

_EARTH_RADIUS_M = 6371000.0


class GPSUtils:
    """GPS utilities for vehicle navigation."""

    _egm96: Optional[GeoidPGM] = None

    @classmethod
    def _get_egm96(cls) -> GeoidPGM:
        """Lazy-load EGM96 geoid model."""
        if cls._egm96 is None:
            cls._egm96 = GeoidPGM("/usr/share/GeographicLib/geoids/egm96-5.pgm", kind=3)
        return cls._egm96

    @classmethod
    def geoid_height(cls, latitude: float, longitude: float) -> float:
        """
        Calculate geoid height for AMSL-to-ellipsoid conversion.

        Uses EGM96 geoid model with 5' grid and cubic interpolation.

        Parameters
        ----------
        latitude : float
            Latitude in degrees.
        longitude : float
            Longitude in degrees.

        Returns
        -------
        float
            Geoid height in meters. Subtract from ellipsoid height to get AMSL.
        """
        return cls._get_egm96().height(latitude, longitude)

    @classmethod
    def create_global_target(
        cls,
        latitude: float,
        longitude: float,
        altitude_rel: float,
        heading: float,
        initial_altitude: float,
    ) -> GlobalTarget:
        """
        Create a global setpoint with EGM96 altitude correction.

        Converts relative altitude to AMSL using the initial GPS altitude and
        geoid height. Yaw is stored in ENU radians (matching the local-frame
        convention), converted from the NED ``heading``.

        Parameters
        ----------
        latitude, longitude : float
            Target coordinates in degrees.
        altitude_rel : float
            Target altitude above ground in meters.
        heading : float
            Target heading in degrees (0 = North, clockwise).
        initial_altitude : float
            Initial GPS altitude for the AMSL offset.

        Returns
        -------
        GlobalTarget
            With AMSL ``altitude`` and ENU ``yaw``.
        """
        alt_adjust = cls.geoid_height(latitude, longitude)
        target_altitude = initial_altitude - alt_adjust + altitude_rel

        return GlobalTarget(
            latitude=float(latitude),
            longitude=float(longitude),
            altitude=float(target_altitude),
            yaw=radians(90.0 - heading),
        )

    @classmethod
    def check_reached(
        cls,
        current_lat: float,
        current_lon: float,
        current_alt: float,
        target_lat: float,
        target_lon: float,
        target_alt: float,
        precision_radius: float = 0.5,
        alt_threshold: float = 0.5,
    ) -> Tuple[bool, float, float]:
        """
        Check if a GPS waypoint has been reached (geodesic horizontal distance).

        Returns
        -------
        tuple of (bool, float, float)
            (reached, horizontal_distance, altitude_difference)
        """
        distance = geodesic(
            (current_lat, current_lon),
            (target_lat, target_lon),
        ).meters

        alt_diff = abs(current_alt - target_alt)
        reached = distance <= precision_radius and alt_diff <= alt_threshold

        return reached, distance, alt_diff

    @staticmethod
    def local_offset(
        current_lat: float,
        current_lon: float,
        target_lat: float,
        target_lon: float,
    ) -> Tuple[float, float]:
        """
        East/north offset in meters from current to target position.

        Equirectangular approximation for display and per-axis error reporting;
        arrival checks use the geodesic distance from :meth:`check_reached`.

        Returns
        -------
        tuple of (float, float)
            (east, north) offset in meters.
        """
        east = radians(target_lon - current_lon) * _EARTH_RADIUS_M * cos(radians(current_lat))
        north = radians(target_lat - current_lat) * _EARTH_RADIUS_M
        return east, north
