# Actuator Examples

Small hardware examples for the GPIO stepper and PWM servo drivers. Run from
the repository root on a supported board:

```bash
python3 nectar/nectar/examples/actuators/stepper_example.py --degrees 90 --rpm 1
python3 nectar/nectar/examples/actuators/servo_example.py --angles 45 90 135
```

By default the actuator module detects Jetson or Raspberry Pi and selects its
GPIO backend. Raspberry Pi users need `lgpio` available to the Python
environment; Jetson users need `Jetson.GPIO`.

## Stepper

The script moves by a relative angle, or runs for a finite time at a signed RPM:

```bash
python3 nectar/nectar/examples/actuators/stepper_example.py --degrees -90 --rpm 1
python3 nectar/nectar/examples/actuators/stepper_example.py --duration 2 --rpm -1
```

Use `--home-pin` to home against a limit switch before the angle command. Check
the switch wiring and travel direction at low speed before operating a
mechanism:

```bash
python3 nectar/nectar/examples/actuators/stepper_example.py \
    --pins 11 13 15 16 --mode BOARD \
    --home-pin 18 --home-direction -1 \
    --degrees 90 --rpm 0.5
```

Set `--steps-per-revolution` to match the motor, gearbox, and driver
microstepping. Connect motor coils to an appropriate motor driver, never
directly to the Jetson or Raspberry Pi GPIO pins.

## Servo

The default command sequence is 0, 90, 180, and 90 degrees, waiting one second
after each command. Adjust pulse endpoints to the servo's specified safe range:

```bash
python3 nectar/nectar/examples/actuators/servo_example.py \
    --pin 32 --mode BOARD --angles 45 90 135 --settle 0.5
python3 nectar/nectar/examples/actuators/servo_example.py --pin 32 --pulse-us 1500
```

Use a suitable external servo supply when needed and connect its ground to the
board ground. Confirm the pin numbering mode and pulse limits before powering
the servo.
