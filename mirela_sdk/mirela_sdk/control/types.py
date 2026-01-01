from enum import Enum, auto


class MoveReference(Enum):
    BODY = auto()
    WORLD = auto()
    TAKEOFF = auto()


class PoseSource(Enum):
    GPS = auto()
    VISION = auto()
    MOCAP = auto()


class NavigationStrategy(Enum):
    PID = auto()
    SETPOINT = auto()


class RTLStrategy(Enum):
    PID = auto()
    ARDUPILOT = auto()
