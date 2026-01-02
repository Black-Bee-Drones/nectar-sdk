import os
from glob import glob
from setuptools import find_packages, setup


package_name = "mirela_sdk"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob(os.path.join("launch", "*launch.[pxy][yma]*")),
        ),
        (
            os.path.join("share", package_name, "config"),
            glob(os.path.join("config", "*.yaml")),
        ),
        (
            os.path.join("share", package_name, "config", "mavros"),
            glob(os.path.join("config", "mavros", "*.yaml")),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Black Bee Drones",
    maintainer_email="samuellimabraz@gmail.com",
    description="Drone control and computer vision SDK for ROS2",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "gui = mirela_sdk.interface.gui:main",
            "aruco_node = mirela_sdk.image_processing.aruco.aruco_node:main",
            "test_velocity = mirela_sdk.examples.test_velocity:main",
            "test_gps = mirela_sdk.examples.test_gps:main",
            "camera_example = mirela_sdk.examples.camera_example:main",
            "depth_example = mirela_sdk.examples.depth_example:main",
            "yolo_example = mirela_sdk.examples.yolo_example:main",
            "color_calibration_node = mirela_sdk.image_processing.color.color_calibration_node:main",
            "click_color_calibration_node = mirela_sdk.image_processing.color.click_color_calibration_node:main",
            "camera_calibration = mirela_sdk.image_processing.camera.calibration.calibration:main",
            "line_detection_node = mirela_sdk.image_processing.line.line_detection_node:main",
            "webcam_publisher = mirela_sdk.image_processing.camera.webcam_publisher_node:main",
            "pid_controller_node = mirela_sdk.control.pid.pid_node:main",
        ],
    },
)
