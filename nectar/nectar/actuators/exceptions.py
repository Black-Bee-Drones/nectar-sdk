"""Exceptions raised by actuator drivers."""


class ActuatorError(RuntimeError):
    """Base error for actuator operation failures."""


class HomingError(ActuatorError):
    """A stepper motor could not complete its limit-switch homing sequence."""
