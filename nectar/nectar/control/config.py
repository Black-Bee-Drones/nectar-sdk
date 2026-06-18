import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from nectar.control.types import PoseSource
from nectar.control.vehicle.types import SensorOrientation

# ArduPilot navigation PID/setpoint presets
_ARDUPILOT_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "ardupilot", "config")

# PX4 navigation PID presets
_PX4_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "px4", "config")


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
class Px4MavrosConfig(DroneConfig):
    name: str = "px4_drone"
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
    # PX4 needs offboard setpoints streamed faster than 2 Hz (500 ms timeout).
    offboard_rate_hz: float = 20.0
    # PX4 SITL exposes the offboard MAVLink API on UDP 14540.
    connection_string: str = "udp://:14540@127.0.0.1:14580"
    # MAVROS launch file: PX4 uses px4.launch (ArduPilot uses apm.launch).
    mavros_launch: str = "px4.launch"


@dataclass(frozen=True)
class Px4DdsConfig(DroneConfig):
    name: str = "px4_dds_drone"
    pose_source: PoseSource = PoseSource.GPS
    expect_lidar: bool = True
    sensor_timeout: float = 10.0
    pid_config_file: Optional[str] = None
    # PX4 needs offboard setpoints streamed faster than 2 Hz (500 ms timeout).
    offboard_rate_hz: float = 20.0
    # uXRCE-DDS topic namespace prefix (PX4 -n option); "" = default /fmu/...
    px4_namespace: str = ""
    # MicroXRCEAgent UDP port (PX4 SITL default 8888).
    agent_port: int = 8888
    local_position_topic: str = "/fmu/out/vehicle_local_position_v1"
    status_topic: str = "/fmu/out/vehicle_status_v4"
    global_position_topic: str = "/fmu/out/vehicle_global_position"


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
    vision_pose_topic: str = "/visual_slam/tracking/vo_pose_covariance"
    vision_rate_hz: float = 90.0
    pid_config_file: Optional[str] = None
    setpoint_config_file: Optional[str] = None
    apply_setpoint_params: bool = False


@dataclass(frozen=True)
class Px4MavlinkConfig(DroneConfig):
    """PX4 over a direct pymavlink link (no MAVROS).

    Mirrors :class:`MavlinkConfig` (pymavlink endpoint + stream settings) but
    drops ArduPilot setpoint-param fields and adds ``offboard_rate_hz`` for the
    PX4 offboard setpoint pump.
    """

    name: str = "px4_mavlink_drone"
    pose_source: PoseSource = PoseSource.GPS
    expect_lidar: bool = True
    sensor_timeout: float = 10.0
    # PX4 SITL exposes the offboard MAVLink API on UDP 14540 (pymavlink listens).
    # Real hardware overrides this (e.g. a serial path like /dev/ttyACM0).
    connection_string: str = "udp:0.0.0.0:14540"
    baud: int = 921600
    source_system: int = 1
    source_component: int = 191  # MAV_COMP_ID_ONBOARD_COMPUTER
    heartbeat_timeout: float = 30.0
    rx_rate_hz: float = 100.0
    heartbeat_hz: float = 1.0
    stream_rates: Optional[Dict[str, float]] = None
    vision_pose_topic: str = "/visual_slam/tracking/vo_pose_covariance"
    # PX4 needs offboard setpoints streamed faster than 2 Hz (500 ms timeout).
    offboard_rate_hz: float = 20.0
    pid_config_file: Optional[str] = None


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
    pid_config_file=os.path.join(_ARDUPILOT_CONFIG_DIR, "position_sim_outdoor.yaml"),
    setpoint_config_file=os.path.join(_ARDUPILOT_CONFIG_DIR, "setpoint_sim_outdoor.yaml"),
    apply_setpoint_params=True,
)
"""MavrosConfig preset for SITL + Gazebo (ardupilot_gazebo iris model, rangefinder enabled)."""

