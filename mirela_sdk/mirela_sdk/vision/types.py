from enum import Enum, auto
from dataclasses import dataclass
from typing import Tuple
import numpy as np


class CoordinateFrame(Enum):
    PIXEL = auto()
    CAMERA = auto()
    WORLD = auto()
    GPS = auto()


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def as_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def as_int_tuple(self) -> Tuple[int, int]:
        return (int(self.x), int(self.y))


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center(self) -> Point2D:
        return Point2D(x=(self.x1 + self.x2) / 2, y=(self.y1 + self.y2) / 2)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class Pose:
    position: Point3D
    rotation: np.ndarray

    @classmethod
    def from_rvec_tvec(cls, rvec: np.ndarray, tvec: np.ndarray) -> "Pose":
        import cv2

        rotation, _ = cv2.Rodrigues(rvec)
        return cls(
            position=Point3D(tvec[0, 0], tvec[1, 0], tvec[2, 0]), rotation=rotation
        )
