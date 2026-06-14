"""
Gazebo + MAVROS launch for ArduPilot SITL.

Starts Gazebo Harmonic with an ArduPilot-enabled world (iris drone with
ArduPilotPlugin) and MAVROS. The ArduPilotPlugin bridges Gazebo physics
to the ArduCopter SITL binary via UDP port 9002.

Supports three world modes:
    - world:=outdoor  — Nectar outdoor_field.sdf (GPS, depth cam, lidar)
    - world:=indoor   — Nectar indoor_room.sdf  (no GPS, vision pose bridge)
    - world:=<file>   — Any .sdf from ardupilot_gazebo/worlds (backward compat)

Prerequisites:
    1. ArduPilot Gazebo plugin installed:
           ./scripts/simulation/install_gazebo.sh
    2. SITL running in Gazebo mode:
           ./scripts/simulation/start_sitl.sh --gazebo          (outdoor)
           ./scripts/simulation/start_sitl.sh --indoor          (indoor)
    3. Environment variables set (done by install_gazebo.sh):
           export GZ_SIM_RESOURCE_PATH=~/ardupilot_gazebo/models:~/ardupilot_gazebo/worlds
           export GZ_SIM_SYSTEM_PLUGIN_PATH=~/ardupilot_gazebo/build

Usage:
    ros2 launch nectar sitl_gazebo.launch.py
    ros2 launch nectar sitl_gazebo.launch.py world:=outdoor
    ros2 launch nectar sitl_gazebo.launch.py world:=indoor
    ros2 launch nectar sitl_gazebo.launch.py world:=iris_runway.sdf
    ros2 launch nectar sitl_gazebo.launch.py mavros:=false   # Gazebo only (direct MAVLink)
"""

import os

from launch_ros.actions import Node

from launch import LaunchContext, LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    TimerAction,
)
from launch.substitutions import LaunchConfiguration

# Map shorthand names to world SDF files
_WORLD_ALIASES = {
    "outdoor": "outdoor_field.sdf",
    "indoor": "indoor_room.sdf",
}


