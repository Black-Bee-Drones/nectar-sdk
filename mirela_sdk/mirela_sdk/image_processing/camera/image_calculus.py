import math
from geopy.distance import distance
from geopy.point import Point
import numpy as np
from scipy.spatial.transform import Rotation as R


class ImageCalculus:
    def __init__(self):
        '''Initializes the class with default settings.'''
        self.camera_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.camera_orientation: tuple[float, float, float] = (0.0, 0.0, 0.0)
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


    def update_camera_orientation(
        self,
        roll: float | None = None,
        pitch: float | None = None,
        yaw: float | None = None,
    ) -> bool:
        '''
        Updates the camera's orientation relative to the drone.

        Args:
            roll (float | None): Rotation around the X-axis (roll) in degrees. If None, keeps the current value.
            pitch (float | None): Rotation around the Y-axis (pitch) in degrees. If None, keeps the current value.
            yaw (float | None): Rotation around the Z-axis (yaw) in degrees. If None, keeps the current value.

        Returns:
            bool: True if the update was successful.
        '''
        try:
            self.camera_orientation = (
                self.camera_orientation[0] if roll is None else roll,
                self.camera_orientation[1] if pitch is None else pitch,
                self.camera_orientation[2] if yaw is None else yaw,
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
        except Exception:
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
            self.pixels_per_degree = self.pixels_per_degree if pixels_per_degree is None else float(pixels_per_degree)
            return True
        except (ValueError, TypeError):
            return False


    def calculate_vector_from_drone_to_ground(
        self,
        altura: float,
        drone_orientation: tuple[float, float, float],
        target_pixel: tuple[float, float],
    ) -> np.ndarray | None:
        '''
        Calculates the vector from the drone's position to the ground intersection point.

        Args:
            altura (float): The drone's altitude relative to the ground (Z=0).
            drone_orientation (tuple[float, float, float]): Drone orientation (Roll, Pitch, Yaw) in degrees.
            target_pixel (tuple[float, float]): The (px, py) coordinates of the target pixel in the image.

        Returns:
            np.ndarray | None: Vector from the drone's position to the ground intersection point,
                               or None if there is no intersection.
        '''
        # In the Z-Down system, the drone's position is at -altitude.
        drone_position = (0, 0, -altura)
        
        point, direction = self._calculate_line_by_pixel(
            drone_position          = drone_position,
            drone_orientation_rpy   = drone_orientation,
            target_pixel            = target_pixel
        )
        
        # The ground is the plane Z=0.
        intersection_point = self._calculate_ground_intersection(
            origin_point = point, 
            direction_vector = direction
        )

        if intersection_point is None:
            return None

        vector = intersection_point - np.array(drone_position)
        return vector


    def _calculate_line_by_pixel(
        self,
        drone_position: tuple, 
        drone_orientation_rpy: tuple, 
        target_pixel: tuple,
    ) -> tuple[np.ndarray, np.ndarray]:
        '''
        Calculates the line of sight (origin and direction) for a specific pixel.

        Args:
            drone_position (tuple): Drone position (X, Y, Z) in the world frame.
            drone_orientation_rpy (tuple): Drone orientation (Roll, Pitch, Yaw) in degrees.
            target_pixel (tuple): The (px, py) coordinates of the target pixel.

        Returns:
            tuple: A tuple containing:
                - np.ndarray: The origin point of the ray (camera position in the world).
                - np.ndarray: The unit direction vector of the ray.
        '''
        P_drone = np.array(drone_position)
        d_gimbal_body = np.array(self.camera_offset)
        rot_drone = R.from_euler('xyz', drone_orientation_rpy, degrees=True)
        d_gimbal_world = rot_drone.apply(d_gimbal_body)
        ponto_origem = P_drone + d_gimbal_world

        largura, altura = self.camera_resolution
        px, py = target_pixel
        
        centro_x = largura / 2.0
        centro_y = altura / 2.0
        
        offset_x = px - centro_x
        offset_y = py - centro_y
        
        ajuste_yaw = offset_x / self.pixels_per_degree
        ajuste_pitch = - (offset_y / self.pixels_per_degree)
        
        rot_pixel_offset = R.from_euler('zy', [ajuste_yaw, ajuste_pitch], degrees=True)
        rot_camera_gimbal = R.from_euler('xyz', self.camera_orientation, degrees=True)
        rot_final_combinada = rot_drone * rot_camera_gimbal * rot_pixel_offset

        v_base = np.array([1, 0, 0])
        vetor_direcao = rot_final_combinada.apply(v_base)
        
        return ponto_origem, vetor_direcao


    def _calculate_ground_intersection(
        self, 
        origin_point: np.ndarray, 
        direction_vector: np.ndarray
    ) -> np.ndarray | None:
        '''
        Calculates the intersection of a line with the ground plane (Z=0).

        Args:
            origin_point (np.ndarray): The origin point of the line (P).
            direction_vector (np.ndarray): The direction vector of the line (V).

        Returns:
            np.ndarray | None: The (X, Y, Z) coordinates of the intersection point,
                               or None if the line does not intersect the ground.
        '''
        _Px, _Py, Pz = origin_point
        _Vx, _Vy, Vz = direction_vector

        # To hit the ground (Z=0) from above (Z<0), Vz must be POSITIVE.
        if Vz <= 1e-6:
            return None

        nivel_do_chao = 0.0
        t = (nivel_do_chao - Pz) / Vz

        intersection_point = origin_point + t * direction_vector
        
        return intersection_point


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
