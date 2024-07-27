import rclpy
from rclpy.node import Node
from rclpy.client import Client
from rclpy.service import SrvTypeRequest
from rclpy.duration import Duration
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy

from mavros_msgs.srv import (
    SetMode,
    CommandBool,
    CommandTOL,
    CommandHome,
    CommandLong,
    ParamSetV2,
)
from time import sleep

from mavros_msgs.msg import State, PositionTarget, GlobalPositionTarget, ParamValue
from std_msgs.msg import Float64, Int64
from geometry_msgs.msg import TwistStamped, PoseStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix, Range
from rcl_interfaces.msg import ParameterValue

from mirela_sdk.control.mavros.gps_controller import GPSController
from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.control.drone import Drone
from mirela_sdk.control.mavros.precision_landing import PrecisionLanding
from mirela_sdk.utils.process import ProcessUtils


class MavDrone(Drone):
    """
    Class to control the mav ros drone using ROS2.
    """

    def __init__(self, node: Node, mavros: bool = True) -> None:
        """
        Initialize the Mavros API

        :param node (Node): ROS2 node to run the API
        :param mavros (bool): True to start the mavros node
        """
        super().__init__(node=node)

        # Variables:
        self._state = State()
        self._gps = NavSatFix()
        self._rng_alt = Range()
        self._rel_alt = Float64()
        self._local_pos = PoseStamped()
        self._vel_body = TwistStamped()
        self._heading = Float64()

        self.gps_controller = GPSController(self)

        # Alterando política de qualidade de serviço para receber dados gps:
        qos_profile = QoSProfile(
            depth=10,
            durability=QoSDurabilityPolicy.VOLATILE,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        # Subscribers:
        self._gps_sub = self._create_subscriber(
            NavSatFix,
            "/mavros/global_position/global",
            lambda data: self.__setattr__("_gps", data),
            qos_profile,
        )
        self._state_sub = self._create_subscriber(
            State, "/mavros/state", lambda data: self.__setattr__("_state", data), 10
        )
        self._rng_alt_sub = self._create_subscriber(
            Range,
            "/mavros/rangefinder/rangefinder",
            lambda data: self.__setattr__("_rng_alt", data),
            10,
        )
        self._rel_alt_sub = self._create_subscriber(
            Float64,
            "/mavros/global_position/rel_alt",
            lambda data: self.__setattr__("_rel_alt", data),
            qos_profile,
        )
        self._local_pos_sub = self._create_subscriber(
            PoseStamped,
            "/mavros/local_position/pose",
            lambda data: self.__setattr__("_local_pos", data),
            qos_profile,
        )
        self._hdg_sub = self._create_subscriber(
            Float64,
            "/mavros/global_position/compass_hdg",
            lambda data: self.__setattr__("_heading", data),
            qos_profile,
        )

        self._vel_body_sub = self._create_subscriber(
            TwistStamped,
            "/mavros/local_position/velocity_body",
            lambda data: self.__setattr__("_vel_body", data), 
            qos_profile
        )

        # Services:
        self._mode_srv = self._create_client(SetMode, "/mavros/set_mode")
        self._arm_srv = self._create_client(CommandBool, "/mavros/cmd/arming")
        self._takeoff_srv = self._create_client(CommandTOL, "/mavros/cmd/takeoff")
        self._land_srv = self._create_client(CommandTOL, "/mavros/cmd/land")
        self._home_srv = self._create_client(CommandHome, "/mavros/cmd/set_home")
        self._param_set_srv = self._create_client(ParamSetV2, "/mavros/param/set")
        self._command_srv = self._create_client(CommandLong, "/mavros/cmd/command")

        # Publishers:
        self.gps_pub = self._create_publisher(
            GeoPoseStamped, "/mavros/setpoint_position/global", 1
        )
        self.gps2_pub = self._create_publisher(
            GlobalPositionTarget, "/mavros/setpoint_raw/global", 1
        )
        self.local_pub = self._create_publisher(
            PositionTarget, "/mavros/setpoint_raw/local", 1
        )

        if mavros:
            self.init_drivers()

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
    def get_gps(self) -> NavSatFix:
        """
        Return gps data

        NavSatFix
        ----------
        http://docs.ros.org/en/api/sensor_msgs/html/msg/NavSatFix.html
        """
        return self._gps

    @property
    def get_rel_alt(self) -> Float64:
        """
        Return relative altitude data from gps

        Float64
        ----------
        http://docs.ros.org/en/api/std_msgs/html/msg/Float64.html
        """
        return self._rel_alt

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
    def get_local_pos(self) -> PoseStamped:
        """
        Return relative position data

        PoseStamped
        ----------
        http://docs.ros.org/en/api/geometry_msgs/html/msg/PoseStamped.html
        """
        return self._local_pos

    @property
    def get_heading(self) -> Float64:
        """
        Return heading data

        Float64
        ----------
        http://docs.ros.org/en/api/std_msgs/html/msg/Float64.html
        """
        return self._heading
    
    @property
    def get_vel_body(self)-> TwistStamped:
        """
        Return body velocity
        TwistStamped
        ------------

        http://docs.ros.org/en/melodic/api/geometry_msgs/html/msg/TwistStamped.html
        """
       
        return self._vel_body

    def __startup(self):
        """
        Get initial values for the drone state, gps, altitude and heading.
        """
        rclpy.spin_once(self.node)
        self.initial_altitude = self.get_gps.altitude
        self.initial_heading = self.get_heading.data

    def _call_service(
        self,
        service: Client,
        request: SrvTypeRequest,
        success_message: str,
        failure_message: str,
    ):
        """
        Auxiliar function to call services and print result.

        :param service (Client): Service client
        :param request (Request): Service request
        :param success_message (str): Message to print if success
        :param failure_message (str): Message to print if failure
        """

        while not service.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().info(
                f"Service {service.srv_name} not available, waiting again..."
            )

        self.node.get_logger().info(f"-- Calling service {service.srv_name}")

        future = service.call_async(request)

        def handle_future(future):
            try:
                result = future.result()

                if result is not None:
                    self.node.get_logger().info(
                        "\033[32;1;4m" + success_message + "\033[0m"
                    )
                else:
                    self.node.get_logger().error(
                        "\033[31;1;4m" + failure_message + "\033[0m"
                    )
            except Exception as e:
                self.node.get_logger().error(
                    f"Service call failed {service.srv_name}: {str(e)}"
                )

        future.add_done_callback(handle_future)

    def geofence(self, coords: list[tuple[float, float]]):
        """
        Create a polygon geofence, to get motors killed.

        :param coords: List of lat ant long coordinates

            exemple: [(-22.41517936,-45.44797450),(-22.41493884,-45.44779748),(-22.41532317,-45.44727176)]
        """
        self.node.get_logger().info("-- Geofence created")
        self.gps_controller.geofence(coords)

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
        req.altitude = takeoff_alt
        self._call_service(
            self._takeoff_srv,
            req,
            f"-- Takeoff to {takeoff_alt}m",
            f"-- Takeoff failed",
        )

    def arm_takeoff(self, takeoff_alt: float):
        """
        Send command to arm, take off and hold

        Parameters
        ----------
        takeoff_alt: float (meters)
        """
        self.arm()
        self.takeoff(takeoff_alt)

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

        :param param_id (str): Parameter id
        :param param_value (Int64): Parameter value
        """

        value = ParameterValue()
        value.integer_value = param_value.data

        request = ParamSetV2.Request()
        request.param_id = param_id
        request.value = value
        request.force_set = True
        self._call_service(
            self._param_set_srv,
            request,
            f"-- {param_id} set to {param_value}",
            f"-- Set {param_id} failed",
        )

    def rtl(self, rtl_alt: int = 10, precision_landing: bool = False, aruco_target: int = 800):
        """
        Send return to launch command.

        The copter will first rise to RTL_ALT before returning home or maintain the current
        altitude if the current altitude is higher than RTL_ALT. The default value for RTL_ALT is 15m.

        Parameters
        ----------
        param rtl_alt (int): altitude in meters to rtl mode
        param precisionland (bool): run precision_landing when the drone start the land or not
        param aruco_target (int): the ArUco marker id to do the precision landing 
        """

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

    def offboard_gps_position(
        self,
        lat_setpoint: float = 0.0,
        lon_setpoint: float = 0.0,
        alt_setpoint: float = 0.0,
        heading: float = 0.0,
        precision_radius: float = 0.0,
        initial_heading: bool = False
    ):
        """
        Move sending a GPS coordinate setpoint

        :param lat_setpoint (float): Latitude setpoint
        :param lon_setpoint (float): Longitude setpoint
        :param alt_setpoint (float): Altitude setpoint (meters AGL)
        :param heading (float): Heading setpoint (degrees refered to North)
        :param precision_radius (float): Precision radius setpoint (meters)
        :param initial_heading (bool): True for keep initial heading value, False for value passed
        """

        self.__startup()
        final_heading = self.initial_heading if initial_heading else heading

        self.node.get_logger().info(
            f"-- Moving to GPS position: {lat_setpoint}, {lon_setpoint}, {alt_setpoint}, {final_heading}"
        )
        self.gps_controller.gps_send(
            lat_setpoint, lon_setpoint, alt_setpoint, final_heading, precision_radius
        )

    def offboard_velocity(
        self,
        linear_x: float = 0.0,
        linear_y: float = 0.0,
        linear_z: float = 0.0,
        angular_z: float = 0.0,
        ground_reference: bool = True,
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
        ground_reference: bool = True,
        pub_rate: int = 30,
        time: int = 0,
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
