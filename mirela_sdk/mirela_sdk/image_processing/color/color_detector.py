import cv2
import numpy as np
import os
import re


class ColorDetector:
    def __init__(self, mode: str = "track", color: str = None):
        self.mode = mode
        self.mask = self.result = None

        self.package_path = os.path.dirname(os.path.realpath(__file__))
        self.file_path = os.path.join(self.package_path, "color_calibration.txt")

        if self.mode == "track":
            print("Create Trackbars")
        elif self.mode == "preset":
            self._hsv_color = None
            self.hsv_color = self.getColorHSV(color)

    @property
    def hsv_color(self):
        return self._hsv_color

    @hsv_color.setter
    def hsv_color(self, values: list):
        try:
            # Verify and adjust HSV value limits
            values = np.clip(values, [0, 0, 0], [179, 255, 255])
        except:
            raise ValueError(
                "Invalid attribute format. Expected [[x, x, x], [x, x, x]]"
            )
        else:
            self._hsv_color = values

    def empty(self, a):
        pass

    def initTrackbars(self):
        # Create window and trackbars for color adjustment

        cv2.namedWindow("TrackBars")
        cv2.resizeWindow("TrackBars", 640, 480)
        cv2.createTrackbar("Hue Min", "TrackBars", 0, 179, self.empty)
        cv2.createTrackbar("Hue Max", "TrackBars", 179, 179, self.empty)
        cv2.createTrackbar("Sat Min", "TrackBars", 0, 255, self.empty)
        cv2.createTrackbar("Sat Max", "TrackBars", 255, 255, self.empty)
        cv2.createTrackbar("Val Min", "TrackBars", 0, 255, self.empty)
        cv2.createTrackbar("Val Max", "TrackBars", 255, 255, self.empty)

    def getTrackValues(self):
        # Get current trackbar values
        hmin = cv2.getTrackbarPos("Hue Min", "TrackBars")
        smin = cv2.getTrackbarPos("Sat Min", "TrackBars")
        vmin = cv2.getTrackbarPos("Val Min", "TrackBars")
        hmax = cv2.getTrackbarPos("Hue Max", "TrackBars")
        smax = cv2.getTrackbarPos("Sat Max", "TrackBars")
        vmax = cv2.getTrackbarPos("Val Max", "TrackBars")

        return [[hmin, smin, vmin], [hmax, smax, vmax]]

    def filterColor(self, img):
        imgHsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        if self.mode == "track":
            self.hsv_color = self.getTrackValues()

        # Filter the desired color
        mask = cv2.inRange(imgHsv, self.hsv_color[0], self.hsv_color[1])

        # Remove noise
        mask = cv2.dilate(mask, np.ones((11, 11), np.uint8), iterations=1)
        mask = cv2.erode(mask, np.ones((7, 7), np.uint8), iterations=1)

        # Morphological operations for further noise removal and closing gaps
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((8, 8), np.uint8))
        # mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((8, 8), np.uint8))

        self.result = cv2.bitwise_and(img, img, mask=mask)
        self.mask = mask

    # Find the HSV values in the file, with name of the color
    def getColorHSV(self, color_name: str):

        with open(self.file_path, "r") as file:
            content = file.read()

        pattern = rf"{color_name}\s+\[\[([\d, ]+)\],\s+\[([\d, ]+)\]\]"

        match = re.search(pattern, content)
        if match:
            hsv_values = match.groups()
            hsv_values = [list(map(int, value.split(","))) for value in hsv_values]
            hsv_color = [hsv_values[0], hsv_values[1]]
            output = hsv_color
        else:
            output = None
            raise ValueError("Color not defined")

        return output

    # Save the name anda HSV values of the color on txt file
    def saveColorHSV(self):
        color_name = input("Enter the color name: ")

        aux = 0

        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as file:
                pass

        with open(self.file_path, "r") as file:
            lines = file.readlines()

        with open(self.file_path, "w") as file:
            color_exists = False

            for line in lines:
                if line.startswith(f"{color_name} "):
                    file.write(f"{color_name} {self.hsv_color.tolist()}\n")
                    color_exists = True
                    aux = 1
                    continue
                if aux != 1:
                    file.write(line)
                aux = 0

            if not color_exists:
                file.write(f"\n{color_name} {self.hsv_color.tolist()}\n")
