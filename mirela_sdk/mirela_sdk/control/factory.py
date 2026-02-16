from typing import Callable, Dict

from rclpy.node import Node

from mirela_sdk.control.config import DroneConfig
from mirela_sdk.control.protocols import Drone

BuilderFunc = Callable[[DroneConfig, Node], Drone]


class DroneFactory:
    """
    Factory for creating drone instances using registry pattern.
    """

    _builders: Dict[str, BuilderFunc] = {}

    @classmethod
    def register(cls, drone_type: str, builder: BuilderFunc) -> None:
        """
        Register drone type with factory.

        Parameters
        ----------
        drone_type : str
            Unique identifier for drone type (case-insensitive).
        builder : BuilderFunc
            Factory function with signature (DroneConfig, Node) -> Drone.
        """
        cls._builders[drone_type.lower()] = builder

    @classmethod
    def create(
        cls,
        drone_type: str,
        config: DroneConfig,
        node: Node,
    ) -> Drone:
        """
        Create drone instance of specified type.

        Parameters
        ----------
        drone_type : str
            Drone type identifier (e.g., 'mavros', 'bebop').
        config : DroneConfig
            Type-specific configuration dataclass.
        node : Node
            ROS2 node for communication.

        Returns
        -------
        Drone
            Concrete drone implementation.

        Raises
        ------
        ValueError
            If drone_type not registered.
        """
        builder = cls._builders.get(drone_type.lower())
        if not builder:
            available = ", ".join(cls._builders.keys())
            raise ValueError(f"Unknown drone type: '{drone_type}'. Available types: {available}")
        return builder(config, node)

    @classmethod
    def available_types(cls) -> list[str]:
        """
        Get list of registered drone types.

        Returns
        -------
        list[str]
            Available drone type identifiers.
        """
        return list(cls._builders.keys())

    @classmethod
    def is_registered(cls, drone_type: str) -> bool:
        """
        Check if drone type is registered.

        Parameters
        ----------
        drone_type : str
            Drone type identifier.

        Returns
        -------
        bool
            True if type is registered.
        """
        return drone_type.lower() in cls._builders
