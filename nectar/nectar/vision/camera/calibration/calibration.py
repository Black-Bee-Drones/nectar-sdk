#!/usr/bin/env python3
import os
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from nectar.vision.camera.config import OpenCVConfig
from nectar.vision.camera.handler import ImageHandler

SUBPIX_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)


class BoardDetector(ABC):
    """Pattern-specific board detection for calibration."""

    @abstractmethod
    def detect(self, gray: np.ndarray) -> Tuple[int, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Detect the calibration board in a grayscale image.

        Returns
        -------
        tuple
            ``(n_corners, object_points, image_points)``. ``object_points``
            and ``image_points`` are ``None`` when the board is not usable.
        """

    @abstractmethod
    def draw(self, img: np.ndarray) -> int:
        """Draw the current detection on ``img`` (BGR) and return corner count."""


class ChessboardDetector(BoardDetector):
    """Plain chessboard detector with subpixel corner refinement."""

    def __init__(self, cols: int, rows: int, square_length: float) -> None:
        self._size = (cols, rows)
        self._objp = np.zeros((cols * rows, 3), dtype=np.float32)
        self._objp[:, :2] = np.indices(self._size).T.reshape(-1, 2)
        self._objp *= square_length

    def detect(self, gray: np.ndarray) -> Tuple[int, Optional[np.ndarray], Optional[np.ndarray]]:
        found, corners = cv2.findChessboardCorners(
            gray,
            self._size,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE,
        )
        if not found:
            return 0, None, None

        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), SUBPIX_CRITERIA)
        return len(corners), self._objp, corners

    def draw(self, img: np.ndarray) -> int:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, self._size, None)
        if found:
            cv2.drawChessboardCorners(img, self._size, corners, found)
            return len(corners)
        return 0


class CharucoDetector(BoardDetector):
    """ChArUco board detector tolerant to partial/occluded views."""

    def __init__(
        self,
        squares_x: int,
        squares_y: int,
        square_length: float,
        marker_length: float,
        aruco_dict_id: int,
    ) -> None:
        self._dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict_id)
        self._board = cv2.aruco.CharucoBoard(
            (squares_x, squares_y),
            square_length,
            marker_length,
            self._dictionary,
        )
        self._detector = cv2.aruco.CharucoDetector(
            self._board,
            cv2.aruco.CharucoParameters(),
            cv2.aruco.DetectorParameters(),
        )

    def detect(self, gray: np.ndarray) -> Tuple[int, Optional[np.ndarray], Optional[np.ndarray]]:
        charuco_corners, charuco_ids, _, _ = self._detector.detectBoard(gray)
        if charuco_ids is None or len(charuco_ids) == 0:
            return 0, None, None

        obj_pts, img_pts = self._board.matchImagePoints(charuco_corners, charuco_ids)
        if obj_pts is None or len(obj_pts) == 0:
            return 0, None, None

        return len(charuco_ids), obj_pts, img_pts

    def draw(self, img: np.ndarray) -> int:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        charuco_corners, charuco_ids, marker_corners, marker_ids = self._detector.detectBoard(gray)
        if marker_ids is not None and len(marker_ids) > 0:
            cv2.aruco.drawDetectedMarkers(img, marker_corners, marker_ids)
        if charuco_ids is not None and len(charuco_ids) > 0:
            cv2.aruco.drawDetectedCornersCharuco(img, charuco_corners, charuco_ids)
            return len(charuco_ids)
        return 0


class CameraCalibration(Node):
    """
    Unified camera intrinsic calibration node.

    Supports both ChArUco and plain chessboard
    patterns, automatic or manual capture

    Capture modes
    -------------
    auto
        Accepts a view automatically whenever the board is detected with at
        least ``min_corners_per_frame`` corners and ``auto_interval`` seconds
        have elapsed since the last capture. Stops after ``target_views``.
    manual
        Key-driven from the preview window: ``c`` capture (when the board is
        good), ``u`` undo last, ``r`` reset all, ``Enter`` finish + calibrate,
        ``q`` abort. Requires a GUI window; falls back to ``auto`` when no GUI
        is available.

    Output files (``camera_matrix.txt``, ``camera_distortion.txt``) and the
    :meth:`load_calibration` API are shared by both patterns.
    """

    DATASET_DIR = "dataset"
    PREVIEW_WINDOW = "Camera Calibration"

    def __init__(self) -> None:
        super().__init__("camera_calibration_node")

        self.declare_parameter("pattern", "charuco")
        self.declare_parameter("mode", "auto")
        self.declare_parameter("image_source", "webcam")
        self.declare_parameter("device_index", 0)
        self.declare_parameter("width", 0)
        self.declare_parameter("height", 0)
        self.declare_parameter("chessboard_cols", 9)
        self.declare_parameter("chessboard_rows", 7)
        self.declare_parameter("squares_x", 5)
        self.declare_parameter("squares_y", 7)
        self.declare_parameter("square_length", 0.040)
        self.declare_parameter("marker_length", 0.030)
        self.declare_parameter("aruco_dict", "DICT_4X4_1000")
        self.declare_parameter("min_corners_per_frame", 6)
        self.declare_parameter("target_views", 20)
        self.declare_parameter("auto_interval", 0.75)
        self.declare_parameter("show_preview", True)
        self.declare_parameter("save_dataset", True)
        self.declare_parameter("output_dir", "")

        self.pattern = str(self.get_parameter("pattern").value).lower()
        self.mode = str(self.get_parameter("mode").value).lower()
        self.image_source = str(self.get_parameter("image_source").value)
        self.device_index = int(self.get_parameter("device_index").value)
        self.width = int(self.get_parameter("width").value)
        self.height = int(self.get_parameter("height").value)
        self.square_length = float(self.get_parameter("square_length").value)
        self.min_corners_per_frame = int(self.get_parameter("min_corners_per_frame").value)
        self.target_views = int(self.get_parameter("target_views").value)
        self.auto_interval = float(self.get_parameter("auto_interval").value)
        self.show_preview = bool(self.get_parameter("show_preview").value)
        self.save_dataset = bool(self.get_parameter("save_dataset").value)
        self.output_dir = str(self.get_parameter("output_dir").value) or self._package_dir()

        self.detector = self._build_detector()

        self.object_points: List[np.ndarray] = []
        self.image_points: List[np.ndarray] = []
        self.image_size: Optional[Tuple[int, int]] = None

        self.calibration_matrix: Optional[np.ndarray] = None
        self.dist_matrix: Optional[np.ndarray] = None
        self.distortion_list: Optional[np.ndarray] = None
        self.reprojection_error: Optional[float] = None

        self._image_handler: Optional[ImageHandler] = None
        self._last_capture = 0.0
        self._saved_frames = 0
        self._gui_ok = self.show_preview and self._gui_available()
        self._finished = False

        if self.mode == "manual" and not self._gui_ok:
            self.get_logger().warn(
                "Manual mode needs a preview window but no GUI is available; "
                "falling back to auto capture."
            )
            self.mode = "auto"

        if self.save_dataset:
            os.makedirs(os.path.join(self.output_dir, self.DATASET_DIR), exist_ok=True)

        self.get_logger().info(
            f"Calibration: pattern={self.pattern}, mode={self.mode}, "
            f"target_views={self.target_views}, preview={self._gui_ok}"
        )
        self.get_logger().info(f"Output dir: {self.output_dir}")

    def _build_detector(self) -> BoardDetector:
        if self.pattern == "chessboard":
            return ChessboardDetector(
                int(self.get_parameter("chessboard_cols").value),
                int(self.get_parameter("chessboard_rows").value),
                self.square_length,
            )
        if self.pattern != "charuco":
            self.get_logger().warn(f"Unknown pattern '{self.pattern}', using charuco.")
            self.pattern = "charuco"
        return CharucoDetector(
            int(self.get_parameter("squares_x").value),
            int(self.get_parameter("squares_y").value),
            self.square_length,
            float(self.get_parameter("marker_length").value),
            self._resolve_aruco_dict(str(self.get_parameter("aruco_dict").value)),
        )

    def run(self) -> None:
        """Open the camera and start the capture loop."""
        config = (
            OpenCVConfig(
                device_index=self.device_index,
                width=self.width if self.width > 0 else None,
                height=self.height if self.height > 0 else None,
            )
            if self.image_source.lower() in ("webcam", "opencv")
            else None
        )
        self._image_handler = ImageHandler(
            image_source=self.image_source,
            image_processing_callback=self._on_frame,
            config=config,
        )
        self._image_handler.run()
        if self.mode == "manual":
            self.get_logger().info(
                "Manual capture: c=capture, u=undo, r=reset, Enter=finish, q=quit"
            )

    def _on_frame(self, frame: np.ndarray) -> None:
        if frame is None or self._finished:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.image_size is None:
            self.image_size = (gray.shape[1], gray.shape[0])

        n_corners, obj_pts, img_pts = self.detector.detect(gray)
        good = obj_pts is not None and n_corners >= self.min_corners_per_frame

        if self._gui_ok:
            key = self._show_preview(frame, n_corners, good)
        else:
            key = -1

        if self.mode == "manual":
            self._handle_manual_key(key, good, frame, obj_pts, img_pts)
        else:
            self._handle_auto(good, frame, obj_pts, img_pts)

    def _handle_auto(
        self,
        good: bool,
        frame: np.ndarray,
        obj_pts: Optional[np.ndarray],
        img_pts: Optional[np.ndarray],
    ) -> None:
        now = time.time()
        if good and (now - self._last_capture) >= self.auto_interval:
            self._accept_view(frame, obj_pts, img_pts)
            self._last_capture = now
        if len(self.object_points) >= self.target_views:
            self._finish()

    def _handle_manual_key(
        self,
        key: int,
        good: bool,
        frame: np.ndarray,
        obj_pts: Optional[np.ndarray],
        img_pts: Optional[np.ndarray],
    ) -> None:
        if key in (ord("c"), ord("C")):
            if good:
                self._accept_view(frame, obj_pts, img_pts)
            else:
                self.get_logger().warn("Board not detected with enough corners; not captured.")
        elif key in (ord("u"), ord("U")):
            self._undo_view()
        elif key in (ord("r"), ord("R")):
            self._reset_views()
        elif key in (13, 10):
            self._finish()
        elif key in (ord("q"), ord("Q")):
            self.get_logger().info("Capture aborted by user.")
            self._stop()

    def _accept_view(
        self,
        frame: np.ndarray,
        obj_pts: Optional[np.ndarray],
        img_pts: Optional[np.ndarray],
    ) -> None:
        self.object_points.append(obj_pts)
        self.image_points.append(img_pts)
        if self.save_dataset:
            filepath = os.path.join(
                self.output_dir,
                self.DATASET_DIR,
                f"{self.pattern}{len(self.object_points)}.jpg",
            )
            cv2.imwrite(filepath, frame)
            self._saved_frames += 1
        self.get_logger().info(f"Captured view {len(self.object_points)}/{self.target_views}")

    def _undo_view(self) -> None:
        if self.object_points:
            self.object_points.pop()
            self.image_points.pop()
            self.get_logger().info(f"Removed last view ({len(self.object_points)} remaining)")
        else:
            self.get_logger().warn("No views to undo.")

    def _reset_views(self) -> None:
        self.object_points.clear()
        self.image_points.clear()
        self.get_logger().info("Cleared all captured views.")

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        if self.calibrate():
            self.save_matrices()
        self._stop()

    def _stop(self) -> None:
        self._finished = True
        if self._image_handler is not None:
            self._image_handler.cleanup()
            self._image_handler = None
        if self._gui_ok:
            cv2.destroyAllWindows()
        if rclpy.ok():
            rclpy.shutdown()

    def _show_preview(self, frame: np.ndarray, n_corners: int, good: bool) -> int:
        self.detector.draw(frame)
        status = f"Board: {n_corners} corners" if n_corners > 0 else "Board: not detected"
        cv2.putText(
            frame,
            f"Views {len(self.object_points)}/{self.target_views}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            status,
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0) if good else (0, 0, 255),
            2,
        )
        if self.mode == "manual":
            cv2.putText(
                frame,
                "c capture | u undo | r reset | Enter finish | q quit",
                (10, frame.shape[0] - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
        try:
            cv2.imshow(self.PREVIEW_WINDOW, frame)
            return cv2.waitKey(1) & 0xFF
        except cv2.error:
            self._gui_ok = False
            self.get_logger().warn("Preview window failed; continuing without GUI.")
            return -1

    def calibrate(self) -> bool:
        """
        Run ``cv2.calibrateCamera`` on the accumulated views.

        Returns
        -------
        bool
            True if calibration succeeded.
        """
        if len(self.object_points) < 4 or self.image_size is None:
            self.get_logger().error(f"Need at least 4 views, have {len(self.object_points)}.")
            return False

        ret, camera_matrix, dist_coeffs, _, _ = cv2.calibrateCamera(
            self.object_points,
            self.image_points,
            self.image_size,
            None,
            None,
        )

        self.reprojection_error = float(ret)
        self.calibration_matrix = camera_matrix
        self.dist_matrix = dist_coeffs
        self.distortion_list = dist_coeffs.ravel()

        self.get_logger().info(f"Calibrated with {len(self.object_points)} views")
        self.get_logger().info(f"Reprojection error: {self.reprojection_error:.4f} px")
        self.get_logger().info(f"Calibration matrix:\n{self.calibration_matrix}")
        self.get_logger().info(f"Distortion coefficients: {self.distortion_list}")

        if self.reprojection_error > 1.0:
            self.get_logger().warn(
                "Reprojection error > 1.0 px. Recapture with better coverage "
                "(image corners and edges, stronger tilts) on a rigid flat board."
            )
        return True

    def save_matrices(self) -> None:
        """Write ``camera_matrix.txt`` and ``camera_distortion.txt``."""
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
    def _gui_available() -> bool:
        try:
            cv2.namedWindow("__nectar_gui_probe__")
            cv2.destroyWindow("__nectar_gui_probe__")
            return True
        except cv2.error:
            return False

    @staticmethod
    def _package_dir() -> str:
        """Resolve the calibration package directory (stable across run modes)."""
        import nectar.vision.camera.calibration as _calib_pkg

        return os.path.dirname(os.path.abspath(_calib_pkg.__file__))

    @staticmethod
    def _resolve_aruco_dict(name: str) -> int:
        """Resolve a dictionary name (``DICT_4X4_1000`` or ``4X4_1000``) to its enum."""
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
            ``camera_distortion.txt``. Defaults to the calibration package
            directory, matching the save default.

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
    """Entry point for the camera calibration node."""
    import nectar

    rclpy.init(args=args)
    nectar.use_executor(rclpy.get_global_executor())

    node = CameraCalibration()

    try:
        node.run()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
