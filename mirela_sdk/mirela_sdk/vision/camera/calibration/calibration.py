import os
import glob
from typing import Optional, Tuple

import cv2
import numpy as np

import rclpy
from rclpy.node import Node

from mirela_sdk.vision.camera.handler import ImageHandler


class Calibration(Node):
    """
    Camera calibration using chessboard pattern.

    Captures images of a chessboard pattern and computes camera intrinsic
    matrix and distortion coefficients using OpenCV's calibration functions.

    Parameters
    ----------
    chessboard_size : tuple of int, optional
        Number of inner corners (width, height). Default is (9, 7).

    Attributes
    ----------
    calibration_matrix : np.ndarray or None
        3x3 camera intrinsic matrix after calibration.
    dist_matrix : np.ndarray or None
        Distortion coefficients after calibration.

    Notes
    -----
    Calibration workflow:
    1. Call run_photos() to capture chessboard images
    2. Images are saved to dataset/ folder
    3. calibrate() is called automatically after capture
    4. Results are saved to camera_matrix.txt and camera_distortion.txt
    """

    PATH = os.path.dirname(__file__)

    def __init__(self, chessboard_size: Tuple[int, int] = (9, 7)) -> None:
        super().__init__("camera_calibration_node")

        self.chessboard_size = chessboard_size

        self.objp = np.zeros((np.prod(self.chessboard_size), 3), dtype=np.float32)
        self.objp[:, :2] = np.indices(self.chessboard_size).T.reshape(-1, 2)

        self.object_points: list = []
        self.image_points: list = []

        self.calibration_matrix: Optional[np.ndarray] = None
        self.dist_matrix: Optional[np.ndarray] = None
        self.distortion_list: Optional[np.ndarray] = None
        self.gray: Optional[np.ndarray] = None

        self._num_photos: int = 0
        self._frame_count: int = 0
        self._photos_taken: int = 0
        self._image_handler: Optional[ImageHandler] = None

    def _capture_callback(self, img: np.ndarray) -> None:
        """Callback for capturing calibration images at intervals."""
        if img is None:
            return

        self._frame_count += 1

        if self._frame_count >= 30:
            self._photos_taken += 1
            filepath = f"{Calibration.PATH}/dataset/chessboard{self._photos_taken}.jpg"
            cv2.imwrite(filepath, img)
            self.get_logger().info(
                f"Captured photo {self._photos_taken}/{self._num_photos}"
            )
            self._frame_count = 0

        if self._photos_taken >= self._num_photos:
            self.get_logger().info("Photo capture complete")
            if self._image_handler:
                self._image_handler.cleanup()
            self.calibrate(show_corners=True)
            self.save_matrices()

    def run_photos(self, num_photos: int = 50) -> None:
        """
        Start capturing calibration images.

        Captures images at regular intervals and saves them to the dataset
        folder for later calibration processing.

        Parameters
        ----------
        num_photos : int, optional
            Number of photos to capture. Default is 50.
        """
        self.get_logger().info(f"Starting capture of {num_photos} calibration images")

        self._num_photos = num_photos
        self._frame_count = 0
        self._photos_taken = 0

        self._image_handler = ImageHandler(
            node=self,
            image_source="webcam",
            image_processing_callback=self._capture_callback,
        )
        self._image_handler.run()

    def _find_corners(self, show_result: bool = False) -> int:
        """
        Detect chessboard corners in dataset images.

        Parameters
        ----------
        show_result : bool, optional
            Display images with detected corners. Default is False.

        Returns
        -------
        int
            Number of images with successfully detected corners.
        """
        image_files = glob.glob(f"{Calibration.PATH}/dataset/*.jpg")
        detected_count = 0

        for image_file in image_files:
            image = cv2.imread(image_file)
            if image is None:
                continue

            self.gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            ret, corners = cv2.findChessboardCorners(
                self.gray, self.chessboard_size, None
            )

            if ret:
                self.object_points.append(self.objp)
                self.image_points.append(corners)
                detected_count += 1
                self.get_logger().info(
                    f"Corners found: {detected_count}/{len(image_files)}"
                )

                if show_result:
                    cv2.drawChessboardCorners(image, self.chessboard_size, corners, ret)
                    cv2.imshow("Calibration", image)
                    cv2.waitKey(500)

        cv2.destroyAllWindows()
        return detected_count

    def calibrate(self, show_corners: bool = False) -> bool:
        """
        Run camera calibration on captured images.

        Detects chessboard corners in dataset images and computes camera
        intrinsic matrix and distortion coefficients.

        Parameters
        ----------
        show_corners : bool, optional
            Display detected corners during processing. Default is False.

        Returns
        -------
        bool
            True if calibration succeeded, False otherwise.
        """
        detected = self._find_corners(show_corners)

        if detected == 0:
            self.get_logger().error("No chessboard corners detected in any image")
            return False

        if self.gray is None:
            self.get_logger().error("No valid images for calibration")
            return False

        _, self.calibration_matrix, self.dist_matrix, _, _ = cv2.calibrateCamera(
            self.object_points,
            self.image_points,
            self.gray.shape[::-1],
            None,
            None,
        )

        self.distortion_list = self.dist_matrix.ravel()

        self.get_logger().info(f"Calibration matrix:\n{self.calibration_matrix}")
        self.get_logger().info(f"Distortion coefficients: {self.distortion_list}")

        return True

    def save_matrices(self) -> None:
        """
        Save calibration results to text files.

        Writes camera_matrix.txt and camera_distortion.txt to the
        calibration module directory.
        """
        if self.calibration_matrix is None or self.distortion_list is None:
            self.get_logger().error("No calibration data to save")
            return

        matrix_path = f"{Calibration.PATH}/camera_matrix.txt"
        with open(matrix_path, "w", encoding="utf-8") as f:
            for i, row in enumerate(self.calibration_matrix):
                f.write(",".join(str(v) for v in row))
                if i < len(self.calibration_matrix) - 1:
                    f.write("\n")

        distortion_path = f"{Calibration.PATH}/camera_distortion.txt"
        with open(distortion_path, "w", encoding="utf-8") as f:
            f.write(",".join(str(v) for v in self.distortion_list))

        self.get_logger().info(f"Saved calibration to {Calibration.PATH}")

    @classmethod
    def load_calibration(cls) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load calibration data from files.

        Returns
        -------
        tuple of np.ndarray
            Camera matrix (3x3) and distortion coefficients.

        Raises
        ------
        FileNotFoundError
            If calibration files do not exist.
        """
        matrix_path = f"{cls.PATH}/camera_matrix.txt"
        distortion_path = f"{cls.PATH}/camera_distortion.txt"

        if not os.path.exists(matrix_path) or not os.path.exists(distortion_path):
            raise FileNotFoundError(
                "Calibration files not found. Run calibration first."
            )

        camera_matrix = np.loadtxt(matrix_path, delimiter=",")
        distortion = np.loadtxt(distortion_path, delimiter=",")

        return camera_matrix, distortion


def main(args=None) -> None:
    """Entry point for camera calibration node."""
    rclpy.init(args=args)

    node = Calibration(chessboard_size=(9, 7))

    try:
        node.run_photos(num_photos=50)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
