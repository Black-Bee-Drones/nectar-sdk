import rclpy
from rclpy.node import Node
from time import time
from mirela_sdk.control.bebop.bebop_api import Bebop
from mirela_sdk.image_processing.aruco.aruco_detect import Aruco
from mirela_sdk.image_processing.camera.image_handler import ImageHandler

class ArucoController(Node):
    def __init__(self):
        super().__init__("aruco_controller")

        self.bebop = Bebop(bebop_driver=False)
        self.aruco = Aruco(5, 20)
        self.img = ImageHandler(self, "webcam", self.run, "Aruco detection", 0)

        self.currentID = None
        self.previousID = None
        self.already_sent = False
        self.t_start = None

        self.continuous_actions: dict[int, tuple[str, callable]] = {
            0:   ("Trás", lambda :self.bebop.offboard_velocity(-0.1, 0.0, 0.0, 0.0)),
            200: ("Frente", lambda :self.bebop.offboard_velocity(0.1, 0.0, 0.0, 0.0)),
        }

        self.single_actions: dict[int, tuple[str, callable]] = {
            600: ("Flip frente", lambda :self.bebop.flip(0)),
            700: ("Flip direita", lambda :self.bebop.flip(2)),
            800: ("Flip tras", lambda :self.bebop.flip(1)),

        }

        self.img.run()

    def run(self, img):
        
        cam = img
        _, id = self.aruco.detect(cam, True)

        if id is not None:
            self.previousID = self.currentID
            self.currentID = id

            if self.previousID == self.currentID and self.previousID is not None:
                if self.t_start is None:
                    self.t_start = time()

            else:
                self.already_sent = False
                self.t_start = None

            if self.t_start is not None and time() - self.t_start >= 0.5:
                action_name, action_func = self.continuous_actions.get(self.currentID, ("Unknown", None))
                if action_func:
                    self.get_logger().info(f"{action_name}")
                    action_func()

                action_name, action_func = self.single_actions.get(
                self.currentID, ("Unknown", None)
            )
                if action_func and not self.already_sent:
                    self.get_logger().info(f"Action: {action_name}")
                    action_func()
                    self.already_sent = True



def main(args = None):
    rclpy.init(args = args)
    aruco_node = ArucoController()

    rclpy.spin(aruco_node)
    aruco_node.destroy_node()
    rclpy.shutdown()


if __name__ ==  "__main__":
    main()