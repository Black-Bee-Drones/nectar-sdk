from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mirela_sdk.control.obstacles.strategies import AvoidanceStrategy


@dataclass
class ObstacleHandlerConfig:
    enabled: bool = True
    strategy: Optional["AvoidanceStrategy"] = None
    update_rate: float = 0.1
