import time
from typing import Optional


class PIDController:
    """
    PID Controller with anti-windup and output limits.
    """

    def __init__(
        self,
        kp: float = 0.0,
        ki: float = 0.0,
        kd: float = 0.0,
        setpoint: float = 0.0,
        output_limits: tuple[float, float] = (-1.0, 1.0),
        integral_limits: tuple[float, float] = (-1.0, 1.0),
    ):
        """
        Initialize PID controller.

        Parameters
        ----------
        kp : float
            Proportional gain.
        ki : float
            Integral gain.
        kd : float
            Derivative gain.
        setpoint : float
            Desired target value.
        output_limits : tuple[float, float]
            Min and max output values (min, max).
        integral_limits : tuple[float, float]
            Min and max integral term values for anti-windup (min, max).
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.output_limits = output_limits
        self.integral_limits = integral_limits

        # Internal state
        self._integral = 0.0
        self._last_error = 0.0
        self._last_time: Optional[float] = None
        self._first_update = True
        self.output = 0.0

        self._proportional = 0.0
        self._derivative = 0.0

    def update(self, current_value: float) -> float:
        """
        Update PID controller with current value.

        Parameters
        ----------
        current_value : float
            Current measured value.

        Returns
        -------
        float
            Control effort output.
        """
        current_time = time.time()

        if self._last_time is not None:
            dt = current_time - self._last_time
        else:
            dt = 0.0

        if self._first_update or dt < 1e-6:
            self._first_update = False
            self._last_time = current_time
            return self.output

        error = self.setpoint - current_value

        # Proportional term
        self._proportional = self.kp * error

        # Integral term (with anti-windup)
        self._integral += self.ki * error * dt
        self._integral = max(min(self._integral, self.integral_limits[1]), self.integral_limits[0])

        # Derivative term
        error_diff = error - self._last_error
        self._derivative = self.kd * error_diff / dt

        # total output
        self.output = self._proportional + self._integral + self._derivative
        self.output = max(min(self.output, self.output_limits[1]), self.output_limits[0])

        # Store state for next iteration
        self._last_error = error
        self._last_time = current_time

        return self.output

    def reset(self):
        """Reset PID controller internal state."""
        self._integral = 0.0
        self._last_error = 0.0
        self._last_time = None
        self._first_update = True
        self.output = 0.0
        self._proportional = 0.0
        self._derivative = 0.0

    def set_setpoint(self, setpoint: float):
        """
        Set new setpoint.

        Parameters
        ----------
        setpoint : float
            New target value.
        """
        self.setpoint = setpoint

    def tune(self, kp: float, ki: float, kd: float):
        """
        Update PID gains.

        Parameters
        ----------
        kp : float
            Proportional gain.
        ki : float
            Integral gain.
        kd : float
            Derivative gain.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def get_components(self) -> dict:
        """
        Get individual PID components for debugging.

        Returns
        -------
        dict
            Dictionary with P, I, D components and output.
        """
        return {
            "proportional": self._proportional,
            "integral": self._integral,
            "derivative": self._derivative,
            "output": self.output,
        }
