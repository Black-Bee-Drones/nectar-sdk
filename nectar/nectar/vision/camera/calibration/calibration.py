#!/usr/bin/env python3
import argparse
import os
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from nectar.vision.camera.cli import add_camera_arguments, parse_camera_args
from nectar.vision.camera.config import CameraConfig
from nectar.vision.camera.handler import ImageHandler
from nectar.vision.stream import add_stream_arguments

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

    def __init__(
        self,
        source: str = "webcam",
        camera_config: Optional[CameraConfig] = None,
        *,
        pattern: str = "charuco",
        mode: str = "auto",
        chessboard_cols: int = 9,
        chessboard_rows: int = 7,
        squares_x: int = 5,
        squares_y: int = 7,
        square_length: float = 0.040,
        marker_length: float = 0.030,
        aruco_dict: str = "DICT_4X4_1000",
        min_corners_per_frame: int = 6,
        target_views: int = 20,
        auto_interval: float = 0.75,
        show: bool = True,
        save_dataset: bool = True,
        output_dir: str = "",
    ) -> None:
        super().__init__("camera_calibration_node")

        self.source = source
        self.camera_config = camera_config
        self.pattern = str(pattern).lower()
        self.mode = str(mode).lower()
        self.square_length = float(square_length)
        self.min_corners_per_frame = int(min_corners_per_frame)
        self.target_views = int(target_views)
        self.auto_interval = float(auto_interval)
        self.show_preview = bool(show)
        self.save_dataset = bool(save_dataset)
        self.output_dir = str(output_dir) or self._package_dir()
        self._chessboard_cols = int(chessboard_cols)
        self._chessboard_rows = int(chessboard_rows)
        self._squares_x = int(squares_x)
        self._squares_y = int(squares_y)
        self._marker_length = float(marker_length)
        self._aruco_dict = str(aruco_dict)

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
        self._gui_ok = bool(self.show_preview)
        self._finished = False
        self._last_good = False
        self._last_frame: Optional[np.ndarray] = None
        self._last_obj_pts: Optional[np.ndarray] = None
        self._last_img_pts: Optional[np.ndarray] = None

        if self._gui_ok:
            try:
                cv2.namedWindow(self.PREVIEW_WINDOW)
            except cv2.error:
                self._gui_ok = False
                self.get_logger().warn("Preview window failed; continuing without GUI.")

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
                self._chessboard_cols,
                self._chessboard_rows,
                self.square_length,
            )
        if self.pattern != "charuco":
            self.get_logger().warn(f"Unknown pattern '{self.pattern}', using charuco.")
            self.pattern = "charuco"
        return CharucoDetector(
            self._squares_x,
            self._squares_y,
            self.square_length,
            self._marker_length,
            self._resolve_aruco_dict(self._aruco_dict),
        )

    def run(self) -> None:
        """Open the camera and start the capture loop."""
        self._image_handler = ImageHandler(
            image_source=self.source,
            image_processing_callback=self._on_frame,
            show_result=self.PREVIEW_WINDOW if self._gui_ok else None,
            on_key=self._on_key if self.mode == "manual" else None,
            config=self.camera_config,
        )
        self._image_handler.run()
        if self.mode == "manual":
            self.get_logger().info(
                "Manual capture: c=capture, u=undo, r=reset, Enter=finish, q=quit"
            )

    def _on_frame(self, frame: np.ndarray) -> Optional[np.ndarray]:
        if frame is None or self._finished:
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.image_size is None:
            self.image_size = (gray.shape[1], gray.shape[0])

        n_corners, obj_pts, img_pts = self.detector.detect(gray)
        good = obj_pts is not None and n_corners >= self.min_corners_per_frame
        self._last_good = good
        self._last_frame = frame
        self._last_obj_pts = obj_pts
        self._last_img_pts = img_pts

        if self._gui_ok:
            self._draw_preview(frame, n_corners, good)

        if self.mode != "manual":
            self._handle_auto(good, frame, obj_pts, img_pts)
        return frame

    def _on_key(self, key: int) -> None:
        if self._last_frame is None:
            return
        self._handle_manual_key(
            key,
            self._last_good,
            self._last_frame,
            self._last_obj_pts,
            self._last_img_pts,
        )

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

    def _draw_preview(self, frame: np.ndarray, n_corners: int, good: bool) -> None:
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Camera intrinsic calibration")
    add_camera_arguments(parser)
    add_stream_arguments(parser, show_default=True, include_publish=False)
    parser.add_argument("--pattern", choices=["charuco", "chessboard"], default="charuco")
    parser.add_argument("--mode", choices=["auto", "manual"], default="auto")
    parser.add_argument("--chessboard-cols", type=int, default=9)
    parser.add_argument("--chessboard-rows", type=int, default=7)
    parser.add_argument("--squares-x", type=int, default=5)
    parser.add_argument("--squares-y", type=int, default=7)
    parser.add_argument("--square-length", type=float, default=0.040)
    parser.add_argument("--marker-length", type=float, default=0.030)
    parser.add_argument("--aruco-dict", default="DICT_4X4_1000")
    parser.add_argument("--min-corners-per-frame", type=int, default=6)
    parser.add_argument("--target-views", type=int, default=20)
    parser.add_argument("--auto-interval", type=float, default=0.75)
    parser.add_argument(
        "--no-save-dataset",
        dest="save_dataset",
        action="store_false",
        help="Do not write accepted frames to dataset/",
    )
    parser.set_defaults(save_dataset=True)
    parser.add_argument("--output-dir", default="")
    return parser


def main(args=None) -> None:
    """Entry point for the camera calibration node."""
    import nectar

    ns, ros_argv, source, camera_config = parse_camera_args(_parser(), args)
    rclpy.init(args=ros_argv)
    nectar.init()
    node = CameraCalibration(
        source,
        camera_config,
        pattern=ns.pattern,
        mode=ns.mode,
        chessboard_cols=ns.chessboard_cols,
        chessboard_rows=ns.chessboard_rows,
        squares_x=ns.squares_x,
        squares_y=ns.squares_y,
        square_length=ns.square_length,
        marker_length=ns.marker_length,
        aruco_dict=ns.aruco_dict,
        min_corners_per_frame=ns.min_corners_per_frame,
        target_views=ns.target_views,
        auto_interval=ns.auto_interval,
        show=ns.show,
        save_dataset=ns.save_dataset,
        output_dir=ns.output_dir,
    )
    nectar.add_node(node)
    try:
        node.run()
        nectar.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if node._image_handler is not None:
            node._image_handler.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
