"""Stepper actuator tests using a fake GPIO backend."""

from unittest.mock import patch

import pytest

from nectar.actuators import (
    HomingError,
    ServoConfig,
    ServoMotor,
    StepperConfig,
    StepperMotor,
)
from nectar.actuators.jetson_gpio import JetsonGPIOBackend

pytestmark = pytest.mark.control


class FakeGPIO:
    def __init__(self, input_states=()):
        self.outputs = []
        self.cleaned = []
        self.setup_args = None
        self.input_setup_args = None
        self.input_states = list(input_states)
        self.input_calls = 0
        self.input_pins = []
        self.duty_cycles = []
        self.pwm_setup_args = None
        self.stopped_pwm = []

    def setup(self, pins, mode):
        self.setup_args = (tuple(pins), mode)

    def setup_input(self, pin, mode, pull="UP"):
        self.input_setup_args = (pin, mode, pull)

    def input(self, pin):
        self.input_pins.append(pin)
        state = self.input_states[min(self.input_calls, len(self.input_states) - 1)]
        self.input_calls += 1
        return state

    def output(self, pins, values):
        self.outputs.append((tuple(pins), tuple(values)))

    def setup_pwm(self, pin, mode, frequency_hz):
        self.pwm_setup_args = (pin, mode, frequency_hz)

    def set_duty_cycle(self, pin, duty_cycle_percent):
        self.duty_cycles.append((pin, duty_cycle_percent))

    def stop_pwm(self, pin):
        self.stopped_pwm.append(pin)

    def cleanup(self, pins):
        self.cleaned.append(tuple(pins))


def test_rotate_by_degrees_uses_configured_steps_and_releases_coils():
    gpio = FakeGPIO()
    config = StepperConfig(pins=(1, 2, 3, 4), steps_per_revolution=8)
    motor = StepperMotor(config, gpio)

    with patch("nectar.actuators.stepper.sleep"):
        assert motor.rotate_by_degrees(90, velocity_rpm=60) == 2

    assert gpio.setup_args == ((1, 2, 3, 4), "BOARD")
    assert gpio.outputs[:2] == [
        ((1, 2, 3, 4), (1, 1, 0, 0)),
        ((1, 2, 3, 4), (0, 1, 0, 0)),
    ]
    assert gpio.outputs[-1] == ((1, 2, 3, 4), (0, 0, 0, 0))


def test_rotate_by_velocity_handles_reverse_and_duration():
    gpio = FakeGPIO()
    motor = StepperMotor(StepperConfig(steps_per_revolution=8), gpio)

    with patch("nectar.actuators.stepper.sleep") as wait:
        assert motor.rotate_by_velocity(-60, duration_s=0.25) == 2

    assert gpio.outputs[0][1] == (1, 0, 0, 1)
    assert wait.call_count == 1
    assert gpio.outputs[-1][1] == (0, 0, 0, 0)


def test_close_is_idempotent_and_motor_cannot_be_reused():
    gpio = FakeGPIO()
    motor = StepperMotor(backend=gpio)

    motor.close()
    motor.close()

    assert len(gpio.cleaned) == 1
    with pytest.raises(RuntimeError, match="closed"):
        motor.rotate_by_degrees(90)


def test_homing_seeks_backs_off_and_latches_then_tracks_position():
    gpio = FakeGPIO(input_states=(1, 1, 0, 0, 1, 1, 1, 0))
    config = StepperConfig(
        pins=(1, 2, 3, 4),
        steps_per_revolution=8,
        home_pin=5,
        home_pull="DOWN",
        max_homing_degrees=360,
    )
    motor = StepperMotor(config, gpio)

    with patch("nectar.actuators.stepper.sleep"):
        assert motor.home(velocity_rpm=60, backoff_degrees=45) == 5

    assert gpio.input_setup_args == (5, "BOARD", "DOWN")
    assert set(gpio.input_pins) == {5}
    assert motor.is_homed
    assert motor.position_degrees == 0.0
    assert gpio.outputs[-1] == ((1, 2, 3, 4), (0, 0, 0, 0))

    with patch("nectar.actuators.stepper.sleep"):
        assert motor.rotate_to_degrees(90, velocity_rpm=60) == 2
    assert motor.position_degrees == 90.0

    motor.close()
    assert gpio.cleaned[-1] == (1, 2, 3, 4, 5)


def test_homing_requires_a_configured_pin_and_is_bounded():
    motor_without_switch = StepperMotor(backend=FakeGPIO())
    with pytest.raises(HomingError, match="home_pin"):
        motor_without_switch.home()

    gpio = FakeGPIO(input_states=(1,))
    motor = StepperMotor(
        StepperConfig(home_pin=5, steps_per_revolution=8, max_homing_degrees=90),
        gpio,
    )
    with patch("nectar.actuators.stepper.sleep"):
        with pytest.raises(HomingError, match="fast seek"):
            motor.home(velocity_rpm=60)
    assert not motor.is_homed
    assert gpio.outputs[-1][1] == (0, 0, 0, 0)


def test_absolute_stepper_move_requires_homing():
    motor = StepperMotor(backend=FakeGPIO())
    with pytest.raises(RuntimeError, match="must be homed"):
        motor.rotate_to_degrees(90)


@pytest.mark.parametrize(
    ("velocity_rpm", "duration_s"),
    [(0, 1), (float("inf"), 1), (1, 0), (1, float("nan"))],
)
def test_velocity_move_rejects_invalid_speed_or_duration(velocity_rpm, duration_s):
    motor = StepperMotor(backend=FakeGPIO())

    with pytest.raises(ValueError):
        motor.rotate_by_velocity(velocity_rpm, duration_s)


