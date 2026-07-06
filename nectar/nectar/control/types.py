from enum import Enum, auto


class MoveReference(Enum):
    BODY = auto()
    WORLD = auto()
    TAKEOFF = auto()


class PoseSource(Enum):
    GPS = auto()
    VISION = auto()


class NavigationMethod(Enum):
    POSITION = auto()
    POSITION_GLOBAL = auto()
    PID = auto()
    PID_EKF = auto()


class RTLMethod(Enum):
    NAVIGATE = auto()
    NATIVE = auto()


class AltitudeSource(Enum):
    AUTO = auto()
    LIDAR = auto()
    VISION = auto()
    REL_ALT = auto()
