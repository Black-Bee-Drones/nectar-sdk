import numpy as np

from typing import Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from mirela_sdk.control.pid.config import PositionPIDConfig

import rclpy
from rclpy.node import Node
from rclpy.client import Client
from rclpy.service import SrvTypeRequest
from rclpy.duration import Duration
from rclpy.qos import qos_profile_sensor_data

from mavros_msgs.srv import (
    SetMode,
    CommandBool,
    CommandTOL,
    CommandHome,
    CommandLong,
    ParamSetV2,
)
from time import sleep
import math

from mavros_msgs.msg import State, PositionTarget, GlobalPositionTarget
from std_msgs.msg import Float64, Int64
from geometry_msgs.msg import PoseWithCovarianceStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix, Range, Imu
from rcl_interfaces.msg import Parameter
from rcl_interfaces.srv import SetParameters

from mirela_sdk.control.mavros.gps_controller import GPSController
from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.control.drone import Drone
from mirela_sdk.control.mavros.position_controller import PositionController
from mirela_sdk.control.mavros.exceptions import (
    TakeoffPositionNotSetError,
    SensorNotAvailableError,
    InvalidModeError,
)
from mirela_sdk.utils.process import ProcessUtils
from mirela_sdk.utils.gps_calculate import GPSCalculate
from mirela_sdk.utils.position_utils import PositionUtils

from tf_transformations import quaternion_from_euler