SITL_VISION_CONFIG = MavrosConfig(
    name="sitl_drone",
    pose_source=PoseSource.VISION,
    connection_string="tcp://127.0.0.1:5760",
    expect_lidar=True,
    pid_config_file=os.path.join(_ARDUPILOT_CONFIG_DIR, "position_sim_indoor.yaml"),
    setpoint_config_file=os.path.join(_ARDUPILOT_CONFIG_DIR, "setpoint_sim_indoor.yaml"),
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
"""MavlinkConfig preset for SITL + Gazebo over the SITL secondary MAVLink port."""

MAVLINK_SITL_VISION_CONFIG = MavlinkConfig(
    name="sitl_drone",
    pose_source=PoseSource.VISION,
    connection_string="tcp:127.0.0.1:5762",
    expect_lidar=False,
    vision_pose_topic="/visual_slam/tracking/vo_pose_covariance",
)
"""MavlinkConfig preset for SITL + Gazebo indoor (vision pose)."""

# PX4 SITL presets (PX4 over MAVROS, offboard via udp:14540)

PX4_SITL_CONFIG = Px4MavrosConfig(
    name="px4_sitl_drone",
    pose_source=PoseSource.GPS,
    expect_lidar=False,
)
"""Px4MavrosConfig preset for PX4 SITL (headless, GPS, no lidar)."""

PX4_SITL_GAZEBO_CONFIG = Px4MavrosConfig(
    name="px4_sitl_drone",
    pose_source=PoseSource.GPS,
    expect_lidar=True,
    pid_config_file=os.path.join(_PX4_CONFIG_DIR, "position_sim_outdoor.yaml"),
)
"""Px4MavrosConfig preset for PX4 SITL + Gazebo (x500_nectar outdoor, GPS + rangefinder).

The downward lidar reaches the SDK as /mavros/rangefinder/rangefinder: PX4 fuses
the gz gpu_lidar into a distance_sensor and streams DISTANCE_SENSOR, which MAVROS
republishes (see simulation/config/px4_config_sitl.yaml)."""

PX4_SITL_VISION_CONFIG = Px4MavrosConfig(
    name="px4_sitl_drone",
    pose_source=PoseSource.VISION,
    expect_lidar=False,
    pid_config_file=os.path.join(_PX4_CONFIG_DIR, "position_sim_indoor.yaml"),
)
"""Px4MavrosConfig preset for PX4 SITL + Gazebo indoor (EKF2 external vision)."""

PX4_DDS_SITL_CONFIG = Px4DdsConfig(
    name="px4_dds_sitl_drone",
    pose_source=PoseSource.GPS,
    pid_config_file=os.path.join(_PX4_CONFIG_DIR, "position_sim_outdoor.yaml"),
)
"""Px4DdsConfig preset for PX4 SITL over native uXRCE-DDS (MicroXRCEAgent on 8888)."""

# PX4 SITL presets (PX4 over direct pymavlink, offboard MAVLink on udp 14540)

PX4_MAVLINK_SITL_CONFIG = Px4MavlinkConfig(
    name="px4_mavlink_sitl_drone",
    pose_source=PoseSource.GPS,
    expect_lidar=False,
)
"""Px4MavlinkConfig preset for PX4 SITL over direct pymavlink (headless, GPS, no lidar)."""

PX4_MAVLINK_SITL_GAZEBO_CONFIG = Px4MavlinkConfig(
    name="px4_mavlink_sitl_drone",
    pose_source=PoseSource.GPS,
    expect_lidar=True,
    pid_config_file=os.path.join(_PX4_CONFIG_DIR, "position_sim_outdoor.yaml"),
)
"""Px4MavlinkConfig preset for PX4 SITL + Gazebo over direct pymavlink (x500_nectar outdoor).

The downward rangefinder arrives as MAVLink DISTANCE_SENSOR on the offboard link
(no MAVROS needed)."""

PX4_MAVLINK_SITL_VISION_CONFIG = Px4MavlinkConfig(
    name="px4_mavlink_sitl_drone",
    pose_source=PoseSource.VISION,
    expect_lidar=False,
    pid_config_file=os.path.join(_PX4_CONFIG_DIR, "position_sim_indoor.yaml"),
)
"""Px4MavlinkConfig preset for PX4 SITL indoor over direct pymavlink (VISION_POSITION_ESTIMATE)."""
