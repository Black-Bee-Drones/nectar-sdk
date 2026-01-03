from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class AbstractCam(ABC):

    def __init__(self, name: str = "camera") -> None:
        self._name = name
        self._is_running: bool = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_running(self) -> bool:
        return self._is_running

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError("Subclasses must implement a start method")

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]:
        raise NotImplementedError("Subclasses must implement a get_frame method")

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError("Subclasses must implement a close method")


class DepthCam(AbstractCam, ABC):

    @abstractmethod
    def get_depth_frame(self) -> Optional[np.ndarray]:
        raise NotImplementedError("Subclasses must implement a get_depth_frame method")

    @abstractmethod
    def get_distance(self, u: int, v: int) -> Optional[float]:
        raise NotImplementedError("Subclasses must implement a get_distance method")
