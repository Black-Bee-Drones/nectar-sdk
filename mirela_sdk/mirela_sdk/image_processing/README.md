# Image Processing Tools 📷

Provides a collection of tools for image processing, focusing on color detection, ArUco marker detection, and camera calibration, built as part of the Mirela SDK.  It leverages OpenCV, ROS 2, and DepthAI for robust and versatile image analysis.

## Features ✨

* **Color Detection:**  Precisely detect and track colors in images using predefined values or interactive trackbars.  Save and load calibrated color ranges for consistent performance.
* **ArUco Marker Detection:**  Detect and estimate the pose (translation and rotation) of ArUco markers in images or video streams.  Publish pose estimates as ROS 2 messages for seamless integration with robotic systems.
* **Camera Calibration:**  Calibrate your camera using a chessboard pattern to obtain accurate intrinsic and distortion parameters.  Save and load calibration data for efficient reuse.
* **Oak-D Camera Support:**  Integrates with DepthAI for advanced functionalities like stereo depth perception and IMU sensor access.
* **ROS 2 Integration:**  Several components are designed as ROS 2 nodes for easy integration into robotic applications.
* **Versatile Image Handling:**  Supports various image sources, including ROS topics, webcams, Oak-D cameras, and image files.

## File Overview 📖

### Camera and Image Handling 👁️

* **`camera/image_handler.py`:**  Handles image acquisition from various sources (ROS topics, webcams, Oak-D, files).
* **`camera/oakd_cam.py`:** Provides the `OakdCam` class for managing and controlling an OAK-D camera.

### Camera Calibration 📸

* **`camera/calibration/calibration.py`:**  Calibrates a camera using a chessboard pattern.
* **`camera/calibration/camera_distortion.txt`:** Stores camera distortion parameters.
* **`camera/calibration/camera_matrix.txt`:** Stores the camera intrinsic matrix.
* **`camera/calibration/dataset/dataset.txt`:** Chessboard dataset for camera calibration.

### Image Calculus 🧮

* **`camera/image_calculus.py`:** Provides the `ImageCalculus` class for calculating GPS coordinates from pixel locations.

### ArUco Marker Detection 🚩

* **`aruco/aruco_detect.py`:** Defines the `Aruco` class for ArUco marker detection and pose estimation.
* **`aruco/aruco_node.py`:** ROS 2 node for detecting ArUco markers and publishing their pose estimates.

### Color Detection 🎨

* **`color/color_detector.py`:**  Defines the `ColorDetector` class for color detection and filtering. Supports 'track' and 'preset' modes.
* **`color/color_calibration_node.py`:** ROS 2 node for calibrating color detection parameters using trackbars.
* **`color/color_calibration.txt`:**  Stores calibrated HSV color ranges for different object categories.

## Usage Examples 💡

Check the individual file descriptions and docstrings for specific usage examples.  A more comprehensive set of examples and tutorials will be added in the future.
