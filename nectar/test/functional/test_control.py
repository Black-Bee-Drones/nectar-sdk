"""Control functional tests that need no flight controller.

Flight over MAVROS / PX4-DDS is validated through SITL (see ``test_simulation``);
here we exercise the pieces that stand alone: the factory/config layer, the PID
controller (a closed-loop step response to convergence), the geodesic and
frame-transform math, and the MAVLink transport's heartbeat handshake over a UDP
loopback (a stand-in FCU, no hardware).
"""

from __future__ import annotations

import math
import time

import pytest

pytestmark = pytest.mark.control


def test_factory_and_configs():
    """Every drone type is registered and each config dataclass instantiates with defaults."""
    from nectar.control.config import (
        BebopConfig,
        CrazyflieConfig,
        MavlinkConfig,
        MavrosConfig,
        Px4DdsConfig,
        Px4MavlinkConfig,
        Px4MavrosConfig,
    )
    from nectar.control.factory import DroneFactory

    expected = {"mavros", "mavlink", "px4", "px4_mavlink", "px4_dds", "bebop", "crazyflie"}
    types = set(DroneFactory.available_types())
    assert expected <= types, f"factory missing drone types: {sorted(expected - types)}"

    for cfg in (
        MavrosConfig,
        MavlinkConfig,
        Px4MavrosConfig,
        Px4MavlinkConfig,
        Px4DdsConfig,
        BebopConfig,
        CrazyflieConfig,
    ):
        cfg()


def test_pid_step_response():
    """A PID driving a pure integrator plant converges to the setpoint."""
    from nectar.control.pid import PIDController

    setpoint = 10.0
    pid = PIDController(
        kp=1.5,
        ki=0.2,
        kd=0.0,
        setpoint=setpoint,
        output_limits=(-50.0, 50.0),
        integral_limits=(-20.0, 20.0),
    )

    value = 0.0
    last = None
    for _ in range(400):
        out = pid.update(value)
        now = time.time()
        dt = (now - last) if last is not None else 0.0
        last = now
        value += out * dt
        time.sleep(0.015)

    err = abs(value - setpoint)
    assert err <= 1.0, f"did not converge: final={value:.3f}, setpoint={setpoint} (err={err:.3f})"


def test_gps_math():
    """Haversine distance and bearing match a known one-degree-north reference."""
    pytest.importorskip("geographiclib", reason="geographiclib not installed (control extra)")
    from nectar.utils.gps_calculate import GPSCalculate

    dist = GPSCalculate.haversine(0.0, 0.0, 1.0, 0.0)
    assert abs(dist - 111_195.0) <= 2_000.0, f"haversine off: {dist:.0f} m (expected ~111195 m)"
    brg = GPSCalculate.bearing(0.0, 0.0, 1.0, 0.0)
    assert brg < 2.0 or brg > 358.0, f"bearing off: {brg:.1f} deg (expected ~0)"


def test_frame_transform():
    """A forward takeoff-frame velocity rotates into +y when the body is yawed +90 deg."""
    from nectar.utils.position_utils import PositionUtils

    vx, vy, vz = PositionUtils.transform_takeoff_to_body_velocities(
        1.0, 0.0, 0.0, current_yaw=math.radians(90.0), takeoff_yaw=0.0
    )
    assert abs(vx) < 1e-6 and abs(vy - 1.0) < 1e-6, (
        f"rotation wrong: ({vx:.3f}, {vy:.3f}, {vz:.3f})"
    )


def test_mavlink_loopback(fake_fcu):
    """The SDK MAVLink connection completes a heartbeat handshake with a loopback FCU."""
    pytest.importorskip("pymavlink", reason="pymavlink not installed (make python-sensors)")
    import helpers

    conn = helpers.mavlink_connection_to(fake_fcu.port, heartbeat_timeout=8.0)
    assert conn.is_connected, "connected but is_connected is False"
    assert conn.master.target_system >= 1
