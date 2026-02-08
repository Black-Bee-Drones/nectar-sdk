from typing import Tuple
from geographiclib.geodesic import Geodesic
import numpy as np


class GPSCalculate:
    @staticmethod
    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great-circle distance between two GPS coordinates using the Haversine formula.

        Assumes the Earth is a perfect sphere.

        Parameters
        ----------
        lat1 : float
            Latitude of the first point in degrees.
        lon1 : float
            Longitude of the first point in degrees.
        lat2 : float
            Latitude of the second point in degrees.
        lon2 : float
            Longitude of the second point in degrees.

        Returns
        -------
        float
            Distance between the two points in meters.
        """

        # Convert degrees to radians
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

        # Compute differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        # Haversine formula
        a = np.sin(dlat / 2) ** 2 + np.cos(lat2) * np.cos(lat1) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        return c * 6371000  # Earth's radius in meters

    @staticmethod
    def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the initial bearing (forward azimuth) between two GPS coordinates.

        The result is the angle in degrees between north and the direction
        from the first point to the second.

        Parameters
        ----------
        lat1 : float
            Latitude of the starting point in degrees.
        lon1 : float
            Longitude of the starting point in degrees.
        lat2 : float
            Latitude of the destination point in degrees.
        lon2 : float
            Longitude of the destination point in degrees.

        Returns
        -------
        float
            Initial bearing in degrees (0° to 360°).
        """

        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

        dlon = lon2 - lon1

        x = np.sin(dlon) * np.cos(lat2)
        y = np.cos(lat1) * np.sin(lat2) - (np.sin(lat1) * np.cos(lat2) * np.cos(dlon))
        bearing = np.arctan2(x, y)

        bearing = np.degrees(bearing)

        bearing = (bearing + 360) % 360

        return bearing

    @staticmethod
    def calculate_gps_offset(
        x: float,
        y: float,
        z: float,
        latitude: float,
        longitude: float,
        altitude: float,
        heading: float,
    ) -> Tuple[float, float, float]:
        """
        Calculate new GPS coordinates given an initial GPS point and offsets in meters.

        Parameters
        ----------
        x : float
            Offset in meters along the East-West axis (positive eastward).
        y : float
            Offset in meters along the North-South axis (positive northward).
        z : float
            Offset in meters along the vertical axis (positive upward).
        latitude : float
            Initial latitude in degrees.
        longitude : float
            Initial longitude in degrees.
        altitude : float
            Initial altitude in meters.
        heading : float
            Initial heading in degrees.

        Returns
        -------
        tuple of (float, float, float)
            New latitude, longitude, and altitude.
        """
        geod = Geodesic.WGS84
        # Calculate the distance and bearing from the offsets
        horizontal_distance = np.sqrt(x**2 + y**2)
        bearing = (heading + np.degrees(np.arctan2(y, x))) % 360

        # Compute the new GPS coordinates using the geodesic direct method
        g = geod.Direct(latitude, longitude, bearing, horizontal_distance)

        new_latitude = g["lat2"]
        new_longitude = g["lon2"]
        new_altitude = altitude + z  # Adjust altitude by vertical offset

        return new_latitude, new_longitude, new_altitude

    @staticmethod
    def interp_geo(
        start: Tuple[float, float], end: Tuple[float, float], frac: float
    ) -> Tuple[float, float]:
        """
        Compute geodesic interpolation between two GPS coordinates.

        Parameters
        ----------
        start : tuple of (float, float)
            Starting GPS coordinate (lat, lon).
        end : tuple of (float, float)
            Ending GPS coordinate (lat, lon).
        frac : float
            Interpolation factor between 0.0 and 1.0.

        Returns
        -------
        tuple of (float, float)
            Interpolated GPS coordinate (lat, lon).
        """
        line = Geodesic.WGS84.InverseLine(start[0], start[1], end[0], end[1])
        position = line.Position(line.s13 * frac)
        return (position["lat2"], position["lon2"])

    @staticmethod
    def generate_point_grid(
        vertices: Tuple[Tuple[float, float]], grid_shape: tuple[int, int]
    ) -> list[list[Tuple[float, float]]]:
        """
        Generate a 2D grid of geodesic-interpolated GPS coordinates within a quadrilateral area.

        Creates a grid of points filling the area defined by 4 GPS vertices, ordered as:

        - vertices[0]: top-left
        - vertices[1]: top-right
        - vertices[2]: bottom-right
        - vertices[3]: bottom-left

        Parameters
        ----------
        vertices : tuple of tuple of (float, float)
            Four (lat, lon) tuples defining the corners of the area.
        grid_shape : tuple of (int, int)
            Number of points as (cols, rows).

        Returns
        -------
        list of list of tuple of (float, float)
            2D grid of interpolated GPS coordinates.
        """

        cols, rows = grid_shape

        # Interpolates points along the left and right edges (top to bottom)
        left_edge = [
            GPSCalculate.interp_geo(vertices[0], vertices[3], i / (rows - 1))
            for i in range(rows)
        ]
        right_edge = [
            GPSCalculate.interp_geo(vertices[1], vertices[2], i / (rows - 1))
            for i in range(rows)
        ]

        grid = []

        # For each row in the grid
        for i in range(rows):
            row = []
            # Interpolates points across the row between left and right edge points
            for j in range(cols):
                frac = j / (cols - 1)  # Horizontal interpolation fraction
                point = GPSCalculate.interp_geo(left_edge[i], right_edge[i], frac)
                row.append(point)
            grid.append(row)

        return grid
