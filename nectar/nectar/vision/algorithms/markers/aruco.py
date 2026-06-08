#!/usr/bin/env python3
import cv2
import cv2.aruco as aruco
import numpy as np

from nectar.vision.camera.calibration import CameraCalibration


class Aruco:
    """
    ArUco marker detector with pose estimation.

    Detects ArUco markers and estimates their 3D pose relative
    to a calibrated camera.

    Parameters
    ----------
    marker_dict : int
        ArUco dictionary size (e.g., 4, 5, 6, 7 for 4x4, 5x5, etc.).
    tag_size : float
        Physical size of the marker in meters.

    Attributes
    ----------
    camera_matrix : np.ndarray
        Camera intrinsic matrix from calibration.
    camera_distortion : np.ndarray
        Camera distortion coefficients.
    aruco_detect : cv2.aruco.Dictionary
        ArUco dictionary for detection.
    aruco_param : cv2.aruco.DetectorParameters
        Detection parameters.
    """

    def __init__(self, marker_dict: int, tag_size: float):
        self._total_markers = 1000
        self.camera_matrix, self.camera_distortion = CameraCalibration.load_calibration()

        self._marker_dict = marker_dict
        self._tag_size = tag_size

        self.key = getattr(aruco, f"DICT_{marker_dict}X{marker_dict}_{self.total_markers}")

        self.aruco_detect = aruco.getPredefinedDictionary(self.key)
        self.aruco_param = aruco.DetectorParameters()

    @property
    def total_markers(self) -> int:
        """int: Maximum number of markers in dictionary."""
        return self._total_markers

    @property
    def marker_dict(self) -> int:
        """int: ArUco dictionary size."""
        return self._marker_dict

    @property
    def tag_size(self) -> float:
        """float: Physical marker size in meters."""
        return self._tag_size

    def aruco_config(self, marker_dict: int, tag_size: float) -> None:
        """
        Reconfigure detector with new dictionary and tag size.

        Parameters
        ----------
        marker_dict : int
            New ArUco dictionary size.
        tag_size : float
            New physical marker size in meters.
        """
        self.key = getattr(aruco, f"DICT_{marker_dict}X{marker_dict}_{self.total_markers}")
        self.aruco_detect = aruco.getPredefinedDictionary(self.key)
        self.aruco_param = aruco.DetectorParameters()
        self._tag_size = tag_size

    def detect(self, img: np.ndarray, draw: bool = False):
        """
        Detect ArUco markers in image.

        Parameters
        ----------
        img : np.ndarray
            Input BGR image.
        draw : bool, default=False
            Whether to draw detected markers on image.

        Returns
        -------
        bbox : tuple
            Bounding box corners for each detected marker.
        ids : int or None
            ID of the first detected marker, or None if no markers found.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        detector = aruco.ArucoDetector(self.aruco_detect, self.aruco_param)
        bbox, ids, _ = detector.detectMarkers(gray)

        if draw:
            aruco.drawDetectedMarkers(img, bbox, ids)

        if ids is not None:
            ids = ids[0][0]

        return bbox, ids

    def calculateYawFromCorners(self, bbox) -> float:
        """
        Calculate yaw angle from marker corners.

        Parameters
        ----------
        bbox : tuple
            Marker bounding box corners.

        Returns
        -------
        float
            Yaw angle in degrees (0-360).
        """
        top_left = bbox[0][0][0]
        top_right = bbox[0][0][1]

        delta_x = top_right[0] - top_left[0]
        delta_y = top_right[1] - top_left[1]

        angle = np.arctan2(delta_y, delta_x)
        yaw_degrees = np.degrees(angle)

        if yaw_degrees < 0:
            yaw_degrees += 360

        if yaw_degrees == 360:
            yaw_degrees = 0

        return float(yaw_degrees)

    def pose_estimate(self, img: np.ndarray, draw: bool = False):
        """
        Estimate marker pose in camera frame.

        Parameters
        ----------
        img : np.ndarray
            Input BGR image.
        draw : bool, default=False
            Whether to draw pose axes on image.

        Returns
        -------
        id : int or None
            Detected marker ID.
        translation : np.ndarray or None
            Translation vector [x, y, z] in meters.
        yaw : float or None
            Yaw angle in degrees.
        """
        bbox, id = self.detect(img, draw)
        if id is not None:
            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                bbox, self.tag_size, self.camera_matrix, self.camera_distortion
            )

            if draw:
                cv2.drawFrameAxes(
                    img,
                    self.camera_matrix,
                    self.camera_distortion,
                    rvecs[0],
                    tvecs[0],
                    self.tag_size,
                )

            translation_vector = tvecs[0][0][0:3]
            _rotation_vector = rvecs[0][0][0:3]

            yaw = self.calculateYawFromCorners(bbox)

        else:
            translation_vector = yaw = None

        return id, translation_vector, yaw


def main():
    """Demo function for ArUco detection."""
    aruco_detector = Aruco(5, 20)

    cap = cv2.VideoCapture(0)

    while cv2.waitKey(1) & 0xFF != ord("q"):
        _, img = cap.read()

        id, t, r = aruco_detector.pose_estimate(img, True)
        cv2.imshow("a", img)
        print(id, t, r)


if __name__ == "__main__":
    main()
