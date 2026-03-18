"""
MAVROS launch file for ArduPilot SITL connection.

Starts MAVROS configured to connect to a running ArduPilot SITL instance
on tcp://127.0.0.1:5760 (SERIAL0 default). No hardware required.

Loads a SITL config override that renames the distance_sensor topic
to /mavros/rangefinder/rangefinder (matching real hardware).

Prerequisites:
    ArduPilot SITL must be running:
        ./scripts/simulation/start_sitl.sh

Usage:
    ros2 launch nectar sitl.launch.py
    ros2 launch nectar sitl.launch.py fcu_url:=tcp://127.0.0.1:5760
    ros2 launch nectar sitl.launch.py gcs_url:=udp://@192.168.1.100:14550
"""

import os

from launch_ros.actions import Node

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    TimerAction,
)
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    # Nectar SITL config paths (custom MAVROS configs with renamed rangefinder topic)
    src_sim_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "simulation",
    )

    # SITL default: TCP port 5760 (SERIAL0 from ArduCopter binary)
    fcu_url_arg = DeclareLaunchArgument(
        "fcu_url",
        default_value="tcp://127.0.0.1:5760",
        description="MAVLink connection URL to ArduPilot SITL",
    )

    gcs_url_arg = DeclareLaunchArgument(
        "gcs_url",
        default_value="",
        description="GCS proxy URL (e.g. udp://@192.168.1.100:14550)",
    )

    mavros_node = Node(
        package="mavros",
        executable="mavros_node",
        namespace="mavros",
        output="screen",
        parameters=[
            os.path.join(src_sim_dir, "config", "apm_pluginlists_sitl.yaml"),
            os.path.join(src_sim_dir, "config", "apm_config_sitl.yaml"),
            {
                "fcu_url": LaunchConfiguration("fcu_url"),
                "gcs_url": LaunchConfiguration("gcs_url"),
                "tgt_system": 1,
                "tgt_component": 1,
                "fcu_protocol": "v2.0",
            },
        ],
    )

    # Request all data streams from ArduPilot SITL at 10 Hz.
    set_stream_rate = TimerAction(
        period=8.0,
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

    return LaunchDescription(
        [
            fcu_url_arg,
            gcs_url_arg,
            mavros_node,
            set_stream_rate,
        ]
    )
