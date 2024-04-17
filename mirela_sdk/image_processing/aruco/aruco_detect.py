#!/usr/bin/env python3

import os
import cv2
import numpy as np
import cv2.aruco as aruco


class Aruco:

    def __init__(self, marker_dict, tag_size):

        self.path = os.path.dirname(os.path.abspath(__file__))  # Diretório do código
        self.path = os.path.dirname(self.path)  # Pega o diretório superior
        self.matrix_file_path = os.path.join(
            self.path, "camera", "calibration", "camera_matrix.txt"
        )
        self.distortion_file_path = os.path.join(
            self.path, "camera", "calibration", "camera_distortion.txt"
        )

        self._total_markers = 1000
        self.camera_matrix = np.loadtxt(self.matrix_file_path, delimiter=",")
        self.camera_distortion = np.loadtxt(self.distortion_file_path, delimiter=",")

        self._marker_dict = marker_dict
        self._tag_size = tag_size

        # Definindo o dicionario da AruUco tag
        self.key = getattr(
            aruco, f"DICT_{marker_dict}X{marker_dict}_{self.total_markers}"
        )

        # Configurando o dicionario
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

    def aruco_config(self, marker_dict, tag_size):
        """
        Configure the aruco marker

        Parameters
        ----------
        marker_dict: int
            aruco dictionary if 4x4 = 4, 5x5 = 5, ...

        tag_size: float
            Tag size in meters
        """
        self.key = getattr(
            aruco, f"DICT_{marker_dict}X{marker_dict}_{self.total_markers}"
        )
        self.aruco_detect = aruco.getPredefinedDictionary(self.key)
        self.aruco_param = aruco.DetectorParameters()
        self.tag_size = tag_size

    def detect(self, img, draw=False):
        """
        Detect one single aruco marker

        Parameters
        ----------
        img: image to be handled

        marker_dict: int
            aruco dictionary if 4x4 = 4, 5x5 = 5, ...

        draw: Bool
            (True) Draw in *img* aruco bbox and id

            (False) do not draw
        """

        # Aplicando um filtro preto e branco
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Pegando os valores do Bounding Box (limite do ArUco marker), e seu ID
        bbox, ids, rejected = aruco.detectMarkers(
            gray, self.aruco_detect, parameters=self.aruco_param
        )

        if draw:
            aruco.drawDetectedMarkers(img, bbox, ids)

        if ids is not None:
            ids = ids[0][0]  # Para identificar apenas uma aruco

        return bbox, ids

    def pose_estimate(self, img, draw=False):
        """
        Estimate pose of one single aruco marker

        Parameters
        ----------
        img: image to be handled

        marker_dict: int
            aruco dictionary if 4x4 = 4, 5x5 = 5, ...

        tag_size: (Float) Tag size in meters

        draw: Bool
            (True) Draw in *img* aruco bbox and id

            (False) do not draw
        """

        bbox, id = self.detect(img, draw)
        if id is not None:
            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                bbox, self.tag_size, self.camera_matrix, self.camera_distortion
            )

            try:
                if draw:
                    cv2.drawFrameAxes(
                        img,
                        self.camera_matrix,
                        self.camera_distortion,
                        rvecs,
                        tvecs,
                        self.tag_size,
                    )
            except Exception as ex:
                print("Something wrong is not correct: ", ex)

            translation_vector = tvecs[0][0][0:3]
            rotation_vector = rvecs[0][0][0:3]

        else:
            translation_vector = rotation_vector = None

        return id, translation_vector, rotation_vector


def main():

    aruco = Aruco(5,20)

    cap = cv2.VideoCapture(0)

    while cv2.waitKey(1) < 0:

        _, img = cap.read()

        id, t, r = aruco.pose_estimate(img, True)
        cv2.imshow("a",img)
        print(id, t, r)


if __name__ == "__main__":
    main()
