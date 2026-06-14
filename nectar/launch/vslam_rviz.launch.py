"""RViz for Isaac VSLAM.

  light : TF + odometry + SLAM path (tracking outputs only, no extra Jetson load)
  full  : light + landmarks / loop-closure clouds + pose graph
          (requires the producer launched with enable_visualization:=true)

Usage:
    ros2 launch nectar vslam_rviz.launch.py
    ros2 launch nectar vslam_rviz.launch.py profile:=full
"""

import os

from launch_ros.actions import Node

import launch
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration


def _rviz_dir() -> str:
    """Resolve the rviz dir from the source tree, else the installed share."""
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(os.path.dirname(here), "nectar", "control", "localization", "rviz")
    if os.path.isdir(src):
        return src
    from ament_index_python.packages import get_package_share_directory

    return os.path.join(get_package_share_directory("nectar"), "control", "localization", "rviz")


def _setup(context):
    profile = LaunchConfiguration("profile").perform(context)
    config = os.path.join(_rviz_dir(), f"vslam_{profile}.rviz")
    return [
        Node(
            package="rviz2",
            executable="rviz2",
            name="vslam_rviz",
            arguments=["-d", config],
            output="screen",
        )
    ]


def generate_launch_description():
    return launch.LaunchDescription(
        [
            DeclareLaunchArgument(
                "profile",
                default_value="light",
                choices=["light", "full"],
                description="RViz profile: light (tracking only) or full (+ /vis topics)",
            ),
            OpaqueFunction(function=_setup),
        ]
    )
