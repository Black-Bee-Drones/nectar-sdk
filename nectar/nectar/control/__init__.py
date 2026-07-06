"""Nectar SDK - Control module."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.control.ardupilot.setpoint_config import SetpointNavConfig
from nectar.control.base import BaseDrone
from nectar.control.capabilities import Capability
from nectar.control.config import (
    MAVLINK_SITL_CONFIG,
    MAVLINK_SITL_GAZEBO_CONFIG,
    MAVLINK_SITL_VISION_CONFIG,
    PX4_DDS_SITL_CONFIG,
    PX4_MAVLINK_SITL_CONFIG,
    PX4_MAVLINK_SITL_GAZEBO_CONFIG,
    PX4_MAVLINK_SITL_VISION_CONFIG,
    PX4_SITL_CONFIG,
    PX4_SITL_GAZEBO_CONFIG,
    PX4_SITL_VISION_CONFIG,
    SITL_CONFIG,
    SITL_GAZEBO_CONFIG,
    SITL_GPS_CONFIG,
    SITL_VISION_CONFIG,
    BebopConfig,
    CrazyflieConfig,
    DistanceSensorTopic,
    DroneConfig,
    MavlinkConfig,
    MavrosConfig,
    Px4DdsConfig,
    Px4MavlinkConfig,
    Px4MavrosConfig,
)
from nectar.control.driver_monitor import (
    DRIVER_INFO,
    DriverInfo,
    DriverMonitor,
    DriverStatus,
    build_driver_command,
    is_driver_running,
)
from nectar.control.exceptions import (
    CapabilityNotSupportedError,
    DriverNotFoundError,
    DroneError,
    SensorNotAvailableError,
    TakeoffPositionNotSetError,
)
from nectar.control.factory import DroneFactory
from nectar.control.obstacles import (
    BaseObstacleDetector,
    ObstacleDirection,
    ObstacleHandler,
    ObstacleHandlerConfig,
    ObstacleInfo,
    ObstacleManager,
    strategies,
)
from nectar.control.pid import (
    PIDConfig,
    PIDController,
    PositionPIDConfig,
)
from nectar.control.px4.setpoint_config import Px4SetpointConfig
from nectar.control.types import (
    AltitudeSource,
    MoveReference,
    NavigationMethod,
    PoseSource,
    RTLMethod,
)
from nectar.control.vehicle.setpoint_config import SetpointConfig
from nectar.control.vehicle.types import DistanceReading, SensorOrientation

_LAZY_ATTRS = {
    # Concrete drones (heavy: MAVROS / olympe / cflib)
    "MavrosDrone": "nectar.control.mavros.drone",
    "Px4MavrosDrone": "nectar.control.px4.mavros_drone",
    "Px4MavlinkDrone": "nectar.control.px4.mavlink_drone",
    "Px4DdsDrone": "nectar.control.px4.dds_drone",
    "VehicleDrone": "nectar.control.vehicle.drone",
    "VehicleNavigator": "nectar.control.vehicle.navigator",
    "MavlinkDrone": "nectar.control.mavlink.drone",
    "BebopDrone": "nectar.control.bebop.drone",
    "CrazyflieDrone": "nectar.control.crazyflie.drone",
    # GPS helpers (pull geopy + pygeodesy; only used for GPS missions)
    "GPSUtils": "nectar.control.vehicle.gps_utils",
    # Camera-based obstacle detectors (pyrealsense2 / sklearn)
    "DepthObstacleDetector": "nectar.control.obstacles.depth_camera",
    # Direct MAVLink connection (pymavlink)
    "MavlinkConnection": "nectar.control.mavlink.connection",
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_ATTRS})


if TYPE_CHECKING:
    from nectar.control.bebop.drone import BebopDrone
    from nectar.control.crazyflie.drone import CrazyflieDrone
    from nectar.control.mavlink.connection import MavlinkConnection
    from nectar.control.mavlink.drone import MavlinkDrone
    from nectar.control.mavros.drone import MavrosDrone
    from nectar.control.obstacles.depth_camera import DepthObstacleDetector
    from nectar.control.px4.dds_drone import Px4DdsDrone
    from nectar.control.px4.mavlink_drone import Px4MavlinkDrone
    from nectar.control.px4.mavros_drone import Px4MavrosDrone
    from nectar.control.vehicle.drone import VehicleDrone
    from nectar.control.vehicle.gps_utils import GPSUtils
    from nectar.control.vehicle.navigator import VehicleNavigator


__all__ = [
    "MoveReference",
    "PoseSource",
    "NavigationMethod",
    "RTLMethod",
    "AltitudeSource",
    "DroneConfig",
    "MavrosConfig",
    "MavlinkConfig",
    "Px4MavrosConfig",
    "Px4MavlinkConfig",
    "Px4DdsConfig",
    "DistanceSensorTopic",
    "BebopConfig",
    "CrazyflieConfig",
    "SensorOrientation",
    "DistanceReading",
    "Capability",
    "SITL_CONFIG",
    "SITL_GPS_CONFIG",
    "SITL_GAZEBO_CONFIG",
    "SITL_VISION_CONFIG",
    "MAVLINK_SITL_CONFIG",
    "MAVLINK_SITL_GAZEBO_CONFIG",
    "MAVLINK_SITL_VISION_CONFIG",
    "PX4_SITL_CONFIG",
    "PX4_SITL_GAZEBO_CONFIG",
    "PX4_SITL_VISION_CONFIG",
    "PX4_DDS_SITL_CONFIG",
    "PX4_MAVLINK_SITL_CONFIG",
    "PX4_MAVLINK_SITL_GAZEBO_CONFIG",
    "PX4_MAVLINK_SITL_VISION_CONFIG",
    "DroneFactory",
    "DriverMonitor",
    "DriverStatus",
    "DriverInfo",
    "DRIVER_INFO",
    "build_driver_command",
    "is_driver_running",
    "DroneError",
    "DriverNotFoundError",
    "TakeoffPositionNotSetError",
    "SensorNotAvailableError",
    "CapabilityNotSupportedError",
    "PIDController",
    "PIDConfig",
    "PositionPIDConfig",
    "SetpointConfig",
    "SetpointNavConfig",
    "Px4SetpointConfig",
    "BaseDrone",
    "VehicleDrone",
    "MavrosDrone",
    "Px4MavrosDrone",
    "Px4MavlinkDrone",
    "Px4DdsDrone",
    "VehicleNavigator",
    "MavlinkDrone",
    "BebopDrone",
    "CrazyflieDrone",
    "GPSUtils",
    "MavlinkConnection",
    "BaseObstacleDetector",
    "DepthObstacleDetector",
    "ObstacleInfo",
    "ObstacleDirection",
    "ObstacleHandlerConfig",
    "ObstacleHandler",
    "ObstacleManager",
    "strategies",
]
