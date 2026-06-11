import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from nectar.control.ardupilot.types import SensorOrientation
from nectar.control.types import PoseSource

_MAVROS_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config", "mavros")


@dataclass(frozen=True)
class DroneConfig:
    name: str = "drone"
    start_driver: bool = False


@dataclass(frozen=True)
class DistanceSensorTopic:
    topic: str
    orientation: SensorOrientation
    sensor_id: int = 0


@dataclass(frozen=True)
class MavrosConfig(DroneConfig):
    name: str = "mavros_drone"
    pose_source: PoseSource = PoseSource.GPS
    expect_lidar: bool = True
    sensor_timeout: float = 10.0
    lidar_topic: str = "/mavros/rangefinder/rangefinder"
    vision_topic: str = "/mavros/vision_pose/pose_cov"
    gps_topic: str = "/mavros/global_position/global"
    heading_topic: str = "/mavros/global_position/compass_hdg"
    rel_alt_topic: str = "/mavros/global_position/rel_alt"
    state_topic: str = "/mavros/state"
    local_position_topic: str = "/mavros/local_position/pose"
    distance_sensors: Tuple[DistanceSensorTopic, ...] = ()
    pid_config_file: Optional[str] = None
    setpoint_config_file: Optional[str] = None
    apply_setpoint_params: bool = False
    connection_string: str = "serial:///dev/ttyUSB0:921600"


@dataclass(frozen=True)
class MavlinkConfig(DroneConfig):
    name: str = "mavlink_drone"
    pose_source: PoseSource = PoseSource.GPS
    expect_lidar: bool = True
    sensor_timeout: float = 10.0
    connection_string: str = "/dev/ttyUSB0"
    baud: int = 921600
    source_system: int = 1
    source_component: int = 191  # MAV_COMP_ID_ONBOARD_COMPUTER
    heartbeat_timeout: float = 30.0
    rx_rate_hz: float = 100.0
    heartbeat_hz: float = 1.0
    stream_rates: Optional[Dict[str, float]] = None
    vision_pose_topic: str = "/vslam/pose"
    vision_rate_hz: float = 90.0
    pid_config_file: Optional[str] = None
    setpoint_config_file: Optional[str] = None
    apply_setpoint_params: bool = False


@dataclass(frozen=True)
class BebopConfig(DroneConfig):
    name: str = "bebop_drone"
    ip: str = "192.168.42.1"
    namespace: str = "bebop"


@dataclass(frozen=True)
class CrazyflieConfig(DroneConfig):
    name: str = "crazyflie_drone"
    uri: str = "radio://0/80/2M/E7E7E7E7E7"
    cf_name: str = "cf231"
    controller: int = 2
    estimator: int = 2
    default_velocity: float = 0.3
    landing_height: float = 0.04
    max_height: float = 3.0
    sensor_timeout: float = 10.0
    enable_logging: bool = True
    log_pose_frequency: int = 10
    backend: str = "cpp"
    mocap: bool = False


# Simulation presets

SITL_CONFIG = MavrosConfig(
    name="sitl_drone",
    connection_string="tcp://127.0.0.1:5760",
    expect_lidar=False,
)
"""MavrosConfig preset for ArduPilot SITL (headless, no lidar)."""

SITL_GPS_CONFIG = MavrosConfig(
    name="sitl_drone",
    pose_source=PoseSource.GPS,
    connection_string="tcp://127.0.0.1:5760",
    expect_lidar=False,
)
"""MavrosConfig preset for SITL with GPS pose source (outdoor simulation)."""

SITL_GAZEBO_CONFIG = MavrosConfig(
    name="sitl_drone",
    pose_source=PoseSource.GPS,
    connection_string="tcp://127.0.0.1:5760",
    expect_lidar=True,
    pid_config_file=os.path.join(_MAVROS_CONFIG_DIR, "position_sim_outdoor.yaml"),
    setpoint_config_file=os.path.join(_MAVROS_CONFIG_DIR, "setpoint_sim_outdoor.yaml"),
    apply_setpoint_params=True,
)
"""MavrosConfig preset for SITL + Gazebo (ardupilot_gazebo iris model, rangefinder enabled)."""

SITL_VISION_CONFIG = MavrosConfig(
    name="sitl_drone",
    pose_source=PoseSource.VISION,
    connection_string="tcp://127.0.0.1:5760",
    expect_lidar=True,
    pid_config_file=os.path.join(_MAVROS_CONFIG_DIR, "position_sim_indoor.yaml"),
    setpoint_config_file=os.path.join(_MAVROS_CONFIG_DIR, "setpoint_sim_indoor.yaml"),
    apply_setpoint_params=True,
)
"""MavrosConfig preset for SITL indoor (no GPS, EKF3 ExternalNav, rangefinder enabled)."""

MAVLINK_SITL_CONFIG = MavlinkConfig(
    name="sitl_drone",
    pose_source=PoseSource.GPS,
    connection_string="tcp:127.0.0.1:5760",
    expect_lidar=False,
)
"""MavlinkConfig preset for ArduPilot SITL over a direct pymavlink TCP link."""

MAVLINK_SITL_GAZEBO_CONFIG = MavlinkConfig(
    name="sitl_drone",
    pose_source=PoseSource.GPS,
    connection_string="tcp:127.0.0.1:5762",
    expect_lidar=False,
)
"""MavlinkConfig preset for SITL + Gazebo over the SITL secondary MAVLink port.

Connects on tcp 5762 (SERIAL1, added by start_sitl.sh) so a direct pymavlink
link can run alongside MAVROS on 5760 against the same simulator. Mirrors
``SITL_GPS_CONFIG`` so the two transports can be compared on equal footing.
"""

MAVLINK_SITL_VISION_CONFIG = MavlinkConfig(
    name="sitl_drone",
    pose_source=PoseSource.VISION,
    connection_string="tcp:127.0.0.1:5762",
    expect_lidar=False,
    vision_pose_topic="/mavros/vision_pose/pose_cov",
)
"""MavlinkConfig preset for SITL + Gazebo indoor (vision pose).

Best-effort: the Gazebo indoor launch already forwards ground-truth pose to the
FCU through MAVROS, so run this without MAVROS vision injection to avoid a
double source.
"""
