import math


class ImageCalculus:

    @staticmethod
    def find_coordinate(
        centerpixel_lon: float,
        centerpixel_lat: float,
        centerpixel_height: int,
        centerpixel_width: int,
        pixel2_height: int,
        pixel2_width: int,
        gdr: float,
        bearing: float,
    ):
        """
        Finds the GPS coordinate of a pixel in an image based on the GPS coordinates of the image center,
        coordinates of the center pixel in the image, coordinates of the pixel you want to find the GPS
        coordinate, GDR (Geographic Resolution) in meters per pixel, and the bearing (compass angulation)
        in degrees.

        Inputs:
        :param centerpixel_lon (float): GPS longitude of the image center.
        :param centerpixel_lat (float): GPS latitude of the image center.

        :param centerpixel_height (int): Vertical coordinate (height) of the central pixel in the image.
        :param centerpixel_width (int): Horizontal coordinate (width) of the central pixel in the image.

        :param pixel2_height (int): Vertical coordinate (height) of the pixel for which you want to
                                    find the GPS coordinate.
        :param pixel2_width (int): Horizontal coordinate (width) of the pixel for which you want to
                                   find the GPS coordinate.

        :param gdr (float): Geographic Resolution in meters per pixel.

        :param bearing (float): Angle of orientation (bearing) in degrees with respect to magnetic north.

        Output:
        Tuple containing the GPS Longitude and Latitude of the desired pixel.
        """

        # Earth radius in kilometers (will be used to calculate the new coordinate): unit kilometers
        earth_radius = 6371.0

        # Converting to radians as math always uses radians: unit radians
        bearing_radians = math.radians(bearing)

        # The distance between the two given points: unit pixels
        module = math.sqrt(
            (centerpixel_height - pixel2_height) ** 2
            + (centerpixel_width - pixel2_width) ** 2
        )

        # Calculating that same distance in meters: unit meters
        distance_in_meters = module * gdr  # gdr should be given as meters/pixel

        # Calculating the angle formed by the reference and a line made by the two points: unit radians
        # In this calculation, the "height" is inverted because opencv's orientation is oposite to ours.
        argument = math.atan2(
            centerpixel_height - pixel2_height, pixel2_width - centerpixel_width
        )

        # 'alpha' in the angle of the vector from the point1 to the point2;
        alpha = bearing_radians - argument

        latitude_distance = distance_in_meters * math.sin(alpha)  # unit -> meters
        longitude_distance = distance_in_meters * math.cos(alpha)  # unit -> meters

        # Convert latitude and longitude from radians to degrees
        lat, lon = map(math.radians, [centerpixel_lat, centerpixel_lon])

        # Calculate the new coordinate point
        newlat = lat - (latitude_distance / (earth_radius * 1000))
        newlon = lon + (longitude_distance / (earth_radius * 1000))

        # Convert back to degrees
        newlat, newlon = map(math.degrees, [newlat, newlon])

        return newlon, newlat

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
