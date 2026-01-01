import math
import numpy as np
from typing import Dict


class ImageCalculus:
    """Utility class for image-based geometric calculations related to drones.

    This class provides methods to convert pixel coordinates from an image
    into metric vectors in the drone reference frame, assuming a flat ground
    (Z = 0) and small-angle approximations for pitch and roll.

    Coordinate frame convention:
        - X (forward): drone forward direction
        - Y (right): drone right direction
        - Z (up): positive upwards
        - Ground plane is located at Z = 0

    Notes:
        - All angles are expressed in degrees.
        - The calculations assume small pitch and roll angles
          (typically <= 5 degrees).
        - Camera offsets are defined in the drone body frame.
    """

    def __init__(
        self,
        camera_offset: Dict[str, float] = None,
        camera_resolution: Dict[str, int] = None,
        pixels_per_degree: Dict[str, int] = None,
    ):
        """Initializes the ImageCalculus object.

        Args:
            camera_offset (Dict[str, float], optional):
                Camera position relative to the drone center, in meters.
                Expected keys are:
                    - 'forward': offset along the forward axis
                    - 'right': offset along the right axis
                    - 'up': offset along the up axis
            camera_resolution (Dict[str, int], optional):
                Camera image resolution in pixels.
                Expected keys are:
                    - 'width'
                    - 'height'
            pixels_per_degree (Dict[str, int], optional):
                Conversion factor from pixels to degrees.
                Expected keys are:
                    - 'horizontal'
                    - 'vertical'
        """

        self._camera_offset = {'forward': 0.0, 'right': 0.0, 'up': 0.0}
        self._camera_resolution = {'width': 1920, 'height': 1080}
        self._pixels_per_degree = {'horizontal': 20, 'vertical': 20}

        if camera_offset:
            self.camera_offset = camera_offset
        if camera_resolution:
            self.camera_resolution = camera_resolution
        if pixels_per_degree:
            self.pixels_per_degree = pixels_per_degree

    @property
    def camera_offset(self):
        """Dict[str, float]: Camera offset relative to the drone body frame."""
        return self._camera_offset

    @camera_offset.setter
    def camera_offset(self, value):
        if not isinstance(value, dict):
            return
        
        for k, v in value.keys():
            if (k in self._camera_offset.keys()) and isinstance(v, (int, float)):
                self._camera_offset[k] = v

    @property
    def camera_resolution(self):
        """Dict[str, int]: Camera image resolution in pixels."""
        return self._camera_resolution

    @camera_resolution.setter
    def camera_resolution(self, value):
        if not isinstance(value, dict):
            return

        for k, v in value.keys():
            if (k in self._camera_resolution.keys()) and isinstance(v, int):
                self._camera_resolution[k] = v

    @property
    def pixels_per_degree(self):
        """Dict[str, int]: Number of pixels corresponding to one degree of view."""
        return self._pixels_per_degree

    @pixels_per_degree.setter
    def pixels_per_degree(self, value):
        if not isinstance(value, dict):
            return
        
        for k, v in value.keys():
            if (k in self._pixels_per_degree.keys()) and isinstance(v, (int, float)):
                self._pixels_per_degree[k] = v

    def calculate_vector_from_drone_to_ground(
        self,
        target_pixel: tuple[float, float],
        height: float,
        pitch = float,
        roll = float,
    ) -> np.ndarray | None:
        """Calculates the vector from the drone to the ground intersection point.

        This method projects a pixel from the image onto the ground plane (Z = 0),
        taking into account the drone height, camera offset, and small pitch and
        roll angles. The calculation uses small-angle approximations and is not
        intended for large attitude angles.

        Args:
            target_pixel (tuple[float, float]):
                Target pixel coordinates (x, y) in the image frame.
            height (float):
                Drone height relative to the ground, in meters.
                Positive values indicate the drone is above the ground.
            pitch (float):
                Drone pitch angle in degrees.
                Positive values indicate nose-up rotation.
            roll (float):
                Drone roll angle in degrees.
                Positive values indicate right-wing-down rotation.

        Returns:
            np.ndarray | None:
                A 3D vector (forward, right, down) from the drone to the
                intersection point on the ground, expressed in meters.
                The Z component is negative (downwards).
                Returns None if the projection is invalid.

        Limitations:
            - Valid only for small pitch and roll angles.
            - Assumes flat ground at Z = 0.
            - Does not account for yaw rotation.
        """

        pixel_center_x = self.camera_resolution['width'] / 2
        pixel_center_y = self.camera_resolution['height'] / 2

        pixel_distance_x = target_pixel[0] - pixel_center_x
        pixel_distance_y = pixel_center_y - target_pixel[1]

        pixel_angle_horizontal = pixel_distance_x / self.pixels_per_degree['horizontal']
        pixel_angle_vertical   = pixel_distance_y / self.pixels_per_degree['vertical']

        sum_pitch = pitch + pixel_angle_vertical
        sum_roll  = roll  + pixel_angle_horizontal

        forward_unit = math.tan(math.radians(sum_pitch))
        right_unit = math.tan(math.radians(sum_roll))

        height += self.camera_offset['up'] * (math.cos(math.radians(pitch)) + math.cos(math.radians(roll)) - 1)
        forward = forward_unit * height + self.camera_offset['forward'] * math.cos(math.radians(pitch)) + self.camera_offset['up'] * math.sin(math.radians(pitch))
        right = right_unit * height + self.camera_offset['right'] * math.cos(math.radians(roll)) - self.camera_offset['up'] * math.sin(math.radians(roll))

        return (forward, right, -height)


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