@pytest.mark.parametrize(
    "config_kwargs",
    [
        {"pins": (1, 1, 2, 3)},
        {"steps_per_revolution": 0},
        {"gpio_mode": "invalid"},
        {"sequence": ((1, 0), (0, 1))},
    ],
)
def test_invalid_config_is_rejected(config_kwargs):
    with pytest.raises(ValueError):
        StepperMotor(StepperConfig(**config_kwargs), FakeGPIO())


@pytest.mark.parametrize(
    "config_kwargs",
    [
        {"home_pin": 11},
        {"home_active_state": 2},
        {"home_pull": "SIDEWAYS"},
        {"home_direction": 0},
        {"max_homing_degrees": float("inf")},
    ],
)
def test_invalid_homing_config_is_rejected(config_kwargs):
    with pytest.raises(ValueError):
        StepperConfig(**config_kwargs)


def test_servo_angle_maps_to_pwm_duty_cycle():
    gpio = FakeGPIO()
    servo = ServoMotor(backend=gpio)

    assert servo.set_angle(0) == 0
    assert servo.set_angle(90) == 90
    assert servo.set_angle(180) == 180
    assert [duty for _, duty in gpio.duty_cycles] == pytest.approx([2.5, 7.5, 12.5])
    assert servo.current_angle == 180


def test_servo_rejects_or_clamps_out_of_range_angles():
    gpio = FakeGPIO()
    servo = ServoMotor(backend=gpio)

    with pytest.raises(ValueError, match="outside"):
        servo.set_angle(190)
    assert servo.set_angle(190, clamp=True) == 180
    assert servo.set_angle(-10, clamp=True) == 0
    with pytest.raises(ValueError, match="finite"):
        servo.set_angle(float("nan"))


def test_servo_pulse_detach_and_close_cleanup_are_idempotent():
    gpio = FakeGPIO()
    config = ServoConfig(pin=7, initial_angle=90)
    servo = ServoMotor(config, gpio)

    assert gpio.pwm_setup_args == (7, "BOARD", 50.0)
    assert servo.current_angle == 90
    servo.set_pulse_width_us(1000)
    assert gpio.duty_cycles[-1] == (7, 5.0)
    assert servo.current_angle is None
    servo.detach()
    assert gpio.duty_cycles[-1] == (7, 0.0)

    servo.close()
    servo.close()
    assert gpio.stopped_pwm == [7]
    assert gpio.cleaned[-1] == (7,)
    with pytest.raises(RuntimeError, match="closed"):
        servo.set_angle(90)


def test_jetson_gpio_backend_maps_inputs_and_tracks_pwm(monkeypatch):
    class FakePWM:
        def __init__(self, pin, frequency_hz):
            self.pin = pin
            self.frequency_hz = frequency_hz
            self.started = []
            self.duty_cycles = []
            self.stopped = False

        def start(self, duty_cycle):
            self.started.append(duty_cycle)

        def ChangeDutyCycle(self, duty_cycle):
            self.duty_cycles.append(duty_cycle)

        def stop(self):
            self.stopped = True

    class FakeJetsonGPIO:
        BOARD = "board"
        BCM = "bcm"
        IN = "in"
        OUT = "out"
        LOW = 0
        PUD_UP = "pull-up"
        PUD_DOWN = "pull-down"
        PUD_OFF = "no-pull"

        def __init__(self):
            self.setup_calls = []
            self.input_pins = []
            self.output_calls = []
            self.cleaned = []
            self.pwm = None

        def setmode(self, mode):
            self.mode = mode

        def setup(self, pin, direction, **kwargs):
            self.setup_calls.append((pin, direction, kwargs))

        def input(self, pin):
            self.input_pins.append(pin)
            return 0

        def output(self, pins, values):
            self.output_calls.append((pins, values))

        def cleanup(self, pins):
            self.cleaned.append(pins)

        def PWM(self, pin, frequency_hz):
            self.pwm = FakePWM(pin, frequency_hz)
            return self.pwm

    gpio_module = FakeJetsonGPIO()
    monkeypatch.setattr(
        "nectar.actuators.jetson_gpio.import_module", lambda _name: gpio_module
    )
    backend = JetsonGPIOBackend()

    backend.setup_input(5, "BOARD", "UP")
    assert gpio_module.setup_calls[-1] == (
        5,
        "in",
        {"pull_up_down": "pull-up"},
    )
    assert backend.input(5) == 0
    assert gpio_module.input_pins == [5]
    backend.setup_pwm(7, "BCM", 50)
    backend.set_duty_cycle(7, 7.5)
    backend.stop_pwm(7)
    assert gpio_module.pwm.started == [0.0]
    assert gpio_module.pwm.duty_cycles == [7.5]
    assert gpio_module.pwm.stopped
    backend.cleanup((7,))
    assert gpio_module.cleaned == [[7]]


@pytest.mark.parametrize(
    "config_kwargs",
    [
        {"gpio_mode": "invalid"},
        {"frequency_hz": 0},
        {"min_angle": 180, "max_angle": 0},
        {"min_pulse_us": 2500, "max_pulse_us": 500},
        {"max_pulse_us": 20_000},
        {"initial_angle": 181},
    ],
)
def test_invalid_servo_config_is_rejected(config_kwargs):
    with pytest.raises(ValueError):
        ServoConfig(**config_kwargs)
