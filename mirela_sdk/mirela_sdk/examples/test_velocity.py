import rclpy
from time import sleep
from mirela_sdk.control.mavros.mavros_api import MavDrone


class TestVelocity:
    def __init__(self):
        self.drone = MavDrone(init_mavros=True)
        self.drone.get_logger().info("Test velocity has been initialized")
        self.drone.check_mavros_node()

    def run(self):
        self.drone.arm_takeoff(3.0)
        sleep(8)

        self.drone.get_logger().info("Moving to front")
        self.drone.offboard_velocity_timer(
            linear_x=1.0, ground_reference=False, pub_rate=30, time=5
        )
        sleep(5)

        self.drone.get_logger().info("Moving to left")
        self.drone.offboard_velocity_timer(
            linear_y=1.0, ground_reference=False, pub_rate=30, time=5
        )
        sleep(5)

        self.drone.get_logger().info("Moving to rigth")
        self.drone.offboard_velocity_timer(
            linear_y=-1.0, ground_reference=False, pub_rate=30, time=5
        )
        sleep(5)

        self.drone.get_logger().info("Moving to back")
        self.drone.offboard_velocity_timer(
            linear_x=-1.0, ground_reference=False, pub_rate=30, time=5
        )
        sleep(5)

        self.drone.get_logger().info("Landing")
        self.drone.land()


def main(args=None):
    rclpy.init(args=args)

    test_velocity = TestVelocity()
    test_velocity.run()

    rclpy.spin(test_velocity.drone)
    # test_velocity.destroy_node()
    rclpy.shutdown()
