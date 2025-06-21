import cv2
import numpy as np
import os
import json
from enum import Enum, auto


class ColorSpace(Enum):
    """Color space enumeration"""

    HSV = auto()
    LAB = auto()


class ColorDetector:
    def __init__(
        self,
        mode: str = "track",
        color: str = None,
        color_space: ColorSpace = ColorSpace.HSV,
    ):
        self.mode = mode
        self.mask = self.result = None
        self.color_space = color_space

        # Define color space specific ranges and conversion methods
        self.color_space_config = {
            ColorSpace.HSV: {
                "convert_func": cv2.COLOR_BGR2HSV,
                "ranges": [[0, 0, 0], [179, 255, 255]],
                "trackbar_names": [
                    "Hue Min",
                    "Hue Max",
                    "Sat Min",
                    "Sat Max",
                    "Val Min",
                    "Val Max",
                ],
                "trackbar_maxes": [179, 179, 255, 255, 255, 255],
            },
            ColorSpace.LAB: {
                "convert_func": cv2.COLOR_BGR2LAB,
                "ranges": [[0, 0, 0], [255, 255, 255]],
                "trackbar_names": [
                    "L Min",
                    "L Max",
                    "A Min",
                    "A Max",
                    "B Min",
                    "B Max",
                ],
                "trackbar_maxes": [255, 255, 255, 255, 255, 255],
            },
        }

        self.package_path = os.path.dirname(os.path.realpath(__file__))
        self.file_path = os.path.join(self.package_path, "color_calibration.json")

        if self.mode == "track":
            print(f"Create Trackbars for {self.color_space.name} color space")
        elif self.mode == "preset":
            self._color_values = None
            self.color_values = self.get_color_values(color)

    @property
    def color_values(self):
        return self._color_values

    @color_values.setter
    def color_values(self, values: list):
        try:
            config = self.color_space_config[self.color_space]
            # Verify and adjust value limits based on the color space
            values = np.clip(values, config["ranges"][0], config["ranges"][1])
        except:
            raise ValueError(
                "Invalid attribute format. Expected [[x, x, x], [x, x, x]]"
            )
        else:
            self._color_values = values

    def empty(self, a):
        pass

    def initTrackbars(self):
        """Create window and trackbars for color adjustment based on selected color space"""
        config = self.color_space_config[self.color_space]
        tb_names = config["trackbar_names"]
        tb_maxes = config["trackbar_maxes"]

        window_name = f"{self.color_space.name}_TrackBars"
        cv2.namedWindow(window_name)
        cv2.resizeWindow(window_name, 640, 480)

        cv2.createTrackbar(tb_names[0], window_name, 0, tb_maxes[0], self.empty)
        cv2.createTrackbar(
            tb_names[1], window_name, tb_maxes[1], tb_maxes[1], self.empty
        )
        cv2.createTrackbar(tb_names[2], window_name, 0, tb_maxes[2], self.empty)
        cv2.createTrackbar(
            tb_names[3], window_name, tb_maxes[3], tb_maxes[3], self.empty
        )
        cv2.createTrackbar(tb_names[4], window_name, 0, tb_maxes[4], self.empty)
        cv2.createTrackbar(
            tb_names[5], window_name, tb_maxes[5], tb_maxes[5], self.empty
        )

    def getTrackValues(self):
        """Get current trackbar values based on selected color space"""
        config = self.color_space_config[self.color_space]
        tb_names = config["trackbar_names"]
        window_name = f"{self.color_space.name}_TrackBars"

        min_val1 = cv2.getTrackbarPos(tb_names[0], window_name)
        min_val2 = cv2.getTrackbarPos(tb_names[2], window_name)
        min_val3 = cv2.getTrackbarPos(tb_names[4], window_name)
        max_val1 = cv2.getTrackbarPos(tb_names[1], window_name)
        max_val2 = cv2.getTrackbarPos(tb_names[3], window_name)
        max_val3 = cv2.getTrackbarPos(tb_names[5], window_name)

        return [[min_val1, min_val2, min_val3], [max_val1, max_val2, max_val3]]

    def filterColor(self, img):
        """Filter color from image based on selected color space and ranges"""
        # Convert image to the selected color space
        converted_img = cv2.cvtColor(
            img, self.color_space_config[self.color_space]["convert_func"]
        )

        if self.mode == "track":
            self.color_values = self.getTrackValues()

        # Filter the desired color
        mask = cv2.inRange(
            converted_img,
            np.array(self.color_values[0]),
            np.array(self.color_values[1]),
        )

        # Remove noise
        mask = cv2.dilate(mask, np.ones((11, 11), np.uint8), iterations=1)
        mask = cv2.erode(mask, np.ones((7, 7), np.uint8), iterations=1)

        # Morphological operations for further noise removal and closing gaps
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((8, 8), np.uint8))

        # Ensure the mask is properly binarized to exactly 0 and 255
        _, mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)

        self.result = cv2.bitwise_and(img, img, mask=mask)
        self.mask = mask

    def get_color_values(self, color_name: str):
        """
        Get color values from JSON file
        :param color_name: Name of the color to retrieve
        :return: List of color range values [[min1, min2, min3], [max1, max2, max3]]
        """
        if not os.path.exists(self.file_path):
            raise ValueError(f"Color calibration file not found: {self.file_path}")

        try:
            with open(self.file_path, "r") as file:
                colors_data = json.load(file)

            if color_name not in colors_data:
                raise ValueError(
                    f"Color '{color_name}' not defined in calibration file"
                )

            if self.color_space.name not in colors_data[color_name]:
                raise ValueError(
                    f"Color '{color_name}' does not have {self.color_space.name} values defined"
                )

            return colors_data[color_name][self.color_space.name]

        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format in color calibration file")
        except Exception as e:
            raise ValueError(f"Error retrieving color values: {str(e)}")

    def saveColorValues(self):
        """Save color values to JSON file"""
        color_name = input("Enter the color name: ")

        colors_data = {}
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as file:
                    colors_data = json.load(file)
            except json.JSONDecodeError:
                # If the file exists but is not valid JSON, start fresh
                pass

        # Create or update the color entry
        if color_name not in colors_data:
            colors_data[color_name] = {}

        # Update the color space values for this color
        colors_data[color_name][self.color_space.name] = self.color_values.tolist()

        # Save back to file with pretty formatting
        with open(self.file_path, "w") as file:
            json.dump(colors_data, file, indent=4)

        print(
            f"Color '{color_name}' saved with {self.color_space.name} values: {self.color_values.tolist()}"
        )
