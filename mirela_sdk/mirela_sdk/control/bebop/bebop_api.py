import rclpy
from rclpy.node import Node
from rclpy.duration import Duration

from time import sleep
import cv2
import subprocess
import shlex

from std_msgs.msg import Empty, UInt8, Float32, Bool
from geometry_msgs.msg import Twist

from mirela_sdk.control.drone import Drone
from mirela_sdk.image_processing.camera.image_handler import ImageHandler


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
        self.gimbal_pub = self._create_publisher(Twist, "/bebop/camera_control", 1)
        self.snap_pub = self._create_publisher(Empty, "/bebop/snapshot", 1)
        self.video_pub = self._create_publisher(Bool, "/bebop/record", 1)
        self.exposure_pub = self._create_publisher(Float32, "/bebop/set_exposure", 1)

        if driver:
            self.init_drivers()
            self.delay(0.5)

        self.node.get_logger().info("Bebop API initialized")

    def init_drivers(self):
        """
        Start the ros2 launch file to initialize the bebop driver.
            ros2 launch ros2_bebop_driver bebop_node_launch.xml
        """
        # Command to start the ros2 launch bebob driver
        command = ["ros2", "launch", "ros2_bebop_driver", "bebop_node_launch.xml"]

        # Join the list elements into a single string
        command_str = " ".join(command)

        # Start the process
        process = subprocess.Popen(
            shlex.split(f'gnome-terminal -- bash -c "{command_str}"')
        )

        # Wait for the process to finish
        stdout, stderr = process.communicate()

        # Check for any errors
        if process.returncode != 0:
            print(
                f"\033[91mErro ao iniciar o bebop driver: {process.returncode}\033[0m"
            )
        else:
            print(f"\033[92mros2_bebop_driver iniciado com sucesso\033[0m")

        sleep(2.0)

    def check_driver_node(self):
        """
        Check if the bebop driver is running.
        """
        # Get all node names
        node_names = self.node.get_node_names()

        # Check if the mavros node is running
        return True if "bebop_driver" in node_names else False

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
        self, linear_x: float, linear_y: float, linear_z: float, angular_z: float
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
        linear_x: float,
        linear_y: float,
        linear_z: float,
        angular_z: float,
        pub_rate: UInt8,
        time: float,
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
        :param pub_rate (UInt8): Rate at which the commands are published.
            Publish rate on cmd_vel topic (Hz)
        :param time (float): Duration of the movement.
            Time in seconds.
        """

        t_start = t_now = self.get_clock().now()
        duration = Duration(seconds=time)
        rate = self.create_rate(pub_rate)

        self.node.get_logger().info("-- Moviment start")

        while t_now <= t_start + duration:

            self.offboard_velocity(linear_x, linear_y, linear_z, angular_z)
            rate.sleep()
            t_now = self.get_clock().now()

        self.node.get_logger().info("-- Moviment end")

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
            (+) Up, (-) Down.
        :param pan (float): Pan angle of the camera.
            (+) Left, (-) Right.
        """

        twist = Twist()
        twist.linear.x = tilt
        twist.linear.y = pan

        self.gimbal_pub.publish(twist)

    def set_exposure(self, exposure: float) -> None:
        """
        Set the exposure of the camera.

        :param exposure (float): Exposure value.
            Acceptable range: [-3, 3]
        """

        self.exposure_pub.publish(Float32(data=exposure))
        self.node.get_logger().info("-- Set exposure to {}".format(exposure))

    def image_viewer(self) -> None:
        """
        Init Image Handler with bebop image_raw topic and show the image.
        """
        self.image_manager = ImageHandler(
            self.node,
            ImageHandler.BEBOP_TOPIC,
            image_processing_callback=lambda image: cv2.imshow("Bebop Camera", image),
        )
        self.image_manager.run()

    def record(self, record: bool) -> None:
        """
        Send a record command to the drone.

        :param record (bool): True to start recording, False to stop recording.
        """

        self.video_pub.publish(Bool(data=record))
        self.node.get_logger().info(
            "-- {} recording".format("Start" if record else "Stop")
        )

    def snapshot(self) -> None:
        """
        Send a snapshot command to the drone.
        """

        self.snap_pub.publish(Empty())
        self.node.get_logger().info("-- Snapshot")


def main(args=None) -> None:
    rclpy.init(args=args)

    node = rclpy.create_node("bebop_node")
    bebop = Bebop(node, True)

    bebop.image_viewer()
    bebop.check_drivers()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
