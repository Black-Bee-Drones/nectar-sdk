class DroneError(Exception):
    """Base exception for all drone-related errors."""
    pass


class DriverNotFoundError(DroneError):
    """Raised when drone driver is not found or not running."""

    def __init__(self, driver_name: str):
        self.driver_name = driver_name
        super().__init__(f"Driver '{driver_name}' not found or not running")


class TakeoffPositionNotSetError(DroneError):
    """Raised when operation requires takeoff position but it hasn't been set."""

    def __init__(self, operation: str = "operation"):
        self.operation = operation
        super().__init__(
            f"Takeoff position not set. Call takeoff() or set_takeoff_position() "
            f"before using {operation}."
        )


class SensorNotAvailableError(DroneError):
    """Raised when accessing a sensor that is not available in current mode."""

    def __init__(self, sensor: str, mode: str = ""):
        self.sensor = sensor
        self.mode = mode
        if mode:
            message = f"{sensor} not available in {mode} mode"
        else:
            message = f"{sensor} not available"
        super().__init__(message)


class CapabilityNotSupportedError(DroneError):
    """Raised when attempting to use a capability not supported by the drone."""

    def __init__(self, capability: str, drone_type: str):
        self.capability = capability
        self.drone_type = drone_type
        super().__init__(f"{drone_type} does not support {capability}")
