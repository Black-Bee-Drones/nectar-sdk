import rclpy
from rclpy.node import Node
from rclpy.duration import Duration

from time import sleep
import cv2

from std_msgs.msg import Empty, UInt8, Float32, Bool
from geometry_msgs.msg import Twist

from mirela_sdk.image_processing.camera.image_handler import ImageHandler


class Bebop(Node):
    """
    Class to control the Parrot Bebop 2 drone using ROS2.
    """

    def __init__(self) -> None:
        super().__init__("bebop_api_node")

        # Publishers:
        self.takeoff_pub = self.create_publisher(Empty, "/bebop/takeoff", 1)
        self.land_pub = self.create_publisher(Empty, "/bebop/land", 1)
        self.vel_pub = self.create_publisher(Twist, "/bebop/cmd_vel", 1)
        self.flip_pub = self.create_publisher(UInt8, "/bebop/flip", 1)
        self.gimbal_pub = self.create_publisher(Twist, "/bebop/camera_control", 1)
        self.snap_pub = self.create_publisher(Empty, "/bebop/snapshot", 1)
        self.video_pub = self.create_publisher(Bool, "/bebop/record", 1)
        self.exposure_pub = self.create_publisher(Float32, "/bebop/set_exposure", 1)

        self.cv_image = None

        self.delay(0.5)

        self.get_logger().info("Bebop API initialized")

    def takeoff(self) -> None:
        """
        Send a takeoff command to the drone.
        """

        self.takeoff_pub.publish(Empty())
        self.get_logger().info("-- Takeoff")

    def land(self) -> None:
        """
        Send a land command to the drone.
        """

        self.land_pub.publish(Empty())
        self.get_logger().info("-- Land")

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

        self.get_logger().info("-- Moviment start")

        while t_now <= t_start + duration:

            self.offboard_velocity(linear_x, linear_y, linear_z, angular_z)
            rate.sleep()
            t_now = self.get_clock().now()

        self.get_logger().info("-- Moviment end")

    def flip(self, direction: int) -> None:
        """
        Send a flip command to the drone.

        :param direction (int): Direction of the flip.
            0: Front, 1: Back, 2: Right, 3: Left
        """

        self.flip_pub.publish(UInt8(data=direction))
        self.get_logger().info("-- Flip")

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

    def snapshot(self) -> None:
        """
        Send a snapshot command to the drone.
        """

        self.snap_pub.publish(Empty())
        self.get_logger().info("-- Snapshot")

    def record(self, record: bool) -> None:
        """
        Send a record command to the drone.

        :param record (bool): True to start recording, False to stop recording.
        """

        self.video_pub.publish(Bool(data=record))
        self.get_logger().info("-- {} recording".format("Start" if record else "Stop"))

    def set_exposure(self, exposure: float) -> None:
        """
        Set the exposure of the camera.

        :param exposure (float): Exposure value.
            Acceptable range: [-3, 3]
        """

        self.exposure_pub.publish(Float32(data=exposure))
        self.get_logger().info("-- Set exposure to {}".format(exposure))

    def delay(self, time: float) -> None:
        """
        Delay the execution of the program.
        """

        self.get_logger().info(f"-- Init delay {time}")
        sleep(time)
        self.get_logger().info(f"-- End delay {time}")

    def show(self, img) -> None:
        """
        Display the image from the drone's camera.
        """
        self.get_logger().info("View")
        cv2.imshow("Bebop Camera", img)

    def image_viewer(self) -> None:
        """
        Display the image from the drone's camera.
        """
        self.image_manager = ImageHandler(
            self, ImageHandler.BEBOP_TOPIC, image_processing_callback=self.show
        )

    def cleanup(self):
        self.land()


def main(args=None) -> None:
    rclpy.init(args=args)
    bebop = Bebop()

    bebop.image_viewer()

    rclpy.spin(bebop)

    bebop.cleanup()

    # rclpy.shutdown()


if __name__ == "__main__":
    main()
