"""
ROS-side bridge for a running PX4 SITL instance.

Brings up MAVROS (PX4 offboard MAVLink API on UDP 14540) plus, optionally, the
Gazebo sensor (camera) bridges and an external-vision relay. PX4 starts Gazebo
itself, so this launch only adds the ROS side. Set ``mavros:=false`` for the
direct-pymavlink ``px4_mavlink`` backend, which connects to UDP 14540 itself.

Prerequisites:
    PX4 SITL must be running (which also starts Gazebo):
        ./scripts/simulation/start_px4.sh

Usage:
    ros2 launch nectar px4_sitl.launch.py
    ros2 launch nectar px4_sitl.launch.py fcu_url:=udp://:14540@127.0.0.1:14580
    ros2 launch nectar px4_sitl.launch.py gcs_url:=udp://@192.168.1.100:14550
    ros2 launch nectar px4_sitl.launch.py vision:=true   # relay an external pose to PX4 EKF2
    ros2 launch nectar px4_sitl.launch.py gz_bridge:=true # bridge Nectar cameras (matches sitl_gazebo)
    ros2 launch nectar px4_sitl.launch.py mavros:=false gz_bridge:=true  # direct-pymavlink (px4_mavlink): cameras only, no MAVROS
"""

import os

from launch_ros.actions import Node

from launch import LaunchContext, LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration


def _launch_setup(context: LaunchContext) -> list:
    fcu_url = LaunchConfiguration("fcu_url").perform(context)
    gcs_url = LaunchConfiguration("gcs_url").perform(context)
    use_mavros = LaunchConfiguration("mavros").perform(context).lower() in ("true", "1", "yes")
    use_vision = LaunchConfiguration("vision").perform(context).lower() in ("true", "1", "yes")
    use_gz_bridge = LaunchConfiguration("gz_bridge").perform(context).lower() in (
        "true",
        "1",
        "yes",
    )

    actions = []

    # MAVROS plugin config: deny the legacy ArduPilot rangefinder plugin and map
    # PX4's downward DISTANCE_SENSOR to /mavros/rangefinder/rangefinder (the same
    # rangefinder topic the SDK reads for ArduPilot). All other plugins use
    # MAVROS' PX4 defaults. PX4 streams telemetry at its own rates, so the
    # SET_STREAM_RATE timer used by the ArduPilot launch is not needed.
    # Skip MAVROS for the direct-pymavlink (px4_mavlink) backend, which connects
    # to UDP 14540 itself (mavros:=false).
    if use_mavros:
        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "simulation",
            "config",
        )
        mavros_node = Node(
            package="mavros",
            executable="mavros_node",
            namespace="mavros",
            output="screen",
            parameters=[
                os.path.join(config_dir, "px4_pluginlists_sitl.yaml"),
                os.path.join(config_dir, "px4_config_sitl.yaml"),
                {
                    "fcu_url": fcu_url,
                    "gcs_url": gcs_url,
                    "tgt_system": 1,
                    "tgt_component": 1,
                    "fcu_protocol": "v2.0",
                },
            ],
        )
        actions.append(mavros_node)

    # Optional: bridge the Nectar cameras from Gazebo to ROS. Same topics and
    # message types as sitl_gazebo.launch.py (ArduPilot side), so downstream
    # nodes are firmware-agnostic. Enable when running the shared Nectar world
    # with x500_nectar (start_px4.sh --model x500_nectar --world outdoor_field_px4).
    # The lidar is NOT bridged here — it reaches ROS as /mavros/rangefinder/
    # rangefinder via PX4's DISTANCE_SENSOR stream (see px4_config_sitl.yaml).
    if use_gz_bridge:
        gz_bridge_node = Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            arguments=[
                "/front_camera/image@sensor_msgs/msg/Image[gz.msgs.Image",
                "/front_camera/depth_image@sensor_msgs/msg/Image[gz.msgs.Image",
                "/front_camera/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked",
                "/down_camera@sensor_msgs/msg/Image[gz.msgs.Image",
            ],
            output="screen",
        )
        actions.append(gz_bridge_node)

    # Optional: relay an external pose source to PX4's EKF2 (indoor / GPS-denied).
    # Provide the pose on the canonical VSLAM topic; the node forwards it to
    # /mavros/vision_pose/pose_cov, which MAVROS sends to PX4.
    if use_vision:
        vision_pose_node = Node(
            package="nectar",
            executable="vision_pose_node.py",
            name="vision_pose_node",
            parameters=[
                {"backend": "mavros"},
                {"input_topic": "/visual_slam/tracking/vo_pose_covariance"},
            ],
            output="screen",
        )
        actions.append(vision_pose_node)

    return actions


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "fcu_url",
                default_value="udp://:14540@127.0.0.1:14580",
                description="MAVLink connection URL to PX4 SITL (offboard API on UDP 14540)",
            ),
            DeclareLaunchArgument(
                "gcs_url",
                default_value="",
                description="GCS proxy URL (e.g. udp://@192.168.1.100:14550)",
            ),
            DeclareLaunchArgument(
                "mavros",
                default_value="true",
                description="Start MAVROS. Set false for the direct-pymavlink "
                "px4_mavlink backend (the drone connects to UDP 14540 itself).",
            ),
            DeclareLaunchArgument(
                "vision",
                default_value="false",
                description="Relay an external pose to PX4 EKF2 (indoor / GPS-denied)",
            ),
            DeclareLaunchArgument(
                "gz_bridge",
                default_value="false",
                description="Bridge Nectar cameras from Gazebo to ROS "
                "(/front_camera/*, /down_camera). Use with --model x500_nectar. "
                "The lidar reaches ROS via /mavros/rangefinder/rangefinder.",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
