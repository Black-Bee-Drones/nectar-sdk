"""
Gazebo + MAVROS launch for ArduPilot SITL.

Starts Gazebo Harmonic with an ArduPilot-enabled world (iris + Nectar cameras)
and MAVROS. Mission packages supply scenery only; Nectar owns the vehicle stack.

World modes:
    - world:=outdoor / indoor — compose from vehicle templates + stock scenery
    - world:=<path.sdf>       — load a full custom world (escape hatch)

Composition args (preferred for custom arenas):
    scenery:=model://name     — scenery include URI (default: stock room/field)
    spawn_pose:="x y z r p y" — iris pose in degrees
    resource_path:=a:b        — extra GZ_SIM_RESOURCE_PATH entries

Indoor vision pose uses fixed world names nectar_indoor / nectar_outdoor when
composed. For a full custom world SDF, the <world name="..."> attribute is parsed.

Usage:
    ros2 launch nectar sitl_gazebo.launch.py world:=outdoor
    ros2 launch nectar sitl_gazebo.launch.py world:=indoor
    ros2 launch nectar sitl_gazebo.launch.py world:=indoor \\
        scenery:=model://my_arena spawn_pose:="-5 0 0.195 0 0 0" \\
        resource_path:=/path/to/models
    ros2 launch nectar sitl_gazebo.launch.py mavros:=false
"""

from __future__ import annotations

import os
import re
import tempfile

from launch_ros.actions import Node

from launch import LaunchContext, LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    TimerAction,
)
from launch.substitutions import LaunchConfiguration

_DEFAULT_SCENERY = {
    "outdoor": "model://outdoor_field_scenery",
    "indoor": "model://indoor_room_scenery",
}

_DEFAULT_SPAWN = {
    "outdoor": "0 0 0.195 0 0 0",
    "indoor": "-5 0 0.195 0 0 0",
}

_COMPOSED_WORLD_NAME = {
    "outdoor": "nectar_outdoor",
    "indoor": "nectar_indoor",
}


