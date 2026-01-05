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
            os.path.join("share", package_name, "control", "config"),
            glob(os.path.join("control", "config", "*.yaml")),
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
            # vision
            "aruco_node = mirela_sdk.vision.nodes.aruco_node:main",
            "color_calibration_node = mirela_sdk.vision.nodes.color_calibration_node:main",
            "click_color_calibration_node = mirela_sdk.vision.nodes.click_color_calibration_node:main",
            "camera_calibration = mirela_sdk.vision.camera.calibration.calibration:main",
            "line_detection_node = mirela_sdk.vision.nodes.line_detection_node:main",
            "webcam_publisher = mirela_sdk.vision.nodes.webcam_publisher_node:main",
            "camera_example = mirela_sdk.examples.vision.camera_example:main",
            "depth_example = mirela_sdk.examples.vision.depth_example:main",
            "yolo_example = mirela_sdk.examples.vision.yolo_example:main",
            # control
            "pid_controller_node = mirela_sdk.control.pid.pid_node:main",
        ],
    },
)
