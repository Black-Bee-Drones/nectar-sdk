from enum import Enum, auto


class MoveReference(Enum):
    BODY = auto()
    WORLD = auto()
    TAKEOFF = auto()


class PoseSource(Enum):
    GPS = auto()
    VISION = auto()


class NavigationStrategy(Enum):
    PID = auto()
    PID_LOCAL = auto()
    SETPOINT = auto()
    SETPOINT_GLOBAL = auto()


class RTLStrategy(Enum):
    PID = auto()
    ARDUPILOT = auto()


class AltitudeSource(Enum):
    AUTO = auto()
    LIDAR = auto()
    VISION = auto()
    REL_ALT = auto()
