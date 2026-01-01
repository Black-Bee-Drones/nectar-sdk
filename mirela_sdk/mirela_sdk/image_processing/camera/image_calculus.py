import math
from geopy.distance import distance
from geopy.point import Point
import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import Tuple


class ImageCalculus:
    def __init__(self):
        '''Initializes the class with default settings.'''
        self.camera_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.camera_resolution: tuple[int, int] = (1920, 1080)
        self.pixels_per_degree: float = 20.0


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
            z (float | None): Downward position (+Z) in meters. If None, keeps the current value.

        Returns:
            bool: True if the update was successful.
        '''
        try:
            self.camera_offset = (
                self.camera_offset[0] if x is None else x,
                self.camera_offset[1] if y is None else y,
                self.camera_offset[2] if z is None else z,
            )
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
            self.camera_resolution = (
                self.camera_resolution[0] if width is None else width,
                self.camera_resolution[1] if height is None else height,
            )
            return True
        except:
            return False


    def update_pixels_per_degree(
        self,
        pixels_per_degree: float | None = None,
    ) -> bool:
        '''
        Sets the camera's angular resolution.

        Args:
            pixels_per_degree (float | None): Pixels-per-degree conversion factor.
                If None, keeps the current value.

        Returns:
            bool: True if the update was successful.
        '''
        try:
            self.pixels_per_degree = self.pixels_per_degree if pixels_per_degree is None else pixels_per_degree
            return True
        except:
            return False


    def calculate_vector_from_drone_to_ground(
        self,
        altura: float,
        target_pixel: tuple[float, float],
        drone_orientation: tuple[float, float, float] = (0, 0, 0),
    ) -> np.ndarray | None:
        '''
        Calculates the vector from the drone's position to the ground intersection point.

        drone_orientation not work!!!!!!!!!!!!

        Args:
            altura (float): The drone's altitude relative to the ground (Z=0).
            target_pixel (tuple[float, float]): The (px, py) coordinates of the target pixel in the image.
            drone_orientation (tuple[float, float, float]): Drone orientation (Roll, Pitch, Yaw) in degrees.

        Returns:
            np.ndarray | None: Vector from the drone's position to the ground intersection point,
                               or None if there is no intersection.
        '''
        camera_vector = self._calc_unit_vector_from_camera(
            target_pixel = target_pixel,
        )

        vector = self._calc_ground_intersection_vector(
            camera_vector = camera_vector,
            alt = altura,
        )

        return vector


    def _calc_unit_vector_from_camera(self, target_pixel: Tuple[float, float]):
        """
        Compute a normalized direction vector from the camera center to a target pixel.

        This function calculates the camera ray corresponding to a given pixel in the image,
        expressed in the drone's reference frame. The resulting vector points from the camera
        center toward the target pixel.

        Args:
            target_pixel (Tuple[float, float]): 
                The (x, y) coordinates of the target pixel in image space (in pixels).

        Returns:
            Tuple[float, float, float]: 
                A normalized direction vector (y, x, -1) in the drone's reference frame, where:
                
                - **x** (float): Forward displacement (positive = forward).
                - **y** (float): Lateral displacement (positive = right).
                - **z** (float): Fixed at -1, indicating the camera points downward.
        """
        pixel_center_x = self.camera_resolution[0] / 2
        pixel_center_y = self.camera_resolution[1] / 2

        pixel_vector_x = target_pixel[0] - pixel_center_x
        pixel_vector_y = pixel_center_y - target_pixel[1]

        degrees_x = pixel_vector_x / self.pixels_per_degree
        degrees_y = pixel_vector_y / self.pixels_per_degree

        x = math.tan(math.radians(degrees_x))
        y = math.tan(math.radians(degrees_y))

        vector = (y, x, -1)  # converts camera XY into drone coordinates

        return vector


    def _calc_ground_intersection_vector(self, alt: float, camera_vector: Tuple[float, float, float]):
        """
        Project a camera ray vector onto the ground plane in meters.

        This function scales the camera direction vector so that it intersects
        the ground plane at the given altitude, considering the camera's vertical offset.

        Args:
            alt (float): 
                The drone's altitude above the ground in **meters**.
            camera_vector (Tuple[float, float, float]): 
                A normalized direction vector (y, x, -1) from the camera center 
                in the drone's reference frame (unitless).

        Returns:
            Optional[Tuple[float, float, float]]: 
                A 3D point in **meters** on the ground plane (y, x, z) expressed 
                in the drone's reference frame, where:
                
                - **x** (float): Forward displacement from the drone center (meters).  
                - **y** (float): Lateral displacement from the drone center (meters).  
                - **z** (float): Vertical coordinate in meters, representing the ground 
                (typically ≈ 0, but offset-adjusted).  

                Returns **None** if the scale factor is zero (no valid ground intersection).
        """
        scale_factor = alt + self.camera_offset[2]

        if scale_factor == 0:
            return None

        ground_vector = tuple((vector * scale_factor + self.camera_offset[i]) for i, vector in enumerate(camera_vector))

        return ground_vector


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
