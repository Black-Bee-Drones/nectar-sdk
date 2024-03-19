import rclpy
from rclpy.node import Node
from rclpy.timer import Rate
from rclpy.duration import Duration

from mirela_sdk.control.mavros.gps_controller import GPSController

from mavros_msgs.srv import (
    SetMode,
    CommandBool,
    CommandTOL,
    CommandHome,
    CommandLong,
    ParamSet,
)
from mavros_msgs.msg import State, PositionTarget, GlobalPositionTarget, ParamValue
from std_msgs.msg import Float64, Int64
from geometry_msgs.msg import Twist, PoseStamped
from geographic_msgs.msg import GeoPoseStamped
from sensor_msgs.msg import NavSatFix, Range

from time import sleep


class MavDrone(Node):
    """
    Class to control the mav ros drone using ROS2.
    """

    def __init__(self) -> None:
        super().__init__("mavros_api_node")

        # Variables:
        self._state = State()
        self._gps = NavSatFix()
        self._rng_alt = Range()
        self._rel_alt = Float64()
        self._local_pos = PoseStamped()
        self._heading = Float64()

        self.gps_controller = GPSController(self)

        # Subscribers:
        self._gps_sub = self.create_subscription(
            NavSatFix,
            "/mavros/global_position/global",
            lambda data: self.__setattr__("_gps", data),
            10,
        )
        self._state_sub = self.create_subscription(
            State, "/mavros/state", lambda data: self.__setattr__("_state", data), 10
        )
        self._rng_alt_sub = self.create_subscription(
            Range,
            "/mavros/distance_sensor/rangefinder_pub",
            lambda data: self.__setattr__("_rng_alt", data),
            10,
        )
        self._rel_alt_sub = self.create_subscription(
            Float64,
            "/mavros/global_position/rel_alt",
            lambda data: self.__setattr__("_rel_alt", data),
            10,
        )
        self._local_pos_sub = self.create_subscription(
            PoseStamped,
            "/mavros/local_position/pose",
            lambda data: self.__setattr__("_local_pos", data),
            10,
        )
        self._hdg_sub = self.create_subscription(
            Float64,
            "/mavros/global_position/compass_hdg",
            lambda data: self.__setattr__("_heading", data),
            10,
        )

        # Services:
        self._mode_srv = self.create_client(SetMode, "/mavros/set_mode")
        self._arm_srv = self.create_client(CommandBool, "/mavros/cmd/arming")
        self._takeoff_srv = self.create_client(CommandTOL, "/mavros/cmd/takeoff")
        self._land_srv = self.create_client(CommandTOL, "/mavros/cmd/land")
        self._home_srv = self.create_client(CommandHome, "/mavros/cmd/set_home")
        # self._param_set_srv = self.create_client(ParamSet, "/mavros/param/set")
        self._command_srv = self.create_client(CommandLong, "/mavros/cmd/command")

        def wait_service(service):
            while not service.wait_for_service(timeout_sec=1.0):
                self.get_logger().info(
                    f"Service {service.srv_name} not available, waiting again..."
                )

        wait_service(self._mode_srv)
        wait_service(self._arm_srv)
        wait_service(self._takeoff_srv)
        wait_service(self._land_srv)
        wait_service(self._home_srv)
        # wait_service(self._param_set_srv)
        wait_service(self._command_srv)

        # Publishers:
        self.gps_pub = self.create_publisher(
            GeoPoseStamped, "/mavros/setpoint_position/global", 1
        )
        self.gps2_pub = self.create_publisher(
            GlobalPositionTarget, "/mavros/setpoint_raw/global", 1
        )
        self.local_pub = self.create_publisher(
            PositionTarget, "/mavros/setpoint_raw/local", 1
        )

        # Wait Services:
        while not self._mode_srv.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Service not available, waiting again...")

        sleep(10)

        self.get_logger().info("Mavros API initialized")

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

    def _startup(self):
        """
        Get initial values for the drone state, gps, altitude and heading.
        """
        self.initial_heading = self._heading.data
        self.initial_altitude = self._gps.altitude
        print(self.initial_altitude)

    def _call_service(
        self,
        service,
        request,
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

        future = service.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        if future.result() is not None:
            self.get_logger().info("\033[32;1;4m" + success_message + "\033[0m")
        else:
            self.get_logger().error("\033[31;1;4m" + failure_message + "\033[0m")

    def geofence(self, coords: list[tuple[float, float]]):
        """
        Create a polygon geofence, to get motors killed.

        :param coords: List of lat ant long coordinates

            exemple: [(-22.41517936,-45.44797450),(-22.41493884,-45.44779748),(-22.41532317,-45.44727176)]
        """
        self.get_logger().info("-- Geofence created")
        self.gps_controller.geofence(coords)

    def kill_motors(self):
        """
        Forced disarm

        Caution: it will disarm even during a flight
        """
        command = CommandLong.Request()
        command.command = 400
        command.param1 = 0
        command.param2 = 0
        command.param3 = 0
        command.param4 = 0
        command.param5 = 21196
        command.param6 = 0
        command.param7 = 0
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
        self.set_mode("GUIDED")
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

        value = ParamValue()
        value.integer = param_value.data

        request = ParamSet.Request()
        request.param_id = param_id
        request.value = value
        self._call_service(
            self._param_set_srv,
            request,
            f"-- {param_id} set to {param_value}",
            f"-- Set {param_id} failed",
        )

    def do_servo(self, aux_out: int, pwm_value: int):
        """
        Send a PWM signal to moviment a servo motor connected *aux_out*

        :param aux_out (int): Auxiliar port (1-6)
        :param pwm_value (int): PWM value (usually between 1000 ~ 2000)
        """

        command = CommandLong.Request()
        command.command = 183
        command.param1 = aux_out + 8
        command.param2 = pwm_value
        self._call_service(
            self._command_srv,
            command,
            f"-- Servo {aux_out} set to {pwm_value}",
            f"-- Set servo {aux_out} failed",
        )

    def offboard_gps_position(
        self,
        lat_setpoint: float,
        lon_setpoint: float,
        alt_setpoint: float,
        heading: float,
        precision_radius: float,
    ):
        """
        Move sending a GPS coordinate setpoint

        :param lat_setpoint (float): Latitude setpoint
        :param lon_setpoint (float): Longitude setpoint
        :param alt_setpoint (float): Altitude setpoint (meters AGL)
        :param heading (float): Heading setpoint (degrees refered to North)
        :param precision_radius (float): Precision radius setpoint (meters)
        """

        self.get_logger().info(
            f"-- Moving to GPS position: {lat_setpoint}, {lon_setpoint}, {alt_setpoint}, {heading}"
        )
        self.gps_controller.gps_send(
            lat_setpoint, lon_setpoint, alt_setpoint, heading, precision_radius
        )

    def offboard_velocity(
        self,
        linear_x: float,
        linear_y: float,
        linear_z: float,
        angular_z: float,
        ground_reference: bool = True,
    ):
        """ """
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
        linear_x: float,
        linear_y: float,
        linear_z: float,
        angular_z: float,
        ground_reference: bool = True,
        pub_rate: int = 30,
        time: int = 0,
    ):
        """ """
        t_start = t_now = self.get_clock().now()
        duration = Duration(secs=time)
        rate = Rate(pub_rate)

        self.get_logger().info("-- Moviment start")

        while t_now <= t_start + duration:
            self.offboard_velocity(
                linear_x, linear_y, linear_z, angular_z, ground_reference
            )
            rate.sleep()
            t_now = self.get_clock().now()


def main(args=None):
    rclpy.init()

    drone = MavDrone()

    drone.arm_takeoff(5.0)

    sleep(5.0)

    # drone.offboard_velocity_timer(1, 0, 0, 1, False, 30, 15)
    # drone.offboard_velocity(0, 0, 0, 0, False)

    drone.land()

    rclpy.spin(drone)


if __name__ == "__main__":
    main()
