import os
import rclpy
from rclpy.node import Node
from pygeodesy.geoids import GeoidPGM
from shapely.geometry import Point, Polygon
from geopy.distance import geodesic
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
        current_lat: float = self.drone.get_gps.latitude
        current_long: float = self.drone.get_gps.longitude
        print(f"Lat: {current_lat} Long: {current_long}")

        current_position = Point(current_lat, current_long)

        if not current_position.within(self.fence):
            self.drone.node.get_logger().info("-- Geofence breach")
            self.drone.kill_motors()
            rclpy.shutdown()

    def geofence(self, coords: list[tuple[float, float]]):
        """
        Set a geofence for the drone

        Create a timer to check the position of the drone, for every 0.01 seconds

        :warning: The geofence call kill_motors() and shutdown() if the drone is outside the geofence

        :param coords: List of coordinates to define the geofence
        """
        self.drone.node.get_logger().info("Geofence function")
        self.fence = Polygon(coords)
        Node.create_timer(self.drone, 0.01, self._check_position)

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

        :return: True if the drone has reached the setpoint, False otherwise
        :warning: This function stuck the code until the drone reaches the setpoint
        """

        while True:
            current_lat = self.drone.get_gps.latitude
            current_long = self.drone.get_gps.longitude
            distance_target = geodesic(
                (current_lat, current_long), (lat_setpoint, lon_setpoint)
            ).meters
            print(distance_target)

            if distance_target <= precision_radius:
                self.drone.node.get_logger().info("-- GPS setpoint reached")
                break

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
