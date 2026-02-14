#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import SetParametersResult
from std_msgs.msg import Float64, Bool

from mirela_sdk.control.pid import PIDController


class PIDControllerNode(Node):
    """
    Standalone PID controller ROS2 node.

    Subscribes to state and setpoint topics, computes PID control,
    and publishes control effort. Supports dynamic parameter reconfiguration.
    """

    def __init__(self):
        super().__init__("pid_controller")

        # Declare parameters
        self.declare_parameter("p_gain", 0.0)
        self.declare_parameter("i_gain", 0.0)
        self.declare_parameter("d_gain", 0.0)
        self.declare_parameter("output_min", -1.0)
        self.declare_parameter("output_max", 1.0)
        self.declare_parameter("integral_min", -1.0)
        self.declare_parameter("integral_max", 1.0)
        self.declare_parameter("state_topic", "state")
        self.declare_parameter("setpoint_topic", "setpoint")
        self.declare_parameter("control_effort_topic", "control_effort")
        self.declare_parameter("pid_enable_topic", "pid_enable")
        self.declare_parameter("auto_start", True)
        self.declare_parameter("reverse_action", False)

        self._init_controller()

        state_topic = self.get_parameter("state_topic").value
        setpoint_topic = self.get_parameter("setpoint_topic").value
        control_topic = self.get_parameter("control_effort_topic").value
        enable_topic = self.get_parameter("pid_enable_topic").value

        # publishers and subscribers
        self._control_pub = self.create_publisher(Float64, control_topic, 10)
        self._state_sub = self.create_subscription(
            Float64, state_topic, self._state_callback, 10
        )
        self._setpoint_sub = self.create_subscription(
            Float64, setpoint_topic, self._setpoint_callback, 10
        )
        self._enable_sub = self.create_subscription(
            Bool, enable_topic, self._enable_callback, 10
        )

        # Internal state
        self._auto_mode = self.get_parameter("auto_start").value
        self._reverse_action = self.get_parameter("reverse_action").value
        self._current_state = 0.0
        self._current_setpoint = 0.0
        self._has_received_state = False
        self._has_received_setpoint = False

        self.add_on_set_parameters_callback(self._parameters_callback)

        self.get_logger().info(
            f"PID controller initialized: Kp={self._pid.kp:.4f}, "
            f"Ki={self._pid.ki:.4f}, Kd={self._pid.kd:.4f}"
        )
        self.get_logger().info(
            f"Topics: state={state_topic}, setpoint={setpoint_topic}, "
            f"control={control_topic}, enable={enable_topic}"
        )

    def _init_controller(self):
        """Initialize PID controller with current parameters."""
        kp = self.get_parameter("p_gain").value
        ki = self.get_parameter("i_gain").value
        kd = self.get_parameter("d_gain").value
        output_min = self.get_parameter("output_min").value
        output_max = self.get_parameter("output_max").value
        integral_min = self.get_parameter("integral_min").value
        integral_max = self.get_parameter("integral_max").value

        self._pid = PIDController(
            kp=kp,
            ki=ki,
            kd=kd,
            setpoint=0.0,
            output_limits=(output_min, output_max),
            integral_limits=(integral_min, integral_max),
        )

    def _state_callback(self, msg: Float64):
        """Process state message and compute control."""
        self._current_state = msg.data
        self._has_received_state = True

        self.get_logger().debug(f"Received state: {msg.data:.4f}")

        if self._auto_mode and self._has_received_setpoint:
            control_effort = self._pid.update(self._current_state)

            if self._reverse_action:
                control_effort = -control_effort

            self.get_logger().info(
                f"Control: state={self._current_state:.4f}, "
                f"setpoint={self._current_setpoint:.4f}, "
                f"effort={control_effort:.4f}",
                throttle_duration_sec=1.0,
            )

            control_msg = Float64()
            control_msg.data = control_effort
            self._control_pub.publish(control_msg)

    def _setpoint_callback(self, msg: Float64):
        """Update setpoint."""
        self._has_received_setpoint = True

        if self._current_setpoint != msg.data:
            self._current_setpoint = msg.data
            self._pid.set_setpoint(self._current_setpoint)
            self.get_logger().info(f"Setpoint updated to {self._current_setpoint:.4f}")

    def _enable_callback(self, msg: Bool):
        """Enable or disable PID controller."""
        self._auto_mode = msg.data

        if not self._auto_mode:
            self._pid.reset()

        self.get_logger().info(
            f"PID controller {'enabled' if self._auto_mode else 'disabled'}"
        )

    def _parameters_callback(self, params):
        """Handle parameter changes."""
        result = SetParametersResult()
        result.successful = True

        for param in params:
            name = param.name

            if name == "p_gain":
                self._pid.kp = param.value
                self.get_logger().info(f"Updated p_gain to {param.value:.4f}")
            elif name == "i_gain":
                self._pid.ki = param.value
                self.get_logger().info(f"Updated i_gain to {param.value:.4f}")
            elif name == "d_gain":
                self._pid.kd = param.value
                self.get_logger().info(f"Updated d_gain to {param.value:.4f}")
            elif name == "output_min":
                self._pid.output_limits = (param.value, self._pid.output_limits[1])
                self.get_logger().info(f"Updated output_min to {param.value:.4f}")
            elif name == "output_max":
                self._pid.output_limits = (self._pid.output_limits[0], param.value)
                self.get_logger().info(f"Updated output_max to {param.value:.4f}")
            elif name == "integral_min":
                self._pid.integral_limits = (param.value, self._pid.integral_limits[1])
                self.get_logger().info(f"Updated integral_min to {param.value:.4f}")
            elif name == "integral_max":
                self._pid.integral_limits = (self._pid.integral_limits[0], param.value)
                self.get_logger().info(f"Updated integral_max to {param.value:.4f}")
            elif name == "auto_start":
                self._auto_mode = param.value
                if not self._auto_mode:
                    self._pid.reset()
                self.get_logger().info(
                    f"PID {'enabled' if self._auto_mode else 'disabled'}"
                )
            elif name == "reverse_action":
                self._reverse_action = param.value
                self.get_logger().info(
                    f"Reverse action {'enabled' if self._reverse_action else 'disabled'}"
                )

        return result


def main(args=None):
    """Run PID controller node."""
    rclpy.init(args=args)
    node = PIDControllerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
