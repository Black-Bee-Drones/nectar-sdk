"""RealSense + Isaac ROS Visual SLAM

ros2 launch nectar isaac_vslam_realsense.launch.py
ros2 launch /path/to/nectar/launch/isaac_vslam_realsense.launch.py enable_depth:=true
"""

import os

from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode
from launch_ros.parameter_descriptions import ParameterValue

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
    params = os.path.join(_config_dir(), "vslam_realsense.yaml")

    enable_depth = LaunchConfiguration("enable_depth")
    enable_color = LaunchConfiguration("enable_color")
    emitter_enabled = LaunchConfiguration("emitter_enabled")
    depth_profile = LaunchConfiguration("depth_profile")

    args = [
        DeclareLaunchArgument("enable_depth", default_value="false"),
        DeclareLaunchArgument("enable_color", default_value="false"),
        DeclareLaunchArgument("emitter_enabled", default_value="0"),
        DeclareLaunchArgument("depth_profile", default_value="640x360x90"),
    ]

    realsense_node = Node(
        name="camera",
        namespace="camera",
        package="realsense2_camera",
        executable="realsense2_camera_node",
        output="screen",
        parameters=[
            params,
            {
                "enable_depth": ParameterValue(enable_depth, value_type=bool),
                "enable_color": ParameterValue(enable_color, value_type=bool),
                "depth_module.emitter_enabled": ParameterValue(emitter_enabled, value_type=int),
                "depth_module.profile": ParameterValue(depth_profile, value_type=str),
            },
        ],
    )

    visual_slam_node = ComposableNode(
        name="visual_slam_node",
        package="isaac_ros_visual_slam",
        plugin="nvidia::isaac_ros::visual_slam::VisualSlamNode",
        parameters=[params],
        remappings=[
            ("visual_slam/image_0", "camera/infra1/image_rect_raw"),
            ("visual_slam/camera_info_0", "camera/infra1/camera_info"),
            ("visual_slam/image_1", "camera/infra2/image_rect_raw"),
            ("visual_slam/camera_info_1", "camera/infra2/camera_info"),
            ("visual_slam/imu", "camera/imu"),
        ],
    )

    container = ComposableNodeContainer(
        name="visual_slam_launch_container",
        namespace="",
        package="rclcpp_components",
        executable="component_container",
        composable_node_descriptions=[visual_slam_node],
        output="screen",
    )

    return launch.LaunchDescription([*args, container, realsense_node])
