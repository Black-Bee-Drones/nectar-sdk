from typing import Tuple
from geographiclib.geodesic import Geodesic
import numpy as np


class GPSCalculate:
    @staticmethod
    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates the great-circle distance between two GPS coordinates using the Haversine formula.

        This method assumes the Earth is a perfect sphere and returns the distance in meters.

        :param lat1 (float): Latitude of the first point in degrees.
        :param lon1 (float): Longitude of the first point in degrees.
        :param lat2 (float): Latitude of the second point in degrees.
        :param lon2 (float): Longitude of the second point in degrees.

        :return: Distance between the two points in meters (float).
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
        Calculates the initial bearing (also known as forward azimuth) from the first GPS coordinate 
        (lat1, lon1) to the second (lat2, lon2). The result is the angle in degrees between north 
        and the direction from the first point to the second.

        Args:
            lat1 (float): Latitude of the starting point (in degrees).
            lon1 (float): Longitude of the starting point (in degrees).
            lat2 (float): Latitude of the destination point (in degrees).
            lon2 (float): Longitude of the destination point (in degrees).

        Returns:
            float: Initial bearing from the first point to the second, in degrees (0° to 360°).
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
    def interp_geo(
        start: Tuple[float, float],
        end: Tuple[float, float],
        frac: float
    ) -> Tuple[float, float]:
        """
        Computes geodesic interpolation between two GPS coordinates.

        Args:
            start (Tuple[float, float]): Starting GPS coordinate (lat, lon).
            end (Tuple[float, float]): Ending GPS coordinate (lat, lon).
            frac (float): Interpolation factor between 0.0 and 1.0.

        Returns:
            Tuple[float, float]: Interpolated GPS coordinate (lat, lon).
        """
        line = Geodesic.WGS84.InverseLine(start[0], start[1], end[0], end[1])
        position = line.Position(line.s13 * frac)
        return (position['lat2'], position['lon2'])


    @staticmethod
    def generate_point_grid(
        vertices: Tuple[Tuple[float, float]],
        grid_shape: tuple[int, int]
    ) -> list[list[Tuple[float, float]]]:
        """
        Generate a 2D grid of geodesic-interpolated GPS coordinates within a quadrilateral area.

        This method creates a grid of points that fills the area defined by 4 GPS vertices, ordered as:
            - vertices[0]: top-left
            - vertices[1]: top-right
            - vertices[2]: bottom-right
            - vertices[3]: bottom-left

        The number of points along each dimension is defined by `grid_shape`, as (cols, rows).

        Args:
            vertices (Tuple[Tuple[float, float]]): 
                A tuple containing four (lat, lon) tuples defining the corners of the area.
            grid_shape (tuple[int, int]): 
                A tuple (cols, rows) defining the number of points per row and per column.

        Returns:
            list[list[Tuple[float, float]]]: 
                A 2D list (grid) of interpolated GPS points.
        """

        cols, rows = grid_shape

        # Interpolates points along the left and right edges (top to bottom)
        left_edge = [GPSCalculate.interp_geo(vertices[0], vertices[3], i / (rows - 1)) for i in range(rows)]
        right_edge = [GPSCalculate.interp_geo(vertices[1], vertices[2], i / (rows - 1)) for i in range(rows)]

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
