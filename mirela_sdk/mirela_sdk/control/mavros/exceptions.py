"""Custom exceptions for Mavros control module."""


class MavrosControlError(Exception):
    """Base exception for Mavros control errors."""

    ...


class TakeoffPositionNotSetError(MavrosControlError):
    """Raised when takeoff position is required but not set."""

    def __init__(self, operation: str = "operation"):
        self.operation = operation
        super().__init__(
            f"Takeoff position not set. Call arm_takeoff() or set_takeoff_position() "
            f"before using {operation}."
        )


class SensorNotAvailableError(MavrosControlError):
    """Raised when required sensor data is not available."""

    def __init__(self, sensor: str, mode: str = None):
        self.sensor = sensor
        self.mode = mode
        if mode:
            message = f"{sensor} not available in {mode} mode"
        else:
            message = f"{sensor} not available"
        super().__init__(message)


class InvalidModeError(MavrosControlError):
    """Raised when operation is not valid for current flight mode."""

    def __init__(self, operation: str, current_mode: str, required_mode: str):
        self.operation = operation
        self.current_mode = current_mode
        self.required_mode = required_mode
        super().__init__(
            f"{operation} requires {required_mode} mode, currently in {current_mode} mode"
        )


class InvalidStrategyError(MavrosControlError):
    """Raised when an invalid control strategy is specified."""

    def __init__(self, strategy: str, valid_strategies: list[str]):
        self.strategy = strategy
        self.valid_strategies = valid_strategies
        super().__init__(
            f"Invalid strategy '{strategy}'. Valid options: {', '.join(valid_strategies)}"
        )


class NavigationError(MavrosControlError):
    """Raised when navigation fails."""

    ...


class GPSError(MavrosControlError):
    """Raised for GPS-related errors."""

    ...
