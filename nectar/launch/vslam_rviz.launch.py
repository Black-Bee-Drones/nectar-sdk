"""RViz for Isaac VSLAM.

  light : TF + odometry + SLAM path (green) + VO path (purple), tracking outputs
          only, no extra Jetson load. The two paths are shown as a rolling buffer
          (last ``window_seconds``) via the path_window_node relay run here.
  full  : light + landmarks / loop-closure clouds + pose graph
          (requires the producer launched with enable_visualization:=true)

Usage:
    ros2 launch nectar vslam_rviz.launch.py
    ros2 launch nectar vslam_rviz.launch.py window_seconds:=30
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
    window_seconds = LaunchConfiguration("window_seconds").perform(context)
    config = os.path.join(_rviz_dir(), f"vslam_{profile}.rviz")
    nodes = [
        Node(
            package="rviz2",
            executable="rviz2",
            name="vslam_rviz",
            arguments=["-d", config],
            output="screen",
        )
    ]

    if profile == "light":
        nodes.append(
            Node(
                package="nectar",
                executable="path_window_node.py",
                name="path_window_node",
                parameters=[{"window_seconds": float(window_seconds)}],
                output="screen",
            )
        )
    return nodes


def generate_launch_description():
    return launch.LaunchDescription(
        [
            DeclareLaunchArgument(
                "profile",
                default_value="light",
                choices=["light", "full"],
                description="RViz profile: light (tracking only) or full (+ /vis topics)",
            ),
            DeclareLaunchArgument(
                "window_seconds",
                default_value="15.0",
                description="light: keep only the last N seconds of path (rolling buffer); "
                "0 = full history",
            ),
            OpaqueFunction(function=_setup),
        ]
    )
