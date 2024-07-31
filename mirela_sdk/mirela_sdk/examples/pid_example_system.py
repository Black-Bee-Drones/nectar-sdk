import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from time import sleep

from mirela_sdk.control.pid.controller import Controller


class ExampleSystem(Node):
    def __init__(self):
        super().__init__("pid_example_system")
        self.declare_parameter("plant_order", 1)

        self.plant_state: Float32 = Float32()
        self._plant_order: int = 1
        self._temp: float = 4.7
        self._displacement: float = 3.3
        self._loop_counter: int = 0
        self._delta_t: float = 0.01
        self._temp_rate: float = 0.0
        self._speed: float = 0.0
        self._acceleration: float = 0.0
        self._mass: float = 0.1
        self._friction: float = 1.0
        self._stiction: float = 1.0
        self._kv: float = 1.0
        self._k_backemf: float = 0.0
        self._decel_force: float = 0.0
        self._control_effort: float = 0.0

        self.controller = Controller(
            self,
            "example_system",
            5.0,
            0.0,
            0.1,
            0.0,
            self.control_callback,
            use_sample_time=False,
            sample_time=2,
            derivative_on_measurement=False,
            remove_ki_bump=False,
            reset_windup=False,
            out_min=-50,
            out_max=50,
            pid_enabled=False,
        )

        sleep(5)

        print("Starting control loop")
        self.controller.enable(True)

    def control_callback(self, control_effort: Float32):
        self._plant_order = self.get_parameter("plant_order").value

        if self._plant_order == 1:  # First order plant
            self._temp_rate = (0.1 * self._temp) + control_effort
            self._temp = self._temp + self._temp_rate * self._delta_t
            self.plant_state.data = self._temp

        elif self._plant_order == 2:  # Second order plant
            if abs(self._speed) < 0.001:
                # if nearly stopped, stop it & require overcoming stiction to restart
                self._speed = 0
                if abs(control_effort) < self._stiction:
                    control_effort = 0
            self._decel_force = -(
                self._speed * self._friction
            )  # can be +ve or -ve. Linear with speed
            self._acceleration = (
                self._kv * (control_effort - (self._k_backemf * self._speed))
                + self._decel_force
            ) / self._mass  # a = F/m
            self._speed = self._speed + (self._acceleration * self._delta_t)
            self._displacement = self._displacement + self._speed * self._delta_t
            self.plant_state.data = self._displacement
        else:
            self.get_logger().error("Invalid plant_order")

        self.controller.state = self.plant_state.data


def main(args=None):
    rclpy.init(args=args)
    node = ExampleSystem()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
