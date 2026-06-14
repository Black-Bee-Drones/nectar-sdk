"""
Consumer side of the localization pipeline. The ``backend`` argument selects how
the VSLAM pose reaches the FCU:

    backend:=mavros   start MAVROS (indoor config) + republish to
                      /mavros/vision_pose/pose_cov
    backend:=mavlink  send VISION_POSITION_ESTIMATE over a direct pymavlink link

Usage::

    ros2 launch nectar vision_pose.launch.py backend:=mavros fcu_url:=/dev/ttyTHS1:921600
    ros2 launch nectar vision_pose.launch.py backend:=mavlink mavlink_url:=udp:127.0.0.1:14551
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)


def generate_launch_description():
    backend = LaunchConfiguration("backend")
    input_topic = LaunchConfiguration("input_topic")
    fcu_url = LaunchConfiguration("fcu_url")
    gcs_url = LaunchConfiguration("gcs_url")
    tgt_system = LaunchConfiguration("tgt_system")
    tgt_component = LaunchConfiguration("tgt_component")
    namespace = LaunchConfiguration("namespace")
    mavlink_url = LaunchConfiguration("mavlink_url")

    cfg = os.path.join(get_package_share_directory("nectar"), "control", "mavros", "config")
    pluginlists = os.path.join(cfg, "indoor_pluginlists.yaml")
    mavros_config = os.path.join(cfg, "indoor_mavros.yaml")

    is_mavros = IfCondition(PythonExpression(["'", backend, "' == 'mavros'"]))
    is_mavlink = IfCondition(PythonExpression(["'", backend, "' == 'mavlink'"]))

    # Resolved lazily so the mavlink-only path does not require MAVROS.
    mavros_launch = PathJoinSubstitution([FindPackageShare("mavros"), "launch", "node.launch"])

    mavros_include = IncludeLaunchDescription(
        XMLLaunchDescriptionSource(mavros_launch),
        condition=is_mavros,
        launch_arguments={
            "pluginlists_yaml": pluginlists,
            "config_yaml": mavros_config,
            "fcu_url": fcu_url,
            "gcs_url": gcs_url,
            "tgt_system": tgt_system,
            "tgt_component": tgt_component,
            "namespace": namespace,
        }.items(),
    )

    bridge_mavros = Node(
        package="nectar",
        executable="vision_pose_node.py",
        name="vision_pose_node",
        output="screen",
        condition=is_mavros,
        parameters=[{"backend": "mavros", "input_topic": input_topic}],
    )

    bridge_mavlink = Node(
        package="nectar",
        executable="vision_pose_node.py",
        name="vision_pose_node",
        output="screen",
        condition=is_mavlink,
        parameters=[
            {
                "backend": "mavlink",
                "input_topic": input_topic,
                "mavlink_url": mavlink_url,
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("backend", default_value="mavros"),
            DeclareLaunchArgument(
                "input_topic",
                default_value="/visual_slam/tracking/vo_pose_covariance",
            ),
            DeclareLaunchArgument("fcu_url", default_value="/dev/ttyTHS1:921600"),
            DeclareLaunchArgument("gcs_url", default_value=""),
            DeclareLaunchArgument("tgt_system", default_value="1"),
            DeclareLaunchArgument("tgt_component", default_value="1"),
            DeclareLaunchArgument("namespace", default_value="mavros"),
            DeclareLaunchArgument("mavlink_url", default_value="udp:127.0.0.1:14551"),
            mavros_include,
            bridge_mavros,
            bridge_mavlink,
        ]
    )
