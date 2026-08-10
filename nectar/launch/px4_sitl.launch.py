"""
ROS-side bridge for a running PX4 SITL instance.

Brings up MAVROS (PX4 offboard MAVLink API on UDP 14540) plus, optionally, the
Gazebo sensor (camera) bridges and the indoor external-vision pipeline
(gz_vision_source → canonical VSLAM topics → vision_pose_node). PX4 starts
Gazebo itself, so this launch only adds the ROS side. Set ``mavros:=false`` for
the direct-pymavlink ``px4_mavlink`` backend, which connects to UDP 14540 itself.

Prerequisites:
    PX4 SITL must be running (which also starts Gazebo):
        ./scripts/simulation/start_px4.sh

Usage:
    ros2 launch nectar px4_sitl.launch.py
    ros2 launch nectar px4_sitl.launch.py fcu_url:=udp://:14540@127.0.0.1:14580
    ros2 launch nectar px4_sitl.launch.py gcs_url:=udp://@192.168.1.100:14550
    ros2 launch nectar px4_sitl.launch.py vision:=true   # indoor external-nav
    ros2 launch nectar px4_sitl.launch.py gz_bridge:=true # bridge Nectar cameras
    ros2 launch nectar px4_sitl.launch.py mavros:=false gz_bridge:=true  # px4_mavlink
    ros2 launch nectar px4_sitl.launch.py vision:=true mavros:=false backend:=dds
"""

import os

from launch_ros.actions import Node

from launch import LaunchContext, LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration


def _truthy(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def _launch_setup(context: LaunchContext) -> list:
    fcu_url = LaunchConfiguration("fcu_url").perform(context)
    gcs_url = LaunchConfiguration("gcs_url").perform(context)
    use_mavros = _truthy(LaunchConfiguration("mavros").perform(context))
    use_vision = _truthy(LaunchConfiguration("vision").perform(context))
    use_gz_bridge = _truthy(LaunchConfiguration("gz_bridge").perform(context))
    backend = LaunchConfiguration("backend").perform(context).strip().lower()
    send_speed = _truthy(LaunchConfiguration("send_speed").perform(context))
    world_name = LaunchConfiguration("world_name").perform(context).strip()
    model_name = LaunchConfiguration("model_name").perform(context).strip()

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
    # with x500_nectar (start_px4.sh --model x500_nectar --world …).
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

    # Indoor: GT → VSLAM topics. Consumer for mavros/dds via vision_pose_node;
    # mavlink leaves feed to the mission (single PX4 offboard UDP).
    if use_vision:
        gz_pose_topic = f"/world/{world_name}/dynamic_pose/info"
        vslam_topic = "/visual_slam/tracking/vo_pose_covariance"
        vslam_odom_topic = "/visual_slam/tracking/odometry"

        gz_pose_bridge = Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="gz_pose_bridge",
            arguments=[
                f"{gz_pose_topic}@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
                "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            ],
            output="screen",
        )

        gz_vision_source = Node(
            package="nectar",
            executable="gz_vision_source.py",
            name="gz_vision_source",
            parameters=[
                {"model_name": model_name},
                {"gz_pose_topic": gz_pose_topic},
                {"input_type": "tf"},
                {"output_topic": vslam_topic},
                {"odometry_topic": vslam_odom_topic},
            ],
            output="screen",
        )
        actions.extend([gz_pose_bridge, gz_vision_source])

        start_consumer = backend in ("mavros", "dds")
        if backend == "mavros" and not use_mavros:
            start_consumer = False
        if start_consumer:
            vision_params = {
                "backend": backend,
                "input_topic": vslam_topic,
                "send_speed": send_speed,
                "speed_topic": vslam_odom_topic,
            }
            vision_pose_node = Node(
                package="nectar",
                executable="vision_pose_node.py",
                name="vision_pose_node",
                parameters=[vision_params],
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
                description="Indoor external-nav: gz_vision_source + optional "
                "vision_pose_node (GPS-denied / EKF2 EV).",
            ),
            DeclareLaunchArgument(
                "backend",
                default_value="mavros",
                description="vision_pose_node backend when vision:=true: "
                "mavros | mavlink | dds. mavlink PROTOCOL usually leaves the "
                "consumer to Px4MavlinkDrone (producer-only).",
            ),
            DeclareLaunchArgument(
                "send_speed",
                default_value="false",
                description="Also feed VSLAM velocity (requires EKF2_EV_CTRL bit 2).",
            ),
            DeclareLaunchArgument(
                "world_name",
                default_value="indoor_room_px4",
                description="Gazebo world name for PosePublisher topic "
                "(/world/<name>/dynamic_pose/info).",
            ),
            DeclareLaunchArgument(
                "model_name",
                default_value="x500_nectar_0",
                description="Gazebo model name for gz_vision_source (PX4 spawns "
                "x500_nectar as x500_nectar_0).",
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
