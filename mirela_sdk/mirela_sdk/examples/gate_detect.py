import rclpy
from rclpy.node import Node
import cv2

from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.image_processing.color.color_detector import ColorDetector


class GateDetector(Node):
    def __init__(self, image_source: str = None):
        super().__init__("gate_detector")

        if image_source is None:
            self.declare_parameter("image_source", "/bebop/camera/image_raw")
            image_source = self.get_parameter("image_source").value

        self.image_source = image_source
        self.image_handler = ImageHandler(
            self, self.image_source, image_processing_callback=self.process
        )
        self.color_detector = ColorDetector("preset", "gate")

        self.get_logger().info("Gate detection node initialized")
        self.get_logger().info("Press 'q' to exit or 's' to save calibration values")

        self.image_handler.run()

    def process(self, img):
        try:
            if img is not None:
                img = img.copy()
                self.color_detector.filterColor(img.copy())

                filter_img = self.color_detector.result.copy()

                # Converter a imagem filtrada para escala de cinza
                gray_img = cv2.cvtColor(filter_img.copy(), cv2.COLOR_BGR2GRAY)

                # Encontrar contornos
                contours, _ = cv2.findContours(
                    gray_img.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
                )

                sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)

                contours = sorted_contours[:4]

                print("Len:", len(contours))

                for contour in contours:
                    # Obter um retângulo delimitador para o contorno
                    x, y, w, h = cv2.boundingRect(contour)

                    # print(x, y, w, h)

                    # Filtrar retângulos com base em suas proporções
                    # if 0.9 < w / h < 1.1:  # Altere esses valores conforme necessário
                    # Desenhar o retângulo na imagem
                    cv2.rectangle(filter_img, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Calcular e desenhar o centro do retângulo
                    center = (int(x + w / 2), int(y + h / 2))
                    cv2.circle(filter_img, center, 5, (0, 0, 255), -1)

                cv2.imshow("Color Calibration", filter_img)
                cv2.imshow("Gray Image", gray_img)
                cv2.imshow("Gate Detection", img)

                key = cv2.waitKey(1)

                if key == ord("q"):
                    self.image_handler.cleanup()
                    cv2.destroyAllWindows()
        except Exception as e:
            self.get_logger().error(f"Failed to process image: {str(e)}")


def main(args=None):
    rclpy.init(args=args)

    gate_detector = GateDetector("/home/samuel/Códigos/teste/gate.jpeg")

    rclpy.spin(gate_detector)

    gate_detector.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
