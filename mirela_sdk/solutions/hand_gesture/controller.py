import rclpy
from rclpy.node import Node

from std_msgs.msg import Int16

from time import time

from mirela_sdk.control.bebop.bebop_api import Bebop


class GestureController(Node):

    def __init__(self) -> None:
        super().__init__("gesture_controller")

        self.bebop = Bebop(bebop_driver=False)
        self.create_subscription(
            Int16, "/bebop/hands_action", self._moviment_callback, 10
        )

        self.action_counter: int = 0
        self.previous_action: int = 0
        self.current_action: int = 0
        self.already_sent: bool = False

        self.continuous_actions: dict[int, tuple[str, callable]] = {
            -1: ("Nada", lambda: self.bebop.offboard_velocity(0.0, 0.0, 0.0, 0.0)),
            2: ("Sobe", lambda: self.bebop.offboard_velocity(0.0, 0.0, 0.1, 0.0)),
            3: ("Desce", lambda: self.bebop.offboard_velocity(0.0, 0.0, -0.1, 0.0)),
            4: ("Esquerda", lambda: self.bebop.offboard_velocity(0.0, -0.1, 0.0, 0.0)),
            5: ("Direita", lambda: self.bebop.offboard_velocity(0.0, 0.1, 0.0, 0.0)),
            11: (
                "Anda pra trás",
                lambda: self.bebop.offboard_velocity(-0.2, 0.0, 0.0, 0.0),
            ),
            12: (
                "Anda pra frente",
                lambda: self.bebop.offboard_velocity(0.2, 0.0, 0.0, 0.0),
            ),
            13: (
                "Yaw Horário",
                lambda: self.bebop.offboard_velocity(0.0, 0.0, 0.0, 0.2),
            ),
            14: (
                "Yaw Anti-Horário",
                lambda: self.bebop.offboard_velocity(0.0, 0.0, 0.0, -0.2),
            ),
        }

        self.single_actions: dict[int, tuple[str, callable]] = {
            1: ("Land", lambda: self.bebop.land()),
            6: ("Flip Direita", lambda: self.bebop.flip(2)),
            7: ("Flip Esquerda", lambda: self.bebop.flip(3)),
            8: ("Flip Frente", lambda: self.bebop.flip(0)),
            9: ("Flip Tras", lambda: self.bebop.flip(1)),
            10: ("Tirando Foto", lambda: self.bebop.snapshot()),
            15: ("Tchau", lambda: self.bebop.bye_bye()),
        }

        self.start_time = None

    def _moviment_callback(self, msg: Int16) -> None:
        """
        Callback function for the gesture recognizer node.

        :param msg (Int16): The message received from the gesture recognizer node (hand_gesture/gesture_recognizer.py).
        """
        self.previous_action = self.current_action
        self.current_action = msg.data

        if self.previous_action == self.current_action and self.previous_action != 0:
            if self.start_time is None:
                self.start_time = time()
        else:
            self.start_time = None
            self.already_sent = False

        if self.start_time is not None and time() - self.start_time >= 0.5:
            action_name, action_func = self.continuous_actions.get(
                self.current_action, ("Unknown", None)
            )
            if action_func:
                self.get_logger().info(f"Action: {action_name}")
                action_func()

            action_name, action_func = self.single_actions.get(
                self.current_action, ("Unknown", None)
            )
            if action_func and not self.already_sent:
                self.get_logger().info(f"Action: {action_name}")
                action_func()
                self.already_sent = True


def main(args=None):
    rclpy.init(args=args)

    controller = GestureController()

    rclpy.spin(controller)

    controller.bebop.land()
    controller.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