def _launch_setup(context: LaunchContext) -> list:
    ardupilot_gazebo_dir = os.path.expanduser("~/ardupilot_gazebo")
    world_raw = LaunchConfiguration("world").perform(context)
    fcu_url = LaunchConfiguration("fcu_url").perform(context)
    use_mavros = LaunchConfiguration("mavros").perform(context).lower() in ("true", "1", "yes")

    # Resolve world shorthand
    world_file = _WORLD_ALIASES.get(world_raw, world_raw)
    is_indoor = world_raw == "indoor"

    # ── Gazebo environment ──────────────────────────────────────────────
    models_dir = os.path.join(ardupilot_gazebo_dir, "models")
    worlds_dir = os.path.join(ardupilot_gazebo_dir, "worlds")
    plugin_dir = os.path.join(ardupilot_gazebo_dir, "build")

    # Nectar simulation paths (source tree)
    src_sim_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "simulation",
    )
    src_worlds_dir = os.path.join(src_sim_dir, "worlds")
    src_models_dir = os.path.join(src_sim_dir, "models")

    existing_resource = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    gz_resource_path = os.pathsep.join(
        p
        for p in [
            src_worlds_dir,
            src_models_dir,
            src_sim_dir,
            models_dir,
            worlds_dir,
            existing_resource,
        ]
        if p
    )

    existing_plugin = os.environ.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
    gz_plugin_path = os.pathsep.join(p for p in [plugin_dir, existing_plugin] if p)

    gz_env = {
        "GZ_SIM_RESOURCE_PATH": gz_resource_path,
        "GZ_SIM_SYSTEM_PLUGIN_PATH": gz_plugin_path,
    }

    # ── Gazebo Harmonic ─────────────────────────────────────────────────
    gz_sim = ExecuteProcess(
        cmd=["gz", "sim", "-v4", "-r", world_file],
        output="screen",
        additional_env=gz_env,
    )

    # ── ros_gz_bridge — cameras + lidar ─────────────────────────────────
    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/front_camera/image@sensor_msgs/msg/Image[gz.msgs.Image",
            "/front_camera/depth_image@sensor_msgs/msg/Image[gz.msgs.Image",
            "/front_camera/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked",
            "/down_camera@sensor_msgs/msg/Image[gz.msgs.Image",
            "/lidar/range@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
        ],
        output="screen",
    )

    # ── MAVROS ──────────────────────────────────────────────────────────
    # Launch mavros_node directly (instead of apm.launch) with custom
    # config that renames the distance_sensor topic from "rangefinder_pub"
    # to "rangefinder/rangefinder" — matching /mavros/rangefinder/rangefinder
    # on real hardware. Legacy rangefinder plugin is denylisted.
    mavros_launch = Node(
        package="mavros",
        executable="mavros_node",
        namespace="mavros",
        output="screen",
        parameters=[
            os.path.join(src_sim_dir, "config", "apm_pluginlists_sitl.yaml"),
            os.path.join(src_sim_dir, "config", "apm_config_sitl.yaml"),
            {
                "fcu_url": fcu_url,
                "gcs_url": "",
                "tgt_system": 1,
                "tgt_component": 1,
                "fcu_protocol": "v2.0",
            },
        ],
    )

    set_stream_rate = TimerAction(
        period=10.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "service",
                    "call",
                    "/mavros/set_stream_rate",
                    "mavros_msgs/srv/StreamRate",
                    "{stream_id: 0, message_rate: 10, on_off: true}",
                ],
                output="log",
            )
        ],
    )

    actions = [gz_sim, ros_gz_bridge]

    # MAVROS is optional: skip it (mavros:=false) to drive the SITL directly via
    # MavlinkDrone (pymavlink) without an unused MAVROS bridge running.
    if use_mavros:
        actions.extend([mavros_launch, set_stream_rate])

    # ── Indoor-only: vision pose pipeline ───
    if is_indoor:
        # World name from SDF filename (e.g. "indoor_room.sdf" -> "indoor_room")
        world_name = os.path.splitext(world_file)[0]
        gz_pose_topic = f"/world/{world_name}/dynamic_pose/info"
        vslam_topic = "/visual_slam/tracking/vo_pose_covariance"

        # Bridge Gazebo ground-truth pose topic to ROS 2
        gz_pose_bridge = Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="gz_pose_bridge",
            arguments=[
                f"{gz_pose_topic}@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
            ],
            output="screen",
        )

        # Gazebo ground-truth -> canonical VSLAM topic
        gz_vision_source = Node(
            package="nectar",
            executable="gz_vision_source.py",
            name="gz_vision_source",
            parameters=[
                {"model_name": "iris"},
                {"gz_pose_topic": gz_pose_topic},
                {"output_topic": vslam_topic},
            ],
            output="screen",
        )

        actions.extend([gz_pose_bridge, gz_vision_source])

        if use_mavros:
            vision_pose_node = Node(
                package="nectar",
                executable="vision_pose_node.py",
                name="vision_pose_node",
                parameters=[
                    {"backend": "mavros"},
                    {"input_topic": vslam_topic},
                ],
                output="screen",
            )
            actions.append(vision_pose_node)

    return actions


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "world",
                default_value="outdoor",
                description=(
                    "World to load: 'outdoor', 'indoor', or an .sdf filename "
                    "from ardupilot_gazebo/worlds"
                ),
            ),
            DeclareLaunchArgument(
                "fcu_url",
                default_value="tcp://127.0.0.1:5760",
                description="MAVLink connection URL to ArduPilot SITL",
            ),
            DeclareLaunchArgument(
                "mavros",
                default_value="true",
                description=(
                    "Start MAVROS (true) or only Gazebo physics (false) for "
                    "direct MAVLink control via MavlinkDrone"
                ),
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
