from typing import Tuple, Optional
from math import radians

from pygeodesy.geoids import GeoidPGM
from geopy.distance import geodesic
from tf_transformations import quaternion_from_euler
from geographic_msgs.msg import GeoPoseStamped


class GPSUtils:
    """
    GPS utilities for MAVROS navigation.
    """

    _egm96: Optional[GeoidPGM] = None

    @classmethod
    def _get_egm96(cls) -> GeoidPGM:
        """Lazy-load EGM96 geoid model."""
        if cls._egm96 is None:
            cls._egm96 = GeoidPGM(
                "/usr/share/GeographicLib/geoids/egm96-5.pgm", kind=-3
            )
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
    def create_gps_setpoint(
        cls,
        latitude: float,
        longitude: float,
        altitude_rel: float,
        heading: float,
        initial_altitude: float,
    ) -> GeoPoseStamped:
        """
        Create GPS setpoint with EGM96 altitude correction.

        Converts relative altitude to AMSL using initial GPS altitude and geoid height.

        Parameters
        ----------
        latitude : float
            Target latitude in degrees.
        longitude : float
            Target longitude in degrees.
        altitude_rel : float
            Target altitude above ground in meters.
        heading : float
            Target heading in degrees (0=North, clockwise).
        initial_altitude : float
            Initial GPS altitude for offset calculation.

        Returns
        -------
        GeoPoseStamped
            GPS setpoint message with AMSL altitude and quaternion orientation.
        """
        alt_adjust = cls.geoid_height(latitude, longitude)
        target_altitude = initial_altitude - alt_adjust + altitude_rel

        setpoint = GeoPoseStamped()
        setpoint.pose.position.latitude = latitude
        setpoint.pose.position.longitude = longitude
        setpoint.pose.position.altitude = target_altitude

        yaw = radians(90 - heading)
        qx, qy, qz, qw = quaternion_from_euler(0, 0, yaw)

        setpoint.pose.orientation.x = qx
        setpoint.pose.orientation.y = qy
        setpoint.pose.orientation.z = qz
        setpoint.pose.orientation.w = qw

        return setpoint

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
        Check if GPS waypoint reached.

        Uses geodesic distance for horizontal separation.

        Parameters
        ----------
        current_lat : float
            Current latitude in degrees.
        current_lon : float
            Current longitude in degrees.
        current_alt : float
            Current altitude in meters.
        target_lat : float
            Target latitude in degrees.
        target_lon : float
            Target longitude in degrees.
        target_alt : float
            Target altitude in meters.
        precision_radius : float, default=0.5
            Horizontal distance threshold in meters.
        alt_threshold : float, default=0.5
            Vertical distance threshold in meters.

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