class MavDrone(Drone):
    """
    Class to control the mav ros drone using ROS2.
    """

    def __init__(
        self,
        node: Node,
        mavros: bool = False,
        indoor: bool = False,
    ) -> None:
        """
        Initialize the Mavros API.

        Parameters
        ----------
        node : Node
            ROS2 node to run the API.
        mavros : bool, optional
            True to start the mavros node.
        indoor : bool, optional
            True if running in indoor mode.
        """
        super().__init__(node=node)

        # Variables:
        self.indoor = indoor
        self.lidar_on = False
        self._state = State()
        self._rng_alt = None
        self._vision_pos = None
        self._imu_data = Imu()
        self._takeoff_position = None
        self._takeoff_height = None
        self._pose_controller = PositionController(self)

        # Outdoor only variables:
        if self.indoor == False:
            self._heading = None
            self._gps = None
            self._rel_alt = Float64()

            self.gps_controller = GPSController(self)

        # Subscribers:
        self._state_sub = self._create_subscriber(
            State, "/mavros/state", lambda data: self.__setattr__("_state", data), 10
        )
        self._rng_alt_sub = self._create_subscriber(
            Range,
            "/mavros/rangefinder/rangefinder",
            lambda data: self.__setattr__("_rng_alt", data),
            10,
        )
        self._imu_data_sub = self._create_subscriber(
            Imu,
            "/mavros/imu/data",
            lambda data: self.__setattr__("_imu_data", data),
            qos_profile_sensor_data,
        )

        # Indoor only Subscribers:
        if self.indoor == True:
            # self._local_pos_sub = self._create_subscriber(
            #     PoseStamped,
            #     "/mavros/local_position/pose",
            #     lambda data: self.__setattr__("_vision_pos", data),
            #     qos_profile_sensor_data,
            # )
            self._vision_pos_sub = self._create_subscriber(
                PoseWithCovarianceStamped,
                "/mavros/vision_pose/pose_cov",
                lambda data: self.__setattr__("_vision_pos", data),
                qos_profile_sensor_data,
            )

        # Outdoor only Subscribers:
        if self.indoor == False:
            self._gps_sub = self._create_subscriber(
                NavSatFix,
                "/mavros/global_position/global",
                lambda data: self.__setattr__("_gps", data),
                qos_profile_sensor_data,
            )

            self._rel_alt_sub = self._create_subscriber(
                Float64,
                "/mavros/global_position/rel_alt",
                lambda data: self.__setattr__("_rel_alt", data),
                qos_profile_sensor_data,
            )

            self._hdg_sub = self._create_subscriber(
                Float64,
                "/mavros/global_position/compass_hdg",
                lambda data: self.__setattr__("_heading", data),
                qos_profile_sensor_data,
            )

        # Services:
        self._mode_srv = self._create_client(SetMode, "/mavros/set_mode")
        self._arm_srv = self._create_client(CommandBool, "/mavros/cmd/arming")
        self._takeoff_srv = self._create_client(CommandTOL, "/mavros/cmd/takeoff")
        self._land_srv = self._create_client(CommandTOL, "/mavros/cmd/land")
        self._home_srv = self._create_client(CommandHome, "/mavros/cmd/set_home")
        # self._param_set_srv = self._create_client(ParamSetV2, "/mavros/param/set")
        self._param_set_srv = self._create_client(
            SetParameters, "/mavros/param/set_parameters"
        )
        self._command_srv = self._create_client(CommandLong, "/mavros/cmd/command")

        # Publishers:
        self.local_pub = self._create_publisher(
            PositionTarget, "/mavros/setpoint_raw/local", 1
        )

        # Outdoor only Publishers:
        if self.indoor == False:
            self.gps_pub = self._create_publisher(
                GeoPoseStamped, "/mavros/setpoint_position/global", 1
            )
            self.gps2_pub = self._create_publisher(
                GlobalPositionTarget, "/mavros/setpoint_raw/global", 1
            )

        if mavros:
            self.init_drivers()

        self.__startup()

        self.node.get_logger().info("Mavros API initialized")

    def start_driver_node(self) -> None:
        """
        Start the mavros launch process.

        Launches:
            ros2 launch mavros apm.launch fcu_url:=serial:///dev/ttyUSB0:921600
        """

        # Start the ros2 launch mavros apm
        result = ProcessUtils.start_process(
            "ros2 launch mavros apm.launch fcu_url:=serial:///dev/ttyUSB0:921600",
            "mavros_node",
        )
        self._driver_initialized = result

    def get_driver_node_name(self) -> str:
        """
        Get the name of the MAVROS driver node.

        Returns
        -------
        str
            Name of the MAVROS driver node.
        """
        return "mavros_node"

    @property
    def get_state(self) -> State:
        """
        Get the current MAVROS state.

        Returns
        -------
        State
            MAVROS state message. See:
            http://docs.ros.org/en/api/mavros_msgs/html/msg/State.html
        """
        return self._state

    @property
    def get_rng_alt(self) -> Range:
        """
        Get relative altitude data from lidar.

        Returns
        -------
        Range
            Lidar range message. See:
            http://docs.ros.org/en/melodic/api/sensor_msgs/html/msg/Range.html
        """
        return self._rng_alt

    @property
    def get_height(self) -> float:
        """
        Get drone height using the appropriate sensor.

        Returns
        -------
        float
            Height in meters. Uses lidar if available, otherwise:
            - Indoor: vision_pos.pose.z
            - Outdoor: GPS rel_alt
        """
        if self.lidar_on == True:
            return self.get_rng_alt.range
        elif self.indoor == True:
            return self.get_vision_pos.pose.position.z
        else:
            return self.get_rel_alt.data

    @property
    def get_position(self) -> PoseWithCovarianceStamped | NavSatFix:
        """
        Get drone position according to the flight mode.

        Returns
        -------
        PoseWithCovarianceStamped or NavSatFix
            - Indoor: returns get_vision_pos as PoseWithCovarianceStamped
            - Outdoor: returns get_gps as NavSatFix
        """
        if self.indoor == True:
            return self.get_vision_pos
        else:
            return self.get_gps

    @property
    def get_position_as_target(self) -> PositionTarget | GeoPoseStamped:
        """
        Get drone position as PositionTarget or GeoPoseStamped according to the flight mode.

        Returns
        -------
        PositionTarget or GeoPoseStamped
            - Indoor: returns get_vision_pos as PositionTarget
            - Outdoor: returns get_gps as GeoPoseStamped
        """
        if self.indoor == True:
            return PositionUtils.convert_position_to_target(self.get_vision_pos)
        else:
            return PositionUtils.convert_position_to_target(
                self.get_gps, self.get_heading.data
            )

    @property
    def get_vision_pos(self) -> PoseWithCovarianceStamped:
        """
        Get relative position data.

        Returns
        -------
        PoseWithCovarianceStamped
            Relative position message. See:
            http://docs.ros.org/en/api/geometry_msgs/html/msg/PoseWithCovarianceStamped.html
        """
        return self._vision_pos

    @property
    def get_imu_data(self) -> Imu:
        """
        Get IMU data.

        Returns
        -------
        Imu
            IMU message. See:
            http://docs.ros.org/en/melodic/api/sensor_msgs/html/msg/Imu.html
        """
        return self._imu_data

    @property
    def get_gps(self) -> NavSatFix:
        """
        Get GPS data.

        Returns
        -------
        NavSatFix
            GPS message. See:
            http://docs.ros.org/en/api/sensor_msgs/html/msg/NavSatFix.html
        Raises
        ------
        SensorNotAvailableError
            If called in indoor mode.
        """
        if self.indoor == False:
            return self._gps
        else:
            raise SensorNotAvailableError("GPS", "indoor")

    @property
    def get_rel_alt(self) -> Float64:
        """
        Get relative altitude data from GPS.

        Returns
        -------
        Float64
            Relative altitude message. See:
            http://docs.ros.org/en/api/std_msgs/html/msg/Float64.html
        Raises
        ------
        SensorNotAvailableError
            If called in indoor mode.
        """
        if self.indoor == False:
            return self._rel_alt
        else:
            raise SensorNotAvailableError("Relative altitude", "indoor")

    @property
    def get_heading(self) -> Float64:
        """
        Get heading data.

        Returns
        -------
        Float64
            Heading message. See:
            http://docs.ros.org/en/api/std_msgs/html/msg/Float64.html
        Raises
        ------
        SensorNotAvailableError
            If called in indoor mode.
        """
        if self.indoor == False:
            return self._heading
        else:
            raise SensorNotAvailableError("Heading", "indoor")

    def __startup(self):
        """
        Test the position estimation sensors and get initial values.
        If data cannot be obtained within timeout period, log warnings and continue with default values.
        """
        self.node.get_logger().info("Starting initialization of sensor data...")
        sensors_initialized = False
        start_time = self.node.get_clock().now()
        timeout = Duration(seconds=10.0)

        while self.node.get_clock().now() - start_time < timeout:
            self.node.get_logger().info(
                "Waiting for lidar data...", throttle_duration_sec=1.0
            )
            rclpy.spin_once(self.node, timeout_sec=0.1)  # Process callbacks
            if self.get_rng_alt is not None:
                self._takeoff_height = self.get_rng_alt.range
                self.lidar_on = True
                self.node.get_logger().info("LiDAR data received")
                break

        if self.indoor == True:
            start_time = self.node.get_clock().now()
            while self.node.get_clock().now() - start_time < timeout:
                self.node.get_logger().info(
                    "Waiting for vision pose data...", throttle_duration_sec=1.0
                )
                rclpy.spin_once(self.node, timeout_sec=0.1)  # Process callbacks
                if self.get_vision_pos is not None:
                    sensors_initialized = True
                    self.node.get_logger().info("vSLAM data received")
                    break

            self.initial_altitude = 0.0  # No altitude data in indoor mode
            self.initial_heading = 0.0  # No heading data in indoor mode

        else:
            start_time = self.node.get_clock().now()
            while self.node.get_clock().now() - start_time < timeout:
                self.node.get_logger().info(
                    "Waiting for GPS data...", throttle_duration_sec=1.0
                )
                rclpy.spin_once(self.node, timeout_sec=0.1)  # Process callbacks
                if self.get_gps is not None and self.get_heading is not None:
                    sensors_initialized = True
                    break

            if sensors_initialized == True:
                self.initial_altitude = self._gps.altitude
                self.initial_heading = self._heading.data
            else:
                self.initial_altitude = 0.0
                self.initial_heading = 0.0

        if not self.lidar_on:
            self.node.get_logger().warn("Lidar data not available.")

        if not sensors_initialized:
            self.node.get_logger().warn(
                "Initialization completed with warnings. Some sensors may not be available."
            )
            self.node.get_logger().warn(
                "Check if MAVROS is running and GPS/SLAM is working properly."
            )
            self.node.get_logger().warn("Using default values for missing sensor data.")
        else:
            self.node.get_logger().info(
                "Sensor data initialization completed successfully."
            )
            self.node.get_logger().info(
                f"Initial altitude: {self.initial_altitude}m, Initial heading: {self.initial_heading}°"
            )

    def _call_service(
        self,
        service: Client,
        request: SrvTypeRequest,
        success_message: str,
        failure_message: str,
        sync: bool = False,
    ):
        """
        Auxiliar function to call services and print result.

        Parameters
        ----------
        service : Client
            Service client.
        request : SrvTypeRequest
            Service request.
        success_message : str
            Message to print if success.
        failure_message : str
            Message to print if failure.
        sync : bool, optional
            If True, call the service synchronously, otherwise asynchronously. Synchronous call will block until the service is done.
        """

        def _wait_for_service():
            while not service.wait_for_service(timeout_sec=1.0):
                self.node.get_logger().info(
                    f"Service {service.srv_name} not available, waiting again..."
                )

        def _print_result(result):
            if result is not None:
                self.node.get_logger().info(f"\033[32;1;4m{success_message}\033[0m")
            else:
                self.node.get_logger().error(f"\033[31;1;4m{failure_message}\033[0m")

        def _handle_future(future):
            try:
                result = future.result()
            except Exception as e:
                self.node.get_logger().error(
                    f"Service call failed {service.srv_name}: {str(e)}"
                )
                result = None
            finally:
                _print_result(result)

        _wait_for_service()
        self.node.get_logger().info(
            f"-- Calling service {service.srv_name} | Sync: {sync}"
        )

        if sync:
            result = service.call(request)
            _print_result(result)
        else:
            future = service.call_async(request)
            future.add_done_callback(_handle_future)

    def kill_motors(self):
        """
        Forced disarm.

        Caution: it will disarm even during a flight.
        """
        command = CommandLong.Request()
        command.command = 400
        command.param1 = 0.0
        command.param2 = 0.0
        command.param3 = 0.0
        command.param4 = 0.0
        command.param5 = 21196.0
        command.param6 = 0.0
        command.param7 = 0.0
        self._call_service(
            self._command_srv, command, "-- Motors killed", "-- Kill motors failed"
        )

    def set_mode(self, mode: str):
        """
        Modify the FCU flight mode.

        Parameters
        ----------
        mode : str
            Flight mode (e.g., 'stabilize', 'alt_hold', 'auto', 'guided', 'loiter', 'rtl', 'land', 'guided_nogps').

        See Also
        --------
        https://ardupilot.org/copter/docs/flight-modes.html
        """
        req = SetMode.Request()
        req.custom_mode = mode
        self._call_service(
            self._mode_srv,
            req,
            f"-- Mode set to {mode}",
            f"-- Set mode to {mode} failed",
        )

    def arm(self):
        """
        Send command to arm the drone.
        """
        # self.__startup()
        self.set_mode("GUIDED")
        req = CommandBool.Request()
        req.value = True
        self._call_service(self._arm_srv, req, "-- Armed", "-- Arm failed")

        sleep(1.5)

    def takeoff(self, takeoff_alt: float):
        """
        Send command to takeoff the drone.

        Parameters
        ----------
        takeoff_alt : float
            Altitude to takeoff in meters.
        """
        req = CommandTOL.Request()
        req.altitude = float(takeoff_alt)
        self._call_service(
            self._takeoff_srv,
            req,
            f"-- Takeoff to {takeoff_alt}m",
            f"-- Takeoff failed",
        )

    def arm_takeoff(self, takeoff_alt: float):
        """
        Send command to arm, take off, and hold.

        After calling arm service, waits for 3 seconds, and stores takeoff_position.
        Then, after calling takeoff service, sleeps for `takeoff_alt` seconds.

        Parameters
        ----------
        takeoff_alt : float
            Target takeoff altitude in meters.
        """

        self.arm()

        # Update variables
        sleep_duration = Duration(seconds=3.0)
        sleep_start_t = self.node.get_clock().now()
        while self.node.get_clock().now() - sleep_start_t < sleep_duration:
            rclpy.spin_once(self.node, timeout_sec=0.1)

        self.set_takeoff_position()

        self.takeoff(takeoff_alt)
        sleep(takeoff_alt)

    def land(self):
        """
        Send command to land the drone.
        """
        req = CommandTOL.Request()
        req.altitude = 0.0
        self._call_service(self._land_srv, req, "-- Landed", "-- Land failed")

    def set_home(
        self, current_gps: bool, yaw=0.0, latitude=0.0, longitude=0.0, altitude=0.0
    ):
        """
        Change home position. Could be current position or specified coordinates.

        Parameters
        ----------
        current_gps : bool
            True to set current position as home; False to use provided coordinates.
        yaw : float, optional
            Yaw angle in degrees.
        latitude : float, optional
            Latitude in degrees.
        longitude : float, optional
            Longitude in degrees.
        altitude : float, optional
            Altitude in meters.
        """

        rclpy.spin_once(self.node)
        req = CommandHome.Request()
        req.current_gps = current_gps
        req.yaw = yaw
        req.latitude = latitude
        req.longitude = longitude
        req.altitude = altitude
        self._call_service(
            self._home_srv,
            req,
            "-- Home set",
            "-- Set home failed",
        )

    def set_param(self, param_id: str, param_value: Int64):
        """
        Set a parameter value.

        Parameters
        ----------
        param_id : str
            Parameter name.
        param_value : Int64
            Parameter value.
        """

        value = Parameter()
        value.name = param_id
        value.value.integer_value = param_value.data

        request = SetParameters.Request()
        request.parameters.append(value)

        self._call_service(
            self._param_set_srv,
            request,
            f"-- {param_id} set to {param_value}",
            f"-- Set {param_id} failed",
        )

    def rtl(
        self,
        rtl_alt: float = None,
        precision_radius: float = 0.1,
        rtl_strategy: str = "default",
        land: bool = True,
    ):
        """
        Return-to-Launch (RTL) operation.

        Moves the drone to a specified altitude, then returns to the takeoff position using the selected strategy,
        and lands if specified.

        Parameters
        ----------
        rtl_alt : float, optional
            Target altitude for RTL (meters).
            If None, uses the current altitude.
        precision_radius : float, optional
            Precision radius for reaching the target (meters).
        rtl_strategy : str, optional
            RTL strategy to use ("default", "PID", or "AP").
        land : bool, optional
            Whether to land after reaching the takeoff position.
        """
        self.node.get_logger().info(f"RTL using strategy: {rtl_strategy}")

        if rtl_alt is not None:
            target_alt = rtl_alt - self.get_height

            self.node.get_logger().info(f"Moving drone to rtl_alt: {rtl_alt}")

            self.offboard_position(
                x=0.0,
                y=0.0,
                z=target_alt,
                timeout_sec=None,
                precision_radius=precision_radius,
                strategy="PID",
            )

        if rtl_strategy == "AP":  # ArduPilot RTL

            self.node.get_logger().info(f"Sending RLT command...")

            if rtl_alt is None:
                rtl_alt = self.get_height

            param_value = Int64()
            param_value.data = rtl_alt * 100

            self.set_param("RTL_ALT", param_value=param_value)
            self.delay(1)
            self.set_mode("rtl")

        else:
            if not (rtl_strategy == "default" or rtl_strategy == "PID"):
                self.node.get_logger().warn(
                    f"Unknown rtl_strategy: {rtl_strategy}, using default."
                )

            if self._takeoff_position is None:
                raise TakeoffPositionNotSetError("RTL")

            if self.lidar_on:
                lidar_alt = self.get_rng_alt.range
            else:
                lidar_alt = None

            self.node.get_logger().info(f"Navigating towards takeoff position...")

            self._pose_controller.navigate_PID(
                target_position=self._takeoff_position,
                lidar_target_alt=lidar_alt,
                precision_radius=precision_radius,
                timeout_sec=None,
            )

        if land == True:
            self.node.get_logger().info(f"Sending LAND command...")
            self.land()

    def do_servo(self, aux_out: float, pwm_value: float):
        """
        Send a PWM signal to move a servo motor connected to *aux_out*.

        Parameters
        ----------
        aux_out : float
            Auxiliar port (1-6).
        pwm_value : float
            PWM value (usually between 1000 ~ 2000).
        """

        command = CommandLong.Request()
        command.command = 183
        command.param1 = aux_out + 8.0
        command.param2 = pwm_value
        self._call_service(
            self._command_srv,
            command,
            f"-- Servo {aux_out} set to {pwm_value}",
            f"-- Set servo {aux_out} failed",
        )

    def offboard_position_gps_coords(
        self,
        latitude: float = 0.0,
        longitude: float = 0.0,
        altitude: float | None = None,
        lidar_altitude: float | None = None,
        heading: float | None = None,
        precision_radius: float = 0.5,
        timeout_sec: float | None = 60.0,
        strategy: str = "default",
    ):
        """
        Move the drone to a specified GPS coordinate using closed-loop control.

        Parameters
        ----------
        latitude : float
            Target latitude in degrees.

        longitude : float
            Target longitude in degrees.

        altitude : float or None
            Target altitude in meters (absolute, not relative to takeoff).

            If None, uses the current altitude.

        lidar_altitude : float or None
            Desired altitude above ground level (meters), limited to 15m.

            If provided, the drone will use lidar data (ONLY USED IN PID STRATEGY).

            This overrides the altitude parameter unless the requested height exceeds 15m.

        heading : float or None
            Desired heading in degrees (0 = North, clockwise positive).

            If None, maintains current heading.

        precision_radius : float
            Acceptable radius (meters) for reaching the target position.

        timeout_sec : float or None
            Maximum time allowed (seconds) to reach the target.

            If None, no timeout is applied.

        strategy : str
            Position control strategy:

            - "default": Use position setpoint messages.

            - "PID": Use closed-loop PID control to reach the target position.
        """
        if self.indoor == True:
            raise InvalidModeError("GPS coordinate navigation", "indoor", "outdoor")

        if heading is None:
            heading = self.get_heading.data
        if altitude is None:
            altitude = self.get_gps.altitude

        gps_setpoint = GeoPoseStamped()
        gps_setpoint.pose.position.latitude = latitude
        gps_setpoint.pose.position.longitude = longitude
        gps_setpoint.pose.position.altitude = altitude
        [qx, qy, qz, qw] = quaternion_from_euler(0, 0, np.radians(heading))

        gps_setpoint.pose.orientation.x = qx
        gps_setpoint.pose.orientation.y = qy
        gps_setpoint.pose.orientation.z = qz
        gps_setpoint.pose.orientation.w = qw

        if strategy == "mavros":
            self._pose_controller.navigate_gps_msg(
                gps_setpoint=gps_setpoint,
                precision_radius=precision_radius,
                timeout_sec=timeout_sec,
            )

        else:
            if strategy != "default" and strategy != "PID":
                self.node.get_logger().warn(
                    f"Unknown strategy {strategy}, using default."
                )
            self._pose_controller.navigate_PID(
                target_position=gps_setpoint,
                lidar_target_alt=lidar_altitude,
                precision_radius=precision_radius,
                timeout_sec=timeout_sec,
            )

    def offboard_position(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        ground_reference: bool = False,
        precision_radius: float = 0.5,
        timeout_sec: float | None = 60.0,
        strategy: str = "default",
    ):
        """
        Move the drone to a position relative to its current location and heading.

        The movement is relative to the drone's current orientation:
        - x-axis: forward/backward relative to drone's heading
        - y-axis: right/left relative to drone's heading
        - z-axis: up/down relative to current altitude

        Parameters
        ----------
        x : float
            Distance to move forward (+) or backward (-) in meters.

        y : float
            Distance to move right (+) or left (-) in meters.

        z : float
            Distance to move up (+) or down (-) in meters.

        ground_reference : bool
            If True, x, y and z are relative to the takeoff_position (ground reference).
            Requires set_takeoff_position() or arm_takeoff() to be called first.

        precision_radius : float
            Acceptable radius in meters for reaching the target position.

        timeout_sec : float, optional
            Maximum time in seconds to reach the target position.
            If None, no timeout is applied.

        strategy : str
            Position control strategy:

            - "default": Use PID control with position setpoints
            - "PID": Use closed-loop PID control to reach the target position
            - "mavros": Use MAVROS position setpoint messages

        Raises
        ------
        RuntimeError
            If called in indoor mode with GPS coordinates (should not happen).
        """
        start_t = self.node.get_clock().now()
        sleep_duration = Duration(seconds=0.05)
        while self.node.get_clock().now() - start_t < sleep_duration:
            rclpy.spin_once(
                self.node, timeout_sec=0.05
            )  # Process callbacks to get latest position

        if self.indoor == False:
            if ground_reference == False:
                heading = self.get_heading.data
                lat, lon, alt = GPSCalculate.calculate_gps_offset(
                    x=x,
                    y=-y,
                    z=z,
                    latitude=self.get_gps.latitude,
                    longitude=self.get_gps.longitude,
                    altitude=self.get_gps.altitude,
                    heading=heading,
                )

            else:
                if self._takeoff_position is None:
                    raise TakeoffPositionNotSetError("ground_reference=True")
                heading = np.degrees(
                    PositionUtils.get_yaw_from_pose(
                        self._takeoff_position.pose.orientation
                    )
                )
                lat, lon, alt = GPSCalculate.calculate_gps_offset(
                    x=x,
                    y=-y,
                    z=z,
                    latitude=self._takeoff_position.pose.position.latitude,
                    longitude=self._takeoff_position.pose.position.longitude,
                    altitude=self._takeoff_position.pose.position.altitude,
                    heading=heading,
                )

            self.node.get_logger().info(
                f"Moving to GPS position: {lat}, {lon}, {alt}, {heading}"
            )

            if strategy == "PID" and self.lidar_on == True:
                print(f"lidar para setar: {self.get_rng_alt.range}")
                lidar_target_alt = self.get_rng_alt.range + z
            else:
                lidar_target_alt = None

            self.offboard_position_gps_coords(
                latitude=lat,
                longitude=lon,
                altitude=alt,
                lidar_altitude=lidar_target_alt,
                heading=heading,
                precision_radius=precision_radius,
                timeout_sec=timeout_sec,
                strategy=strategy,
            )

        else:
            if ground_reference == False:
                current_position = self.get_vision_pos.pose.pose.position
                current_yaw_rad = PositionUtils.get_yaw_from_pose(self.get_vision_pos)
            else:
                if self._takeoff_position is None:
                    raise TakeoffPositionNotSetError("ground_reference=True")
                current_position = self._takeoff_position.position
                current_yaw_rad = self._takeoff_position.yaw
            dx_world = x * math.cos(current_yaw_rad) - y * math.sin(current_yaw_rad)
            dy_world = x * math.sin(current_yaw_rad) + y * math.cos(current_yaw_rad)
            dz_world = z

            # Prepares pose message (keeping current orientation)
            pose_msg = PositionTarget()
            pose_msg.header.frame_id = "map"
            pose_msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED

            # Mask: ignores acceleration and yaw rate values
            pose_msg.type_mask = (
                PositionTarget.IGNORE_AFX
                | PositionTarget.IGNORE_AFY
                | PositionTarget.IGNORE_AFZ
                | PositionTarget.IGNORE_YAW_RATE
                | PositionTarget.IGNORE_VX
                | PositionTarget.IGNORE_VY
                | PositionTarget.IGNORE_VZ
            )

            pose_msg.position.x = current_position.x + dx_world
            pose_msg.position.y = current_position.y + dy_world
            pose_msg.position.z = current_position.z + dz_world
            pose_msg.yaw = current_yaw_rad

            if self.lidar_on == True:
                lidar_target_alt = self.get_rng_alt.range + z
            else:
                lidar_target_alt = None

            if strategy == "mavros":
                self._pose_controller.navigate_local_msg(
                    target_position=pose_msg,
                    precision_radius=precision_radius,
                    timeout_sec=timeout_sec,
                )

            else:
                if strategy != "default" and strategy != "PID":
                    self.node.get_logger().warn(
                        f"Unknown strategy {strategy}, using default."
                    )
                self._pose_controller.navigate_PID(
                    target_position=pose_msg,
                    lidar_target_alt=lidar_target_alt,
                    precision_radius=precision_radius,
                    timeout_sec=timeout_sec,
                )

    def offboard_gps_position(
        self,
        lat_setpoint: float = 0.0,
        lon_setpoint: float = 0.0,
        alt_setpoint: float = 0.0,
        heading: float = 0.0,
        precision_radius: float = 0.1,
        wait: bool = True,
        timeout_sec: float | None = 60.0,
        check_rate_hz: float = 10.0,
        initial_heading: bool = False,
    ):
        """
        Deprecated. Use offboard_position_gps_coords instead.

        Move sending a GPS coordinate setpoint

        :param lat_setpoint (float): Latitude setpoint
        :param lon_setpoint (float): Longitude setpoint
        :param alt_setpoint (float): Altitude setpoint (meters AGL)
        :param heading (float): Heading setpoint (degrees refered to North)
        :param precision_radius (float): Precision radius setpoint (meters)
        :param initial_heading (bool): True for keep initial heading value, False for value passed
        """

        self.node.get_logger().warn(
            "offboard_gps_position is deprecated. Use offboard_position_gps_coords instead."
        )

        self.node.get_logger().info(
            f"-- Moving to GPS position: {lat_setpoint}, {lon_setpoint}, {alt_setpoint}, {heading}"
        )
        self.gps_controller.gps_send(
            lat_setpoint,
            lon_setpoint,
            alt_setpoint,
            heading,
            precision_radius,
            wait,
            timeout_sec,
            check_rate_hz,
        )

    def offboard_velocity(
        self,
        linear_x: float = 0.0,
        linear_y: float = 0.0,
        linear_z: float = 0.0,
        angular_z: float = 0.0,
        ground_reference: bool = False,
    ):
        """
        Move sending velocity commands

        Parameters
        ----------
        linear_x: float (m/s)
            (+)Move forward

            (-)Move backward

        linear_y: float (m/s)
            (+)Move left

            (-)Move right

        linear_z: float (m/s)
            (+)Move up

            (-)Move down

        angular_z: float
            (+)Rotate counter clockwise

            (-)Rotate clockwise

        ground_reference: Bool
            (True)Groud reference

            (False)Body reference
        """
        vel_msg = PositionTarget()

        if ground_reference:
            vel_msg.coordinate_frame = 1
        else:
            vel_msg.coordinate_frame = 8

        vel_msg.type_mask = 1479

        vel_msg.velocity.x = linear_x
        vel_msg.velocity.y = linear_y
        vel_msg.velocity.z = linear_z
        vel_msg.yaw_rate = angular_z

        self.local_pub.publish(vel_msg)

    def offboard_velocity_timer(
        self,
        linear_x: float = 0.0,
        linear_y: float = 0.0,
        linear_z: float = 0.0,
        angular_z: float = 0.0,
        ground_reference: bool = False,
        pub_rate: int = 30,
        time: float = 0,
    ):
        """
        Move sending velocity commands

        Parameters
        ----------
        linear_x: float (m/s)
            (+)Move forward

            (-)Move backward

        linear_y: float (m/s)
            (+)Move left

            (-)Move right

        linear_z: float (m/s)
            (+)Move up

            (-)Move down

        angular_z: float
            (+)Rotate counter clockwise

            (-)Rotate clockwise

        ground_reference: Bool
            (True)Groud reference

            (False)Body reference

        time: float (seconds)
            Movement time duration
        """
        t_start = t_now = self.node.get_clock().now()

        duration = Duration(seconds=time)
        # rate = self.node.create_rate(pub_rate, self.node.get_clock())
        rate = 1.0 / pub_rate

        self.node.get_logger().info("-- Movement start")

        while t_now <= t_start + duration:
            self.offboard_velocity(
                linear_x, linear_y, linear_z, angular_z, ground_reference
            )
            self.delay(rate)
            t_now = self.node.get_clock().now()

        self.node.get_logger().info(
            "-- Moviment end - time: {:.4f} s".format(
                (t_now - t_start).nanoseconds / 1000000000
            )
        )

    def image_viewer(self):
        """
        Init Image Handler with raspicam image_raw topic and show the image.
        """
        self.image_handler = ImageHandler(
            node=self.node,
            image_source="/image_raw",
            image_processing_callback=None,
            show_result="Raspicam Viewer",
        )
        self.image_handler.run()

    def record(self, record):
        """
        Not implemented.

        Parameters
        ----------
        record : any
            Placeholder parameter.
        """
        pass

    def snapshot(self):
        """
        Not implemented.
        """
        pass

    def set_takeoff_position(
        self,
        pose: Optional[
            PoseWithCovarianceStamped | NavSatFix | PositionTarget | GeoPoseStamped
        ] = None,
        heading: Optional[float] = None,
    ):
        """
        Sets the takeoff position for Return-To-Launch (RTL) and Ground Referenced operations.

        Parameters
        ----------
        pose : PoseWithCovarianceStamped, NavSatFix, PositionTarget, or GeoPoseStamped, optional
            The takeoff position object.
        heading : float, optional
            Heading to use for NavSatFix.
        """
        if pose is None:
            self._takeoff_position = self.get_position_as_target
            self.node.get_logger().info("Takeoff position set to current position.")
            return

        if self.indoor == True:
            if isinstance(pose, PoseWithCovarianceStamped):
                self._takeoff_position = PositionUtils.convert_position_to_target(pose)
                return

            elif isinstance(pose, PositionTarget):
                self._takeoff_position = pose
                return

            else:
                raise ValueError(
                    "In indoor mode, pose parameter must be of type PoseWithCovarianceStamped or PositionTarget"
                )

        else:
            if isinstance(pose, NavSatFix) and heading is not None:
                self._takeoff_position = PositionUtils.convert_position_to_target(
                    pose, heading
                )
                return

            elif isinstance(pose, GeoPoseStamped):
                self._takeoff_position = pose
                return

            else:
                raise ValueError(
                    "In outdoor mode, pose parameter must be of type GeoPoseStamped or NavSatFix with heading specified"
                )

    def set_pid_config(self, config: str | dict | "PositionPIDConfig"):
        """
        Set PID configuration for position control.

        Parameters
        ----------
        config : str, dict, or PositionPIDConfig
            PID configuration. Can be:
            - str: Path to YAML configuration file
            - dict: Dictionary with x, y, z PID parameters
            - PositionPIDConfig: Direct configuration object

        Examples
        --------
        From file:
        >>> drone.set_pid_config("/path/to/config.yaml")

        From dict:
        >>> drone.set_pid_config({
        ...     "x": {"kp": 0.5, "output_min": -0.5, "output_max": 0.5},
        ...     "y": {"kp": 0.5, "output_min": -0.5, "output_max": 0.5},
        ...     "z": {"kp": 0.3, "output_min": -0.2, "output_max": 0.2}
        ... })

        From object:
        >>> from mirela_sdk.control.pid import PositionPIDConfig, PIDConfig
        >>> config = PositionPIDConfig(
        ...     x=PIDConfig(kp=0.5, output_min=-0.5, output_max=0.5),
        ...     y=PIDConfig(kp=0.5, output_min=-0.5, output_max=0.5),
        ...     z=PIDConfig(kp=0.3, output_min=-0.2, output_max=0.2)
        ... )
        >>> drone.set_pid_config(config)
        """
        from mirela_sdk.control.pid import PositionPIDConfig, PIDConfig

        if isinstance(config, str):
            # Load from YAML file
            pid_config = PositionPIDConfig.from_yaml(config)
        elif isinstance(config, dict):
            # Create from dictionary
            pid_config = PositionPIDConfig(
                x=PIDConfig.from_dict(config.get("x", {})),
                y=PIDConfig.from_dict(config.get("y", {})),
                z=PIDConfig.from_dict(config.get("z", {})),
            )
        elif isinstance(config, PositionPIDConfig):
            # Use directly
            pid_config = config
        else:
            raise TypeError(
                f"config must be str, dict, or PositionPIDConfig, got {type(config)}"
            )

        # Update position controller configuration
        self._pose_controller.set_pid_config(pid_config)
        self.node.get_logger().info("PID configuration updated")

    def delay(self, seconds: float):
        """
        Simple delay function that allows processing of callbacks.

        Parameters
        ----------
        seconds : float
            Time to delay in seconds.
        """
        duration = Duration(seconds=seconds)
        start_time = self.node.get_clock().now()
        while (self.node.get_clock().now() - start_time) < duration:
            rclpy.spin_once(self.node, timeout_sec=0.1)
