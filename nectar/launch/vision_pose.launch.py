"""
Consumer side of the localization pipeline. The ``backend`` argument selects how
the VSLAM pose reaches the FCU:

    backend:=mavros   start MAVROS (indoor config) + republish to
                      /mavros/vision_pose/pose_cov
    backend:=mavlink  send VISION_POSITION_ESTIMATE over a direct pymavlink link
    backend:=dds      publish px4_msgs/VehicleOdometry on
                      /fmu/in/vehicle_visual_odometry (PX4 native uXRCE-DDS)

send_speed:=true additionally feeds the VSLAM velocity to the estimator; it only
does anything once the FCU is configured to fuse it

Usage::

    ros2 launch nectar vision_pose.launch.py backend:=mavros fcu_url:=/dev/ttyTHS1:921600
    ros2 launch nectar vision_pose.launch.py backend:=mavlink mavlink_url:=udp:127.0.0.1:14552
    ros2 launch nectar vision_pose.launch.py backend:=dds
    ros2 launch nectar vision_pose.launch.py backend:=mavros send_speed:=true

``mavlink_url`` is any pymavlink endpoint (override the default). Use a dedicated
link from the mission process (see localization README: one feeder rule).
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
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
    odometry_topic = LaunchConfiguration("odometry_topic")
    px4_namespace = LaunchConfiguration("px4_namespace")
    send_speed = ParameterValue(LaunchConfiguration("send_speed"), value_type=bool)
    speed_topic = LaunchConfiguration("speed_topic")

    cfg = os.path.join(get_package_share_directory("nectar"), "control", "mavros", "config")
    pluginlists = os.path.join(cfg, "indoor_pluginlists.yaml")
    mavros_config = os.path.join(cfg, "indoor_mavros.yaml")

    is_mavros = IfCondition(PythonExpression(["'", backend, "' == 'mavros'"]))
    is_mavlink = IfCondition(PythonExpression(["'", backend, "' == 'mavlink'"]))
    is_dds = IfCondition(PythonExpression(["'", backend, "' == 'dds'"]))

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
        parameters=[
            {
                "backend": "mavros",
                "input_topic": input_topic,
                "send_speed": send_speed,
                "speed_topic": speed_topic,
            }
        ],
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
                "send_speed": send_speed,
                "speed_topic": speed_topic,
            }
        ],
    )

    bridge_dds = Node(
        package="nectar",
        executable="vision_pose_node.py",
        name="vision_pose_node",
        output="screen",
        condition=is_dds,
        parameters=[
            {
                "backend": "dds",
                "input_topic": input_topic,
                "odometry_topic": odometry_topic,
                "px4_namespace": px4_namespace,
                "send_speed": send_speed,
                "speed_topic": speed_topic,
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
            DeclareLaunchArgument("mavlink_url", default_value="udp:127.0.0.1:14552"),
            DeclareLaunchArgument(
                "odometry_topic", default_value="/fmu/in/vehicle_visual_odometry"
            ),
            DeclareLaunchArgument("px4_namespace", default_value=""),
            DeclareLaunchArgument("send_speed", default_value="false"),
            DeclareLaunchArgument("speed_topic", default_value="/visual_slam/tracking/odometry"),
            mavros_include,
            bridge_mavros,
            bridge_mavlink,
            bridge_dds,
        ]
    )
