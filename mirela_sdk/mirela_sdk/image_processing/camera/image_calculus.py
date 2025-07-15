import math
from geopy.distance import distance
from geopy.point import Point


class ImageCalculus:
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
