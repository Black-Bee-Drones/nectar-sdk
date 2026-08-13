"""RealSense + Isaac ROS Visual SLAM (release-3.2).

All RealSense and Visual SLAM parameters live in the YAML (single source of
truth). Edit that file and restart the producer — do not rely on scattered
launch overrides.

  nectar-vslam
  ros2 launch nectar isaac_vslam_realsense.launch.py
  ros2 launch /path/to/nectar/launch/isaac_vslam_realsense.launch.py

Optional alternate config:

  nectar-vslam params_file:=/path/to/other.yaml

Defaults
  - infra @ 640x360x90 + IMU for cuVSLAM (emitter off)
  - RGB on (realsense default rgb_camera.profile 0,0,0) for /camera/color/...
  - depth off (set enable_depth: true in the YAML if needed)
  - visualization topics off (set enable_slam_visualization etc. in the YAML)
"""

import os

from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode

import launch
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def _config_dir() -> str:
    """Resolve the config dir from the source tree, else the installed share."""
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(os.path.dirname(here), "nectar", "control", "localization", "config")
    if os.path.isdir(src):
        return src
    from ament_index_python.packages import get_package_share_directory

    return os.path.join(get_package_share_directory("nectar"), "control", "localization", "config")


def generate_launch_description():
    default_params = os.path.join(_config_dir(), "vslam_realsense.yaml")
    params_file = LaunchConfiguration("params_file")

    return launch.LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                default_value=default_params,
                description="YAML with /camera/camera and /visual_slam_node parameters",
            ),
            ComposableNodeContainer(
                name="visual_slam_launch_container",
                namespace="",
                package="rclcpp_components",
                executable="component_container",
                composable_node_descriptions=[
                    ComposableNode(
                        name="visual_slam_node",
                        package="isaac_ros_visual_slam",
                        plugin="nvidia::isaac_ros::visual_slam::VisualSlamNode",
                        parameters=[params_file],
                        remappings=[
                            ("visual_slam/image_0", "camera/infra1/image_rect_raw"),
                            ("visual_slam/camera_info_0", "camera/infra1/camera_info"),
                            ("visual_slam/image_1", "camera/infra2/image_rect_raw"),
                            ("visual_slam/camera_info_1", "camera/infra2/camera_info"),
                            ("visual_slam/imu", "camera/imu"),
                        ],
                    ),
                ],
                output="screen",
            ),
            Node(
                name="camera",
                namespace="camera",
                package="realsense2_camera",
                executable="realsense2_camera_node",
                output="screen",
                parameters=[params_file],
            ),
        ]
    )
