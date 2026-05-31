from importlib import import_module
from typing import Callable, Dict, Optional, Tuple

from rclpy.executors import Executor

from nectar.control.config import DroneConfig
from nectar.control.protocols import Drone

BuilderFunc = Callable[[DroneConfig, Optional[Executor]], Drone]

# Built-in drone types are lazy-loaded so importing ``nectar.control`` does
# not pull MAVROS / olympe (Bebop) / cflib (Crazyflie) until needed.
# Each entry: drone_type -> (module_path, class_name); ``<class>.from_config``
# is used as the builder.
_BUILTINS: Dict[str, Tuple[str, str]] = {
    "mavros": ("nectar.control.mavros.drone", "MavrosDrone"),
    "bebop": ("nectar.control.bebop.drone", "BebopDrone"),
    "crazyflie": ("nectar.control.crazyflie.drone", "CrazyflieDrone"),
}


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
    def _resolve(cls, drone_type: str) -> BuilderFunc:
        """Resolve a builder, lazy-importing built-ins on first use."""
        key = drone_type.lower()
        builder = cls._builders.get(key)
        if builder is not None:
            return builder

        target = _BUILTINS.get(key)
        if target is None:
            available = ", ".join(sorted({*cls._builders, *_BUILTINS}))
            raise ValueError(f"Unknown drone type: '{drone_type}'. Available types: {available}")

        module_path, class_name = target
        # Importing the drone module triggers its own bottom-of-file
        # ``DroneFactory.register(...)`` call, populating ``_builders``.
        import_module(module_path)
        builder = cls._builders.get(key)
        if builder is None:
            # Fallback if the module did not self-register: read class directly.
            cls_obj = getattr(import_module(module_path), class_name)
            builder = cls_obj.from_config
            cls._builders[key] = builder
        return builder

    @classmethod
    def create(
        cls,
        drone_type: str,
        config: DroneConfig,
        executor: Optional[Executor] = None,
    ) -> Drone:
        """
        Create drone instance of specified type.

        Parameters
        ----------
        drone_type : str
            Drone type identifier (e.g., 'mavros', 'bebop').
        config : DroneConfig
            Type-specific configuration dataclass.
        executor : Executor, optional
            ROS 2 executor to register the drone's internal node with. Defaults
            to the shared :mod:`nectar.runtime` executor.

        Returns
        -------
        Drone
            Concrete drone implementation.

        Raises
        ------
        ValueError
            If drone_type not registered.
        """
        return cls._resolve(drone_type)(config, executor)

    @classmethod
    def available_types(cls) -> list[str]:
        """
        Get list of registered drone types.

        Returns
        -------
        list[str]
            Available drone type identifiers, including built-ins that
            have not been imported yet.
        """
        return sorted({*cls._builders, *_BUILTINS})

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
            True if type is registered (explicitly or as a built-in).
        """
        key = drone_type.lower()
        return key in cls._builders or key in _BUILTINS
