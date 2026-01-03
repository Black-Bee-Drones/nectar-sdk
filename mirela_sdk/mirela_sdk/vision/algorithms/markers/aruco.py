#!/usr/bin/env python3

import cv2
import numpy as np
import cv2.aruco as aruco
from mirela_sdk.vision.camera.calibration.calibration import Calibration


class Aruco:

    def __init__(self, marker_dict: int, tag_size: int):

        self._total_markers = 1000
        self.camera_matrix, self.camera_distortion = (
            Calibration.get_camera_matrix_distortion()
        )

        self._marker_dict = marker_dict
        self._tag_size = tag_size

        self.key = getattr(
            aruco, f"DICT_{marker_dict}X{marker_dict}_{self.total_markers}"
        )

        self.aruco_detect = aruco.getPredefinedDictionary(self.key)
        self.aruco_param = aruco.DetectorParameters()

    @property
    def total_markers(self):
        return self._total_markers

    @property
    def marker_dict(self):
        return self._marker_dict

    @property
    def tag_size(self):
        return self._tag_size

    def aruco_config(self, marker_dict: int, tag_size: int):
        self.key = getattr(
            aruco, f"DICT_{marker_dict}X{marker_dict}_{self.total_markers}"
        )
        self.aruco_detect = aruco.getPredefinedDictionary(self.key)
        self.aruco_param = aruco.DetectorParameters()
        self.tag_size = tag_size

    def detect(self, img, draw=False):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        detector = aruco.ArucoDetector(self.aruco_detect, self.aruco_param)
        bbox, ids, _ = detector.detectMarkers(gray)

        if draw:
            aruco.drawDetectedMarkers(img, bbox, ids)

        if ids is not None:
            ids = ids[0][0]

        return bbox, ids

    def calculateYawFromCorners(self, bbox) -> float:
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

    def pose_estimate(self, img, draw=False):
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
            rotation_vector = rvecs[0][0][0:3]

            yaw = self.calculateYawFromCorners(bbox)

        else:
            translation_vector = yaw = None

        return id, translation_vector, yaw


def main():

    aruco_detector = Aruco(5, 20)

    cap = cv2.VideoCapture(0)

    while cv2.waitKey(1) & 0xFF != ord("q"):

        _, img = cap.read()

        id, t, r = aruco_detector.pose_estimate(img, True)
        cv2.imshow("a", img)
        print(id, t, r)


if __name__ == "__main__":
    main()