def _truthy(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def _normalize_scenery_uri(scenery: str) -> str:
    scenery = scenery.strip()
    if not scenery:
        return ""
    if "://" in scenery:
        return scenery
    return f"model://{scenery}"


def _parse_world_name_from_sdf(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read(8192)
    except OSError:
        return None
    match = re.search(r'<world\s+name="([^"]+)"', text)
    return match.group(1) if match else None


def _compose_vehicle_world(
    template_path: str,
    scenery_uri: str,
    spawn_pose: str,
    dest_path: str,
) -> None:
    with open(template_path, encoding="utf-8") as fh:
        text = fh.read()

    if scenery_uri:
        scenery_block = f"    <include>\n      <uri>{scenery_uri}</uri>\n    </include>"
    else:
        scenery_block = ""

    text = text.replace("{{SCENERY_INCLUDE}}", scenery_block)
    text = text.replace("{{SPAWN_POSE}}", spawn_pose.strip())

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _launch_setup(context: LaunchContext) -> list:
    ardupilot_gazebo_dir = os.path.expanduser("~/ardupilot_gazebo")
    world_raw = LaunchConfiguration("world").perform(context).strip()
    fcu_url = LaunchConfiguration("fcu_url").perform(context)
    use_mavros = _truthy(LaunchConfiguration("mavros").perform(context))
    headless = _truthy(LaunchConfiguration("headless").perform(context))
    vision_arg = LaunchConfiguration("vision").perform(context).lower()
    resource_path_extra = LaunchConfiguration("resource_path").perform(context)
    scenery_raw = LaunchConfiguration("scenery").perform(context)
    spawn_pose_raw = LaunchConfiguration("spawn_pose").perform(context).strip()

    src_sim_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "simulation",
    )
    src_worlds_dir = os.path.join(src_sim_dir, "worlds")
    src_models_dir = os.path.join(src_sim_dir, "models")
    src_templates_dir = os.path.join(src_sim_dir, "templates")

    compose_env = world_raw if world_raw in ("outdoor", "indoor") else None
    composed = False
    world_name = None

    if compose_env is not None:
        scenery_uri = _normalize_scenery_uri(scenery_raw) or _DEFAULT_SCENERY[compose_env]
        spawn_pose = spawn_pose_raw or _DEFAULT_SPAWN[compose_env]
        template = os.path.join(src_templates_dir, f"{compose_env}_vehicle.sdf.in")
        dest = os.path.join(
            tempfile.gettempdir(),
            f"nectar_{compose_env}_composed.sdf",
        )
        _compose_vehicle_world(template, scenery_uri, spawn_pose, dest)
        world_file = dest
        world_name = _COMPOSED_WORLD_NAME[compose_env]
        composed = True
    else:
        world_file = os.path.expanduser(world_raw)
        if os.path.isfile(world_file):
            world_name = _parse_world_name_from_sdf(world_file)
        if not world_name:
            world_name = os.path.splitext(os.path.basename(world_file))[0]

    # Vision / indoor ExternalNav
    if vision_arg in ("true", "1", "yes"):
        is_indoor = True
    elif vision_arg in ("false", "0", "no"):
        is_indoor = False
    else:
        is_indoor = compose_env == "indoor" or world_raw == "indoor"

    models_dir = os.path.join(ardupilot_gazebo_dir, "models")
    worlds_dir = os.path.join(ardupilot_gazebo_dir, "worlds")
    plugin_dir = os.path.join(ardupilot_gazebo_dir, "build")

    extra_dirs = [os.path.expanduser(p) for p in resource_path_extra.split(os.pathsep) if p.strip()]
    # If world is an absolute path, add its parent dir so sibling models resolve.
    if os.path.isabs(world_file) and os.path.isfile(world_file):
        extra_dirs.append(os.path.dirname(world_file))

    existing_resource = os.environ.get("GZ_SIM_RESOURCE_PATH", "")
    gz_resource_path = os.pathsep.join(
        p
        for p in [
            src_worlds_dir,
            src_models_dir,
            src_sim_dir,
            *extra_dirs,
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

    gz_cmd = ["gz", "sim", "-v4", "-r", world_file]
    if headless:
        gz_cmd.insert(2, "-s")
    gz_sim = ExecuteProcess(
        cmd=gz_cmd,
        output="screen",
        additional_env=gz_env,
    )

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

    if use_mavros:
        actions.extend([mavros_launch, set_stream_rate])

    if is_indoor:
        gz_pose_topic = f"/world/{world_name}/dynamic_pose/info"
        vslam_topic = "/visual_slam/tracking/vo_pose_covariance"

        gz_pose_bridge = Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="gz_pose_bridge",
            arguments=[
                f"{gz_pose_topic}@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
            ],
            output="screen",
        )

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

    _ = composed  # composition path always sets world_name explicitly
    return actions


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "world",
                default_value="outdoor",
                description=(
                    "'outdoor' / 'indoor' (compose Nectar vehicle + scenery), "
                    "or path/filename to a full custom .sdf"
                ),
            ),
            DeclareLaunchArgument(
                "scenery",
                default_value="",
                description=(
                    "Scenery include URI for composed worlds "
                    "(e.g. model://my_arena). Empty = stock room/field scenery."
                ),
            ),
            DeclareLaunchArgument(
                "spawn_pose",
                default_value="",
                description=(
                    'Iris pose "x y z roll pitch yaw" in degrees for composed '
                    "worlds. Empty = template default."
                ),
            ),
            DeclareLaunchArgument(
                "vision",
                default_value="auto",
                description=(
                    "Indoor vision-pose pipeline: 'auto' (on for world:=indoor), "
                    "'true', or 'false'."
                ),
            ),
            DeclareLaunchArgument(
                "resource_path",
                default_value="",
                description=(
                    "Extra colon-separated dirs prepended to GZ_SIM_RESOURCE_PATH "
                    "(mission package simulation/models, etc.)."
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
            DeclareLaunchArgument(
                "headless",
                default_value="false",
                description="Run Gazebo server-only (no GUI) for headless CI / no display",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
