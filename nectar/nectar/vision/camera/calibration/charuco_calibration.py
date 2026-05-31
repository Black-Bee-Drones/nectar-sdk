#!/usr/bin/env python3
import glob
import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from nectar.vision.camera.config import OpenCVConfig
from nectar.vision.camera.handler import ImageHandler


class CharucoCalibration(Node):
    """
    Camera calibration using a ChArUco board.

    Captures images of a ChArUco board and computes camera intrinsic
    matrix and distortion coefficients using OpenCV's ChArUco detector
    combined with ``cv2.calibrateCamera``.

    Compared to the plain chessboard pipeline (``Calibration``), this
    keeps subpixel chessboard-corner accuracy while accepting frames
    where the board is partially occluded or partially outside the
    image, which is critical for sampling the image borders where lens
    distortion is strongest.

    Parameters
    ----------
    squares_x : int, optional
        Number of squares in the X direction. Default is 5.
    squares_y : int, optional
        Number of squares in the Y direction. Default is 7.
    square_length : float, optional
        Side length of a chessboard square in meters. Default is 0.040.
        Use the *measured* value of the printed board, not the nominal
        one from the source PDF (printers always rescale).
    marker_length : float, optional
        Side length of an ArUco marker in meters. Default is 0.030.
        Must match the same scaling factor as ``square_length``.
    aruco_dict_id : int, optional
        OpenCV predefined ArUco dictionary identifier. Default is
        ``cv2.aruco.DICT_4X4_1000`` (matches DictionaryNumber 3 in the
        ``carlosmccosta/charuco_detector`` board PDFs).
    min_corners_per_frame : int, optional
        Minimum number of ChArUco corners required to accept a frame
        for calibration. Default is 6.
    image_source : str, optional
        Camera source passed to ``ImageHandler``. Default is ``"webcam"``.
    device_index : int, optional
        OpenCV ``VideoCapture`` device index. Only used when
        ``image_source`` is ``"webcam"`` or ``"opencv"``. Default is 0.
    width : int, optional
        Requested capture width in pixels. Only used for webcam /
        OpenCV sources. ``0`` means "use the camera default". Default
        is 0. **Calibrate at the same resolution you'll use in
        production** -- the intrinsic matrix is resolution-specific.
    height : int, optional
        Requested capture height in pixels. Default is 0 (camera
        default). See ``width`` for behavior.
    num_photos : int, optional
        Number of dataset frames to capture. Default is 30.
    show_preview : bool, optional
        Display a live preview window during capture with capture
        progress and live ChArUco detection overlay. Default is True.
    show_corners : bool, optional
        Display detected ChArUco corners during the post-capture
        calibration pass. Default is True.
    output_dir : str, optional
        Directory where ``camera_matrix.txt`` and ``camera_distortion.txt``
        will be written, and where the ``dataset_charuco/`` capture
        folder will be created. Empty string (the default) resolves to
        the ``nectar.vision.camera.calibration`` package directory so
        that ``load_calibration()`` finds the result without further
        configuration.

    ROS Parameters
    --------------
    Every constructor argument above is also exposed as a ROS parameter
    with the same name (``aruco_dict_id`` is exposed as ``aruco_dict``
    and accepts the dictionary name as a string, e.g. ``"DICT_4X4_1000"``
    or the shorthand ``"4X4_1000"``). Values passed via ``--ros-args -p``
    override the constructor defaults.

    Attributes
    ----------
    calibration_matrix : np.ndarray or None
        3x3 camera intrinsic matrix after calibration.
    dist_matrix : np.ndarray or None
        Distortion coefficients after calibration.
    reprojection_error : float or None
        Mean reprojection error (in pixels) returned by
        ``cv2.calibrateCamera``. Aim for < 0.5 px.

    Notes
    -----
    Calibration workflow:

    1. Call ``run_photos()`` to capture board images
    2. Images are saved to ``dataset_charuco/``
    3. ``calibrate()`` is called automatically after capture
    4. Results are saved to ``camera_matrix.txt`` and
       ``camera_distortion.txt`` (same filenames as the chessboard
       pipeline, so ``Calibration.load_calibration()`` keeps working)
    """

    DATASET_DIR = "dataset_charuco"
    PREVIEW_WINDOW = "ChArUco Capture"

    def __init__(
        self,
        squares_x: int = 5,
        squares_y: int = 7,
        square_length: float = 0.040,
        marker_length: float = 0.030,
        aruco_dict_id: int = cv2.aruco.DICT_4X4_1000,
        min_corners_per_frame: int = 6,
        image_source: str = "webcam",
        device_index: int = 0,
        width: int = 0,
        height: int = 0,
        num_photos: int = 30,
        show_preview: bool = True,
        show_corners: bool = True,
        output_dir: str = "",
    ) -> None:
        super().__init__("camera_charuco_calibration_node")

        self.declare_parameter("image_source", image_source)
        self.declare_parameter("device_index", int(device_index))
        self.declare_parameter("width", int(width))
        self.declare_parameter("height", int(height))
        self.declare_parameter("squares_x", int(squares_x))
        self.declare_parameter("squares_y", int(squares_y))
        self.declare_parameter("square_length", float(square_length))
        self.declare_parameter("marker_length", float(marker_length))
        self.declare_parameter("aruco_dict", self._aruco_dict_name(aruco_dict_id))
        self.declare_parameter("num_photos", int(num_photos))
        self.declare_parameter("min_corners_per_frame", int(min_corners_per_frame))
        self.declare_parameter("show_preview", bool(show_preview))
        self.declare_parameter("show_corners", bool(show_corners))
        self.declare_parameter("output_dir", str(output_dir))

        self.image_source = self.get_parameter("image_source").value
        self.device_index = int(self.get_parameter("device_index").value)
        self.width = int(self.get_parameter("width").value)
        self.height = int(self.get_parameter("height").value)
        self.squares_x = int(self.get_parameter("squares_x").value)
        self.squares_y = int(self.get_parameter("squares_y").value)
        self.square_length = float(self.get_parameter("square_length").value)
        self.marker_length = float(self.get_parameter("marker_length").value)
        self.num_photos = int(self.get_parameter("num_photos").value)
        self.min_corners_per_frame = int(self.get_parameter("min_corners_per_frame").value)
        self.show_preview = bool(self.get_parameter("show_preview").value)
        self.show_corners = bool(self.get_parameter("show_corners").value)
        self.output_dir = str(self.get_parameter("output_dir").value) or self._package_dir()

        resolved_dict_id = self._resolve_aruco_dict(self.get_parameter("aruco_dict").value)

        self.dictionary = cv2.aruco.getPredefinedDictionary(resolved_dict_id)
        self.board = cv2.aruco.CharucoBoard(
            (self.squares_x, self.squares_y),
            self.square_length,
            self.marker_length,
            self.dictionary,
        )

        self.detector = cv2.aruco.CharucoDetector(
            self.board,
            cv2.aruco.CharucoParameters(),
            cv2.aruco.DetectorParameters(),
        )

        self.get_logger().info(
            f"ChArUco board: {self.squares_x}x{self.squares_y}, "
            f"square={self.square_length:.4f} m, marker={self.marker_length:.4f} m, "
            f"dict={self.get_parameter('aruco_dict').value}"
        )

        self.all_object_points: List[np.ndarray] = []
        self.all_image_points: List[np.ndarray] = []

        self.calibration_matrix: Optional[np.ndarray] = None
        self.dist_matrix: Optional[np.ndarray] = None
        self.distortion_list: Optional[np.ndarray] = None
        self.reprojection_error: Optional[float] = None
        self.image_size: Optional[Tuple[int, int]] = None

        self._num_photos: int = 0
        self._frame_count: int = 0
        self._photos_taken: int = 0
        self._image_handler: Optional[ImageHandler] = None

        os.makedirs(
            os.path.join(self.output_dir, CharucoCalibration.DATASET_DIR),
            exist_ok=True,
        )

        self.get_logger().info(f"Calibration output dir: {self.output_dir}")

    def _capture_callback(self, img: np.ndarray) -> None:
        """Callback for capturing calibration images at intervals."""
        if img is None:
            return

        self._frame_count += 1

        if self._frame_count >= 30:
            self._photos_taken += 1
            filepath = os.path.join(
                self.output_dir,
                CharucoCalibration.DATASET_DIR,
                f"charuco{self._photos_taken}.jpg",
            )
            cv2.imwrite(filepath, img)
            self.get_logger().info(f"Captured photo {self._photos_taken}/{self._num_photos}")
            self._frame_count = 0

        if self.show_preview:
            self._draw_preview_overlay(img)

        if self._photos_taken >= self._num_photos:
            self.get_logger().info("Photo capture complete")
            if self._image_handler:
                self._image_handler.cleanup()
            self.calibrate(show_corners=self.show_corners)
            self.save_matrices()

    def _draw_preview_overlay(self, img: np.ndarray) -> None:
        """
        Draw live capture progress and ChArUco detection on the frame.

        Runs ChArUco detection on the current frame and overlays the
        detected markers/corners plus a status line. Mutates ``img`` in
        place; must be called *after* ``cv2.imwrite`` so the saved
        dataset stays free of drawings.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        charuco_corners, charuco_ids, marker_corners, marker_ids = self.detector.detectBoard(gray)

        if marker_ids is not None and len(marker_ids) > 0:
            cv2.aruco.drawDetectedMarkers(img, marker_corners, marker_ids)

        n_corners = 0
        if charuco_ids is not None:
            cv2.aruco.drawDetectedCornersCharuco(img, charuco_corners, charuco_ids)
            n_corners = len(charuco_ids)

        good = n_corners >= self.min_corners_per_frame
        status = f"Board: {n_corners} corners" if n_corners > 0 else "Board: not detected"

        cv2.putText(
            img,
            f"Captured {self._photos_taken}/{self._num_photos}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            img,
            status,
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0) if good else (0, 0, 255),
            2,
        )

    def run_photos(self, num_photos: Optional[int] = None) -> None:
        """
        Start capturing calibration images.

        Captures images at regular intervals and saves them to the
        ``dataset_charuco/`` folder for later calibration processing.

        For webcam / OpenCV sources, ``device_index`` controls which
        ``/dev/video*`` device is opened. For other sources the index
        is ignored.

        Parameters
        ----------
        num_photos : int, optional
            Number of photos to capture. Defaults to the ``num_photos``
            ROS parameter (constructor default: 30).
        """
        if num_photos is None:
            num_photos = self.num_photos

        source_info = f"[{self.image_source}]"
        if self._uses_opencv_source():
            source_info += f" device={self.device_index}"
            if self.width > 0 and self.height > 0:
                source_info += f" {self.width}x{self.height}"

        self.get_logger().info(
            f"Starting capture of {num_photos} ChArUco calibration images from {source_info}"
        )

        self._num_photos = num_photos
        self._frame_count = 0
        self._photos_taken = 0

        config = (
            OpenCVConfig(
                device_index=self.device_index,
                width=self.width if self.width > 0 else None,
                height=self.height if self.height > 0 else None,
            )
            if self._uses_opencv_source()
            else None
        )

        self._image_handler = ImageHandler(
            image_source=self.image_source,
            image_processing_callback=self._capture_callback,
            show_result=(CharucoCalibration.PREVIEW_WINDOW if self.show_preview else None),
            config=config,
        )
        self._image_handler.run()

    def _uses_opencv_source(self) -> bool:
        """Whether the configured ``image_source`` is an OpenCV webcam."""
        return self.image_source.lower() in ("webcam", "opencv")

    def _detect_in_dataset(self, show_result: bool = False) -> int:
        """
        Detect ChArUco corners in dataset images.

        Builds ``all_object_points`` and ``all_image_points`` from each
        frame where the board is detected with at least
        ``min_corners_per_frame`` corners.

        Parameters
        ----------
        show_result : bool, optional
            Display images with detected corners. Default is False.

        Returns
        -------
        int
            Number of images that contributed valid views.
        """
        dataset_path = os.path.join(self.output_dir, CharucoCalibration.DATASET_DIR)
        image_files = sorted(glob.glob(os.path.join(dataset_path, "*.jpg")))
        detected_count = 0

        for image_file in image_files:
            image = cv2.imread(image_file)
            if image is None:
                continue

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            if self.image_size is None:
                self.image_size = (gray.shape[1], gray.shape[0])

            charuco_corners, charuco_ids, _, _ = self.detector.detectBoard(gray)

            if charuco_ids is None or len(charuco_ids) < self.min_corners_per_frame:
                continue

            obj_pts, img_pts = self.board.matchImagePoints(charuco_corners, charuco_ids)

            if obj_pts is None or len(obj_pts) < self.min_corners_per_frame:
                continue

            self.all_object_points.append(obj_pts)
            self.all_image_points.append(img_pts)
            detected_count += 1
            self.get_logger().info(
                f"Valid view {detected_count}/{len(image_files)} ({len(charuco_ids)} corners)"
            )

            if show_result:
                vis = image.copy()
                cv2.aruco.drawDetectedCornersCharuco(vis, charuco_corners, charuco_ids)
                cv2.imshow("ChArUco Calibration", vis)
                cv2.waitKey(500)

        cv2.destroyAllWindows()
        return detected_count

    def calibrate(self, show_corners: bool = False) -> bool:
        """
        Run camera calibration on captured images.

        Detects the ChArUco board in every dataset image and computes
        the camera intrinsic matrix and distortion coefficients via
        ``cv2.calibrateCamera``.

        Parameters
        ----------
        show_corners : bool, optional
            Display detected corners during processing. Default is False.

        Returns
        -------
        bool
            True if calibration succeeded, False otherwise.
        """
        detected = self._detect_in_dataset(show_corners)

        if detected < 4:
            self.get_logger().error(
                f"Only {detected} valid views; need at least 4 frames with "
                f">= {self.min_corners_per_frame} ChArUco corners each."
            )
            return False

        if self.image_size is None:
            self.get_logger().error("No valid images for calibration")
            return False

        ret, camera_matrix, dist_coeffs, _, _ = cv2.calibrateCamera(
            self.all_object_points,
            self.all_image_points,
            self.image_size,
            None,
            None,
        )

        self.reprojection_error = float(ret)
        self.calibration_matrix = camera_matrix
        self.dist_matrix = dist_coeffs
        self.distortion_list = dist_coeffs.ravel()

        self.get_logger().info(f"Calibration succeeded with {detected} views")
        self.get_logger().info(f"Reprojection error: {self.reprojection_error:.4f} px")
        self.get_logger().info(f"Calibration matrix:\n{self.calibration_matrix}")
        self.get_logger().info(f"Distortion coefficients: {self.distortion_list}")

        if self.reprojection_error > 1.0:
            self.get_logger().warn(
                "Reprojection error > 1.0 px. Recapture with better coverage "
                "(image corners and edges, stronger tilts) and ensure the "
                "board is glued to a rigid flat surface."
            )

        return True

    def save_matrices(self) -> None:
        """
        Save calibration results to text files.

        Writes ``camera_matrix.txt`` and ``camera_distortion.txt`` to
        the calibration module directory, using the same format as the
        chessboard pipeline.
        """
        if self.calibration_matrix is None or self.distortion_list is None:
            self.get_logger().error("No calibration data to save")
            return

        matrix_path = os.path.join(self.output_dir, "camera_matrix.txt")
        with open(matrix_path, "w", encoding="utf-8") as f:
            for i, row in enumerate(self.calibration_matrix):
                f.write(",".join(str(v) for v in row))
                if i < len(self.calibration_matrix) - 1:
                    f.write("\n")

        distortion_path = os.path.join(self.output_dir, "camera_distortion.txt")
        with open(distortion_path, "w", encoding="utf-8") as f:
            f.write(",".join(str(v) for v in self.distortion_list))

        self.get_logger().info(f"Saved calibration to {self.output_dir}")

    @staticmethod
    def _package_dir() -> str:
        """
        Resolve the calibration package directory.

        Uses a lazy import so the result is stable regardless of whether
        this module is loaded as ``__main__`` (via ``ros2 run``) or as a
        regular package member. The path always points at the
        ``nectar.vision.camera.calibration`` package itself, so save and
        load operations agree on a single location.
        """
        import nectar.vision.camera.calibration as _calib_pkg

        return os.path.dirname(os.path.abspath(_calib_pkg.__file__))

    @staticmethod
    def _aruco_dict_name(dict_id: int) -> str:
        """Resolve a predefined dictionary id back to its ``DICT_*`` name."""
        for name in dir(cv2.aruco):
            if name.startswith("DICT_") and getattr(cv2.aruco, name) == dict_id:
                return name
        return "DICT_4X4_1000"

    @staticmethod
    def _resolve_aruco_dict(name: str) -> int:
        """
        Resolve a dictionary name to its OpenCV enum value.

        Accepts both the full name (``"DICT_4X4_1000"``) and the
        shorthand (``"4X4_1000"``).
        """
        if not isinstance(name, str):
            raise TypeError(f"aruco_dict must be a string, got {type(name).__name__}")
        normalized = name if name.startswith("DICT_") else f"DICT_{name}"
        if not hasattr(cv2.aruco, normalized):
            raise ValueError(f"Unknown ArUco dictionary: {name!r}")
        return int(getattr(cv2.aruco, normalized))

    @classmethod
    def load_calibration(cls, output_dir: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Load calibration data from files.

        Parameters
        ----------
        output_dir : str, optional
            Directory containing ``camera_matrix.txt`` and
            ``camera_distortion.txt``. Defaults to the calibration
            package directory, matching the save default.

        Returns
        -------
        tuple of np.ndarray
            Camera matrix (3x3) and distortion coefficients.

        Raises
        ------
        FileNotFoundError
            If calibration files do not exist.
        """
        base_dir = output_dir or cls._package_dir()
        matrix_path = os.path.join(base_dir, "camera_matrix.txt")
        distortion_path = os.path.join(base_dir, "camera_distortion.txt")

        if not os.path.exists(matrix_path) or not os.path.exists(distortion_path):
            raise FileNotFoundError(
                f"Calibration files not found in {base_dir}. Run calibration first."
            )

        camera_matrix = np.loadtxt(matrix_path, delimiter=",")
        distortion = np.loadtxt(distortion_path, delimiter=",")

        return camera_matrix, distortion


def main(args=None) -> None:
    """Entry point for ChArUco camera calibration node."""
    import nectar

    rclpy.init(args=args)
    nectar.use_executor(rclpy.get_global_executor())

    node = CharucoCalibration()

    try:
        node.run_photos()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
