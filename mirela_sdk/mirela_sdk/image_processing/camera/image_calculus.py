import math
from geopy.distance import distance
from geopy.point import Point
import numpy as np
from scipy.spatial.transform import Rotation as R


class ImageCalculus:
    def __init__(self):
        self.camera_offset = (0.0, 0.0, 0.0)
        self.camera_orientation = (0.0, 0.0, 0.0)
        self.camera_resolution= (1920, 1080)
        self.pixels_per_degree= 20.0


    def update_camera_offset(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ):
        '''
        Updates the camera's offset relative to the drone.

        Args:
            x (float | None): Forward position relative to the drone in meters. 
                If None, keeps the current value.
            y (float | None): Right position relative to the drone in meters.
                If None, keeps the current value.
            z (float | None): Upward position relative to the drone in meters.
                If None, keeps the current value.

        Returns:
            bool: True if the update was successful, False otherwise.
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
    ):
        '''
        Updates the camera's orientation relative to the drone.

        Args:
            roll (float | None): Rotation around the X-axis in degrees.
                If None, keeps the current value.
            pitch (float | None): Rotation around the Y-axis in degrees.
                If None, keeps the current value.
            yaw (float | None): Rotation around the Z-axis in degrees.
                If None, keeps the current value.

        Returns:
            bool: True if the update was successful, False otherwise.
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
        Sets or updates the camera's resolution.

        Args:
            width (int | None): Image width in pixels. 
                If None, keeps the current value.
            height (int | None): Image height in pixels.
                If None, keeps the current value.

        Returns:
            bool: True if the update was successful, False otherwise.
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
        Sets or updates the camera's pixels per degree (angular resolution), measured radially from the image center.

        Args:
            pixels_per_degree (float | None): Pixels per degree, representing the angular resolution 
                If None, keeps the current value.

        Returns:
            bool: True if the update was successful, False otherwise.
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
    ):
        '''
        Calculates the vector from the drone's position at a given altitude to the intersection point on the ground
        corresponding to a specific pixel in the camera image.

        Args:
            altura (float): The altitude (height) of the drone above the ground.
            drone_orientation (tuple[float, float, float]): Drone orientation (Roll, Pitch, Yaw) in degrees.
            target_pixel (tuple[float, float]): Coordinates (px, py) of the target pixel in the camera image.

        Returns:
            numpy.ndarray: Vector from the drone's position to the ground intersection point corresponding to the target pixel.
        '''
        drone_position = (0, 0, altura)
        point, direction = self._calculate_line_by_pixel(
            drone_position          = drone_position,
            drone_orientation_rpy   = drone_orientation,
            camera_offset           = self.camera_offset,
            camera_orientation_rpy   = self.camera_orientation,
            resolution              = self.camera_resolution,
            pixels_per_degree       = self.pixels_per_degree,
            target_pixel            = target_pixel
        )
        
        intersection_point = self._calculate_ground_intersection(
            origin_point = point, 
            direction_vector = direction
        )

        vector = intersection_point - drone_position
        return vector


    def _calculate_line_by_pixel(
        self,
        drone_position, 
        drone_orientation_rpy, 
        camera_offset, 
        camera_orientation_rpy,
        resolution,
        pixels_per_degree,
        target_pixel,
    ):
        '''
        Calculates the viewing ray for a specific pixel in the camera image.

        Args:
            drone_position (tuple): Drone position (X, Y, Z) in the world frame.
            drone_orientation_rpy (tuple): Drone orientation (Roll, Pitch, Yaw) in degrees.
            camera_offset (tuple): Camera gimbal offset relative to the drone center.
            camera_orientation_rpy (tuple): Camera orientation (Roll, Pitch, Yaw) relative to the drone in degrees.
            resolution (tuple): Image resolution (width, height) in pixels.
            pixels_per_degree (float): Conversion factor indicating how many pixels correspond to 1 degree of FoV.
            target_pixel (tuple): Coordinates (px, py) of the target pixel.

        Returns:
            tuple: A tuple containing:
                - numpy.ndarray: The origin point of the ray (camera position in world coordinates).
                - numpy.ndarray: The unit direction vector of the ray towards the target pixel.
        '''
        # --- Parte 1: Calcular a POSIÇÃO da câmera (não muda) ---
        P_drone = np.array(drone_position)
        d_gimbal_body = np.array(camera_offset)
        rot_drone = R.from_euler('xyz', drone_orientation_rpy, degrees=True)
        d_gimbal_world = rot_drone.apply(d_gimbal_body)
        ponto_origem = P_drone + d_gimbal_world

        # --- Parte 2: Calcular a DIREÇÃO da reta para o pixel alvo ---
        
        # 2a. Converter coordenadas do pixel em desvio angular
        largura, altura = resolution
        px, py = target_pixel
        
        centro_x = largura / 2.0
        centro_y = altura / 2.0
        
        offset_x = px - centro_x
        offset_y = py - centro_y
        
        ajuste_yaw = offset_x / pixels_per_degree
        # Invertemos o sinal do pitch: Y do pixel cresce para baixo, Pitch positivo é para cima
        ajuste_pitch = - (offset_y / pixels_per_degree)
        
        # Pequena rotação que representa o desvio do pixel em relação ao centro da câmera
        # Usamos a convenção 'zy' -> primeiro o desvio horizontal (Yaw), depois o vertical (Pitch)
        rot_pixel_offset = R.from_euler('zy', [ajuste_yaw, ajuste_pitch], degrees=True)
        
        # 2b. Combinar todas as rotações
        rot_camera_gimbal = R.from_euler('xyz', camera_orientation_rpy, degrees=True)

        # A rotação final combinada é a do drone * a do gimbal * a do desvio do pixel
        # A ordem é importante! As rotações são aplicadas da direita para a esquerda.
        rot_final_combinada = rot_drone * rot_camera_gimbal * rot_pixel_offset

        # 2c. Aplicar a rotação final ao vetor "para frente"
        v_base = np.array([1, 0, 0]) # Vetor 'para frente' no referencial mais básico
        vetor_direcao = rot_final_combinada.apply(v_base)
        
        return ponto_origem, vetor_direcao


    def _calculate_ground_intersection(
        self, 
        origin_point: np.ndarray, 
        direction_vector: np.ndarray,
    ):
        '''
        Calculates the intersection point of a line with the ground plane (Z=0).

        Args:
            origin_point (np.ndarray): The origin point of the line (P).
            direction_vector (np.ndarray): The direction vector of the line (V).

        Returns:
            np.ndarray or None: The (X, Y, Z) coordinates of the intersection point,
                                or None if the line does not intersect the ground.
        '''
        Px, Py, Pz = origin_point
        Vx, Vy, Vz = direction_vector

        # Se o vetor de direção não aponta para baixo (Vz >= 0),
        # a reta é paralela ao chão ou aponta para cima, logo não há interseção.
        if Vz >= -1e-6: # Usamos uma pequena tolerância para evitar divisão por quase zero
            return None

        # Resolve para t: Pz + t * Vz = nivel_do_chao
        nivel_do_chao = 0.0
        t = (nivel_do_chao - Pz) / Vz

        # Calcula o ponto de interseção usando o valor de t
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
