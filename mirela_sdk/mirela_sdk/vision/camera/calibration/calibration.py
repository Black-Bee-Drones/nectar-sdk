import cv2
import os
import numpy as np
import glob
import rclpy
from rclpy.node import Node
from mirela_sdk.vision.camera.handler import ImageHandler


class Calibration(Node):
    """
    Class to calibrate a camera with OpenCV and a chessboard
    """

    PATH = os.path.dirname(__file__)

    def __init__(self, chessboard_size: tuple = (9, 7)) -> None:
        """
        Calibration class constructor
        ----------------------------

        :param chessboard_size (tuple(int, int)): the chessboard size that is used in calibration
            default: (9,7)

        """

        super().__init__("camera_calibration_node")

        # Chessboard parameters
        self.chessboard_size = (
            chessboard_size  # Number of inner corners on the board (width x height)
        )

        # Prepare 3D object points
        self.objp = np.zeros((np.prod(self.chessboard_size), 3), dtype=np.float32)
        self.objp[:, :2] = np.indices(self.chessboard_size).T.reshape(-1, 2)

        # Lists to store 3D object points and 2D image points
        self.object_points = []
        self.image_points = []

    def __photo(self, img) -> None:

        # TODO: add time duration logic to this
        if self.cont == 30:

            self.photos += 1
            cv2.imwrite(f"{Calibration.PATH}/dataset/chessboard{self.photos}.jpg", img)
            self.get_logger().info(f"Saving photo number {self.photos}")
            self.cont = 0

        if self.photos == self.num_photos:
            self.get_logger().info("Photos completed")
            self.image_handler.cleanup()
            self.calibrate(show_corners=True)
            self.overwrite_matrices()

        self.cont += 1

    def run_photos(self, num_photos: int) -> None:
        """
        Function to initialize photos capture to store on dataset folder

        :param num_photos (int): Number of photos to take

        """
        self.get_logger().info("Taking photos to dataset")
        self.num_photos = num_photos
        self.cont = 1
        self.photos = 0
        self.image_handler = ImageHandler(self, "webcam", self.__photo, None, 0)
        self.image_handler.run()

    def __find_corners(self, show_result: bool) -> None:

        list_of_image_files = glob.glob(f"{Calibration.PATH}/dataset/*.jpg")
        imgs_detected = 0

        # Load and process each image
        for image_file in list_of_image_files:
            image = cv2.imread(image_file)
            self.gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Detect chessboard corners
            ret, corners = cv2.findChessboardCorners(
                self.gray, self.chessboard_size, None
            )

            # If corners are found, add object and image points
            if ret:
                self.object_points.append(self.objp)
                self.image_points.append(corners)
                imgs_detected += 1
                self.get_logger().info(f"Images with found corners: {imgs_detected}")

                if show_result:

                    # Draw and display the corners
                    cv2.drawChessboardCorners(image, self.chessboard_size, corners, ret)
                    cv2.imshow("img", image)
                    cv2.waitKey(500)

        cv2.destroyAllWindows()

    def calibrate(self, show_corners: bool = False) -> None:
        """
        Function to initialize the calibration with the search for the chessboard
        corners in the images from dataset and obtaining calibration and distortion
        matrices

        :param show_corners (bool): True for show the images with corners drawn, False for not
        """

        self.__find_corners(show_corners)
        # Calibrate the camera
        ret, self.calibration_matrix, self.dist_matrix, rvecs, tvecs = (
            cv2.calibrateCamera(
                self.object_points, self.image_points, self.gray.shape[::-1], None, None
            )
        )

        self.distortion_list = self.dist_matrix.ravel()
        print("Calibration matrix:\n", self.calibration_matrix)
        print("Distortion:\n", self.distortion_list)

    def overwrite_matrices(self) -> None:
        """
        Functions to write or overwrite the calibration and distortion matrices files
        """

        with open(f"{Calibration.PATH}/camera_matrix.txt", "w") as matrix:

            for i in range(len(self.calibration_matrix)):
                for j in range(len(self.calibration_matrix[i])):
                    matrix.write(str(self.calibration_matrix[i][j]))
                    if j != len(self.calibration_matrix[i]) - 1:
                        matrix.write(",")

                if i != len(self.calibration_matrix) - 1:
                    matrix.write("\n")

        with open(f"{Calibration.PATH}/camera_distortion.txt", "w") as distortion:
            for i in range(len(self.distortion_list)):
                distortion.write(str(self.distortion_list[i]))
                if i != len(self.distortion_list) - 1:
                    distortion.write(",")

    @classmethod
    def get_camera_matrix_distortion(cls) -> tuple[list, list]:
        """
        Class method to get the camera matrix and distortion coefficients from .txt files.

        Use this function only if you are sure that calibration is complete and the files exist.
        """

        camera_matrix_list = np.loadtxt(f"{cls.PATH}/camera_matrix.txt", delimiter=",")
        camera_distortion_list = np.loadtxt(
            f"{cls.PATH}/camera_distortion.txt", delimiter=","
        )

        return (camera_matrix_list, camera_distortion_list)


def main():

    rclpy.init()
    try:
        calibration = Calibration(chessboard_size=(9, 7))
        calibration.run_photos(num_photos=50)
        rclpy.spin(calibration)

    except KeyboardInterrupt:
        ...
    except Exception as ex:
        print("Exception: ", ex)
    finally:
        calibration.destroy_node()


if __name__ == "__main__":
    main()
