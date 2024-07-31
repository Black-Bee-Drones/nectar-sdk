from rclpy.node import Node

from std_msgs.msg import Float32, Bool
from rcl_interfaces.msg import ParameterValue, ParameterType, Parameter
from rcl_interfaces.srv import SetParameters, GetParameters, ListParameters

from time import sleep
from mirela_sdk.utils.process import ProcessUtils


class Controller:

    def __init__(
        self,
        node: Node,
        name: str,
        kp: float,
        ki: float,
        kd: float,
        setpoint: float,
        callback: callable = None,
        use_sample_time: bool = False,
        sample_time: float = 5,
        derivative_on_measurement: bool = False,
        remove_ki_bump: bool = False,
        reset_windup: bool = True,
        pid_enabled: bool = True,
        cut_off_freq: float = 0,
        out_min: int = -1,
        out_max: int = 1,
        control_value_topic: str = "control_value",
        actual_state_topic: str = "actual_state",
        set_point_topic: str = "set_point",
        loop_freq: int = 10,
    ) -> None:
        """
        Inicializa o controlador com parâmetros e configurações.

        :param name: Nome do nó do controlador.
        :param kp: Ganho proporcional.
        :param ki: Ganho integral.
        :param kd: Ganho derivativo.
        """
        self.node, self.name = node, name
        self.callback = callback

        self.gains = {"kp": kp, "ki": ki, "kd": kd}
        self.topics = [
            f"{self.name}/{control_value_topic}",
            f"{self.name}/{actual_state_topic}",
            f"{self.name}/{set_point_topic}",
        ]
        self.params = {
            "kp": kp,
            "ki": ki,
            "kd": kd,
            "use_sample_time": use_sample_time,
            "sample_time": sample_time,
            "derivative_on_measurement": derivative_on_measurement,
            "remove_ki_bump": remove_ki_bump,
            "reset_windup": reset_windup,
            "pid_enabled": pid_enabled,
            "cut_off_freq": cut_off_freq,
            "out_min": out_min,
            "out_max": out_max,
            "control_value_topic": self.topics[0],
            "actual_state_topic": self.topics[1],
            "set_point_topic": self.topics[2],
            "loop_freq": loop_freq,
        }
        self._init_topics()

        self._init_node()

        sleep(2)

        self._init_client_params()

        self.control_effort = 0.0
        self.setpoint = setpoint
        self.able = False

    def _init_node(self):
        """
        Inicializa o nó do controlador com os parâmetros especificados.
        """

        args = " -p ".join([f"{k}:={v}" for k, v in self.params.items()])
        cli = f"ros2 run use_library use_library --ros-args -p {args}"
        ProcessUtils.start_process(cli)

    def _init_topics(self):
        """
        Inicializa os tópicos de publicação e assinatura para o controlador.
        """
        self.state_msg = Float32()
        self.setpoint_msg = Float32()
        self.state_pub = self.node.create_publisher(Float32, self.topics[1], 10)
        self.setpoint_pub = self.node.create_publisher(Float32, self.topics[2], 10)

        self.state_sub = self.node.create_subscription(
            Float32,
            self.topics[1],
            lambda msg: setattr(self, "_state", msg.data),
            10,
        )
        self.setpoint_sub = self.node.create_subscription(
            Float32,
            self.topics[2],
            lambda msg: setattr(self, "_setpoint", msg.data),
            10,
        )
        self.control_sub = self.node.create_subscription(
            Float32,
            self.topics[0],
            self._control_callback,
            10,
        )

    def _init_client_params(self):
        self.cli = self.node.create_client(
            SetParameters, "ros2_pid_library/set_parameters"
        )
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().info("service not available, waiting again...")
        self.req = SetParameters.Request()

    def _control_callback(self, msg: Float32):
        """
        Callback para o tópico de controle.
        """

        self.control_effort = msg.data
        if self.callback:
            self.callback(self.control_effort)

    def enable(self, enable: bool):
        """
        Habilita ou desabilita o controlador.
        """

        self.able = enable

        new_param_value = ParameterValue()
        new_param_value.bool_value = enable
        new_param_value.type = ParameterType.PARAMETER_BOOL

        self.req.parameters = [Parameter(name="pid_enabled", value=new_param_value)]
        self.future = self.cli.call_async(self.req)

        if self.future.done():
            try:
                response = self.future.result()
                self.node.get_logger().info(f"Response: {response}")
            except Exception as e:
                self.node.get_logger().error(f"Service call failed: {e}")

    @property
    def setpoint(self):
        return self._setpoint

    @setpoint.setter
    def setpoint(self, value):
        print("setter")
        self._setpoint = value
        self.setpoint_msg.data = self._setpoint
        self.setpoint_pub.publish(self.setpoint_msg)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self.setpoint_msg.data = self._setpoint
        self.setpoint_pub.publish(self.setpoint_msg)

        self._state = value
        self.state_msg.data = self._state
        self.state_pub.publish(self.state_msg)
