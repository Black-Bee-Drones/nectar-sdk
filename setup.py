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
            "gesture_recognizer = mirela_sdk.solutions.hand_gesture.gesture_recognizer:main",
            "gesture_controller = mirela_sdk.solutions.hand_gesture.controller:main",
            "test_velocity = mirela_sdk.control.mavros.examples.test_velocity:main",
        ],
    },
)
