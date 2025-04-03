from setuptools import find_packages, setup
import os
from glob import glob


package_name = "mirela_sdk"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob(os.path.join("launch", "*launch.[pxy][yma]*")),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="samuel",
    maintainer_email="samuellimabraz@gmail.com",
    description="TODO: Package description",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "gui = mirela_sdk.interface.gui:main",
            "aruco_node = mirela_sdk.image_processing.aruco.aruco_node:main",
            "test_velocity = mirela_sdk.examples.test_velocity:main",
            "test_raspicam = mirela_sdk.examples.raspicam_viewer:main",
            "color_calibration_node = mirela_sdk.image_processing.color.color_calibration_node:main",
            "camera_calibration = mirela_sdk.image_processing.camera.calibration.calibration:main",
            "line_detection_node = mirela_sdk.image_processing.line.line_detection_node:main",
        ],
    },
)
