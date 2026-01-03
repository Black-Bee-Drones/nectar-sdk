from typing import Protocol, runtime_checkable, Optional, Any, Dict
from dataclasses import dataclass, field
import numpy as np


@dataclass
class ProcessingResult:
    success: bool
    image: Optional[np.ndarray] = None
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ImageProcessor(Protocol):
    def process(self, image: np.ndarray, **kwargs) -> ProcessingResult: ...

    def draw(
        self, image: np.ndarray, result: ProcessingResult, **kwargs
    ) -> np.ndarray: ...
