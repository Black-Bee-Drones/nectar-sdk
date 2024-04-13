import rclpy
from time import sleep
from mirela_sdk.control.mavros.mavros_api import MavDrone


class TestVelocity(MavDrone):
    def __init__(self):
        super().__init__()
        self.get_logger().info("Test velocity has been initialized")

    def run(self):
        self.arm_takeoff(3.0)
        sleep(8)

        self.get_logger().info("Moving to front")
        self.offboard_velocity_timer(
            linear_x=1.0,
            ground_reference=False,
            pub_rate=30,
            time=5
        )
        sleep(5)

        self.get_logger().info("Moving to left")
        self.offboard_velocity_timer(
            linear_y=1.0,
            ground_reference=False,
            pub_rate=30,
            time=5
        )
        sleep(5)

        self.get_logger().info("Moving to rigth")
        self.offboard_velocity_timer(
            linear_y=-1.0,
            ground_reference=False,
            pub_rate=30,
            time=5
        )
        sleep(5)

        self.get_logger().info("Moving to back")
        self.offboard_velocity_timer(
            linear_x=-1.0,
            ground_reference=False,
            pub_rate=30,
            time=5
        )
        sleep(5)

        self.get_logger().info("Landing")
        self.land()


def main(args=None):
    rclpy.init(args=args)

    test_velocity = TestVelocity()
    test_velocity.run()

    rclpy.spin(test_velocity)
    test_velocity.destroy_node()
    rclpy.shutdown()
