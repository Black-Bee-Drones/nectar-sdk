from mirela_sdk.vision.camera import ImageHandler
import rclpy
from rclpy.node import Node


class OakdTeste(Node):

    def __init__(self) -> None:
        super().__init__("oakd_test")
        self.img_handler = ImageHandler(self, "oakd", show_result="Teste oakd")
        self.img_handler.run()


def main():

    rclpy.init()
    teste = OakdTeste()
    rclpy.spin(teste)
    rclpy.shutdown()


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        pass
