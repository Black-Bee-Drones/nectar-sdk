import cv2
import os
import numpy as np
import glob
import rclpy
from time import sleep
from rclpy.node import Node
from mirela_sdk.image_processing.camera.image_handler import ImageHandler

class Calibration(Node):

    """
    Class to calibrate a camera with OpenCV and a chessboard
    """

    def __init__(self, chessboard_size: tuple = (9,7)):

        """
        Calibration class constructor
        ----------------------------

        :param chessboard_size (tuple(int, int)): the chessboard size that is used in calibration
            default: (9,7)

        """

        super().__init__("camera_calibration_node")

        # Chessboard parameters
        self.chessboard_size = chessboard_size  # Number of inner corners on the board (width x height)
        self.path = os.path.dirname(__file__)
        
        # Prepare 3D object points
        self.objp = np.zeros((np.prod(self.chessboard_size), 3), dtype=np.float32)
        self.objp[:, :2] = np.indices(self.chessboard_size).T.reshape(-1, 2)

        # Lists to store 3D object points and 2D image points
        self.object_points = []
        self.image_points = []

    def __photo(self, img):

        if self.cont == 10:

            self.photos += 1
            cv2.imwrite(f"{self.path}/dataset/chessboard{self.photos}.jpg", img)
            self.get_logger().info(f"Saving photo number {self.photos}")
            self.cont = 0

        if self.photos == 100:
            self.get_logger().info("Photos completed")
            self.image_handler.cleanup()

        self.cont += 1

            

    def run_photos(self):
        self.get_logger().info("Taking photos to dataset")
        self.cont = 1
        self.photos = 0
        self.image_handler = ImageHandler(self, "webcam", self.__photo, None, 0)
        self.image_handler.run()

    def __find_corners(self, show_result: bool):

        list_of_image_files = glob.glob(f'{self.path}/dataset/*.jpg')
        imgs_detected = 0
        # Load and process each image
        for image_file in list_of_image_files:
            image = cv2.imread(image_file)
            self.gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Detect chessboard corners
            ret, corners = cv2.findChessboardCorners(self.gray, self.chessboard_size, None)

            # If corners are found, add object and image points
            if ret:
                self.object_points.append(self.objp)
                self.image_points.append(corners)
                imgs_detected += 1
                self.get_logger().info(f"Images with found corners: {imgs_detected}")

                if show_result:

                    # Draw and display the corners
                    cv2.drawChessboardCorners(image, self.chessboard_size, corners, ret)
                    cv2.imshow('img', image)
                    cv2.waitKey(500)

        cv2.destroyAllWindows()

    def calibrate(self, show_corners: bool = False):
        """
        Function to initialize the calibration with the search for the chessboard
        corners in the images from dataset and obtaining calibration and distortion 
        matrices

        :param show_corners (bool): True for show the images with corners drawn, False for not
        """

        self.__find_corners(show_corners)
        # Calibrate the camera
        ret, self.calibration_matrix, self.dist_matrix, rvecs, tvecs = cv2.calibrateCamera(
            self.object_points, self.image_points, self.gray.shape[::-1], None, None
        )

        self.distortion_list = self.dist_matrix.ravel()
        print("Calibration matrix:\n", self.calibration_matrix)
        print("Distortion:\n", self.distortion_list)

    def overwrite_matrices(self):

        """
        Functions to write or overwrite the calibration and distortion matrices files
        """

        with open(f"{self.path}/camera_matrix.txt", "w") as matrix:

            for i in range (len(self.calibration_matrix)):
                for j in range(len(self.calibration_matrix[i])):
                    matrix.write(str(self.calibration_matrix[i][j]))
                    if j != len(self.calibration_matrix[i]) -1:
                        matrix.write(",")

                if i != len(self.calibration_matrix) - 1:
                    matrix.write("\n")

        with open(f"{self.path}/camera_distortion.txt", "w") as distortion:
            for i in range (len(self.distortion_list)):
                distortion.write(str(self.distortion_list[i]))
                if i != len(self.distortion_list) - 1:
                    distortion.write(",")


def main():
    rclpy.init()
    calibration = Calibration()
    # calibration.run_photos()
    calibration.calibrate(show_corners=False)
    calibration.overwrite_matrices()
    rclpy.spin(calibration)
    rclpy.shutdown()

if __name__ == "__main__":
    main()
