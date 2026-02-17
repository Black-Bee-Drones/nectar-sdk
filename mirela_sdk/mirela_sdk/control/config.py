from dataclasses import dataclass
from typing import Optional

from mirela_sdk.control.types import NavigationStrategy, PoseSource


@dataclass(frozen=True)
class DroneConfig:
    name: str = "drone"
    start_driver: bool = False


@dataclass(frozen=True)
class MavrosConfig(DroneConfig):
    name: str = "mavros_drone"
    pose_source: PoseSource = PoseSource.GPS
    default_nav_strategy: NavigationStrategy = NavigationStrategy.PID
    expect_lidar: bool = True
    sensor_timeout: float = 10.0
    lidar_topic: str = "/mavros/rangefinder/rangefinder"
    vision_topic: str = "/mavros/vision_pose/pose_cov"
    gps_topic: str = "/mavros/global_position/global"
    heading_topic: str = "/mavros/global_position/compass_hdg"
    rel_alt_topic: str = "/mavros/global_position/rel_alt"
    imu_topic: str = "/mavros/imu/data"
    state_topic: str = "/mavros/state"
    pid_config_file: Optional[str] = None
    connection_string: str = "serial:///dev/ttyUSB0:921600"


@dataclass(frozen=True)
class BebopConfig(DroneConfig):
    name: str = "bebop_drone"
    ip: str = "192.168.42.1"
    namespace: str = "bebop"
