import math
from geopy.distance import distance
from geopy.point import Point
import numpy as np
from typing import Callable


class ImageCalculus:
    def __init__(self):
        '''Initializes the class with default settings.'''
        self.camera_offset: np.ndarray = np.array((0, 0, 0)) # Forward, right, up
        self.camera_orientation: np.ndarray = np.array((0, np.deg2rad(-90), 0)) # Roll, pitch, rotation
        self.camera_resolution: np.ndarray = np.array((1920, 1080))
        self.pixels_to_degree: Callable[[float], float] = lambda p: p/25


    def update_camera_offset(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> bool:
        '''
        Updates the camera's offset relative to the drone's center.

        Args:
            x (float | None): Forward position (+X) in meters. If None, keeps the current value.
            y (float | None): Right position (+Y) in meters. If None, keeps the current value.
            z (float | None): Up position (+Z) in meters. If None, keeps the current value.

        Returns:
            bool: True if the update was successful.
        '''
        try:
            self.camera_offset = np.array((
                self.camera_offset[0] if x is None else x,
                self.camera_offset[1] if y is None else y,
                self.camera_offset[2] if z is None else z,
            ))
            return True
        except:
            return False


    def update_camera_orientation(
        self,
        roll: float | None = None,
        pitch: float | None = None,
        rotation: float | None = None,
    ) -> bool:
        '''
        Updates the camera's orientation relative to the drone.

        Args:
            roll (float | None): Rotation around the X-axis (roll) in degrees. If None, keeps the current value.
            pitch (float | None): Rotation around the Y-axis (pitch) in degrees. If None, keeps the current value.
            rotation (float | None): Rotation around the camera-axis in degrees. If None, keeps the current value.

        Returns:
            bool: True if the update was successful.
        '''
        try:
            self.camera_orientation = np.array((
                self.camera_orientation[0] if roll is None else roll,
                self.camera_orientation[1] if pitch is None else pitch,
                self.camera_orientation[2] if rotation is None else rotation,
            ))
            return True
        except:
            return False


    def update_camera_resolution(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bool:
        '''
        Sets or updates the camera's resolution in pixels.

        Args:
            width (int | None): Image width in pixels. If None, keeps the current value.
            height (int | None): Image height in pixels. If None, keeps the current value.

        Returns:
            bool: True if the update was successful.
        '''
        try:
            self.camera_resolution = np.array((
                self.camera_resolution[0] if width is None else width,
                self.camera_resolution[1] if height is None else height,
            ))
            return True
        except:
            return False


    def update_pixels_to_degree(
        self,
        pixels_to_degree: Callable[[float], float],
    ) -> bool:
        '''
        Sets the camera's angular resolution.

        Args:
            pixels_to_degree (float | None): Pixels-per-degree conversion factor.
                If None, keeps the current value.

        Returns:
            bool: True if the update was successful.
        '''
        try:
            self.pixels_to_degree = self.pixels_to_degree if pixels_to_degree is None else pixels_to_degree
            return True
        except:
            return False


    def _calculate_camera_vector(
        self, 
        alfa: float, 
        theta: float,
    ) -> np.ndarray:
        '''
        calculate a unit vector pointing towards a pixel in the camera reference frame.

        The vector is defined in the camera coordinate system, assuming:
        - X axis pointing forward,
        - Y axis pointing to the right,
        - Z axis pointing upward (or according to your frame convention).

        Args:
            alfa (float): Angle in radians around the X axis.
            theta (float): Angle in radians around the Y axis in the YZ plane.

        Returns:
            np.ndarray: 3D vector (x, y, z) pointing in the direction of the pixel.
        '''
        x = np.cos(alfa)
        y = np.sin(alfa) * np.cos(theta)
        z = np.sin(alfa) * np.sin(theta)
        return (x, y, z)


    def _calculate_rotate_vector(
        self,
        vector: np.ndarray,
        pitch: float,
        roll: float,
    ) -> np.ndarray:
        '''
        Rotates a 3D vector by the given pitch and roll angles.

        Args:
            vector (np.ndarray): 3D vector (x, y, z) to be rotated.
            pitch (float): Rotation angle in radians.
            roll (float): Rotation angle in radians.

        Returns:
            np.ndarray: Rotated 3D vector (x, y, z).
        '''
        x = vector[0] * np.cos(pitch) - vector[2] * np.sin(pitch)
        y = vector[1] * np.cos(roll) - vector[2] * np.sin(roll)
        z = vector[0] * np.sin(pitch) + vector[1] * np.sin(roll) + vector[2] * np.cos(pitch) * np.cos(roll)
        return np.array((x, y, z))


    def _calculate_direction_vector(
        self,
        alfa: float,
        theta: float,
        pitch: float,
        roll: float,
    ) -> np.ndarray:
        '''
        Computes the 3D direction vector from the camera to a target pixel, taking into account 
        the camera's orientation and the drone's pitch and roll.

        This function first calculates a vector in the camera reference frame pointing toward
        the target pixel, then rotates it according to the camera's fixed orientation offset 
        and the drone's current pitch and roll.

        Args:
            alfa (float): Angle in radians around the camera's X-axis (roll in the camera frame).
            theta (float): Angle in radians around the camera's Y-axis (pitch in the camera frame).
            pitch (float): Additional pitch angle of the drone in radians.
            roll (float): Additional roll angle of the drone in radians.

        Returns:
            np.ndarray: Rotated 3D direction vector in the world or drone reference frame.
        '''
        camera_vector = self._calculate_camera_vector(
            alfa,
            theta + self.camera_orientation[2],
        )

        vector = self._calculate_rotate_vector(
            camera_vector,
            pitch = self.camera_orientation[1] + pitch,
            roll = self.camera_orientation[0] + roll,
        )

        return vector


    def _calculate_calculate_line(
        self,
        pixel_x: float,
        pixel_y: float,
        pitch: float,
        roll: float,
    ) -> np.ndarray:
        '''
        Calculates a line from the camera to a target pixel in 3D space, returning the origin 
        point and the direction vector of the line, taking into account the camera offset 
        and the drone's pitch and roll.

        The function performs the following steps:
        1. Applies the camera offset and drone orientation to determine the origin point.
        2. Computes the vector from the image center to the target pixel.
        3. Converts this pixel offset into an angular displacement (`alfa` and `theta`).
        4. Calculates the 3D direction vector of the line in the world/drone reference frame.

        Args:
            pixel_x (float): Coordinates x of the target pixel in the image.
            pixel_y (float): Coordinates y of the target pixel in the image.
            pitch (float): Pitch angle of the drone in radians.
            roll (float): Roll angle of the drone in radians.

        Returns:
            tuple:
                origin_point (np.ndarray): 3D point representing the origin of the line 
                    (camera position in world/drone frame).
                direction_vector (np.ndarray): 3D unit vector pointing from the origin towards 
                    the target pixel in space.
        '''
        origin_point = self._calculate_rotate_vector(
            self.camera_offset,
            pitch,
            roll,
        )

        centro = self.camera_resolution / 2
        vector = centro - np.array(pixel_x, pixel_y)
        vector *= np.array((-1, 1))

        theta = np.arctan2(vector[1], vector[0])

        r = np.linalg.norm(vector)
        alfa = np.deg2rad(self.pixels_to_degree(r))

        direction_vector = self._calculate_direction_vector(
            alfa,
            theta,
            pitch,
            roll,
        )

        return origin_point, direction_vector


    def _calculate_ground_intersection_by_line(
        self, 
        origin_point: np.ndarray, 
        direction_vector: np.ndarray
    ) -> np.ndarray | None:
        '''
        Calculates the intersection of a line with the ground.

        Args:
            origin_point (np.ndarray): The origin point of the line.
            direction_vector (np.ndarray): The direction vector of the line.

        Returns:
            np.ndarray | None: The (X, Y, Z) coordinates of the intersection point,
                               or None if the line does not intersect the ground.
        '''
        if direction_vector[2] == 0:
            return None

        t = - origin_point[2] / direction_vector[2]

        intersection_point = origin_point + t * direction_vector

        return intersection_point


    def calculate_ground_intersection(
        self, 
        pixel_x: float,
        pixel_y: float,
        altitude: float,
        pitch: float = 0.0, 
        roll: float = 0.0,
    ) -> np.ndarray | None:
        '''
        Computes the 3D vector from the drone/camera center to the ground intersection of a target pixel.

        The function considers the camera offset, drone pitch/roll, and the drone's altitude. 
        It returns the vector pointing from the drone/camera to the intersection point on the ground.

        Args:
            pixel_x (float): Coordinates x of the target pixel in the image.
            pixel_y (float): Coordinates y of the target pixel in the image.
            altitude (float): Height of the drone/camera above the ground.
            pitch (float, optional): Additional pitch angle of the drone in radians. Defaults to 0.0.
            roll (float, optional): Additional roll angle of the drone in radians. Defaults to 0.0.

        Returns:
            np.ndarray | None: 3D vector from the drone/camera to the intersection point on the ground,
                               or None if the line does not intersect the ground.
        '''
        origin_point, direction_vector = self._calculate_calculate_line(pixel_x, pixel_y, pitch, roll)

        origin_point += np.array((0, 0, altitude))

        point = self._calculate_ground_intersection_by_line(origin_point, direction_vector)

        if point is not None:
            vector = point - np.array((0, 0, altitude))

            return vector

        return point


    def _calculate_gps_by_vector(
        self,
        latitude: float,
        longitude: float,
        vector: np.ndarray,
        bearing: float,
    ) -> tuple[float, float]:
        """
        Converts a local 3D vector from the drone to a target point on the ground 
        into GPS coordinates (latitude, longitude), taking into account the drone's bearing.

        Args:
            latitude (float): latitude coordinates of the drone in degrees.
            longitude (float): longitude coordinates of the drone in degrees.
            vector (np.ndarray): 3D vector from the drone to the point (x, y, z) in meters.
                                x = forward, y = right, z = up (ignored for ground intersection).
            bearing (float): Drone bearing in radians (0 = North, positive clockwise).

        Returns:
            tuple[float, float]: GPS coordinates (latitude, longitude) of the target point.
        """
        x_local, y_local, _ = vector  # z ignored

        # Rotate vector by bearing to align with North-East frame
        cos_bearing = np.cos(bearing)
        sin_bearing = np.sin(bearing)
        x_global = x_local * cos_bearing - y_local * sin_bearing  # North
        y_global = x_local * sin_bearing + y_local * cos_bearing  # East

        # Earth's radius in meters
        R = 6378137  

        # Offsets in radians
        dlat = x_global / R
        dlon = y_global / (R * np.cos(np.radians(latitude)))

        # New GPS coordinates
        new_lat = latitude + np.degrees(dlat)
        new_lon = longitude + np.degrees(dlon)

        return (new_lat, new_lon)


    def calculate_gsp(
        self, 
        pixel_x: float,
        pixel_y: float,
        latitude: float,
        longitude: float,
        altitude: float,
        bearing: float,
        pitch: float = 0.0,
        roll: float = 0.0,
    ) -> tuple[float, float]:
        '''
        Calculates the GPS coordinates of a point on the ground corresponding to a target pixel 
        in the camera image.

        This function first computes the 3D vector from the drone/camera to the ground point using
        the camera geometry, altitude, pitch, and roll. It then converts this vector into GPS 
        coordinates using the drone's current GPS position and bearing (yaw).

        Args:
            pixel_x (float): Coordinates x of the target pixel in the image.
            pixel_y (float): Coordinates y of the target pixel in the image.
            latitude (float): latitude coordinates of the drone in degrees.
            longitude (float): longitude coordinates of the drone in degrees.
            altitude (float): Height of the drone/camera above the ground in meters.
            bearing (float): Drone's yaw/bearing in radians (0 = North, positive clockwise).
            pitch (float, optional): Additional pitch angle of the drone in radians. Defaults to 0.0.
            roll (float, optional): Additional roll angle of the drone in radians. Defaults to 0.0.

        Returns:
            tuple[float, float]: GPS coordinates (latitude, longitude) of the target point on the ground.
        '''
        vector = self.calculate_ground_intersection(
            pixel_x,
            pixel_y,
            altitude,
            pitch, 
            roll,
        )

        coordinate = self._calculate_gps_by_vector(
            latitude,
            longitude,
            vector,
            bearing,
        )

        return coordinate


    @staticmethod
    def estimate_pixel_gps(
        origin_lat: float,
        origin_lon: float,
        origin_row: int,
        origin_col: int,
        target_row: int,
        target_col: int,
        gsd: float,
        image_bearing: float,
    ):
        """
        Estimates the GPS coordinates of a target pixel in an image based on a known GPS coordinate 
        of a reference pixel (origin), the Ground Sampling Distance (GSD), and the image orientation (bearing).

        Parameters:
        ----------
        origin_lat : float
            Latitude of the origin pixel in decimal degrees.
        origin_lon : float
            Longitude of the origin pixel in decimal degrees.
        origin_row : int
            Row index (vertical axis) of the origin pixel.
        origin_col : int
            Column index (horizontal axis) of the origin pixel.
        target_row : int
            Row index (vertical axis) of the target pixel.
        target_col : int
            Column index (horizontal axis) of the target pixel.
        gsd : float
            Ground Sampling Distance (meters per pixel).
        image_bearing : float
            Orientation of the image in degrees (0° is North, increases clockwise).

        Returns:
        -------
        (float, float)
            A tuple containing the estimated latitude and longitude (in decimal degrees)
            of the target pixel.
        """

        # Euclidean distance in pixel space between origin and target
        pixel_distance = math.hypot(target_row - origin_row, target_col - origin_col)

        # Convert pixel distance to meters using GSD
        distance_m = pixel_distance * gsd

        # Compute the angle from origin to target in image coordinates
        # Y-axis is inverted: rows increase downward, so we subtract
        pixel_angle_deg = math.degrees(
            math.atan2(origin_row - target_row, target_col - origin_col)
        )

        # Adjust angle according to the image's bearing (compass orientation)
        absolute_bearing = (image_bearing - pixel_angle_deg + 90) % 360

        # Construct origin GPS point
        origin = Point(origin_lat, origin_lon)

        # Estimate target coordinate using geodesic projection
        destination = distance(meters=distance_m).destination(origin, absolute_bearing)

        return destination.latitude, destination.longitude


    @staticmethod
    def calculate_offset_pixels(
        offset_meters: float,
        height_meters: float,
        fov_degrees: float,
        image_pixels: int,
    ) -> float:
        """
        Calculates the offset in pixels corresponding to a physical offset (in meters) from the camera to a reference point (e.g., the center of the drone),
        given the camera's height above the ground, the field of view (FOV) in degrees (horizontal or vertical), and the image resolution in pixels (width or height).

        1. Convert FOV to radians:
            fov_radians = fov_degrees * π / 180

        2. Calculate the width of the field of view on the ground (ground_span), in meters:
            ground_span = 2 * height_meters * tan(fov_radians / 2)

        3. Convert to meters per pixel (meters_per_pixel):
            ground_span / image_pixels

        4. Convert physical offset (offset_meters) to offset in pixels (offset_pixels):
            offset_pixels = offset_meters / meters_per_pixel

        :param offset_meters: Physical offset from the camera to the reference point (meters).
        :param height_meters: Height of the camera above the ground (meters).
        :param fov_degrees: Field of view of the camera (horizontal or vertical) in degrees.
        :param image_pixels: Number of pixels in the corresponding image dimension (width or height).
        :return: Offset in pixels (float).
        """
        ground_span = 2 * height_meters * math.tan(math.radians(fov_degrees) / 2)
        offset_pixels = offset_meters / (ground_span / image_pixels)
        return offset_pixels
