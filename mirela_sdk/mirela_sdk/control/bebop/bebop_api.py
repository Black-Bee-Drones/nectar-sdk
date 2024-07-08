import rclpy
from rclpy.node import Node
from time import sleep
from rclpy.duration import Duration
from std_msgs.msg import Empty, UInt8, Float32, Bool
from geometry_msgs.msg import Twist, Vector3

from mirela_sdk.control.drone import Drone
from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.utils.process import ProcessUtils


class Bebop(Drone):

    def __init__(self, node: Node, driver: bool = True) -> None:
        """
        Class to control the Parrot Bebop 2 drone using ROS2.
        It provides a python interface to send commands to the driver node.

        :param node (Node): ROS2 node to create commands publishers.
        :param driver (bool): True to start the bebop driver node.
        """

        super().__init__(node=node)

        # Publishers:
        self.takeoff_pub = self._create_publisher(Empty, "/bebop/takeoff", 1)
        self.land_pub = self._create_publisher(Empty, "/bebop/land", 1)
        self.vel_pub = self._create_publisher(Twist, "/bebop/cmd_vel", 1)
        self.flip_pub = self._create_publisher(UInt8, "/bebop/flip", 1)
        self.gimbal_pub = self._create_publisher(Vector3, "/bebop/move_camera", 1)
        self.emergency_pub = self._create_publisher(Empty, "/bebop/reset", 1)
        self.flattrim_pub = self._create_publisher(Empty, "/bebop/flattrim", 1)
        self.navigate_home_pub = self._create_publisher(
            Empty, "/bebop/autoflight/navigate_home", 1
        )
        self.photo_pub = self._create_publisher(Bool, "/bebop/photo", 1)

        if driver:
            self.init_drivers()

        self.node.get_logger().info("Bebop API initialized")

    def start_driver_node(self):
        """
        Start the ros2 launch file to initialize the bebop driver.
            ros2 launch ros2_bebop_driver bebop_node_launch.xml
        """
        # Command to start the ros2 launch bebob driver
        result = ProcessUtils.start_process(
            "ros2 launch ros2_bebop_driver bebop_node_launch.xml", "bebop_driver"
        )
        self._driver_initialized = result

    def get_driver_node_name(self) -> str:
        return "bebop_driver"

    def takeoff(self) -> None:
        """
        Send a takeoff command to the drone.
        """

        self.takeoff_pub.publish(Empty())
        self.node.get_logger().info("-- Takeoff")

    def land(self) -> None:
        """
        Send a land command to the drone.
        """

        self.land_pub.publish(Empty())
        self.node.get_logger().info("-- Land")

    def offboard_velocity(
        self,
        linear_x: float = 0.0,
        linear_y: float = 0.0,
        linear_z: float = 0.0,
        angular_z: float = 0.0,
    ) -> None:
        """
        Send velocity commands to the drone.

        Acceptable range for all fields are [-1, 1]

        :param linear_x (float): Linear velocity in the x-axis.
            (+) Forward, (-) Backward.
        :param linear_y (float): Linear velocity in the y-axis.
            (+) Left, (-) Right.
        :param linear_z (float): Linear velocity in the z-axis.
            (+) Up, (-) Down.
        :param angular_z (float): Angular velocity in the z-axis.
            (+) Counter-clockwise, (-) Clockwise.
        """

        twist = Twist()
        twist.linear.x = linear_x
        twist.linear.y = linear_y
        twist.linear.z = linear_z
        twist.angular.z = angular_z

        self.vel_pub.publish(twist)

    def offboard_velocity_timer(
        self,
        linear_x: float = 0.0,
        linear_y: float = 0.0,
        linear_z: float = 0.0,
        angular_z: float = 0.0,
        pub_rate: int = 30,
        time: float = 1.0,
    ) -> None:
        """
        Send velocity commands to the drone for a certain amount of time.

        :param linear_x (float): Linear velocity in the x-axis.
            (+) Forward, (-) Backward.
        :param linear_y (float): Linear velocity in the y-axis.
            (+) Left, (-) Right.
        :param linear_z (float): Linear velocity in the z-axis.
            (+) Up, (-) Down.
        :param angular_z (float): Angular velocity in the z-axis.
            (+) Counter-clockwise, (-) Clockwise.
        :param pub_rate (int): Rate at which the commands are published.
            Publish rate on cmd_vel topic (Hz)
        :param time (float): Duration of the movement.
            Time in seconds.
        """

        t_start = t_now = self.node.get_clock().now()

        duration = Duration(seconds=time)
        # rate = self.node.create_rate(pub_rate, self.node.get_clock())
        rate = 1.0 / pub_rate

        self.node.get_logger().info("-- Moviment start")

        while t_now <= t_start + duration:
            self.offboard_velocity(linear_x, linear_y, linear_z, angular_z)
            sleep(rate)
            t_now = self.node.get_clock().now()

        self.node.get_logger().info(
            "-- Moviment end - time: {:.4f} s".format(
                (t_now - t_start).nanoseconds / 1000000000
            )
        )

    def flip(self, direction: int) -> None:
        """
        Send a flip command to the drone.

        :param direction (int): Direction of the flip.
            0: Front, 1: Back, 2: Right, 3: Left
        """
        directions = ["Front", "Back", "Right", "Left"]
        self.flip_pub.publish(UInt8(data=direction))
        self.node.get_logger().info("-- Flip " + directions[direction])

    def camera_control(self, tilt: float, pan: float) -> None:
        """
        Send a camera control command to the drone.

        :param tilt (float): Tilt angle of the camera.
            (+) Down, (-) Up.
        :param pan (float): Pan angle of the camera.
            (+) Left, (-) Right.
        """

        twist = Vector3()
        twist.x = tilt
        twist.y = pan

        self.node.get_logger().info(f"Move camera tilt: {tilt}, pan: {pan}")
        self.gimbal_pub.publish(twist)

    def image_viewer(self) -> None:
        """
        Init Image Handler with bebop image_raw topic and show the image.
        """

        self.image_manager = ImageHandler(
            self.node,
            ImageHandler.BEBOP_TOPIC,
            show_result="Bebop Image",
        )
        self.image_manager.run()

    def record(self, record: bool) -> None:
        """
        Send a record command to the drone.

        :param record (bool): True to start recording, False to stop recording.
        """
        # TODO: Implement record command
        pass

    def snapshot(self) -> None:
        """
        Send a snapshot command to the drone.
        """

        self.photo_pub.publish(Bool(data=True))
        self.node.get_logger().info("-- Snapshot")


def main(args=None) -> None:
    rclpy.init(args=args)

    node = rclpy.create_node("bebop_node")
    bebop = Bebop(node, True)

    # bebop.image_viewer()
    print(bebop.check_driver_node())

    sleep(2.0)
    bebop.camera_control(180.0, 0.0)

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
