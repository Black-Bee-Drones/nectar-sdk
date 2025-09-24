import numpy as np

from typing import Optional

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
from geometry_msgs.msg import TwistStamped, PoseStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix, Range, Imu
from rcl_interfaces.msg import Parameter
from rcl_interfaces.srv import SetParameters

from mirela_sdk.control.mavros.gps_controller import GPSController
from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.control.drone import Drone
from mirela_sdk.control.mavros.precision_landing import PrecisionLanding
from mirela_sdk.control.mavros.position_controller import PositionController
from mirela_sdk.utils.process import ProcessUtils
from mirela_sdk.utils.gps_calculate import GPSCalculate

from tf_transformations import quaternion_from_euler
from tf_transformations import euler_from_quaternion

INDOOR = 0.3
OUTDOOR = 1.6

class MavDrone(Drone):
    """
    Class to control the mav ros drone using ROS2.
    """

    def __init__(self, node: Node, mavros: bool = False, indoor: bool = False) -> None:
        """
        Initialize the Mavros API

        :param node (Node): ROS2 node to run the API
        :param mavros (bool): True to start the mavros node
        """
        super().__init__(node=node)

        # Variables:
        self.indoor = indoor
        self.lidar_on = False
        self._state = State()
        self._rng_alt = None
        self._local_pos = None
        self._vel_body = TwistStamped()
        self._imu_data = Imu()
        self._takeoff_position = PositionTarget()
        self._takeoff_height = None
        self._home_position_set = False
        self._pose_controller = PositionController(self)
        
        # Outdoor only variables:
        if self.indoor == False:
            self._heading = None()
            self._gps = None
            self._rel_alt = Float64()
            self._takeoff_position = GeoPoseStamped()

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
        self._local_pos_sub = self._create_subscriber(
            PoseStamped,
            "/mavros/local_position/pose",
            lambda data: self.__setattr__("_local_pos", data),
            qos_profile_sensor_data,
        )
        self._vel_body_sub = self._create_subscriber(
            TwistStamped,
            "/mavros/local_position/velocity_body",
            lambda data: self.__setattr__("_vel_body", data),
            qos_profile_sensor_data,
        )
        self._imu_data_sub = self._create_subscriber(
            Imu,
            "/mavros/imu/data",
            lambda data: self.__setattr__("_imu_data", data),
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
        Start the mavros launch
            ros2 launch mavros apm.launch fcu_url:=serial:///dev/ttyUSB0:57600
        """

        # Start the ros2 launch mavros apm
        result = ProcessUtils.start_process(
            "ros2 launch mavros apm.launch fcu_url:=serial:///dev/ttyUSB0:57600",
            "mavros_node",
        )
        self._driver_initialized = result

    def get_driver_node_name(self) -> str:
        return "mavros_node"

    @property
    def get_state(self) -> State:
        """
        Return state data

        State
        ----------
        http://docs.ros.org/en/api/mavros_msgs/html/msg/State.html
        """
        return self._state

    @property
    def get_rng_alt(self) -> Range:
        """
        Return relative altitude data from lidar

        Range
        ----------
        http://docs.ros.org/en/melodic/api/sensor_msgs/html/msg/Range.html
        """
        return self._rng_alt
    
    @property
    def get_position(self) -> PoseStamped | NavSatFix:
        """
        Return drone position according to the flight mode.

        Indoor mode: returns get_local_pos

        Outdoor mode: returns get_gps
        """
        if self.indoor == True:
            return self.get_local_pos
        
        else:
            return self.get_gps

    @property
    def get_local_pos(self) -> PoseStamped:
        """
        Return relative position data

        PoseStamped
        ----------
        http://docs.ros.org/en/api/geometry_msgs/html/msg/PoseStamped.html
        """
        return self._local_pos

    @property
    def get_vel_body(self) -> TwistStamped:
        """
        Return body velocity

        TwistStamped
        ------------
        http://docs.ros.org/en/melodic/api/geometry_msgs/html/msg/TwistStamped.html
        """

        return self._vel_body

    @property
    def get_imu_data(self) -> Imu:
        """
        Return imu data

        Imu
        ------------
        http://docs.ros.org/en/melodic/api/sensor_msgs/html/msg/Imu.html
        """

        return self._imu_data
    
    @property
    def get_gps(self) -> NavSatFix:
        """
        Return gps data

        NavSatFix
        ----------
        http://docs.ros.org/en/api/sensor_msgs/html/msg/NavSatFix.html
        """
        if self.indoor == False: 
            return self._gps
        else:
            raise AttributeError("GPS data not available in indoor mode.")

    @property
    def get_rel_alt(self) -> Float64:
        """
        Return relative altitude data from gps

        Float64
        ----------
        http://docs.ros.org/en/api/std_msgs/html/msg/Float64.html
        """
        if self.indoor == False:
            return self._rel_alt
        else:
            raise AttributeError("Relative altitude data not available in indoor mode.")

    @property
    def get_heading(self) -> Float64:
        """
        Return heading data

        Float64
        ----------
        http://docs.ros.org/en/api/std_msgs/html/msg/Float64.html
        """
        if self.indoor == False:
            return self._heading
        else:
            raise AttributeError("Heading data not available in indoor mode.")

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
                self.node.get_logger().info("Waiting for lidar data...", throttle_duration_sec=1.0)
                rclpy.spin_once(self.node, timeout_sec=0.1)  # Process callbacks
                if self.get_rng_alt is not None:
                    self._takeoff_height = self.get_rng_alt.range
                    self.lidar_on = True
                    break

        if self.indoor == True:
            start_time = self.node.get_clock().now()
            while self.node.get_clock().now() - start_time < timeout:
                self.node.get_logger().info("Waiting for local position data...", throttle_duration_sec=1.0)
                rclpy.spin_once(self.node, timeout_sec=0.1)  # Process callbacks
                if self.get_local_pos is not None:
                    sensors_initialized = True
                    break

            self.initial_altitude = 0.0 # No altitude data in indoor mode
            self.initial_heading = 0.0  # No heading data in indoor mode
        
        else:
            start_time = self.node.get_clock().now()
            while self.node.get_clock().now() - start_time < timeout:
                self.node.get_logger().info("Waiting for GPS data...", throttle_duration_sec=1.0)
                rclpy.spin_once(self.node, timeout_sec=0.1)  # Process callbacks
                if self.get_gps.altitude is not None and self.get_heading.data is not None:
                    sensors_initialized = True
                    break

            self.initial_altitude = self._gps.altitude
            self.initial_heading = self._heading.data

        if self.lidar_on == True:
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

    @staticmethod
    def _convert_position_to_target(pose: PoseStamped|NavSatFix) -> PositionTarget|GeoPoseStamped:
        """
        Converts objects, ignoring orientation:

        PoseStamped -> PositionTarget

        NavSatFix -> GeoPoseStamped
        """
        if isinstance(pose, PoseStamped):
            msg = PositionTarget()
            msg.position.x = pose.pose.position.x
            msg.position.y = pose.pose.position.y
            msg.position.z = pose.pose.position.z
            return msg
            
        elif isinstance(pose, NavSatFix):
            msg = GeoPoseStamped()
            msg.pose.position.latitude = pose.latitude
            msg.pose.position.longitude = pose.longitude
            msg.pose.position.altitude = pose.altitude
            return msg
        
        else:
            raise ValueError("pose parameter must be of type PoseStamped or NavSatFix")
        

    def _call_service(
        self,
        service: Client,
        request: SrvTypeRequest,
        success_message: str,
        failure_message: str,
        sync: bool = False,
    ):
        """
        to-do: rclpy.spin_until_future_complete?

        Auxiliar function to call services and print result.

        :param service (Client): Service client
        :param request (Request): Service request
        :param success_message (str): Message to print if success
        :param failure_message (str): Message to print if failure
        :param sync: If True, call the service synchronously, otherwise asynchronously.
            Synchoronous call will block the code until the service is done
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
        Forced disarm

        Caution: it will disarm even during a flight
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
        https://ardupilot.org/copter/docs/flight-modes.html

        :param mode (strig): (stabilize, alt_hold ,auto, guided, loiter, rtl, land, guided_nogps)
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

        :param takeoff_alt (float): Altitude to takeoff
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
        Send command to arm, take off and hold

        After calling arm service, waits for 3 seconds, and stores takeoff_position

        Then, after calling takeoff service, sleeps for [takeoff_alt] seconds

        Parameters
        ----------
        takeoff_alt: float (meters)
        """

        self.arm()

        # Store the takeoff position for custom RTL strategy
        self._home_position_set = True

        # Update variables
        sleep_duration = Duration(seconds=3.0)
        sleep_start_t = self.node.get_clock().now()
        while self.node.get_clock().now() - sleep_start_t < sleep_duration:
            rclpy.spin_once(self.node, timeout_sec=0.1)
        
        self._takeoff_position = self._convert_position_to_target(self.get_position)
        
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
        Change home position. Could be current position or a specified coordinates

        :param current_gps (bool): True to set current position as home
                                   False, enter the reaming parameters

        :param yaw (float): Yaw angle in degrees
        :param latitude (float): Latitude in degrees
        :param longitude (float): Longitude in degrees
        :param altitude (float): Altitude in meters
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
        Set a parameter value

        :param param_id (str): Parameter name
        :param param_value (Int64): Parameter value
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
        rtl_alt: int = 10,
        precision_landing: bool = False,
        aruco_target: int = 800,
        rtl_strategy: str = "default",
    ):
        """
        Deprecate this method

        Send return to launch command using the selected strategy.

        The copter will first rise to RTL_ALT before returning home or maintain the current
        altitude if the current altitude is higher than RTL_ALT. The default value for RTL_ALT is 15m.

        Parameters
        ----------
        param rtl_alt (int): altitude in meters to rtl mode
        param precision_landing (bool): run precision_landing when the drone start the land or not
        param aruco_target (int): the ArUco marker id to do the precision landing
        param rtl_strategy (str): RTL strategy to use:
            - "default": Use ArduPilot's built-in RTL mode
            - "set_home": Set home to current GPS position and then use RTL
            - "gps_return": Return to takeoff position using offboard_gps_position
            - "gps_current_alt": Return to takeoff position maintaining current altitude
        """
        self.node.get_logger().info(f"RTL using strategy: {rtl_strategy}")

        if rtl_strategy == "default":
            # Default ArduPilot RTL mode
            param_value = Int64()
            param_value.data = rtl_alt * 100

            self.set_param("RTL_ALT", param_value=param_value)
            self.delay(1)
            self.set_mode("rtl")

        elif rtl_strategy == "set_home":
            # Set home to current position then RTL
            current_lat = self.get_gps.latitude
            current_lon = self.get_gps.longitude
            current_alt = self.get_gps.altitude
            current_heading = self.get_heading.data

            self.node.get_logger().info(
                f"Setting home to current position: {current_lat}, {current_lon}, {current_alt}, {current_heading}"
            )

            self.set_home(
                current_gps=False,
                yaw=current_heading,
                latitude=current_lat,
                longitude=current_lon,
                altitude=current_alt,
            )

            self.delay(1)

            param_value = Int64()
            param_value.data = rtl_alt * 100
            self.set_param("RTL_ALT", param_value=param_value)
            self.delay(1)
            self.set_mode("rtl")

        elif rtl_strategy == "gps_return" or rtl_strategy == "gps_current_alt":
            # Return to takeoff position using GPS control
            if not self._home_position_set:
                self.node.get_logger().error(
                    "Cannot use GPS return strategy: takeoff position not stored"
                )
                self.set_mode("rtl")  # Fallback to default RTL
            else:
                self.node.get_logger().info(
                    f"Returning to takeoff position: Lat {self._takeoff_lat}, Lon {self._takeoff_lon}"
                )

                # If gps_current_alt strategy, use current altitude, otherwise use takeoff altitude
                return_alt = (
                    self.get_rel_alt.data
                    if rtl_strategy == "gps_current_alt"
                    else self._takeoff_position.altitude
                )

                # First climb to return altitude if needed
                current_alt = self.get_rel_alt.data
                if return_alt > current_alt:
                    self.node.get_logger().info(
                        f"Climbing to return altitude: {return_alt}m"
                    )
                    self.offboard_velocity_timer(
                        0.0, 0.0, 0.5, 0.0, False, 30, (return_alt - current_alt) / 0.5
                    )

                # Then return to takeoff position
                self.offboard_gps_position(
                    lat_setpoint=self._takeoff_position.latitude,
                    lon_setpoint=self._takeoff_position.longitude,
                    alt_setpoint=return_alt,
                    heading=self._takeoff_heading,
                    precision_radius=1.0,
                )

                # After reaching position, land
                self.delay(10)  # Give time to reach the position
                self.land()
        else:
            self.node.get_logger().error(f"Unknown RTL strategy: {rtl_strategy}")
            # Fallback to default RTL
            param_value = Int64()
            param_value.data = rtl_alt * 100
            self.set_param("RTL_ALT", param_value=param_value)
            self.delay(1)
            self.set_mode("rtl")

        if precision_landing:
            PrecisionLanding(self, self.node, False, aruco_target)

    def do_servo(self, aux_out: float, pwm_value: float):
        """
        Send a PWM signal to moviment a servo motor connected *aux_out*

        :param aux_out (float): Auxiliar port (1-6)
        :param pwm_value (float): PWM value (usually between 1000 ~ 2000)
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
            strategy: str = "default"
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
            raise RuntimeError("offboard_position with GPS coordinates cannot be used in indoor mode.")
        
        if heading is None: heading = self.get_heading.data
        if altitude is None: altitude = self.get_gps.altitude

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
                timeout_sec=timeout_sec
            )
            
        else:
            if strategy != "default" and strategy != "PID":
                self.node.get_logger().warn(f"Unknown strategy {strategy}, using default.")
            self._pose_controller.navigate_PID(
                target_position=gps_setpoint,
                lidar_target_alt=lidar_altitude,
                precision_radius=precision_radius,
                timeout_sec=timeout_sec
            )

    def offboard_position(
            self,
            x: float = 0.0,
            y: float = 0.0,
            z: float = 0.0,
            precision_radius: float = 0.5,
            timeout_sec: float | None = 60.0,
            strategy: str = "default"
    ):
        """
        NEEDS REVISION!
        Move sending a local position setpoint

        Parameters
        ----------

        x : float (meters)
            (+) Forward

            (-) Backward

        y : float (meters)
            (+) Left
            
            (-) Right

        z : float (meters)
            (+) Up

            (-) Down

        precision_radius : float (meters)
            Radius of the precision

        timeout_sec : float|None (seconds)
            Timeout in seconds to reach the position.

            If None, no timeout.

        strategy : str
            Position control strategy:
                - "default": Use position setpoint messages
                - "PID": Use closed loop PID control to reach the target position        

        """
        start_t = self.node.get_clock().now()
        sleep_duration = Duration(seconds=0.05)
        while self.node.get_clock().now() - start_t < sleep_duration:
            rclpy.spin_once(self.node, timeout_sec=0.05)  # Process callbacks to get latest position

        if self.indoor == False:
            lat, lon, alt = GPSCalculate.calculate_gps_offset(
                x=x, y=-y, z=z,
                latitude=self.get_gps.latitude,
                longitude=self.get_gps.longitude,
                altitude=self.get_gps.altitude,
                heading=self.get_heading.data
            )

            heading = self.get_heading.data
            self.node.get_logger().info(f"Moving to GPS position: {lat}, {lon}, {alt}, {heading}")

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
                strategy=strategy
            )

        else:
            current_position = self.get_local_pos.pose.position
            orientation = self.get_local_pos.pose.orientation
            quat = [orientation.x, orientation.y, orientation.z, orientation.w]
            current_yaw_rad = euler_from_quaternion(quat)[2]
            dx_world = x * math.cos(current_yaw_rad) - y * math.sin(current_yaw_rad)
            dy_world = x * math.sin(current_yaw_rad) + y * math.cos(current_yaw_rad)
            dz_world = z

            #Prepares pose message (keeping current orientation)
            pose_msg = PositionTarget()
            pose_msg.header.frame_id = 'map'
            pose_msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED

            #Mask: ignores acceleration and yaw rate values
            pose_msg.type_mask = (
                PositionTarget.IGNORE_AFX |
                PositionTarget.IGNORE_AFY |
                PositionTarget.IGNORE_AFZ |
                PositionTarget.IGNORE_YAW_RATE|
                PositionTarget.IGNORE_VX|
                PositionTarget.IGNORE_VY|
                PositionTarget.IGNORE_VZ
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
                    timeout_sec=timeout_sec
                )
                
            else:
                if strategy != "default" and strategy != "PID":
                    self.node.get_logger().warn(f"Unknown strategy {strategy}, using default.")
                self._pose_controller.navigate_PID(
                    target_position=pose_msg,
                    lidar_target_alt=lidar_target_alt,
                    precision_radius=precision_radius,
                    timeout_sec=timeout_sec
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
        todo: add new offboard_position, and deprecate this one

        Move sending a GPS coordinate setpoint

        :param lat_setpoint (float): Latitude setpoint
        :param lon_setpoint (float): Longitude setpoint
        :param alt_setpoint (float): Altitude setpoint (meters AGL)
        :param heading (float): Heading setpoint (degrees refered to North)
        :param precision_radius (float): Precision radius setpoint (meters)
        :param initial_heading (bool): True for keep initial heading value, False for value passed
        """

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
            Moviment time duration
        """
        t_start = t_now = self.node.get_clock().now()

        duration = Duration(seconds=time)
        # rate = self.node.create_rate(pub_rate, self.node.get_clock())
        rate = 1.0 / pub_rate

        self.node.get_logger().info("-- Moviment start")

        while t_now <= t_start + duration:
            self.offboard_velocity(
                linear_x, linear_y, linear_z, angular_z, ground_reference
            )
            sleep(rate)
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
        pass

    def snapshot(self):
        pass

    def set_takeoff_position(self, pose: Optional[PoseStamped|NavSatFix] = None):
        """
        Sets the takeoff position for custom Return-To-Launch (RTL) operations. 
        This method is intended for outdoor use only and requires a valid NavSatFix object.

        Parameters
        ----------
        pose : NavSatFix
            NavSatFix object containing latitude, longitude, and altitude of the takeoff position.
        """
        if pose == None:
            self._takeoff_position = self._convert_position_to_target(self.get_position)

        if self.indoor == True:
            if not isinstance(pose, PoseStamped):
                raise ValueError("In indoor mode, pose parameter must be of type PoseStamped")
                          
            else:
                self._takeoff_position = self._convert_position_to_target(pose)

        else:
            if not isinstance(pose, NavSatFix):
                raise ValueError("In outdoor mode, pose parameter must be of type NavSatFix")
                          
            else:
                self._takeoff_position = self._convert_position_to_target(pose)

        self._home_position_set = True

    def custom_rtl(self):
        """
        Perform a custom return-to-launch (RTL) maneuver.

        The drone will ascend to the takeoff altitude, then navigate to the
        takeoff latitude and longitude, and finally descend to the takeoff
        altitude.
        """

        if not self._home_position_set:
            self.node.get_logger().warn(
                "Home position not set, using current position."
            )
            # If home position is not set, use current position as home
            home_lat = self.get_gps.latitude
            home_lon = self.get_gps.longitude
            home_alt = self.get_rng_alt.range
            home_heading = self.get_heading.data

            self.set_takeoff_position(home_lat, home_lon, home_alt, home_heading)

        # Ascend to takeoff altitude
        self.node.get_logger().info(
            f"Ascending to takeoff altitude: {self._takeoff_alt}m"
        )
        self.offboard_velocity_timer(
            linear_z=0.5, time=(self._takeoff_alt / 0.5)
        )  # Ascend at 0.5 m/s

        # Navigate to takeoff position
        self.node.get_logger().info(
            f"Navigating to takeoff position: {self._takeoff_lat}, {self._takeoff_lon}"
        )
        self.gps_controller.gps_send(
            self._takeoff_lat,
            self._takeoff_lon,
            self._takeoff_alt,
            self._takeoff_heading,
            precision_radius=0.5,
        )

        # Descend to takeoff altitude
        self.node.get_logger().info(
            f"Descending to takeoff altitude: {self._takeoff_alt}m"
        )
        self.offboard_velocity_timer(
            linear_z=-0.5, time=(self._takeoff_alt / 0.5)
        )  # Descend at 0.5 m/s

        # Land
        self.node.get_logger().info("Landing...")
        self.land()

        self.node.get_logger().info("Custom RTL completed.")

    def delay(self, seconds: float):
        """
        Simple delay function that allows processing of callbacks.

        :param seconds (float): Time to delay in seconds
        """
        start_time = self.node.get_clock().now()
        while (self.node.get_clock().now() - start_time).nanoseconds / 1e9 < seconds:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            sleep(0.1)
