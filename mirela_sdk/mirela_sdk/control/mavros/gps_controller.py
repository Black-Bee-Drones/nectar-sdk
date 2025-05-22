import os
import rclpy
import numpy as np
from typing import Tuple
from rclpy.node import Node, Rate
from pygeodesy.geoids import GeoidPGM
from shapely.geometry import Point, Polygon
from geopy.distance import geodesic
from geographiclib.geodesic import Geodesic
from math import radians
from tf_transformations import quaternion_from_euler
from geographic_msgs.msg import GeoPoseStamped


class GPSController:

    def __init__(self, drone):
        self.drone = drone
        self._egm96 = GeoidPGM("/usr/share/GeographicLib/geoids/egm96-5.pgm", kind=-3)
        self.photo_count: int = 0
        self.path = os.path.dirname(os.path.abspath(__file__))


    def _check_position(self):
        rclpy.spin_once(self.drone.node)
        current_lat: float = self.drone.get_gps.latitude
        current_long: float = self.drone.get_gps.longitude
        print(f"Lat: {current_lat} Long: {current_long}")

        current_position = Point(current_lat, current_long)

        if not current_position.within(self.fence):
            self.drone.node.get_logger().info("-- Geofence breach")
            self.drone.rtl() if self.rtl else self.drone.kill_motors()
            rclpy.shutdown()

    def geofence(self, coords: list[tuple[float, float]], rtl: bool):

        """
        Set a geofence for the drone
        Create a polygon geofence, to get motors killed

        :param coords: List of lat ant long coordinates

            exemple: [(-22.41517936,-45.44797450),(-22.41493884,-45.44779748),(-22.41532317,-45.44727176)]

        Create a timer to check the position of the drone, for every 0.01 seconds

        :warning: The geofence call kill_motors() and shutdown() if the drone is outside the geofence

        :param coords: List of coordinates to define the geofence
        """

        self.rtl = rtl
        self.drone.set_mode("GUIDED")
        self.drone.node.get_logger().info("-- Geofence created")
        self.fence = Polygon(coords)
        self.drone.node.create_timer(0.01, self._check_position)

    def geoid_height(self, lat, lon):
        """
        Calculates AMSL to ellipsoid conversion offset.
        Uses EGM96 data with 5' grid and cubic interpolation.
        The value returne can help you convert from meters
        above mean sea level (AMSL) to meters above
        the WGS84 ellipsoid.
        If you want to go from AMSL to ellipsoid height, add the value.
        To go from ellipsoid height to AMSL, subtract this value.
        """
        return self._egm96.height(lat, lon)

    def gps_reach(
        self, lat_setpoint: float, lon_setpoint: float, precision_radius: float
    ):
        """
        Verify if the drone has reached the GPS setpoint

        :param lat_setpoint: Latitude of the setpoint
        :param lon_setpoint: Longitude of the setpoint
        :param precision_radius: Radius of the precision

        :warning: This function stuck the code until the drone reaches the setpoint
        """

        last_distance: float = 1
        rate: Rate = self.drone.node.create_rate(10)

        while rclpy.ok():
            rclpy.spin_once(self.drone.node)
            current_lat = self.drone.get_gps.latitude
            current_long = self.drone.get_gps.longitude
            distance_target = geodesic(
                (current_lat, current_long), (lat_setpoint, lon_setpoint)
            ).meters
            self.drone.node.get_logger().info(f"Coordinate distance: {distance_target}")

            ds = distance_target - last_distance

            if (ds < 0.1 or ds <= 0) and distance_target <= precision_radius:
                self.drone.node.get_logger().info("-- GPS setpoint reached")
                break

            last_distance = distance_target

            rate.sleep()

    def gps_send(
        self,
        lat_setpoint: float,
        lon_setpoint: float,
        alt_setpoint: float,
        heading: float,
        precision_radius: float,
    ):
        """
        Move sending a GPS coordinate setpoint

        :param lat_setpoint (float): Latitude of the setpoint
        :param lon_setpoint (float): Longitude of the setpoint
        :param alt_setpoint (float): Altitude of the setpoint
        :param heading (float): Heading of the drone
        :param precision_radius (float): Radius of the precision
        """

        # ellipsoid to AMSL conversion: subtract alt_adjust
        alt_adjust = self.geoid_height(lat_setpoint, lon_setpoint)

        target_altitude = self.drone.initial_altitude - alt_adjust + alt_setpoint

        gps_setpoint = GeoPoseStamped()
        gps_setpoint.pose.position.latitude = lat_setpoint
        gps_setpoint.pose.position.longitude = lon_setpoint
        gps_setpoint.pose.position.altitude = target_altitude
        yaw = radians(90 - heading)
        [x, y, z, w] = quaternion_from_euler(0, 0, yaw)

        gps_setpoint.pose.orientation.x = x
        gps_setpoint.pose.orientation.y = y
        gps_setpoint.pose.orientation.z = z
        gps_setpoint.pose.orientation.w = w

        self.drone.gps_pub.publish(gps_setpoint)

        self.gps_reach(lat_setpoint, lon_setpoint, precision_radius)

    def calculate_bearing(self, lat: float, lon: float):

        """
        Calculate the bearing/heading towards a given a coordinate.
        The lat and lon represents the latitude and longitude of the desired coordinate to compare with the drone one.
        This method returns an angle in degrees, in which zero corresponds to North, and increases clock-wise.
        
        :param lat (float): setpoint latitude (degrees)
        :param lon (float): setpoint longitute (degrees)
        """
        lat, lon = map(np.radians, [lat, lon])
        lat1 = self.drone.get_gps.latitude
        lon1 = self.drone.get_gps.longitude

        lat1, lon1 = map(np.radians, [lat1, lon1])

        dlon = lon - lon1

        x = np.sin(dlon) * np.cos(lat)
        y = np.cos(lat1) * np.sin(lat) - (np.sin(lat1) * np.cos(lat) * np.cos(dlon))
        bearing = np.arctan2(x, y)

        bearing = np.degrees(bearing)

        bearing = (bearing + 360) % 360

        return bearing
    

    def haversine_distance(self, lat: float, lon: float):
        """
        This method returns the distance between the drone and a given GPS coordinate, in meters.

        :param lat (float): setpoint's latitude in degrees
        :param lon (float): setpoint's longitude in degrees
        """
        lat, lon = map(np.radians, [lat, lon])

        lat1 = self.drone.get_gps.latitude
        lon1 = self.drone.get_gps.longitude

        lat1, lon1 = map(np.radians, [lat1, lon1])
        dlat = lat1 - lat
        dlon = lon1 - lon

        a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        return c * 6371000 # angle in the great-cricle between the two point times earth's radius
    
    def interp_geo(
        self,
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
